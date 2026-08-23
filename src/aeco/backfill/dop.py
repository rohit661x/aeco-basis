"""Backfill of the NGTL Daily Operating Plan publication archive.

The announcement date of an outage is the timestamp of the earliest publication
containing its outageId, so the complete snapshot history is the backbone of H1.
"""

from __future__ import annotations

import gzip
import json
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aeco import config
from aeco.fetch import FetchError, fetch

BASE = "https://f51561ras5.execute-api.us-west-2.amazonaws.com/production"
MAX_CONCURRENCY = 3  # at 8, ~40% of requests return HTTP 500


def published_dates() -> list[str]:
    body = fetch(f"{BASE}/outages/publisheddates", timeout=60)
    return json.loads(body)["data"]


def snapshot_path(ts: str) -> Path:
    slug = ts.replace(" ", "T").replace(":", "")
    return config.EXTERNAL / "dop" / f"{slug}.json.gz"


def _one(ts: str) -> tuple[str, str]:
    out = snapshot_path(ts)
    if out.exists():
        return ts, "skipped"
    try:
        body = fetch(
            f"{BASE}/outages/history/{urllib.parse.quote(ts)}", timeout=120, retries=3
        )
        json.loads(body)  # reject truncated bodies before persisting
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(gzip.compress(body))
        return ts, "ok"
    except (FetchError, json.JSONDecodeError) as e:
        return ts, f"FAILED: {e}"


def harvest(
    timestamps: list[str] | None = None, concurrency: int = MAX_CONCURRENCY
) -> dict[str, str]:
    if concurrency > MAX_CONCURRENCY:
        raise ValueError(
            f"concurrency must be <= {MAX_CONCURRENCY}; higher rates cause silent data loss"
        )
    ts_list = published_dates() if timestamps is None else timestamps
    if not ts_list:
        return {}
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        return dict(ex.map(_one, ts_list))


def main() -> int:
    res = harvest()
    counts: dict[str, int] = {}
    for status in res.values():
        key = status.split(":")[0]
        counts[key] = counts.get(key, 0) + 1
    print(counts)
    for ts, status in sorted(res.items()):
        if status.startswith("FAILED"):
            print(f"  {ts}: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
