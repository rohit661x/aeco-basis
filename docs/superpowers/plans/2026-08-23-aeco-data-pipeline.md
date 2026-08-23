# AECO Data Pipeline (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the point-in-time data acquisition and panel-assembly system for the AECO basis study — capture, backfill, parse, and assemble — producing a daily basis panel and an event panel of NGTL outage announcements.

**Architecture:** Six tiers with one invariant: raw bytes are immutable and everything else is re-derivable. Parsers are pure `raw → records` functions, so a parser bug is fixed by re-deriving, never re-fetching. This matters because most sources cannot be re-fetched: rolling windows drop off, CPC realized files are overwritten in place, and Alliance retains only three years.

**Tech Stack:** Python 3.12 via `uv`, httpx, pandas, pyarrow, lxml, xlrd, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-aeco-basis-system-design.md`
**Evidence:** `docs/data-feasibility-2026-08-23.md`

## Global Constraints

- Python **3.12**, managed by `uv`. Do **not** use `/opt/anaconda3` — it cannot `import pandas` (numpy 2.4.6 ABI vs pandas 2.1.4 built for numpy 1.x). Leave it untouched.
- **DOP API concurrency ≤ 3.** At concurrency 8, ~40% of requests return HTTP 500. Silent holes look like "no outages announced that day."
- **All fetches assert on HTTP status code, never response size.** TC returns a 16,835-byte HTML error page on 404. CER returns HTTP 200 with a "File not found" body, so content validators are also required where noted.
- **Everything written to `data/raw/` is gzipped.** `data/external/` and `data/derived/` are gitignored.
- Every derived record carries `as_of`. Any join importing a future-dated value is an error, not a warning.
- Unit conversion is fixed: `USD/MMBtu = (CAD/GJ × 1.055056) / FXUSDCAD`, where `FXUSDCAD` is CAD per USD.
- DOP outage size uses the **JSON** endpoint only. The CSV endpoint drops all RPTA/DPTA rows (verified: 103 JSON records vs 79 CSV) and omits `areaBaseCapability` entirely.

### Verified endpoints (all checked 2026-08-23, all keyless)

| Purpose | URL |
|---|---|
| DOP publication index | `https://f51561ras5.execute-api.us-west-2.amazonaws.com/production/outages/publisheddates` |
| DOP snapshot | `.../production/outages/history/{ts}` (ts URL-encoded, e.g. `2026-08-21%2021:31:35`) |
| Regime driver | `https://www.tccustomerexpress.com/alberta/dashboard/ngtldash.csv` |
| AECO forward curve | `https://www.gasalberta.com/actions/charts/default?id=aeco_c_futures` |
| AECO daily index | `https://www.gasalberta.com/actions/charts/default?id=aeco_ng_current` (and `aeco_ng_prior`) |
| NGTL gas day summary | `https://www.tccustomerexpress.com/gdsr/GdsrNGTLMetric{YYYYMMDD}.csv` |
| Henry Hub daily spot | `https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDd.xls` |
| CAD/USD | `https://www.bankofcanada.ca/valet/observations/FXUSDCAD/csv` |
| AECO daily (2025+) | `https://www.dobenergy.com/data/markets/prices/` |

FRED is **not** used — `fredgraph.csv` was unreachable from the build network. EIA's keyless XLS mirror and Bank of Canada Valet are the substitutes and require no API key.

### Verified DOP record schema

```
areaId, impactId, publishedDateTimeUtc, endDateTime, localAreaBaseCapability,
typicalFlow, description, id, outageId, outagePublicationId, startDateTime,
flowCapability, localAreaOutageCapability, impact, areaBaseCapability,
area:{id, acronym, centerLng, ...}
```

Envelope is `{"message": "Success", "data": [...]}` on **every** endpoint — never a bare array. `areaBaseCapability` may be the string `"N/A"`. Plant-turnaround rows (RPTA/DPTA) carry **negative** synthetic `outageId`s.

---

### Task 1: Project scaffold and fetch layer

**Files:**
- Create: `pyproject.toml`, `src/aeco/__init__.py`, `src/aeco/config.py`, `src/aeco/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Produces: `config.RAW`, `config.EXTERNAL`, `config.DERIVED` (`pathlib.Path`); `fetch.FetchError`; `fetch.fetch(url, *, validator=None, timeout=60, retries=3, headers=None) -> bytes`; `fetch.capture(url, source, artifact, *, day=None, validator=None) -> Path`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetch.py
import gzip, json, pytest, httpx
from aeco import fetch as F

def test_fetch_returns_body(monkeypatch):
    monkeypatch.setattr(F, "_get", lambda u, t, h: httpx.Response(200, content=b"hello"))
    assert F.fetch("http://x") == b"hello"

def test_fetch_raises_on_404_regardless_of_body_size(monkeypatch):
    # TC returns a 16,835-byte HTML error page on 404. Size must never imply success.
    big = b"<html>" + b"x" * 16_829
    monkeypatch.setattr(F, "_get", lambda u, t, h: httpx.Response(404, content=big))
    with pytest.raises(F.FetchError, match="404"):
        F.fetch("http://x", retries=1)

def test_fetch_validator_catches_soft_404(monkeypatch):
    # CER returns HTTP 200 with a "File not found" body.
    monkeypatch.setattr(F, "_get", lambda u, t, h: httpx.Response(200, content=b"File not found"))
    with pytest.raises(F.FetchError, match="validator"):
        F.fetch("http://x", validator=lambda b: b"File not found" not in b, retries=1)

def test_capture_writes_gzipped_body_and_meta(tmp_path, monkeypatch):
    monkeypatch.setattr(F.config, "RAW", tmp_path)
    monkeypatch.setattr(F, "_get", lambda u, t, h: httpx.Response(200, content=b"payload"))
    p = F.capture("http://x", source="demo", artifact="a.json", day="2026-08-23")
    assert gzip.decompress(p.read_bytes()) == b"payload"
    meta = json.loads(p.with_suffix(".meta.json").read_text())
    assert meta["status"] == 200 and meta["bytes"] == 7
    assert meta["sha256"] and meta["fetched_utc"].endswith("Z")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fetch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aeco'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[project]
name = "aeco"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["httpx>=0.27", "pandas>=2.2", "pyarrow>=16", "lxml>=5", "xlrd>=2.0"]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov>=5"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/aeco"]

[tool.pytest.ini_options]
pythonpath = ["src"]
```

```python
# src/aeco/config.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
EXTERNAL = ROOT / "data" / "external"
DERIVED = ROOT / "data" / "derived"
```

```python
# src/aeco/fetch.py
"""HTTP layer. Asserts on status code, never on response size."""
from __future__ import annotations
import gzip, hashlib, json, time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from aeco import config

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"

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
                last = FetchError(f"{url} -> validator rejected body ({len(r.content)} bytes)")
            else:
                return r.content
        except httpx.HTTPError as e:
            last = FetchError(f"{url} -> {type(e).__name__}: {e}")
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
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
        "url": url, "source": source, "artifact": artifact, "status": 200,
        "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv sync --extra dev && uv run pytest tests/test_fetch.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/aeco tests/test_fetch.py
git commit -m "feat: project scaffold and status-asserting fetch layer"
```

---

### Task 2: Capture registry and runner

**Files:**
- Create: `src/aeco/capture/__init__.py`, `src/aeco/capture/sources.py`, `src/aeco/capture/runner.py`
- Test: `tests/test_capture_runner.py`

**Interfaces:**
- Consumes: `fetch.capture`, `fetch.FetchError`
- Produces: `sources.CaptureSource(name, url, artifact, validator=None)`; `sources.SOURCES: list[CaptureSource]`; `runner.run_all(sources=None, day=None) -> dict[str, str]`; exits non-zero if any source fails

- [ ] **Step 1: Write the failing test**

```python
# tests/test_capture_runner.py
import pytest
from aeco.capture import runner, sources
from aeco import fetch as F

def test_run_all_reports_per_source_status(tmp_path, monkeypatch):
    monkeypatch.setattr(F.config, "RAW", tmp_path)
    monkeypatch.setattr(F, "_get", lambda u, t, h: __import__("httpx").Response(200, content=b"{}"))
    srcs = [sources.CaptureSource("a", "http://a", "a.json"),
            sources.CaptureSource("b", "http://b", "b.json")]
    assert runner.run_all(srcs, day="2026-08-23") == {"a": "ok", "b": "ok"}

def test_one_failure_does_not_abort_the_others_but_is_reported(tmp_path, monkeypatch):
    # A capture failure must never be silent: other sources still run, and the
    # failure surfaces in the result so the runner can exit non-zero.
    monkeypatch.setattr(F.config, "RAW", tmp_path)
    def flaky(u, t, h):
        import httpx
        return httpx.Response(500 if "bad" in u else 200, content=b"{}")
    monkeypatch.setattr(F, "_get", flaky)
    srcs = [sources.CaptureSource("bad", "http://bad", "x.json"),
            sources.CaptureSource("good", "http://good", "y.json")]
    res = runner.run_all(srcs, day="2026-08-23")
    assert res["good"] == "ok"
    assert res["bad"].startswith("FAILED")

def test_registry_covers_the_perishable_sources():
    names = {s.name for s in sources.SOURCES}
    assert {"gasalberta_futures", "gasalberta_index_current", "ngtldash",
            "dop_publisheddates", "gdsr", "dobenergy"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_capture_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aeco.capture'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/capture/__init__.py
```

```python
# src/aeco/capture/sources.py
"""Sources that are actively losing history. Capture is business-daily."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

@dataclass(frozen=True)
class CaptureSource:
    name: str
    url: str
    artifact: str
    validator: Optional[Callable[[bytes], bool]] = None

DOP = "https://f51561ras5.execute-api.us-west-2.amazonaws.com/production"
TCX = "https://www.tccustomerexpress.com"
GA = "https://www.gasalberta.com/actions/charts/default"

def _gdsr_url() -> str:
    # Filename date is the PUBLICATION date; content is the PRIOR gas day.
    return f"{TCX}/gdsr/GdsrNGTLMetric{datetime.now(timezone.utc):%Y%m%d}.csv"

def _json_ok(b: bytes) -> bool:
    return b.lstrip().startswith((b"{", b"["))

SOURCES = [
    CaptureSource("gasalberta_futures", f"{GA}?id=aeco_c_futures", "curve.json", _json_ok),
    CaptureSource("gasalberta_index_current", f"{GA}?id=aeco_ng_current", "index.json", _json_ok),
    CaptureSource("gasalberta_index_prior", f"{GA}?id=aeco_ng_prior", "index_prior.json", _json_ok),
    CaptureSource("ngtldash", f"{TCX}/alberta/dashboard/ngtldash.csv", "ngtldash.csv"),
    CaptureSource("dop_publisheddates", f"{DOP}/outages/publisheddates", "publisheddates.json", _json_ok),
    CaptureSource("dop_chart", f"{DOP}/chart/csv", "chart.csv"),
    CaptureSource("gdsr", _gdsr_url(), "gdsr.csv"),
    CaptureSource("dobenergy", "https://www.dobenergy.com/data/markets/prices/", "prices.html"),
]
```

```python
# src/aeco/capture/runner.py
"""Daily capture driver. Fails loudly: a silent miss is unrecoverable data loss."""
from __future__ import annotations
import sys
from aeco.capture.sources import SOURCES, CaptureSource
from aeco.fetch import capture, FetchError

def run_all(sources: list[CaptureSource] | None = None, day: str | None = None) -> dict[str, str]:
    results: dict[str, str] = {}
    for s in (sources if sources is not None else SOURCES):
        try:
            capture(s.url, s.name, s.artifact, day=day, validator=s.validator)
            results[s.name] = "ok"
        except FetchError as e:
            results[s.name] = f"FAILED: {e}"
    return results

def main() -> int:
    results = run_all()
    for name, status in sorted(results.items()):
        print(f"{status:<8.8} {name}" if status == "ok" else f"{name}: {status}")
    failures = [n for n, s in results.items() if s != "ok"]
    if failures:
        print(f"\n{len(failures)} source(s) failed: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_capture_runner.py -v`
Expected: PASS, 3 tests

- [ ] **Step 5: Verify against the live endpoints once, then commit**

Run: `uv run python -m aeco.capture.runner`
Expected: every source prints `ok`; `data/raw/` now holds today's gzipped captures.

```bash
git add src/aeco/capture tests/test_capture_runner.py
git commit -m "feat: daily capture registry and runner"
```

---

### Task 3: GitHub Actions daily capture workflow

**Files:**
- Create: `.github/workflows/capture.yml`, `.gitignore` (modify)

**Interfaces:**
- Consumes: `python -m aeco.capture.runner`
- Produces: a daily commit of `data/raw/**` to the default branch

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/capture.yml
name: daily-capture
on:
  schedule:
    - cron: "0 23 * * 1-5"   # 23:00 UTC weekdays = ~17:00 MT, after the ~15:30 MT DOP publication
  workflow_dispatch:
permissions:
  contents: write
jobs:
  capture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --extra dev
      - name: Capture
        run: uv run python -m aeco.capture.runner
      - name: Commit captures
        run: |
          git config user.name  "aeco-capture-bot"
          git config user.email "aeco-capture-bot@users.noreply.github.com"
          git add data/raw
          git diff --staged --quiet || git commit -m "capture: $(date -u +%Y-%m-%d)"
          git push
```

- [ ] **Step 2: Confirm `data/raw` is NOT gitignored while the rest is**

```bash
# .gitignore must contain exactly these ignores for data/
cat .gitignore
```
Expected: `data/external/` and `data/derived/` present; `data/raw/` absent.

- [ ] **Step 3: Validate the workflow parses**

Run: `uv run python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/capture.yml')); print('yaml ok')"`
Expected: `yaml ok`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/capture.yml .gitignore
git commit -m "ci: business-daily capture workflow"
```

> **Note for the operator:** the schedule only runs once the repo is pushed to GitHub. Until then, run `uv run python -m aeco.capture.runner` manually each weekday. Every missed day is unrecoverable.

---

### Task 4: DOP backfill harvester

**Files:**
- Create: `src/aeco/backfill/__init__.py`, `src/aeco/backfill/dop.py`
- Test: `tests/test_dop_backfill.py`

**Interfaces:**
- Consumes: `fetch.fetch`, `config.EXTERNAL`
- Produces: `dop.published_dates() -> list[str]`; `dop.snapshot_path(ts) -> Path`; `dop.harvest(timestamps=None, concurrency=3) -> dict[str, str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dop_backfill.py
import gzip, json, pytest
from aeco.backfill import dop
from aeco import fetch as F

ENVELOPE = json.dumps({"message": "Success", "data": ["2026-08-21 21:31:35"]}).encode()

def test_published_dates_unwraps_the_envelope(monkeypatch):
    # Every DOP endpoint returns {"message":..,"data":[..]} — never a bare array.
    monkeypatch.setattr(dop, "fetch", lambda url, **k: ENVELOPE)
    assert dop.published_dates() == ["2026-08-21 21:31:35"]

def test_snapshot_path_is_filesystem_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(dop.config, "EXTERNAL", tmp_path)
    p = dop.snapshot_path("2026-08-21 21:31:35")
    assert " " not in p.name and ":" not in p.name
    assert p.name.endswith(".json.gz")

def test_harvest_is_idempotent_and_skips_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(dop.config, "EXTERNAL", tmp_path)
    calls = []
    def spy(url, **k):
        calls.append(url)
        return json.dumps({"message": "Success", "data": [{"outageId": 1}]}).encode()
    monkeypatch.setattr(dop, "fetch", spy)
    dop.harvest(["2026-08-21 21:31:35"], concurrency=1)
    assert len(calls) == 1
    dop.harvest(["2026-08-21 21:31:35"], concurrency=1)   # second run must not refetch
    assert len(calls) == 1

def test_harvest_records_failure_without_writing_a_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dop.config, "EXTERNAL", tmp_path)
    def boom(url, **k):
        raise F.FetchError("504 timeout")
    monkeypatch.setattr(dop, "fetch", boom)
    res = dop.harvest(["2019-10-07 13:18:28"], concurrency=1)
    assert res["2019-10-07 13:18:28"].startswith("FAILED")
    assert not dop.snapshot_path("2019-10-07 13:18:28").exists()

def test_concurrency_is_capped_at_three():
    with pytest.raises(ValueError, match="concurrency"):
        dop.harvest([], concurrency=8)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dop_backfill.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aeco.backfill'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/backfill/__init__.py
```

```python
# src/aeco/backfill/dop.py
"""Backfill of the NGTL Daily Operating Plan publication archive.

The announcement date of an outage is the timestamp of the earliest publication
containing its outageId, so the complete snapshot history is the backbone of H1.
"""
from __future__ import annotations
import gzip, json, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from aeco import config
from aeco.fetch import fetch, FetchError

BASE = "https://f51561ras5.execute-api.us-west-2.amazonaws.com/production"
MAX_CONCURRENCY = 3   # at 8, ~40% of requests return HTTP 500

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
        body = fetch(f"{BASE}/outages/history/{urllib.parse.quote(ts)}", timeout=120, retries=3)
        json.loads(body)                      # reject truncated bodies before persisting
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(gzip.compress(body))
        return ts, "ok"
    except (FetchError, json.JSONDecodeError) as e:
        return ts, f"FAILED: {e}"

def harvest(timestamps: list[str] | None = None, concurrency: int = MAX_CONCURRENCY) -> dict[str, str]:
    if concurrency > MAX_CONCURRENCY:
        raise ValueError(f"concurrency must be <= {MAX_CONCURRENCY}; higher rates cause silent data loss")
    ts_list = published_dates() if timestamps is None else timestamps
    if not ts_list:
        return {}
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        return dict(ex.map(_one, ts_list))

def main() -> int:
    res = harvest()
    counts: dict[str, int] = {}
    for status in res.values():
        counts[status.split(":")[0]] = counts.get(status.split(":")[0], 0) + 1
    print(counts)
    for ts, status in sorted(res.items()):
        if status.startswith("FAILED"):
            print(f"  {ts}: {status}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dop_backfill.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Run the real backfill, then commit**

Run: `uv run python -m aeco.backfill.dop`
Expected: ~1,511 `ok`, and exactly 2 `FAILED` — the 2019-10-07 and 2019-10-08 entries, which return HTTP 504 on every retry. This is the documented history floor, not a bug.

```bash
git add src/aeco/backfill tests/test_dop_backfill.py
git commit -m "feat: DOP publication archive backfill"
```

---

### Task 5: DOP outage parser and announcement-date derivation

**Files:**
- Create: `src/aeco/parse/__init__.py`, `src/aeco/parse/dop_outages.py`
- Test: `tests/traps/test_dop_outages.py`

**Interfaces:**
- Consumes: `dop.snapshot_path`, `config.EXTERNAL`
- Produces: `dop_outages.parse_snapshot(raw: bytes, ts: str) -> list[dict]` with keys `outage_id, published_utc, start, end, area, base_capability, flow_capability, reduction_e3m3d, reduction_bcfd, description, impact`; `dop_outages.build_events(snapshot_dir=None) -> pandas.DataFrame` (one row per outage_id, column `announced_utc` = earliest appearance)

- [ ] **Step 1: Write the failing test**

```python
# tests/traps/test_dop_outages.py
import json, pytest, pandas as pd
from aeco.parse import dop_outages as P

def _rec(**kw):
    base = dict(outageId=20216786, publishedDateTimeUtc="2026-08-21 21:31:35",
                startDateTime="2026-10-01 00:00:00", endDateTime="2026-10-02 00:00:00",
                areaBaseCapability=385000.0, flowCapability=368000,
                description=" Meikle River C - Compressor Station Maintenance",
                impact=" Potential impact to FT-R; USJR ", area={"acronym": "USJR"})
    base.update(kw)
    return base

def _env(recs):
    return json.dumps({"message": "Success", "data": recs}).encode()

def test_reduction_is_base_minus_flow_and_converts_to_bcfd():
    r = P.parse_snapshot(_env([_rec()]), "2026-08-21 21:31:35")[0]
    assert r["reduction_e3m3d"] == pytest.approx(17000.0)
    # 1 e3m3/d ~= 35.3147 Mcf/d; 17,000 e3m3/d ~= 0.600 Bcf/d
    assert r["reduction_bcfd"] == pytest.approx(17000 * 35.3147 / 1e6, rel=1e-6)

def test_na_base_capability_yields_null_reduction_not_a_crash():
    r = P.parse_snapshot(_env([_rec(areaBaseCapability="N/A")]), "2026-08-21 21:31:35")[0]
    assert r["reduction_e3m3d"] is None

def test_plant_turnaround_rows_with_negative_ids_are_retained():
    # The CSV endpoint drops every RPTA/DPTA row (103 JSON vs 79 CSV). The JSON
    # parser must keep them; they are 24% of the panel.
    recs = [_rec(outageId=-1788588011, area={"acronym": "RPTA"}), _rec()]
    out = P.parse_snapshot(_env(recs), "2026-08-21 21:31:35")
    assert {r["area"] for r in out} == {"RPTA", "USJR"}

def test_description_and_impact_are_stripped():
    r = P.parse_snapshot(_env([_rec()]), "2026-08-21 21:31:35")[0]
    assert r["description"].startswith("Meikle") and not r["impact"].endswith(" ")

def test_bare_array_without_envelope_is_rejected():
    with pytest.raises(ValueError, match="envelope"):
        P.parse_snapshot(json.dumps([_rec()]).encode(), "2026-08-21 21:31:35")

def test_build_events_takes_earliest_appearance_as_announcement(tmp_path, monkeypatch):
    import gzip
    d = tmp_path / "dop"; d.mkdir()
    (d / "2026-08-20T213145.json.gz").write_bytes(gzip.compress(_env([_rec()])))
    (d / "2026-08-21T213135.json.gz").write_bytes(gzip.compress(_env([_rec()])))
    ev = P.build_events(d)
    assert len(ev) == 1
    assert ev.iloc[0]["announced_utc"] == pd.Timestamp("2026-08-20 21:31:45")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/traps/test_dop_outages.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aeco.parse'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/parse/__init__.py
```

```python
# src/aeco/parse/dop_outages.py
"""Parse DOP snapshots and derive announcement dates.

An outage's announcement date is the timestamp of the earliest publication in
which its outageId appears. This is directly observed, not inferred.
"""
from __future__ import annotations
import gzip, json
from pathlib import Path
import pandas as pd
from aeco import config

E3M3D_TO_BCFD = 35.3147 / 1e6   # 1 e3m3/d -> Mcf/d -> Bcf/d

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None   # 'N/A' appears in capability fields

def parse_snapshot(raw: bytes, ts: str) -> list[dict]:
    doc = json.loads(raw)
    if not isinstance(doc, dict) or "data" not in doc:
        raise ValueError("expected the {'message','data'} envelope, got a bare payload")
    out = []
    for r in doc["data"]:
        base, flow = _num(r.get("areaBaseCapability")), _num(r.get("flowCapability"))
        red = base - flow if (base is not None and flow is not None) else None
        out.append({
            "outage_id": r.get("outageId"),
            "published_utc": r.get("publishedDateTimeUtc") or ts,
            "start": r.get("startDateTime"),
            "end": r.get("endDateTime"),
            "area": (r.get("area") or {}).get("acronym"),
            "base_capability": base,
            "flow_capability": flow,
            "reduction_e3m3d": red,
            "reduction_bcfd": red * E3M3D_TO_BCFD if red is not None else None,
            "description": (r.get("description") or "").strip(),
            "impact": (r.get("impact") or "").strip(),
        })
    return out

def build_events(snapshot_dir: Path | None = None) -> pd.DataFrame:
    d = snapshot_dir or (config.EXTERNAL / "dop")
    rows = []
    for f in sorted(d.glob("*.json.gz")):
        rows.extend(parse_snapshot(gzip.decompress(f.read_bytes()), f.stem))
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
    ev["announced_utc"] = df.groupby("outage_id")["published_utc"].min().values
    return ev
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/traps/test_dop_outages.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Sanity-check against the real archive, then commit**

Run:
```bash
uv run python -c "
from aeco.parse.dop_outages import build_events
ev = build_events()
print('events:', len(ev))
print('announced range:', ev.announced_utc.min(), '->', ev.announced_utc.max())
print('with sized reduction:', ev.reduction_bcfd.notna().sum())
print(ev.area.value_counts().to_dict())
"
```
Expected: several thousand events; announcement range starting 2020-06-24; RPTA/DPTA present in the area counts. **If RPTA/DPTA are missing, the CSV endpoint was used somewhere — stop and fix.**

```bash
git add src/aeco/parse tests/traps/test_dop_outages.py
git commit -m "feat: DOP outage parser with directly observed announcement dates"
```

---

### Task 6: NGTL restriction dashboard parser (regime driver)

**Files:**
- Create: `src/aeco/parse/ngtldash.py`
- Test: `tests/traps/test_ngtldash.py`

**Interfaces:**
- Consumes: `config.RAW`
- Produces: `ngtldash.parse(raw: bytes) -> pandas.DataFrame` indexed by `date`, with columns normalised to `usjr_it, egat_it, wgat_it, osda_it, fh_bc_it, fh_sk_it` (percentages, 0-100)

- [ ] **Step 1: Write the failing test**

```python
# tests/traps/test_ngtldash.py
import pandas as pd, pytest
from aeco.parse import ngtldash as N

CSV = (b"Date,USJR IT,EGAT IT,Foorhills BC IT\n"
       b"2026-08-20,100,100,100\n"
       b"2026-08-21,45,100,100\n"
       b"2026-08-21,45,100,100\n")   # duplicate date: 105 such rows exist in the live file

def test_duplicate_dates_are_collapsed():
    df = N.parse(CSV)
    assert df.index.is_unique
    assert len(df) == 2

def test_misspelled_foothills_bc_column_is_mapped():
    # The source header really is 'Foorhills BC'. Code keyed on the correct
    # spelling silently yields no data for that gate.
    df = N.parse(CSV)
    assert "fh_bc_it" in df.columns

def test_restricted_flag_is_it_below_one_hundred():
    df = N.parse(CSV)
    assert df.loc[pd.Timestamp("2026-08-21"), "usjr_it"] == 45
    assert N.restricted(df)["usjr"].tolist() == [False, True]

def test_conflicting_duplicate_rows_raise_rather_than_silently_pick_one():
    bad = (b"Date,USJR IT\n2026-08-21,45\n2026-08-21,99\n")
    with pytest.raises(ValueError, match="conflicting"):
        N.parse(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/traps/test_ngtldash.py -v`
Expected: FAIL — `ImportError: cannot import name 'ngtldash'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/parse/ngtldash.py
"""NGTL restriction dashboard — the regime driver.

IT nomination acceptance below 100% at a gate is a direct constrained flag.
USJR is restricted on ~30% of days, which is why it is the primary driver;
Alliance utilization averages 97.7% and has almost no variation to threshold on.
"""
from __future__ import annotations
import io
import pandas as pd

# The BC column is misspelled 'Foorhills' in the source file.
COLUMN_MAP = {
    "usjr it": "usjr_it", "egat it": "egat_it", "wgat it": "wgat_it",
    "osda it": "osda_it", "foorhills bc it": "fh_bc_it", "foothills bc it": "fh_bc_it",
    "foothills sk it": "fh_sk_it", "foorhills sk it": "fh_sk_it",
}

def parse(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.strip() for c in df.columns]
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.rename(columns={c: COLUMN_MAP.get(c.strip().lower(), c) for c in df.columns})
    df = df.rename(columns={date_col: "date"}).set_index("date").sort_index()
    dupes = df[df.index.duplicated(keep=False)]
    if not dupes.empty:
        # 105 duplicate-date rows exist. Identical duplicates collapse;
        # conflicting ones are a data problem and must not be silently resolved.
        if dupes.groupby(level=0).nunique().gt(1).any().any():
            raise ValueError("conflicting duplicate dates in ngtldash.csv")
        df = df[~df.index.duplicated(keep="first")]
    return df

def restricted(df: pd.DataFrame) -> pd.DataFrame:
    it = df[[c for c in df.columns if c.endswith("_it")]]
    return (it < 100).rename(columns=lambda c: c[:-3])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/traps/test_ngtldash.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Verify restriction frequencies against the documented values, then commit**

Run:
```bash
uv run python -c "
import gzip,glob
from aeco.parse.ngtldash import parse, restricted
f = sorted(glob.glob('data/raw/ngtldash/**/ngtldash.csv.gz', recursive=True))[-1]
df = parse(gzip.decompress(open(f,'rb').read()))
print('rows:', len(df), 'range:', df.index.min().date(), '->', df.index.max().date())
print((restricted(df).mean()*100).round(1).to_dict())
"
```
Expected: coverage from 2019-10-24; USJR restricted ≈30%, EGAT ≈11%, WGAT ≈9%, OSDA ≈8%. Material deviation means the column mapping is wrong.

```bash
git add src/aeco/parse/ngtldash.py tests/traps/test_ngtldash.py
git commit -m "feat: NGTL restriction dashboard parser (regime driver)"
```

---

### Task 7: Gas Alberta parsers (inline era and live JSON)

**Files:**
- Create: `src/aeco/parse/gasalberta.py`
- Test: `tests/traps/test_gasalberta.py`

**Interfaces:**
- Consumes: nothing
- Produces: `gasalberta.parse_inline_daily(html: bytes) -> pandas.DataFrame` (`date`, `daily_cad_gj`, `monthly_cad_gj`); `gasalberta.parse_inline_curve(html: bytes) -> list[tuple[str, float]]`; `gasalberta.parse_live_curve(raw: bytes) -> list[tuple[str, float]]`

- [ ] **Step 1: Write the failing test**

```python
# tests/traps/test_gasalberta.py
import json, pytest
from aeco.parse import gasalberta as G

INLINE_DAILY = b"""
<script>var d = google.visualization.arrayToDataTable([
 ['Date', 'Monthly Index', 'Daily Index'],
 ['1-Oct-16', 2.47, 2.63],
 ['2-Oct-16', 2.47, 2.55],
 ['3-Oct-16', 2.47, 2.71]]);</script>"""

INLINE_CURVE = b"""
<script>var c = google.visualization.arrayToDataTable([
 ['Month', 'One Year Ago','One Month Ago','Current'],
 ['Dec-16',2.83,2.74,2.42],
 ['Jan-17',2.90,2.80,2.55]]);</script>"""

def test_daily_series_identified_behaviourally_not_by_header_order():
    # The site's own JS swaps columns before charting, so the header order is a
    # trap. The column that is FLAT within a calendar month is the monthly index.
    df = G.parse_inline_daily(INLINE_DAILY)
    assert df["monthly_cad_gj"].nunique() == 1
    assert df["daily_cad_gj"].tolist() == [2.63, 2.55, 2.71]

def test_curve_takes_the_last_numeric_as_current():
    curve = G.parse_inline_curve(INLINE_CURVE)
    assert curve[0] == ("Dec-16", 2.42)

def test_prompt_month_comes_from_the_label_never_the_timestamp():
    # A 2017-06-08 capture starts at Jun-17, the CURRENT month, not the next one.
    curve = G.parse_inline_curve(INLINE_CURVE)
    assert curve[0][0] == "Dec-16"

def test_short_curves_are_rejected():
    tiny = b"[['Month', 'One Year Ago','One Month Ago','Current'],['Dec-16',1,2,3]]"
    with pytest.raises(ValueError, match="too short"):
        G.parse_inline_curve(tiny, min_points=24)

def test_live_json_maps_index_three_to_current():
    raw = json.dumps([["Sep-26", 2.64, 1.46, 1.23]]).encode()
    assert G.parse_live_curve(raw)[0] == ("Sep-26", 1.23)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/traps/test_gasalberta.py -v`
Expected: FAIL — `ImportError: cannot import name 'gasalberta'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/parse/gasalberta.py
"""Gas Alberta parsers.

Three incompatible eras exist. This module covers the 2016-2022 inline
Google-Charts era and the current AJAX JSON era. Column order is a trap in both:
the site's JS remaps columns before display, so identify series behaviourally.
"""
from __future__ import annotations
import json, re
import pandas as pd

_DAILY_ROW = re.compile(r"\['(\d{1,2}-[A-Z][a-z]{2}-\d{2})'\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\]")
_CURVE_ROW = re.compile(r"\['([A-Z][a-z]{2}-\d{2})'\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\]")

def parse_inline_daily(html: bytes) -> pd.DataFrame:
    text = html.decode("utf-8", errors="replace")
    rows = [(d, float(a), float(b)) for d, a, b in _DAILY_ROW.findall(text)]
    if not rows:
        return pd.DataFrame(columns=["date", "daily_cad_gj", "monthly_cad_gj"])
    df = pd.DataFrame(rows, columns=["date", "col1", "col2"])
    df["date"] = pd.to_datetime(df["date"], format="%d-%b-%y")
    # The monthly index is constant within a calendar month; the daily one moves.
    by_month = df.groupby(df["date"].dt.to_period("M"))
    flat1 = by_month["col1"].nunique().max() == 1
    monthly, daily = ("col1", "col2") if flat1 else ("col2", "col1")
    return (df.rename(columns={monthly: "monthly_cad_gj", daily: "daily_cad_gj"})
              [["date", "daily_cad_gj", "monthly_cad_gj"]]
              .drop_duplicates("date").sort_values("date").reset_index(drop=True))

def parse_inline_curve(html: bytes, min_points: int = 24) -> list[tuple[str, float]]:
    text = html.decode("utf-8", errors="replace")
    # Raw row order is (month, oneYearAgo, oneMonthAgo, current): last numeric is live.
    curve = [(m, float(cur)) for m, _yr, _mo, cur in _CURVE_ROW.findall(text)]
    if len(curve) < min_points:
        raise ValueError(f"curve too short: {len(curve)} points (< {min_points})")
    return curve

def parse_live_curve(raw: bytes, min_points: int = 1) -> list[tuple[str, float]]:
    doc = json.loads(raw)
    rows = doc.get("data", doc) if isinstance(doc, dict) else doc
    curve = [(r[0], float(r[3])) for r in rows if isinstance(r, list) and len(r) >= 4]
    if len(curve) < min_points:
        raise ValueError(f"curve too short: {len(curve)} points (< {min_points})")
    return curve
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/traps/test_gasalberta.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Commit**

```bash
git add src/aeco/parse/gasalberta.py tests/traps/test_gasalberta.py
git commit -m "feat: Gas Alberta inline and live-JSON parsers"
```

---

### Task 8: Wayback harvester and Gas Alberta backfill

**Files:**
- Create: `src/aeco/backfill/wayback.py`
- Test: `tests/test_wayback.py`

**Interfaces:**
- Consumes: `fetch.fetch`, `config.EXTERNAL`
- Produces: `wayback.captures(url, *, status="200") -> list[str]`; `wayback.snapshot(url, ts) -> bytes`; `wayback.harvest(url, dest_name) -> dict[str, str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wayback.py
import json, pytest
from aeco.backfill import wayback as W

CDX = json.dumps([["timestamp", "statuscode"],
                  ["20161107165832", "200"],
                  ["20170101000000", "301"],
                  ["20170608120000", "200"]]).encode()

def test_captures_filters_to_status_200_and_drops_the_header_row(monkeypatch):
    monkeypatch.setattr(W, "fetch", lambda url, **k: CDX)
    assert W.captures("http://x") == ["20161107165832", "20170608120000"]

def test_snapshot_url_uses_the_id_suffix(monkeypatch):
    # Without `id_`, Wayback injects a toolbar and rewrites URLs, which corrupts
    # the inline arrayToDataTable blocks we parse.
    seen = {}
    def spy(url, **k):
        seen["url"] = url
        return b"<html/>"
    monkeypatch.setattr(W, "fetch", spy)
    W.snapshot("http://example.com/p", "20161107165832")
    assert "/20161107165832id_/" in seen["url"]

def test_gzipped_archived_body_is_decompressed(monkeypatch):
    import gzip
    monkeypatch.setattr(W, "fetch", lambda url, **k: gzip.compress(b"<html>hi</html>"))
    assert b"hi" in W.snapshot("http://x", "20230216110811")

def test_harvest_skips_already_downloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(W.config, "EXTERNAL", tmp_path)
    monkeypatch.setattr(W, "captures", lambda url, **k: ["20161107165832"])
    calls = []
    monkeypatch.setattr(W, "snapshot", lambda u, t: calls.append(t) or b"<html/>")
    W.harvest("http://x", "ga")
    W.harvest("http://x", "ga")
    assert len(calls) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wayback.py -v`
Expected: FAIL — `ImportError: cannot import name 'wayback'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/backfill/wayback.py
"""Wayback harvesting.

A capture of a page that displayed a posted quote is a real point-in-time
observation: the capture timestamp is the vintage and there is no revision
mechanism. Always use the `id_` suffix to get raw archived bytes.
"""
from __future__ import annotations
import gzip, json, time
from pathlib import Path
from aeco import config
from aeco.fetch import fetch, FetchError

CDX = "https://web.archive.org/cdx/search/cdx"

def captures(url: str, *, status: str = "200", limit: int = 3000) -> list[str]:
    q = f"{CDX}?url={url}&output=json&limit={limit}&fl=timestamp,statuscode&collapse=digest"
    rows = json.loads(fetch(q, timeout=120))
    return [r[0] for r in rows[1:] if r[1] == status]   # row 0 is the header

def snapshot(url: str, ts: str) -> bytes:
    body = fetch(f"https://web.archive.org/web/{ts}id_/{url}", timeout=120, retries=4)
    if body[:2] == b"\x1f\x8b":     # some archived responses come back undecoded
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
        time.sleep(1.5)   # web.archive.org throttles hard; a tight loop gets refused
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wayback.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Run the real harvest, then commit**

Run: `uv run python -m aeco.backfill.wayback`
Expected: roughly 128 captures for `gasalberta_market_prices`, 37 for `gasalberta_pricing_market`, 11 for `ngx_absettle`, ~19 for `ngx_settle`. Expect to re-run — Wayback throttles and the harvest is idempotent by design.

```bash
git add src/aeco/backfill/wayback.py tests/test_wayback.py
git commit -m "feat: Wayback harvester for forward and index reconstruction"
```

---

### Task 9: Henry Hub and FX loaders

**Files:**
- Create: `src/aeco/parse/henryhub.py`, `src/aeco/parse/fx.py`
- Test: `tests/test_henryhub_fx.py`

**Interfaces:**
- Consumes: `fetch.fetch`
- Produces: `henryhub.load() -> pandas.Series` (name `hh_usd_mmbtu`, DatetimeIndex); `fx.load() -> pandas.Series` (name `fx_usdcad`, CAD per USD)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_henryhub_fx.py
import pandas as pd
from aeco.parse import fx as X

FXCSV = (b'"OBSERVATIONS"\n"date","FXUSDCAD"\n'
         b'"2026-08-19","1.3824"\n"2026-08-20","1.3785"\n"2026-08-21","1.3760"\n')

def test_fx_parses_bank_of_canada_valet_csv(monkeypatch):
    monkeypatch.setattr(X, "fetch", lambda url, **k: FXCSV)
    s = X.load()
    assert s.name == "fx_usdcad"
    assert s.loc[pd.Timestamp("2026-08-21")] == 1.3760
    assert s.index.is_monotonic_increasing

def test_fx_is_cad_per_usd_orientation(monkeypatch):
    # A CAD/GJ price divided by this must give USD. Values near 1.3-1.4 confirm
    # the orientation; an inverted series would sit near 0.7.
    monkeypatch.setattr(X, "fetch", lambda url, **k: FXCSV)
    assert X.load().between(1.0, 2.0).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_henryhub_fx.py -v`
Expected: FAIL — `ImportError: cannot import name 'fx'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/parse/fx.py
"""CAD/USD from the Bank of Canada Valet API (keyless).

FXUSDCAD is CAD per USD, so USD = CAD / FXUSDCAD.
"""
from __future__ import annotations
import io
import pandas as pd
from aeco.fetch import fetch

URL = "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/csv"

def load() -> pd.Series:
    raw = fetch(URL, timeout=60).decode("utf-8", errors="replace")
    body = raw.split("OBSERVATIONS", 1)[-1].lstrip("\"\r\n")
    df = pd.read_csv(io.StringIO(body))
    df.columns = [c.strip().strip('"').lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    s = (df.set_index("date")["fxusdcad"].astype(float)
           .sort_index().rename("fx_usdcad"))
    return s[~s.index.duplicated(keep="last")]
```

```python
# src/aeco/parse/henryhub.py
"""Henry Hub daily spot from EIA's keyless dnav XLS mirror.

FRED is deliberately not used: fredgraph.csv was unreachable from the build
network. This mirror needs no API key.
"""
from __future__ import annotations
import io
import pandas as pd
from aeco.fetch import fetch

URL = "https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDd.xls"

def load() -> pd.Series:
    raw = fetch(URL, timeout=120)
    df = pd.read_excel(io.BytesIO(raw), sheet_name="Data 1", skiprows=2)
    df.columns = ["date", "hh"]
    df["date"] = pd.to_datetime(df["date"])
    return (df.dropna().set_index("date")["hh"].astype(float)
              .sort_index().rename("hh_usd_mmbtu"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_henryhub_fx.py -v`
Expected: PASS, 2 tests

- [ ] **Step 5: Verify both against live sources, then commit**

Run:
```bash
uv run python -c "
from aeco.parse.henryhub import load as hh
from aeco.parse.fx import load as fx
h, f = hh(), fx()
print('HH:', len(h), h.index.min().date(), '->', h.index.max().date(), 'last', h.iloc[-1])
print('FX:', len(f), f.index.min().date(), '->', f.index.max().date(), 'last', f.iloc[-1])
"
```
Expected: HH from 1997-01-07 with ~7,400 observations; FX in the 1.3-1.4 range. If FX prints ~0.72 the orientation is inverted — fix before proceeding, because it silently corrupts every basis value.

```bash
git add src/aeco/parse/henryhub.py src/aeco/parse/fx.py tests/test_henryhub_fx.py
git commit -m "feat: Henry Hub and CAD/USD loaders (keyless sources)"
```

---

### Task 10: Daily basis panel assembly

**Files:**
- Create: `src/aeco/panel/__init__.py`, `src/aeco/panel/daily.py`
- Test: `tests/test_daily_panel.py`

**Interfaces:**
- Consumes: `gasalberta.parse_inline_daily`, `henryhub.load`, `fx.load`, `ngtldash.parse`
- Produces: `daily.build() -> pandas.DataFrame` with `aeco_cad_gj, aeco_usd_mmbtu, hh_usd_mmbtu, basis_usd_mmbtu, block, usjr_it, restricted`; `daily.BLOCKS`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_daily_panel.py
import pandas as pd, pytest
from aeco.panel import daily as D

def test_unit_conversion_matches_the_documented_formula():
    # USD/MMBtu = (CAD/GJ * 1.055056) / FXUSDCAD
    assert D.to_usd_mmbtu(2.00, 1.3760) == pytest.approx(2.00 * 1.055056 / 1.3760)

def test_basis_is_aeco_minus_henry_in_common_units():
    idx = pd.to_datetime(["2026-08-20"])
    df = D.assemble(
        aeco_cad=pd.Series([2.00], index=idx),
        hh=pd.Series([2.82], index=idx),
        fx=pd.Series([1.3760], index=idx),
    )
    exp = 2.00 * 1.055056 / 1.3760 - 2.82
    assert df["basis_usd_mmbtu"].iloc[0] == pytest.approx(exp)

def test_the_28_month_gap_is_labelled_and_never_interpolated():
    idx = pd.to_datetime(["2022-08-30", "2025-01-02"])
    df = D.assemble(
        aeco_cad=pd.Series([2.0, 1.5], index=idx),
        hh=pd.Series([8.0, 3.0], index=idx),
        fx=pd.Series([1.30, 1.43], index=idx),
    )
    assert df["block"].tolist() == ["A", "B"]
    assert df["basis_usd_mmbtu"].notna().all()
    assert len(df) == 2                      # no rows manufactured across the hole

def test_missing_fx_yields_null_basis_rather_than_a_forward_filled_guess():
    idx = pd.to_datetime(["2026-08-20"])
    df = D.assemble(
        aeco_cad=pd.Series([2.00], index=idx),
        hh=pd.Series([2.82], index=idx),
        fx=pd.Series(dtype=float),
    )
    assert df["basis_usd_mmbtu"].isna().all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_daily_panel.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aeco.panel'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/panel/__init__.py
```

```python
# src/aeco/panel/daily.py
"""Daily AECO-Henry basis panel.

Coverage is two disjoint blocks separated by a 28-month hole with no free data.
The hole is labelled, never interpolated, and results are reported per block.
"""
from __future__ import annotations
import gzip
import pandas as pd
from aeco import config
from aeco.parse import gasalberta, henryhub, fx as fxmod, ngtldash

GJ_PER_MMBTU = 1.055056
BLOCKS = {"A": ("2020-06-24", "2022-08-30"), "B": ("2025-01-01", None)}

def to_usd_mmbtu(cad_per_gj: float, fx_usdcad: float) -> float:
    return cad_per_gj * GJ_PER_MMBTU / fx_usdcad

def _block(ts: pd.Timestamp) -> str | None:
    for name, (lo, hi) in BLOCKS.items():
        if pd.Timestamp(lo) <= ts and (hi is None or ts <= pd.Timestamp(hi)):
            return name
    return None

def assemble(aeco_cad: pd.Series, hh: pd.Series, fx: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"aeco_cad_gj": aeco_cad}).sort_index()
    # as-of joins: never import a future-dated value
    df["hh_usd_mmbtu"] = hh.reindex(df.index, method="ffill") if len(hh) else pd.NA
    df["fx_usdcad"] = fx.reindex(df.index, method="ffill") if len(fx) else pd.NA
    df["aeco_usd_mmbtu"] = df["aeco_cad_gj"] * GJ_PER_MMBTU / df["fx_usdcad"]
    df["basis_usd_mmbtu"] = df["aeco_usd_mmbtu"] - df["hh_usd_mmbtu"]
    df["block"] = [_block(t) for t in df.index]
    return df

def _aeco_from_wayback() -> pd.Series:
    d = config.EXTERNAL / "wayback" / "gasalberta_market_prices"
    frames = [gasalberta.parse_inline_daily(gzip.decompress(f.read_bytes()))
              for f in sorted(d.glob("*.html.gz"))]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.Series(dtype=float)
    all_ = pd.concat(frames).drop_duplicates("date").set_index("date").sort_index()
    return all_["daily_cad_gj"]

def build() -> pd.DataFrame:
    df = assemble(_aeco_from_wayback(), henryhub.load(), fxmod.load())
    latest = sorted((config.RAW / "ngtldash").rglob("ngtldash.csv.gz"))
    if latest:
        nd = ngtldash.parse(gzip.decompress(latest[-1].read_bytes()))
        df = df.join(nd[["usjr_it"]], how="left")
        df["restricted"] = df["usjr_it"] < 100
    out = config.DERIVED / "daily_panel.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    return df
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_daily_panel.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Build the real panel, then commit**

Run:
```bash
uv run python -c "
from aeco.panel.daily import build
df = build()
print(df.groupby('block').agg(n=('basis_usd_mmbtu','size'), mean=('basis_usd_mmbtu','mean')))
print('total days:', len(df))
"
```
Expected: block A ≈ 494 days. Block B stays empty until the dobenergy parser lands (Phase 1b) — that is expected, not a failure.

```bash
git add src/aeco/panel tests/test_daily_panel.py
git commit -m "feat: daily AECO-Henry basis panel with block labelling"
```

---

### Task 11: Event panel with cumulative abnormal responses

**Files:**
- Create: `src/aeco/panel/events.py`
- Test: `tests/test_event_panel.py`

**Interfaces:**
- Consumes: `dop_outages.build_events`, `daily.build`
- Produces: `events.build(daily_df=None, events_df=None) -> pandas.DataFrame` with `outage_id, announced_utc, start, area, reduction_bcfd, car_announce, car_drift, episode_id, season, block`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_event_panel.py
import pandas as pd, numpy as np, pytest
from aeco.panel import events as E

def _daily():
    idx = pd.date_range("2026-09-25", "2026-10-05", freq="D")
    return pd.DataFrame({"basis_usd_mmbtu": np.arange(len(idx), dtype=float),
                         "block": "B"}, index=idx)

def _events():
    return pd.DataFrame([{"outage_id": 1, "announced_utc": pd.Timestamp("2026-09-28 21:31:35"),
                          "start": pd.Timestamp("2026-10-03"), "end": pd.Timestamp("2026-10-05"),
                          "area": "USJR", "reduction_bcfd": 0.6}])

def test_announcement_window_is_a_to_a_plus_one():
    ev = E.build(_daily(), _events())
    # basis rises 1.0/day; [2026-09-28, 2026-09-29] spans one step
    assert ev["car_announce"].iloc[0] == pytest.approx(1.0)

def test_drift_window_runs_from_a_plus_two_to_effective_start():
    ev = E.build(_daily(), _events())
    # [2026-09-30, 2026-10-03] spans three steps
    assert ev["car_drift"].iloc[0] == pytest.approx(3.0)

def test_announcement_date_is_used_never_the_effective_date():
    shifted = _events().assign(start=pd.Timestamp("2026-10-05"))
    assert E.build(_daily(), shifted)["car_announce"].iloc[0] == pytest.approx(1.0)

def test_events_outside_covered_days_are_dropped_not_interpolated():
    ev = _events().assign(announced_utc=pd.Timestamp("2023-05-01"), start=pd.Timestamp("2023-05-10"))
    assert E.build(_daily(), ev).empty

def test_overlapping_outages_in_one_area_share_an_episode_id():
    two = pd.DataFrame([
        {"outage_id": 1, "announced_utc": pd.Timestamp("2026-09-28"), "start": pd.Timestamp("2026-10-01"),
         "end": pd.Timestamp("2026-10-04"), "area": "USJR", "reduction_bcfd": 0.6},
        {"outage_id": 2, "announced_utc": pd.Timestamp("2026-09-29"), "start": pd.Timestamp("2026-10-03"),
         "end": pd.Timestamp("2026-10-05"), "area": "USJR", "reduction_bcfd": 0.2}])
    ev = E.build(_daily(), two)
    assert ev["episode_id"].nunique() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_panel.py -v`
Expected: FAIL — `ImportError: cannot import name 'events'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/panel/events.py
"""Event panel: one row per NGTL outage announcement.

The event date is the ANNOUNCEMENT date, never the effective date. Two windows:
[a, a+1] measures whether the announcement is priced; [a+2, s] measures whether
the reaction was complete.
"""
from __future__ import annotations
import pandas as pd
from aeco import config

def _car(daily: pd.DataFrame, lo: pd.Timestamp, hi: pd.Timestamp) -> float | None:
    if pd.isna(lo) or pd.isna(hi) or hi < lo:
        return None
    w = daily.loc[(daily.index >= lo) & (daily.index <= hi), "basis_usd_mmbtu"].dropna()
    return float(w.iloc[-1] - w.iloc[0]) if len(w) >= 2 else None

def _episodes(ev: pd.DataFrame) -> pd.Series:
    """Outages overlapping in time within an area form one episode."""
    ids = pd.Series(index=ev.index, dtype="object")
    for area, grp in ev.groupby("area"):
        grp = grp.sort_values("start")
        ep, cutoff = 0, None
        for i, row in grp.iterrows():
            if cutoff is None or row["start"] > cutoff:
                ep += 1
                cutoff = row["end"]
            else:
                cutoff = max(cutoff, row["end"])
            ids.at[i] = f"{area}-{ep}"
    return ids

def build(daily_df: pd.DataFrame | None = None, events_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if daily_df is None:
        from aeco.panel.daily import build as build_daily
        daily_df = build_daily()
    if events_df is None:
        from aeco.parse.dop_outages import build_events
        events_df = build_events()
    if events_df.empty:
        return events_df

    ev = events_df.copy()
    a = pd.to_datetime(ev["announced_utc"]).dt.normalize()
    ev["car_announce"] = [_car(daily_df, d, d + pd.Timedelta(days=1)) for d in a]
    ev["car_drift"] = [_car(daily_df, d + pd.Timedelta(days=2), s)
                       for d, s in zip(a, pd.to_datetime(ev["start"]))]
    ev = ev[ev["car_announce"].notna()].copy()
    if ev.empty:
        return ev
    ev["episode_id"] = _episodes(ev)
    ev["season"] = pd.to_datetime(ev["start"]).dt.month
    ev["block"] = [daily_df.loc[daily_df.index <= d, "block"].iloc[-1]
                   if (daily_df.index <= d).any() else None for d in a]
    out = config.DERIVED / "event_panel.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    ev.to_parquet(out)
    return ev
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_event_panel.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Build the real event panel and report power, then commit**

Run:
```bash
uv run python -c "
from aeco.panel.events import build
ev = build()
print('events with usable windows:', len(ev))
print('distinct episodes:', ev.episode_id.nunique())
print('by block:', ev.block.value_counts().to_dict())
print('reduction_bcfd described:'); print(ev.reduction_bcfd.describe())
"
```
Expected: the episode count is the study's power. **Record it — it goes on page one of the note**, per the brief's §7.7 and pre-registered decision rule 1 (under ~15 episodes ⇒ framed as an identification demonstration, t-hurdle 3).

```bash
git add src/aeco/panel/events.py tests/test_event_panel.py
git commit -m "feat: event panel with announcement and drift windows"
```

---

### Task 12: Full-suite run and power report

**Files:**
- Create: `src/aeco/report_power.py`
- Test: none (this task is a reporting entry point; correctness is covered by Tasks 1-11)

**Interfaces:**
- Consumes: `daily.build`, `events.build`
- Produces: `docs/power-report.md`

- [ ] **Step 1: Write the reporting script**

```python
# src/aeco/report_power.py
"""Emit the power and coverage numbers the note must state up front."""
from __future__ import annotations
from pathlib import Path
from aeco.panel.daily import build as build_daily
from aeco.panel.events import build as build_events

def main() -> int:
    d, e = build_daily(), build_events()
    lines = [
        "# Power and Coverage Report", "",
        f"- Daily basis observations: **{d['basis_usd_mmbtu'].notna().sum()}**",
        f"- Coverage by block: {d.groupby('block').size().to_dict()}",
        f"- Outage announcements with usable price windows: **{len(e)}**",
        f"- Distinct maintenance episodes: **{e['episode_id'].nunique() if len(e) else 0}**",
        f"- Events by block: {e['block'].value_counts().to_dict() if len(e) else {}}",
        "",
        "Pre-registered rule: under ~15 episodes, the event study is framed as an",
        "identification demonstration and the t-stat hurdle is stated as 3.",
    ]
    Path("docs/power-report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the whole test suite**

Run: `uv run pytest -v`
Expected: all tests pass across every module.

- [ ] **Step 3: Generate the power report**

Run: `uv run python -m aeco.report_power`
Expected: `docs/power-report.md` written with real counts.

- [ ] **Step 4: Commit**

```bash
git add src/aeco/report_power.py docs/power-report.md
git commit -m "feat: power and coverage report"
```

---

## Phase 1b — deferred, small

Deliberately out of this plan to keep it shippable. Each is a self-contained follow-up:

- **dobenergy parser** — unlocks block B (~600 days, 2025-01→2026-08). Highest value of the four.
- **GDSR parser** — daily linepack/storage/border flows. Must handle the 2009 sign-convention inversion and the publication-date-vs-gas-day offset.
- **CPC HDD loaders** — realized plus the vintage-stamped 7-day forecast archive, for forecast-revision controls.
- **Alliance EBB loader** — corroborating regime signal only. Guard `oprCapQty in (None, 0)`; `designCapQty` is seasonal.

## Phase 2 — estimation

Gets its own plan once the panel exists and the power report is real: Hansen (2000) threshold regression from scratch (blocking validation gate: reproduce his Table II on `dur_john.txt` — threshold 863, bootstrap p ≈ 0.005), the event-study regressions, episode-clustered and HAC inference, the specification log, THE figure, and the Octave-runnable Matlab mirror.

---

## Self-review

**Spec coverage.** Tier 0 capture → Tasks 2-3. Tier 1 backfill → Tasks 4, 8. Tier 2 parse → Tasks 5-7, 9. Tier 3 panel → Tasks 10-11. Tiers 4-5 → Phase 2, deliberately deferred. Spec §5 trap matrix: rows 1-3 (Tasks 4-5), 6-7 (Task 6), 11-14 (Tasks 7-8) are covered here; rows 4-5 (GDSR signs/offset), 9-10 (Alliance nulls/seasonal capacity), 15-18 (estimation and secondary sources) belong to Phase 1b and Phase 2 and are listed there rather than dropped.

**Placeholders.** None. Every step carries runnable code or an exact command with an expected result.

**Type consistency.** `build_events()` produces `outage_id, announced_utc, start, end, area, reduction_bcfd`, consumed under those exact names in Task 11. `daily.assemble()` produces `basis_usd_mmbtu` and `block`, consumed under those names in Tasks 11-12. `ngtldash.parse()` produces `usjr_it`, consumed in Task 10.

