"""HTTP layer. Asserts on status code, never on response size."""

from __future__ import annotations

import gzip
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from aeco import config

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "Chrome/131.0.0.0 Safari/537.36"
)


class FetchError(RuntimeError):
    pass


def _get(url: str, timeout: float, headers: dict) -> httpx.Response:
    return httpx.get(url, timeout=timeout, headers=headers, follow_redirects=True)


def fetch(url, *, validator=None, timeout=60, retries=3, headers=None) -> bytes:
    hdrs = {"User-Agent": UA, **(headers or {})}
    last = None
    for attempt in range(retries):
        try:
            r = _get(url, timeout, hdrs)
            if r.status_code != 200:
                last = FetchError(f"{url} -> HTTP {r.status_code}")
            elif validator is not None and not validator(r.content):
                last = FetchError(
                    f"{url} -> validator rejected body ({len(r.content)} bytes)"
                )
            else:
                return r.content
        except httpx.HTTPError as e:
            last = FetchError(f"{url} -> {type(e).__name__}: {e}")
        if attempt < retries - 1:
            time.sleep(2**attempt)
    raise last


def capture(url, source, artifact, *, day=None, validator=None, timeout=60) -> Path:
    body = fetch(url, validator=validator, timeout=timeout)
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    y, m, d = day.split("-")
    out_dir = config.RAW / source / y / m / d
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / (artifact + ".gz")
    out.write_bytes(gzip.compress(body))
    meta = {
        "url": url,
        "source": source,
        "artifact": artifact,
        "status": 200,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return out
