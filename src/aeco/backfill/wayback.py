"""Wayback harvesting.

A capture of a page that displayed a posted quote is a real point-in-time
observation: the capture timestamp is the vintage and there is no revision
mechanism. Always use the `id_` suffix to get raw archived bytes - without it
Wayback's injected JS corrupts the inline data arrays.
"""

from __future__ import annotations

import gzip
import json
import time

from aeco import config
from aeco.fetch import FetchError, fetch

CDX = "https://web.archive.org/cdx/search/cdx"


def captures(url: str, *, status: str = "200", limit: int = 3000) -> list[str]:
    q = f"{CDX}?url={url}&output=json&limit={limit}&fl=timestamp,statuscode&collapse=digest"
    rows = json.loads(fetch(q, timeout=120))
    return [r[0] for r in rows[1:] if r[1] == status]  # row 0 is the header


def snapshot(url: str, ts: str) -> bytes:
    body = fetch(f"https://web.archive.org/web/{ts}id_/{url}", timeout=120, retries=4)
    # Some archived responses come back double-gzipped. Peel every layer, not
    # just one - real archive had 10/127 captures still compressed after a
    # single decompress, which a text parser then silently read as zero rows.
    while body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    return body


def harvest(url: str, dest_name: str) -> dict[str, str]:
    dest = config.EXTERNAL / "wayback" / dest_name
    dest.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}
    for ts in captures(url):
        f = dest / f"{ts}.html.gz"
        if f.exists():
            out[ts] = "skipped"
            continue
        try:
            f.write_bytes(gzip.compress(snapshot(url, ts)))
            out[ts] = "ok"
        except FetchError as e:
            out[ts] = f"FAILED: {e}"
        time.sleep(1.5)  # web.archive.org throttles hard
    return out


TARGETS = {
    "gasalberta_market_prices": "gasalberta.com/gas-market/market-prices",
    "gasalberta_pricing_market": "gasalberta.com/pricing-market.htm",
    "ngx_absettle": "ngx.com/marketdata/settlements/ABSETTLE.html",
    "ngx_settle": "ngx.com/marketdata/NGXSETTLE.html",
}


def main() -> int:
    for name, url in TARGETS.items():
        res = harvest(url, name)
        counts: dict[str, int] = {}
        for s in res.values():
            counts[s.split(":")[0]] = counts.get(s.split(":")[0], 0) + 1
        print(f"{name}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
