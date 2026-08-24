"""Parse DOP snapshots and derive announcement dates.

An outage's announcement date is the timestamp of the earliest publication in
which its outageId appears. This is directly observed, not inferred.

The snapshot timestamp is the authoritative vintage. Verified against live data:
`publishedDateTimeUtc` is uniform within a snapshot and equals the snapshot's own
timestamp, so it carries no per-record announcement information.
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from aeco import config

E3M3D_TO_BCFD = 35.3147 / 1e6  # 1 e3m3/d -> Mcf/d -> Bcf/d


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None  # 'N/A' appears in capability fields


def ts_from_stem(stem: str) -> str:
    """'2026-08-20T213145' -> '2026-08-20 21:31:45'."""
    try:
        return datetime.strptime(stem, "%Y-%m-%dT%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return stem


def parse_snapshot(raw: bytes, ts: str) -> list[dict]:
    doc = json.loads(raw)
    if not isinstance(doc, dict) or "data" not in doc:
        raise ValueError("expected the {'message','data'} envelope, got a bare payload")
    out = []
    for r in doc["data"]:
        base, flow = _num(r.get("areaBaseCapability")), _num(r.get("flowCapability"))
        red = base - flow if (base is not None and flow is not None) else None
        out.append(
            {
                "outage_id": r.get("outageId"),
                "published_utc": ts,
                "start": r.get("startDateTime"),
                "end": r.get("endDateTime"),
                "area": (r.get("area") or {}).get("acronym"),
                "base_capability": base,
                "flow_capability": flow,
                "reduction_e3m3d": red,
                "reduction_bcfd": red * E3M3D_TO_BCFD if red is not None else None,
                "description": (r.get("description") or "").strip(),
                "impact": (r.get("impact") or "").strip(),
            }
        )
    return out


def build_events(snapshot_dir: Path | None = None) -> pd.DataFrame:
    d = snapshot_dir or (config.EXTERNAL / "dop")
    rows = []
    for f in sorted(Path(d).glob("*.json.gz")):
        stem = f.name[: -len(".json.gz")]
        rows.extend(parse_snapshot(gzip.decompress(f.read_bytes()), ts_from_stem(stem)))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["published_utc"] = pd.to_datetime(df["published_utc"])
    for c in ("start", "end"):
        df[c] = pd.to_datetime(df[c])
    # published_utc is uniform within a snapshot, so a stable sort keeps
    # each snapshot's own record order rather than an arbitrary sort-algorithm
    # tie-break.
    df = df.sort_values("published_utc", kind="stable")
    # One outageId can carry several concurrent (outage_id, area) records in a
    # single snapshot - e.g. one maintenance event impacting USJR, WGAT and
    # EGAT simultaneously. groupby("outage_id").first() collapses those to one
    # row, and because GroupBy.first() skips NaN per column independently, it
    # can splice fields from DIFFERENT area records into a single row. Key on
    # the full (outage_id, area) pair and take an intact first-appearance
    # record instead.
    key = ["outage_id", "area"]
    ev = df.drop_duplicates(key, keep="first")
    first_seen = df.groupby(key)["published_utc"].min().rename("announced_utc")
    ev = ev.merge(first_seen, on=key, how="left")
    bad = ev["base_capability"] - ev["flow_capability"] != ev["reduction_e3m3d"]
    bad &= ev["reduction_e3m3d"].notna()
    if bad.any():
        raise ValueError(
            f"{int(bad.sum())} emitted row(s) fail base - flow == reduction; "
            "the (outage_id, area) key is no longer unique per record"
        )
    return ev
