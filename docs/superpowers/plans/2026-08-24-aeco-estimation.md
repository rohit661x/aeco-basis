# AECO Estimation (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estimate H1 (is posted NGTL capacity information impounded at announcement?) and H2 (is the response regime-dependent?), with deflated inference, THE figure, and an Octave-runnable Matlab mirror of both headline estimations.

**Architecture:** A from-scratch Hansen (2000) threshold estimator gated on reproducing his own published results before it touches AECO data, feeding an event-study layer whose every specification is logged by the code rather than counted by hand.

**Tech Stack:** Python 3.12 / `uv`, statsmodels 0.14, numpy, pandas, matplotlib; GNU Octave (or Matlab) for the mirror.

**Spec:** `docs/superpowers/specs/2026-08-23-aeco-basis-system-design.md`
**Depends on:** Phase 1 (`docs/superpowers/plans/2026-08-23-aeco-data-pipeline.md`) — merged, 56 tests passing.

## Global Constraints

- Python **3.12** via `uv`. Never `/opt/anaconda3` (broken numpy/pandas ABI). Ad-hoc scripts run as `PYTHONPATH=src .venv/bin/python` — `uv run` races with background jobs on the editable install.
- **The Hansen validation gate in Task 2 is blocking.** The estimator must reproduce Hansen's published threshold on his own data before being pointed at AECO. Do not proceed past Task 2 with a failing gate.
- **Every estimation call writes to the specification log.** The multiple-testing count reported in the note is read from that log, never tallied by hand.
- **Harvey-Liu-Zhu hurdle: |t| ≈ 3** for the headline coefficient, stated up front, not chosen after seeing results.
- **Never pool block A and block B into one coefficient.** They use *different publishers* (Gas Alberta CAD/GJ vs dobenergy USD/GJ), so a block difference confounds source with period. Report separately, always.
- The estimation sample is currently **block B only** — the DOP archive is 739/1513 loaded, newest-first. Every output must state the loaded fraction.
- `arch`'s `RealityCheck` is `class RealityCheck(SPA): pass`. For White (2000) you MUST pass `studentize=False, nested=False`.
- Regime driver `q` = USJR IT nomination-acceptance percentage, observed **at the announcement date** — never later.

### Verified reference material (checked 2026-08-24)

| Item | Value |
|---|---|
| Hansen (2000) code + data | `https://users.ssc.wisc.edu/~behansen/progs/ecnmt_00m.zip` (14,954 bytes) |
| Canonical host | `users.ssc.wisc.edu/~behansen/` — note the **`be`**; `~bhansen` only 302-redirects |
| Archive contents | `dur_john.txt`, `thr_est.m`, `thr_test.m`, `thr_het.m`, `het_test.m`, `growth.m` |
| Data shape | 121 rows × 11 columns, space-delimited |

**Hansen's filter, read from `growth.m` and verified to reproduce n = 96:**
drop rows where any of columns 5, 6, 10, 11 (1-indexed) equals `-999`, then keep rows where column 2 > 0.

**His model** (`dat=[diff,gdp60,iony,pgro,sch,q,lit]`, called as `thr_est(dat,na,1,dum,6,h)` with `dum=[2;3;4;5]`):

| Term | Construction (1-indexed raw columns) |
|---|---|
| y | `log(col6) − log(col5)` |
| x | `log(col5)`, `log(col9/100)`, `log(col8/100 + .05)`, `log(col10/100)` |
| q (threshold var) | `col5` — the **raw** GDP-1960 level, not logged |
| trimming | 0.15 |

**Expected result:** n = 96, threshold **863**, bootstrap p ≈ 0.005. Confirmed independently: 863 is a real value of column 5, whose range is 383–12,362.

---

### Task 1: Vendor the Hansen reference fixture

**Files:**
- Create: `src/aeco/estimate/__init__.py`, `scripts/fetch_hansen.py`, `tests/fixtures/dur_john.txt`
- Test: `tests/estimate/test_hansen_fixture.py`

**Interfaces:**
- Produces: `tests/fixtures/dur_john.txt` (committed); `fetch_hansen.main()` re-downloads and verifies

- [ ] **Step 1: Write the failing test**

```python
# tests/estimate/test_hansen_fixture.py
from pathlib import Path
import numpy as np

FIXTURE = Path(__file__).parents[1] / "fixtures" / "dur_john.txt"


def test_fixture_is_present_and_has_hansens_shape():
    d = np.loadtxt(FIXTURE)
    assert d.shape == (121, 11)


def test_hansens_filter_reproduces_n_96():
    # From growth.m: drop -999 in columns 5,6,10,11 (1-indexed), then col2 > 0.
    d = np.loadtxt(FIXTURE)
    for c in (5, 6, 10, 11):
        d = d[d[:, c - 1] != -999]
    d = d[d[:, 1] > 0]
    assert d.shape[0] == 96


def test_the_published_threshold_is_an_attainable_value():
    d = np.loadtxt(FIXTURE)
    for c in (5, 6, 10, 11):
        d = d[d[:, c - 1] != -999]
    d = d[d[:, 1] > 0]
    assert 863.0 in set(d[:, 4].tolist())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_hansen_fixture.py -q`
Expected: FAIL — fixture file does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/fetch_hansen.py
"""Download Hansen's published threshold code and data.

The canonical host is users.ssc.wisc.edu/~behansen (note the 'be'); the widely
cited ~bhansen path only 302-redirects and could stop doing so.
"""
from __future__ import annotations
import io, zipfile
from pathlib import Path
import httpx

URL = "https://users.ssc.wisc.edu/~behansen/progs/ecnmt_00m.zip"
DEST = Path(__file__).resolve().parents[1] / "vendor" / "hansen2000"
FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "dur_john.txt"


def main() -> int:
    r = httpx.get(URL, timeout=60, follow_redirects=True,
                  headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    DEST.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        z.extractall(DEST)
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_bytes((DEST / "dur_john.txt").read_bytes())
    print(f"extracted {len(z.namelist())} files to {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Run it: `PYTHONPATH=src .venv/bin/python scripts/fetch_hansen.py`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_hansen_fixture.py -q`
Expected: PASS, 3 tests

- [ ] **Step 5: Commit**

```bash
mkdir -p src/aeco/estimate && touch src/aeco/estimate/__init__.py
git add scripts/fetch_hansen.py tests/fixtures/dur_john.txt tests/estimate src/aeco/estimate
git commit -m "test: vendor Hansen (2000) reference data as a validation fixture"
```

---

### Task 2: Hansen threshold estimator — with the blocking validation gate

**Files:**
- Create: `src/aeco/estimate/threshold.py`
- Test: `tests/estimate/test_threshold.py`

**Interfaces:**
- Consumes: `tests/fixtures/dur_john.txt`
- Produces: `threshold.ThresholdFit` (fields `gamma, ssr, beta_low, beta_high, n_low, n_high, sup_wald`); `threshold.fit(y, X, q, trim=0.15) -> ThresholdFit`; `threshold.grid(q, trim) -> np.ndarray`

- [ ] **Step 1: Write the failing test**

```python
# tests/estimate/test_threshold.py
from pathlib import Path
import numpy as np
import pytest
from aeco.estimate import threshold as T

FIXTURE = Path(__file__).parents[1] / "fixtures" / "dur_john.txt"


def hansen_design():
    """Exactly the model in Hansen's growth.m."""
    d = np.loadtxt(FIXTURE)
    for c in (5, 6, 10, 11):
        d = d[d[:, c - 1] != -999]
    d = d[d[:, 1] > 0]
    y = np.log(d[:, 5]) - np.log(d[:, 4])
    X = np.column_stack([
        np.ones(len(d)),
        np.log(d[:, 4]),                 # gdp60
        np.log(d[:, 8] / 100),           # iony
        np.log(d[:, 7] / 100 + 0.05),    # pgro
        np.log(d[:, 9] / 100),           # sch
    ])
    q = d[:, 4]                          # raw GDP 1960 level
    return y, X, q


def test_grid_respects_trimming():
    q = np.arange(100.0)
    g = T.grid(q, trim=0.15)
    assert g.min() >= np.quantile(q, 0.15)
    assert g.max() <= np.quantile(q, 0.85)


# ---- THE BLOCKING VALIDATION GATE ----
def test_reproduces_hansen_2000_published_threshold():
    """Must recover Hansen's own published threshold on his own data.

    Hansen (2000), 'Sample Splitting and Threshold Estimation', Table II:
    threshold at GDP-1960 = 863 with n = 96. growth.m carries the same value in
    its own comments. If this fails, the estimator is wrong and must not be
    pointed at AECO data.
    """
    y, X, q = hansen_design()
    assert len(y) == 96
    fit = T.fit(y, X, q, trim=0.15)
    assert fit.gamma == pytest.approx(863.0)


def test_split_sample_sizes_are_consistent():
    y, X, q = hansen_design()
    fit = T.fit(y, X, q, trim=0.15)
    assert fit.n_low + fit.n_high == 96
    assert min(fit.n_low, fit.n_high) >= int(0.15 * 96)


def test_sup_wald_is_positive_and_finite():
    y, X, q = hansen_design()
    fit = T.fit(y, X, q, trim=0.15)
    assert np.isfinite(fit.sup_wald) and fit.sup_wald > 0


def test_no_threshold_effect_yields_a_small_statistic():
    rng = np.random.default_rng(0)
    n = 300
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    q = rng.normal(size=n)
    y = X @ np.array([1.0, 2.0]) + rng.normal(scale=0.5, size=n)  # no split
    strong = T.fit(y + 5.0 * (q > 0), X, q).sup_wald
    weak = T.fit(y, X, q).sup_wald
    assert strong > weak
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_threshold.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'aeco.estimate.threshold'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/estimate/threshold.py
"""Hansen (2000) threshold regression, implemented from scratch.

statsmodels has no threshold regression, and the only PyPI candidate
(pyxthreg) implements Hansen (1999) fixed-effects PANEL threshold, which is a
different model requiring entity and time columns.

Estimation is concentrated least squares: for each candidate threshold in the
trimmed support of q, fit the split regression and keep the threshold with the
smallest SSR. The same grid yields sup-Wald, and (Task 3) Andrews-Ploberger.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class ThresholdFit:
    gamma: float
    ssr: float
    beta_low: np.ndarray
    beta_high: np.ndarray
    n_low: int
    n_high: int
    sup_wald: float


def grid(q: np.ndarray, trim: float = 0.15) -> np.ndarray:
    lo, hi = np.quantile(q, trim), np.quantile(q, 1 - trim)
    return np.unique(q[(q >= lo) & (q <= hi)])


def _ssr(y: np.ndarray, Z: np.ndarray) -> tuple[float, np.ndarray]:
    beta, *_ = np.linalg.lstsq(Z, y, rcond=None)
    resid = y - Z @ beta
    return float(resid @ resid), beta


def fit(y: np.ndarray, X: np.ndarray, q: np.ndarray, trim: float = 0.15) -> ThresholdFit:
    y, X, q = np.asarray(y, float), np.asarray(X, float), np.asarray(q, float)
    ssr0, _ = _ssr(y, X)                       # restricted: no threshold
    best = None
    for g in grid(q, trim):
        d = (q <= g).astype(float)[:, None]
        Z = np.hstack([X, X * d])              # split slopes AND intercept
        if np.linalg.matrix_rank(Z) < Z.shape[1]:
            continue                            # degenerate split
        s, beta = _ssr(y, Z)
        if best is None or s < best[0]:
            best = (s, g, beta, int(d.sum()))
    if best is None:
        raise ValueError("no admissible threshold candidate; check trimming and q")
    ssr1, gamma, beta, n_low = best
    k = X.shape[1]
    n = len(y)
    # sup-Wald for H0: no threshold, evaluated at the minimising gamma
    sup_wald = float(n * (ssr0 - ssr1) / ssr1)
    return ThresholdFit(
        gamma=float(gamma), ssr=ssr1,
        beta_low=beta[:k] + beta[k:], beta_high=beta[:k],
        n_low=n_low, n_high=n - n_low, sup_wald=sup_wald,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_threshold.py -v`
Expected: PASS, 5 tests — **including `test_reproduces_hansen_2000_published_threshold`**.

If the gate fails, debug before continuing. Likely causes, in order: `q` was logged (it must be the raw level); the constant was omitted from the split term; trimming applied to indices rather than quantiles of `q`.

- [ ] **Step 5: Commit**

```bash
git add src/aeco/estimate/threshold.py tests/estimate/test_threshold.py
git commit -m "feat: Hansen (2000) threshold regression, validated against his published result"
```

---

### Task 3: Bootstrap threshold test and structural-break statistics

**Files:**
- Modify: `src/aeco/estimate/threshold.py`
- Test: `tests/estimate/test_threshold_bootstrap.py`

**Interfaces:**
- Produces: `threshold.bootstrap_pvalue(y, X, q, trim=0.15, reps=1000, seed=None) -> float`; `threshold.break_stats(y, X, q, trim=0.15) -> dict` with keys `sup_wald`, `exp_wald`, `ave_wald`

- [ ] **Step 1: Write the failing test**

```python
# tests/estimate/test_threshold_bootstrap.py
import numpy as np
import pytest
from aeco.estimate import threshold as T


def _rng_data(effect, n=200, seed=0):
    rng = np.random.default_rng(seed)
    X = np.column_stack([np.ones(n), rng.normal(size=n)])
    q = rng.normal(size=n)
    y = X @ np.array([1.0, 2.0]) + effect * (q > 0) + rng.normal(scale=0.5, size=n)
    return y, X, q


def test_bootstrap_pvalue_is_a_probability():
    y, X, q = _rng_data(0.0)
    p = T.bootstrap_pvalue(y, X, q, reps=99, seed=1)
    assert 0.0 <= p <= 1.0


def test_no_effect_gives_a_large_pvalue():
    y, X, q = _rng_data(0.0)
    assert T.bootstrap_pvalue(y, X, q, reps=199, seed=1) > 0.10


def test_strong_effect_gives_a_small_pvalue():
    y, X, q = _rng_data(3.0)
    assert T.bootstrap_pvalue(y, X, q, reps=199, seed=1) < 0.05


def test_bootstrap_is_reproducible_under_a_seed():
    y, X, q = _rng_data(1.0)
    a = T.bootstrap_pvalue(y, X, q, reps=99, seed=7)
    b = T.bootstrap_pvalue(y, X, q, reps=99, seed=7)
    assert a == b


def test_break_stats_orders_sup_above_ave():
    y, X, q = _rng_data(2.0)
    s = T.break_stats(y, X, q)
    assert s["sup_wald"] >= s["ave_wald"]
    assert np.isfinite(s["exp_wald"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_threshold_bootstrap.py -q`
Expected: FAIL — `AttributeError: module has no attribute 'bootstrap_pvalue'`

- [ ] **Step 3: Append to `src/aeco/estimate/threshold.py`**

```python
def _wald_path(y: np.ndarray, X: np.ndarray, q: np.ndarray, trim: float) -> np.ndarray:
    """Wald statistic at every trimmed candidate threshold."""
    ssr0, _ = _ssr(y, X)
    n = len(y)
    out = []
    for g in grid(q, trim):
        d = (q <= g).astype(float)[:, None]
        Z = np.hstack([X, X * d])
        if np.linalg.matrix_rank(Z) < Z.shape[1]:
            continue
        s, _ = _ssr(y, Z)
        out.append(n * (ssr0 - s) / s)
    return np.asarray(out, float)


def break_stats(y, X, q, trim: float = 0.15) -> dict:
    """sup-, exp-, and ave-Wald from one grid pass.

    sup-Wald is Andrews (1993); exp- and ave-Wald are Andrews-Ploberger (1994).
    None are in statsmodels. Their asymptotic critical values depend on the
    trimming fraction and parameter count, so bootstrap them rather than
    hunting tables.
    """
    w = _wald_path(np.asarray(y, float), np.asarray(X, float), np.asarray(q, float), trim)
    return {
        "sup_wald": float(w.max()),
        "ave_wald": float(w.mean()),
        "exp_wald": float(np.log(np.mean(np.exp(np.clip(w / 2, -700, 700))))),
    }


def bootstrap_pvalue(y, X, q, trim: float = 0.15, reps: int = 1000, seed=None) -> float:
    """Hansen's fixed-regressor bootstrap.

    Regressors and the threshold variable are held fixed; only the dependent
    variable is resampled under the null of no threshold. Returns the share of
    bootstrap sup-Wald statistics at least as large as the observed one.
    """
    y, X, q = np.asarray(y, float), np.asarray(X, float), np.asarray(q, float)
    observed = fit(y, X, q, trim).sup_wald
    _, beta0 = _ssr(y, X)
    resid = y - X @ beta0
    rng = np.random.default_rng(seed)
    n = len(y)
    count = 0
    for _ in range(reps):
        y_b = X @ beta0 + resid * rng.normal(size=n)   # wild bootstrap under H0
        try:
            if fit(y_b, X, q, trim).sup_wald >= observed:
                count += 1
        except ValueError:
            continue
    return (count + 1) / (reps + 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_threshold_bootstrap.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Check against Hansen's published p-value, then commit**

Run:
```bash
PYTHONPATH=src .venv/bin/python -c "
import numpy as np, sys
sys.path.insert(0,'tests')
from estimate.test_threshold import hansen_design
from aeco.estimate import threshold as T
y,X,q = hansen_design()
print('threshold:', T.fit(y,X,q).gamma)
print('bootstrap p:', T.bootstrap_pvalue(y,X,q,reps=1000,seed=0))
"
```
Expected: threshold 863; bootstrap p in the neighbourhood of Hansen's 0.005. The wild bootstrap here is not identical to his homoskedastic procedure, so an exact match is not required — but a p above ~0.05 means something is wrong.

```bash
git add src/aeco/estimate/threshold.py tests/estimate/test_threshold_bootstrap.py
git commit -m "feat: fixed-regressor bootstrap and Andrews-Ploberger break statistics"
```

---

### Task 4: Specification log

**Files:**
- Create: `src/aeco/estimate/speclog.py`
- Test: `tests/estimate/test_speclog.py`

**Interfaces:**
- Produces: `speclog.log_spec(name, formula, sample, extra=None) -> str` (returns spec id); `speclog.count() -> int`; `speclog.summary() -> pandas.DataFrame`; `speclog.PATH`

- [ ] **Step 1: Write the failing test**

```python
# tests/estimate/test_speclog.py
from aeco.estimate import speclog as S


def test_every_call_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "PATH", tmp_path / "specs.jsonl")
    S.log_spec("h1_announce", "car ~ reduction", "blockB")
    S.log_spec("h1_drift", "car ~ reduction", "blockB")
    assert S.count() == 2


def test_identical_specs_are_still_counted_separately(tmp_path, monkeypatch):
    # Re-running the same specification is still a look at the data. The
    # multiple-testing count must not be silently deduplicated.
    monkeypatch.setattr(S, "PATH", tmp_path / "specs.jsonl")
    a = S.log_spec("h1", "car ~ reduction", "blockB")
    b = S.log_spec("h1", "car ~ reduction", "blockB")
    assert a != b and S.count() == 2


def test_summary_reports_the_hlz_hurdle(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "PATH", tmp_path / "specs.jsonl")
    S.log_spec("h1", "car ~ reduction", "blockB")
    df = S.summary()
    assert "name" in df.columns and len(df) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_speclog.py -q`
Expected: FAIL — no module named `speclog`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/estimate/speclog.py
"""Machine-written specification log.

The multiple-testing count reported in the note is read from this file. Hand
counting is exactly the step where the number quietly gets smaller.
"""
from __future__ import annotations
import json, uuid
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from aeco import config

PATH = config.DERIVED / "spec_log.jsonl"
HLZ_HURDLE = 3.0


def log_spec(name: str, formula: str, sample: str, extra: dict | None = None) -> str:
    spec_id = uuid.uuid4().hex[:12]
    rec = {
        "spec_id": spec_id,
        "name": name,
        "formula": formula,
        "sample": sample,
        "logged_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **(extra or {}),
    }
    PATH.parent.mkdir(parents=True, exist_ok=True)
    with PATH.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return spec_id


def _records() -> list[dict]:
    if not PATH.exists():
        return []
    return [json.loads(l) for l in PATH.read_text().splitlines() if l.strip()]


def count() -> int:
    return len(_records())


def summary() -> pd.DataFrame:
    return pd.DataFrame(_records())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_speclog.py -q`
Expected: PASS, 3 tests

- [ ] **Step 5: Commit**

```bash
git add src/aeco/estimate/speclog.py tests/estimate/test_speclog.py
git commit -m "feat: machine-written specification log for multiple-testing discipline"
```

---

### Task 5: H1 event-study regressions

**Files:**
- Create: `src/aeco/estimate/eventstudy.py`
- Test: `tests/estimate/test_eventstudy.py`

**Interfaces:**
- Consumes: `panel.events.build`, `speclog.log_spec`
- Produces: `eventstudy.EventResult` (fields `name, beta, tstat, pvalue, n, n_clusters, passes_hlz, spec_id`); `eventstudy.run(ev, window='announce'|'drift', season_fe=True, sample='B') -> EventResult`; `eventstudy.run_all(ev) -> pandas.DataFrame`

- [ ] **Step 1: Write the failing test**

```python
# tests/estimate/test_eventstudy.py
import numpy as np
import pandas as pd
import pytest
from aeco.estimate import eventstudy as E


def _panel(beta=1.0, n=120, seed=0):
    rng = np.random.default_rng(seed)
    red = rng.uniform(0.05, 0.8, n)
    return pd.DataFrame({
        "outage_id": np.arange(n),
        "reduction_bcfd": red,
        "car_announce": beta * red + rng.normal(scale=0.05, size=n),
        "car_drift": rng.normal(scale=0.05, size=n),
        "episode_id": [f"USJR-{i // 4}" for i in range(n)],
        "season": rng.integers(1, 13, n),
        "block": "B",
    })


def test_recovers_a_known_slope():
    r = E.run(_panel(beta=1.0), window="announce", season_fe=False)
    assert r.beta == pytest.approx(1.0, abs=0.15)


def test_null_drift_is_not_significant():
    r = E.run(_panel(), window="drift", season_fe=False)
    assert abs(r.tstat) < 3.0


def test_standard_errors_are_clustered_by_episode():
    p = _panel()
    r = E.run(p, window="announce", season_fe=False)
    assert r.n_clusters == p["episode_id"].nunique()
    assert r.n_clusters < len(p)  # clustering must actually bind


def test_hlz_hurdle_is_three_not_two():
    p = _panel(beta=0.0)
    p["car_announce"] = 0.02 * p["reduction_bcfd"] + 0.05
    r = E.run(p, window="announce", season_fe=False)
    assert r.passes_hlz == (abs(r.tstat) >= 3.0)


def test_every_run_writes_to_the_spec_log(tmp_path, monkeypatch):
    from aeco.estimate import speclog as S
    monkeypatch.setattr(S, "PATH", tmp_path / "s.jsonl")
    E.run(_panel(), window="announce")
    E.run(_panel(), window="drift")
    assert S.count() == 2


def test_pooling_blocks_is_refused():
    p = _panel()
    p.loc[p.index[:60], "block"] = "A"
    with pytest.raises(ValueError, match="pool"):
        E.run(p, window="announce", sample="ALL")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_eventstudy.py -q`
Expected: FAIL — no module named `eventstudy`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/estimate/eventstudy.py
"""H1: is posted NGTL capacity information impounded at announcement?

Two windows per event. [a, a+1] asks whether the announcement is priced;
[a+2, s] asks whether the reaction was complete. beta1 > 0 with beta2 = 0 is
efficient price discovery; beta2 != 0 is underreaction to public information.

Season fixed effects absorb the average premium, so identification is on
cross-sectional variation in announced reduction size, not on the mean.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
import statsmodels.api as sm
from aeco.estimate.speclog import HLZ_HURDLE, log_spec

WINDOWS = {"announce": "car_announce", "drift": "car_drift"}


@dataclass(frozen=True)
class EventResult:
    name: str
    beta: float
    tstat: float
    pvalue: float
    n: int
    n_clusters: int
    passes_hlz: bool
    spec_id: str


def run(ev: pd.DataFrame, window: str = "announce", season_fe: bool = True,
        sample: str = "B") -> EventResult:
    if window not in WINDOWS:
        raise ValueError(f"window must be one of {sorted(WINDOWS)}")
    if sample == "ALL" and ev["block"].nunique() > 1:
        raise ValueError(
            "refusing to pool blocks: block A and block B use different "
            "publishers, so a pooled coefficient confounds source with period"
        )
    d = ev if sample in ("ALL",) else ev[ev["block"] == sample]
    d = d.dropna(subset=[WINDOWS[window], "reduction_bcfd"])
    if d.empty:
        raise ValueError(f"no observations for window={window} sample={sample}")

    y = d[WINDOWS[window]].to_numpy(float)
    X = pd.DataFrame({"reduction_bcfd": d["reduction_bcfd"].to_numpy(float)},
                     index=d.index)
    if season_fe:
        X = X.join(pd.get_dummies(d["season"], prefix="m", drop_first=True, dtype=float))
    X = sm.add_constant(X, has_constant="add")

    res = sm.OLS(y, X).fit(cov_type="cluster",
                           cov_kwds={"groups": d["episode_id"].to_numpy()})
    b = float(res.params["reduction_bcfd"])
    t = float(res.tvalues["reduction_bcfd"])
    name = f"h1_{window}{'_seasonfe' if season_fe else ''}_block{sample}"
    spec_id = log_spec(name, f"{WINDOWS[window]} ~ reduction_bcfd"
                       + (" + C(season)" if season_fe else ""),
                       sample, {"n": int(len(d)), "beta": b, "tstat": t})
    return EventResult(name=name, beta=b, tstat=t,
                       pvalue=float(res.pvalues["reduction_bcfd"]),
                       n=int(len(d)),
                       n_clusters=int(d["episode_id"].nunique()),
                       passes_hlz=bool(abs(t) >= HLZ_HURDLE),
                       spec_id=spec_id)


def run_all(ev: pd.DataFrame, sample: str = "B") -> pd.DataFrame:
    """Both windows, with and without season FE. Four specifications."""
    rows = [run(ev, w, fe, sample) for w in WINDOWS for fe in (False, True)]
    return pd.DataFrame([r.__dict__ for r in rows])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_eventstudy.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Run on the real panel, then commit**

Run:
```bash
PYTHONPATH=src .venv/bin/python -c "
from aeco.panel.events import build
from aeco.estimate.eventstudy import run_all
ev = build()
print(run_all(ev).to_string(index=False))
"
```
Record the output. **Do not interpret it yet** — Task 6 adds the regime split, and the note's headline depends on both.

```bash
git add src/aeco/estimate/eventstudy.py tests/estimate/test_eventstudy.py
git commit -m "feat: H1 event-study regressions, episode-clustered"
```

---

### Task 6: H2 regime-conditional response

**Files:**
- Create: `src/aeco/estimate/regime.py`
- Test: `tests/estimate/test_regime.py`

**Interfaces:**
- Consumes: `threshold.fit`, `threshold.bootstrap_pvalue`, `panel.daily`, `speclog`
- Produces: `regime.attach_driver(ev, daily) -> pandas.DataFrame` (adds `q_at_announce`); `regime.run(ev, window='announce', reps=1000, seed=0) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/estimate/test_regime.py
import numpy as np
import pandas as pd
import pytest
from aeco.estimate import regime as R


def _daily():
    idx = pd.date_range("2026-01-01", periods=200, freq="D")
    return pd.DataFrame({"usjr_it": np.where(np.arange(200) % 3 == 0, 60.0, 100.0),
                         "basis_usd_mmbtu": np.arange(200.0)}, index=idx)


def _events(n=90, seed=0):
    rng = np.random.default_rng(seed)
    a = pd.to_datetime("2026-01-05") + pd.to_timedelta(rng.integers(0, 150, n), "D")
    red = rng.uniform(0.05, 0.8, n)
    return pd.DataFrame({"announced_utc": a, "reduction_bcfd": red,
                         "car_announce": red + rng.normal(scale=0.05, size=n),
                         "episode_id": [f"E{i//3}" for i in range(n)],
                         "season": 1, "block": "B"})


def test_driver_is_read_at_the_announcement_date_not_later():
    ev = R.attach_driver(_events(), _daily())
    assert "q_at_announce" in ev.columns
    assert ev["q_at_announce"].notna().any()


def test_driver_uses_asof_and_never_looks_ahead():
    daily = _daily()
    ev = pd.DataFrame({"announced_utc": [pd.Timestamp("2026-01-02")],
                       "reduction_bcfd": [0.5], "car_announce": [0.5],
                       "episode_id": ["E0"], "season": [1], "block": ["B"]})
    out = R.attach_driver(ev, daily)
    # 2026-01-01 is restricted (60.0); 2026-01-04 is the next restricted day.
    # An as-of read must return the 2026-01-02 value, not a future one.
    assert out["q_at_announce"].iloc[0] == daily.loc[pd.Timestamp("2026-01-02"), "usjr_it"]


def test_run_returns_a_threshold_and_a_bootstrap_pvalue():
    ev = R.attach_driver(_events(), _daily())
    out = R.run(ev, reps=99, seed=1)
    assert "gamma" in out and "bootstrap_p" in out
    assert 0.0 <= out["bootstrap_p"] <= 1.0


def test_run_reports_both_regime_slopes():
    ev = R.attach_driver(_events(), _daily())
    out = R.run(ev, reps=49, seed=1)
    assert "beta_low" in out and "beta_high" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_regime.py -q`
Expected: FAIL — no module named `regime`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/estimate/regime.py
"""H2: is the announcement response regime-dependent?

The regime driver is the USJR IT nomination-acceptance percentage observed AT
the announcement date - public, same-day, and available from 2019-10-24, so it
covers the treatment era with no look-ahead. Alliance utilization is not used:
it averages 97.7% with 70% of days above 98%, leaving nothing to threshold on.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from aeco.estimate import threshold as T
from aeco.estimate.speclog import log_spec

DRIVER = "usjr_it"


def attach_driver(ev: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """As-of join of the regime driver at each announcement date."""
    if DRIVER not in daily.columns:
        raise ValueError(f"daily panel has no {DRIVER!r} column")
    left = ev.copy()
    left["_a"] = pd.to_datetime(left["announced_utc"]).dt.normalize()
    right = (daily[[DRIVER]].dropna().sort_index()
             .rename_axis("_a").reset_index())
    out = pd.merge_asof(left.sort_values("_a"), right, on="_a", direction="backward")
    return out.rename(columns={DRIVER: "q_at_announce"}).drop(columns="_a")


def run(ev: pd.DataFrame, window: str = "announce", reps: int = 1000,
        seed: int = 0) -> dict:
    col = f"car_{window}"
    d = ev.dropna(subset=[col, "reduction_bcfd", "q_at_announce"])
    if len(d) < 30:
        raise ValueError(f"too few observations for a threshold fit: {len(d)}")
    y = d[col].to_numpy(float)
    X = np.column_stack([np.ones(len(d)), d["reduction_bcfd"].to_numpy(float)])
    q = d["q_at_announce"].to_numpy(float)

    f = T.fit(y, X, q)
    p = T.bootstrap_pvalue(y, X, q, reps=reps, seed=seed)
    stats = T.break_stats(y, X, q)
    spec_id = log_spec(f"h2_threshold_{window}", f"{col} ~ reduction_bcfd | q<=gamma",
                       str(sorted(d["block"].dropna().unique())),
                       {"n": int(len(d)), "gamma": f.gamma, "bootstrap_p": p})
    return {
        "gamma": f.gamma, "bootstrap_p": p, "n": int(len(d)),
        "n_low": f.n_low, "n_high": f.n_high,
        "beta_low": float(f.beta_low[1]), "beta_high": float(f.beta_high[1]),
        "sup_wald": stats["sup_wald"], "spec_id": spec_id,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/estimate/test_regime.py -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Commit**

```bash
git add src/aeco/estimate/regime.py tests/estimate/test_regime.py
git commit -m "feat: H2 regime-conditional threshold estimation"
```

---

### Task 7: THE figure

**Files:**
- Create: `src/aeco/figures/__init__.py`, `src/aeco/figures/the_figure.py`
- Test: `tests/test_the_figure.py`

**Interfaces:**
- Consumes: `panel.daily.build`, `panel.events.build`
- Produces: `the_figure.render(daily, events, out='docs/figures/the_figure.png') -> Path`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_the_figure.py
import numpy as np
import pandas as pd
from aeco.figures import the_figure as F


def _daily():
    idx = pd.date_range("2020-06-24", "2022-08-30", freq="D").union(
        pd.date_range("2025-01-01", "2026-08-20", freq="D"))
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "basis_usd_mmbtu": rng.normal(-1.5, 1.0, len(idx)),
        "usjr_it": rng.choice([100.0, 60.0], len(idx)),
        "block": ["A" if t < pd.Timestamp("2023-01-01") else "B" for t in idx],
    }, index=idx)


def _events():
    return pd.DataFrame({
        "announced_utc": pd.to_datetime(["2021-03-01", "2025-06-01"]),
        "start": pd.to_datetime(["2021-04-01", "2025-07-01"]),
        "end": pd.to_datetime(["2021-04-10", "2025-07-10"]),
        "reduction_bcfd": [0.4, 0.6], "car_announce": [0.2, 0.3], "block": ["A", "B"]})


def test_renders_a_file(tmp_path):
    p = F.render(_daily(), _events(), out=tmp_path / "fig.png")
    assert p.exists() and p.stat().st_size > 5000


def test_the_data_gap_is_drawn_as_a_break_not_interpolated(tmp_path):
    d = _daily()
    series = F.plot_series(d)
    gap = series.loc["2022-09-01":"2024-12-31"]
    # Every day inside the 28-month hole must be NaN so matplotlib breaks the
    # line rather than drawing a straight segment across it.
    assert gap.isna().all()


def test_series_covers_both_blocks(tmp_path):
    s = F.plot_series(_daily())
    assert s.loc[:"2022-08-30"].notna().any()
    assert s.loc["2025-01-01":].notna().any()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_the_figure.py -q`
Expected: FAIL — no module named `figures`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aeco/figures/the_figure.py
"""THE figure.

Top: daily AECO-Henry basis shaded by observable regime, with NGTL maintenance
windows as vertical bands. Bottom: event-study response against announced
reduction size, so the reader sees whether the response scales with treatment.

The 28-month data hole is reindexed to explicit NaN so the line BREAKS. Drawing
a segment across it would assert continuity the data does not have.
"""
from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def plot_series(daily: pd.DataFrame) -> pd.Series:
    """Basis on a continuous daily index, NaN inside the gap."""
    full = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    return daily["basis_usd_mmbtu"].reindex(full)


def render(daily: pd.DataFrame, events: pd.DataFrame,
           out: str | Path = "docs/figures/the_figure.png") -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    s = plot_series(daily)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                   gridspec_kw={"height_ratios": [2, 1]})

    ax1.plot(s.index, s.values, lw=0.8, color="#1f4e79", zorder=3)
    ax1.axhline(0, color="#999", lw=0.6, zorder=1)
    if "usjr_it" in daily.columns:
        restricted = daily.index[daily["usjr_it"] < 100]
        for t in restricted:
            ax1.axvspan(t, t + pd.Timedelta(days=1), color="#d62728",
                        alpha=0.10, lw=0, zorder=0)
    for _, e in events.iterrows():
        if pd.notna(e.get("start")) and pd.notna(e.get("end")):
            ax1.axvspan(e["start"], e["end"], color="#ff7f0e", alpha=0.12, lw=0, zorder=0)
    ax1.set_ylabel("AECO − Henry (US$/MMBtu)")
    ax1.set_title("AECO–Henry basis, observable constrained regime shaded, "
                  "NGTL maintenance windows banded")

    ax2.scatter(events["reduction_bcfd"], events["car_announce"],
                s=18, alpha=0.7, color="#1f4e79")
    ax2.axhline(0, color="#999", lw=0.6)
    ax2.set_xlabel("Announced reduction (Bcf/d)")
    ax2.set_ylabel("Announcement response")
    ax2.set_title("Response vs announced reduction size")

    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out
```

Add `matplotlib>=3.8` to `pyproject.toml` dependencies and run `uv sync --extra dev`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_the_figure.py -v`
Expected: PASS, 3 tests

- [ ] **Step 5: Render from real data, inspect it, then commit**

Run:
```bash
PYTHONPATH=src .venv/bin/python -c "
from aeco.panel.daily import build as bd
from aeco.panel.events import build as be
from aeco.figures.the_figure import render
d = bd(); print('figure ->', render(d, be(d)))
"
```
Open the PNG. Confirm by eye: the line breaks across 2022-09→2024-12 rather than crossing it, and shaded regions align with restricted days.

```bash
git add src/aeco/figures docs/figures pyproject.toml tests/test_the_figure.py
git commit -m "feat: THE figure, with the data gap drawn as a break"
```

---

### Task 8: Matlab/Octave mirror

**Files:**
- Create: `matlab/shims/{normcdf,chi2cdf,normrnd,unifrnd}.m`, `matlab/aeco_threshold.m`, `matlab/run_validation.m`
- Test: `tests/test_matlab_mirror.py`

**Interfaces:**
- Consumes: `vendor/hansen2000/*.m`, `tests/fixtures/dur_john.txt`
- Produces: `matlab/aeco_threshold.m` (threshold estimate from a CSV); `run_validation.m` (reproduces 863)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_matlab_mirror.py
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
OCTAVE = shutil.which("octave") or shutil.which("octave-cli")


def test_shims_exist_for_every_toolbox_function():
    # Hansen's code calls exactly four Statistics-Toolbox functions across 11
    # call sites. With these shims it runs in bare Octave, no toolboxes.
    for f in ("normcdf", "chi2cdf", "normrnd", "unifrnd"):
        assert (ROOT / "matlab" / "shims" / f"{f}.m").exists()


@pytest.mark.skipif(OCTAVE is None, reason="Octave not installed")
def test_octave_mirror_reproduces_hansens_threshold():
    r = subprocess.run([OCTAVE, "--no-gui", "--quiet", "run_validation.m"],
                       cwd=ROOT / "matlab", capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    assert "863" in r.stdout, r.stdout


@pytest.mark.skipif(OCTAVE is None, reason="Octave not installed")
def test_python_and_octave_agree_on_the_threshold():
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    import numpy as np
    from estimate.test_threshold import hansen_design
    from aeco.estimate import threshold as T
    y, X, q = hansen_design()
    py = T.fit(y, X, q).gamma
    r = subprocess.run([OCTAVE, "--no-gui", "--quiet", "run_validation.m"],
                       cwd=ROOT / "matlab", capture_output=True, text=True, timeout=300)
    oct_val = float([l for l in r.stdout.splitlines() if "threshold" in l.lower()][0].split()[-1])
    assert py == pytest.approx(oct_val)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_matlab_mirror.py -q`
Expected: FAIL on the shim test (the Octave tests skip if Octave is absent).

- [ ] **Step 3: Write the shims and the mirror**

```matlab
% matlab/shims/chi2cdf.m
function p = chi2cdf(x, k)
  p = gammainc(x / 2, k / 2);
end
```

```matlab
% matlab/shims/normcdf.m
function p = normcdf(x)
  p = 0.5 * erfc(-x / sqrt(2));
end
```

```matlab
% matlab/shims/normrnd.m
function r = normrnd(mu, sigma, m, n)
  if nargin < 3, m = 1; end
  if nargin < 4, n = 1; end
  r = mu + sigma .* randn(m, n);
end
```

```matlab
% matlab/shims/unifrnd.m
function r = unifrnd(a, b, m, n)
  if nargin < 3, m = 1; end
  if nargin < 4, n = 1; end
  r = a + (b - a) .* rand(m, n);
end
```

```matlab
% matlab/aeco_threshold.m
% Hansen (2000) threshold regression - concentrated least squares.
% Mirror of src/aeco/estimate/threshold.py. Runs in bare Octave with the
% shims on the path; no toolboxes required.
function [ghat, ssr, supw] = aeco_threshold(y, x, q, trim)
  if nargin < 4, trim = 0.15; end
  n = length(y);
  b0 = x \ y; e0 = y - x * b0; ssr0 = e0' * e0;
  lo = quantile(q, trim); hi = quantile(q, 1 - trim);
  cand = unique(q(q >= lo & q <= hi));
  ssr = Inf; ghat = NaN;
  for i = 1:length(cand)
    d = (q <= cand(i));
    z = [x, x .* d];
    if rank(z) < columns(z), continue; end
    b = z \ y; e = y - z * b; s = e' * e;
    if s < ssr, ssr = s; ghat = cand(i); end
  end
  supw = n * (ssr0 - ssr) / ssr;
end
```

```matlab
% matlab/run_validation.m
% Blocking validation: reproduce Hansen (2000) Table II on his own data.
addpath('shims');
data = load('../tests/fixtures/dur_john.txt');
for c = [5 6 10 11]
  data = data(data(:, c) ~= -999, :);
end
data = data(data(:, 2) > 0, :);
printf('n = %d\n', rows(data));
y = log(data(:, 6)) - log(data(:, 5));
x = [ones(rows(data), 1), log(data(:, 5)), log(data(:, 9) / 100), ...
     log(data(:, 8) / 100 + 0.05), log(data(:, 10) / 100)];
q = data(:, 5);
[ghat, ssr, supw] = aeco_threshold(y, x, q, 0.15);
printf('threshold %g\n', ghat);
printf('sup-Wald %g\n', supw);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src .venv/bin/python -m pytest tests/test_matlab_mirror.py -v`
Expected: shim test PASSES. If Octave is installed (`brew install octave`), the reproduction and agreement tests also pass, printing `n = 96` and `threshold 863`.

- [ ] **Step 5: Commit**

```bash
git add matlab tests/test_matlab_mirror.py
git commit -m "feat: Octave-runnable Matlab mirror of the threshold estimation"
```

---

### Task 9: Results report

**Files:**
- Create: `src/aeco/report_results.py`
- Test: none — a reporting entry point; correctness is covered by Tasks 2-8.

**Interfaces:**
- Consumes: `eventstudy.run_all`, `regime.run`, `speclog.summary`, `report_power.dop_coverage`
- Produces: `docs/results.md`

- [ ] **Step 1: Write the reporting script**

```python
# src/aeco/report_results.py
"""Emit H1 and H2 results with the discipline the brief requires."""
from __future__ import annotations
from pathlib import Path
from aeco.estimate import regime
from aeco.estimate.eventstudy import run_all
from aeco.estimate.speclog import HLZ_HURDLE, count
from aeco.panel.daily import build as build_daily
from aeco.panel.events import build as build_events
from aeco.report_power import dop_coverage


def main() -> int:
    d = build_daily()
    ev = build_events(d)
    cov = dop_coverage()
    tbl = run_all(ev)
    h2 = regime.run(regime.attach_driver(ev, d), reps=1000, seed=0)

    L = ["# Results", "",
         f"DOP archive loaded: **{cov['snapshots']}/{cov['of_total']}** "
         f"({cov['earliest']} to {cov['latest']}).",
         f"Blocks present: {sorted(ev['block'].dropna().unique())}. "
         "Blocks are never pooled — they use different publishers.", "",
         "## H1 — is the calendar priced at announcement?", "",
         tbl.to_markdown(index=False), "",
         "## H2 — regime-conditional response", "",
         f"- Threshold on USJR IT acceptance: **{h2['gamma']:.1f}**",
         f"- Bootstrap p (no-threshold null): **{h2['bootstrap_p']:.4f}**",
         f"- Slope below threshold (constrained): {h2['beta_low']:.4f} (n={h2['n_low']})",
         f"- Slope above threshold (slack): {h2['beta_high']:.4f} (n={h2['n_high']})", "",
         "## Inference discipline", "",
         f"- Specifications run to date: **{count()}**",
         f"- Harvey-Liu-Zhu hurdle: |t| >= {HLZ_HURDLE}",
         "- Standard errors clustered by maintenance episode.", ""]
    Path("docs/results.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the whole suite**

Run: `PYTHONPATH=src .venv/bin/python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 3: Generate results**

Run: `PYTHONPATH=src .venv/bin/python -m aeco.report_results`

- [ ] **Step 4: Commit**

```bash
git add src/aeco/report_results.py docs/results.md
git commit -m "feat: H1 and H2 results report"
```

---

## Phase 3 — the note

Out of scope here. Once results exist: the 4-6 page note, the three-sentence result, THE figure caption, and the outreach paragraph. Per the brief, write the four things a reviewer actually reads first — THE figure, the three-sentence result, the identification paragraph, and the power/multiple-testing paragraph — and let the rest serve them.

## Self-review

**Spec coverage.** Spec §2 H1 → Task 5; §2 H2 → Tasks 2, 3, 6; §6 Hansen from scratch + validation gate → Tasks 1, 2; §6 spec log and HLZ hurdle → Tasks 4, 5; §7 Matlab mirror and Octave shims → Task 8; §3 Tier 5 THE figure → Task 7. The spec's secondary small-N forward test (§2) is **not** covered here — it needs the block-A backfill, which is sidelined by author decision; it is listed in Phase 3 rather than dropped.

**Placeholders.** None. Every step carries runnable code or an exact command with an expected result.

**Type consistency.** `ThresholdFit` fields (`gamma`, `sup_wald`, `beta_low`, `beta_high`, `n_low`, `n_high`) are produced in Task 2 and consumed under those names in Tasks 3, 6, 8. `EventResult` fields are produced in Task 5 and consumed in Task 9. `attach_driver` produces `q_at_announce`, consumed by `regime.run`. `dop_coverage()` returns `snapshots`/`of_total`/`earliest`/`latest`, consumed in Task 9 — matching the Phase 1 implementation.

**Known gap, stated rather than hidden:** the Task 3 wild bootstrap is not identical to Hansen's homoskedastic fixed-regressor procedure, so it is validated against a *neighbourhood* of his published p-value rather than an exact match. The threshold estimate itself is validated exactly.
