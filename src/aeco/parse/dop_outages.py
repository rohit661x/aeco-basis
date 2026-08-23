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
    df = df.sort_values("published_utc")
    # Announcement = first appearance. Keying on outage_id alone gives the
    # ORIGINAL announcement; add start/end/area to the key to get revisions.
    ev = df.groupby("outage_id", as_index=False).first()
    first_seen = df.groupby("outage_id")["published_utc"].min().rename("announced_utc")
    return ev.merge(first_seen, on="outage_id", how="left")
