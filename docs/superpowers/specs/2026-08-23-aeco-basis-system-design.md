# AECO Basis Research System — Design

**Date:** 2026-08-23 · **Author:** Rohit Suryadevara (with Claude) · **Status:** approved, pending implementation plan

Companion document: [`docs/data-feasibility-2026-08-23.md`](../../data-feasibility-2026-08-23.md) — the measured resolution of the brief's §5 gates. This design assumes those findings and does not restate them.

---

## 1. What changed from the brief, and why

The brief's §5 gates were resolved empirically. Three results forced design changes:

1. **Gate 1 failed.** EIA's ICE-republished daily hub table was discontinued after 2017 and never contained AECO. The cross-hub panel (§6.5) is impossible on free data and is cut.
2. **The treatment and outcome eras barely overlap.** NGTL announcement data begins 2020-06-24. Reconstructable prompt-forward quotes with a capture in the canonical pre-bidweek window overlap that era in **2 delivery months**. H1 as specified is not estimable.
3. **The free dependent variable is the wrong object.** The 7A index that basis swaps settle against is paywalled. Free candidates (AMP, Alberta Reference Price) are different indices, and the substitution error is largest in constrained months — correlated with the treatment.

Scope decisions taken with the author: free public sources only; single spread (AECO–Henry); **H3 and the DiD dropped**; open-ended schedule; lean build.

**The redesign.** H1 moves from the monthly forward to the **daily announcement response**, where data is dense. This is a deliberate deviation from brief §6.1 ("daily spot changes are used only for regime classification and the event-study reaction of the forward, never as the forecast target") and must be stated as such in the note. It changes the claim from *semi-strong efficiency of the forward* to *price discovery around public capacity information* — a narrower but well-identified and well-powered question. The original forward test survives as a reported small-N secondary.

**Measured feasibility of the redesign:**

| Window | Daily AECO spot coverage | Source |
|---|---|---|
| 2020-06-24 → 2022-08-30 | 494 days (3 gaps > 80d) | Wayback captures, harvested |
| 2022-09 → 2024-12 | **none free** — 28-month hole | — |
| 2025-01 → 2026-08 | ~600 days | dobenergy, single fetch |

~1,100 usable days in two disjoint blocks against ~20 outage announcements/month. The hole is real and is never interpolated across; it is a reported sample split.

---

## 2. Research objects

Let `b_d = AECO_d − HH_d` in US$/MMBtu, both daily spot. Let event `e` be the first appearance of an `outageId` in a DOP publication, at announcement timestamp `a_e`, with announced reduction `ΔCap_e = areaBaseCapability − flowCapability` (10³m³/d → Bcf/d), area `A_e`, and effective window `[s_e, t_e]`.

### H1 — is public capacity information impounded on announcement?

Two-part, mirroring brief §6.2 steps 1–2:

**(i) Immediate response.** `CAR_e[a_e, a_e+1] = β₁·ΔCap_e + α_season + γ'X_e + ε_e`

**(ii) Drift — was the reaction complete?** `CAR_e[a_e+2, s_e] = β₂·ΔCap_e + α_season + γ'X_e + ε_e`

- `β₁ > 0`, `β₂ = 0` → information impounded at announcement. Efficient.
- `β₂ ≠ 0` → **underreaction to public information**, the paper's headline finding.
- `α_season` significant with `β` insignificant → risk premium, not mispricing. Reported plainly, per brief §9.

Season fixed effects absorb the average premium; identification is on cross-sectional variation in announced reduction size. Standard errors clustered by **maintenance episode** (outages overlapping in time and area), with the episode count reported up front.

### H2 — regime-conditional response

Hansen (2000) threshold regression with regime driver `q_{a_e}` observed at announcement. **`q` is defined concretely as the IT nomination-acceptance percentage at Upstream James River (USJR) from `ngtldash.csv`**, the gate with the most variation (restricted 30.3% of days). It is public, same-day, and available from 2019-10-24, so it covers the whole treatment era with no look-ahead. Alliance border utilization is *not* used as the primary driver — it is 97.7% on average with 70% of days above 98%, leaving almost no variation to threshold on. It is retained only as a corroborating signal, and the two are never averaged (they disagree by ~13 points on the same gas day due to different measurement conventions).

`CAR_e = α_r + β_r·ΔCap_e + γ_r'X_e + ε_e`,  `r = 1 if q ≤ τ else 2`

τ estimated by grid search minimising SSR over trimmed candidates; threshold significance by fixed-regressor bootstrap. Tests `β₁ = β₂`.

**Robustness only:** two-state Markov switching using `predicted_marginal_probabilities` (P(S_t | info through t−1)) — *not* filtered, and never smoothed. Note: brief §6.3 says "filtered"; filtered probabilities still condition on time-*t* data, so predicted is the genuinely ex-ante object. This is a deliberate strengthening, stated in the note.

### Secondary — original forward efficiency, small-N

Regime-conditional Mincer-Zarnowitz on the 13 reconstructed months, reported with N, no extrapolation, framed as an identification demonstration per the brief's own decision rule.

### Controls `X_e`

Midwest HDD forecast revision (CPC vintage archive, differenced across issue dates); Western Canada cold snap indicator (**modelled separately from Midwest demand** — different mechanism, per brief §3); EIA storage surprise vs. 5-year-norm model (flagged weaker, no free consensus exists); bidweek and day-of-week dummies; lagged basis level. LNG Canada feedgas enters only as a **monthly** covariate — no free daily series exists, for the structural reason that Coastal GasLink is BC-provincially regulated.

---

## 3. Architecture

Six tiers. One invariant:

> **Raw bytes are immutable; everything else is re-derivable.**

Parsers are pure `raw → records` functions. A parser bug is fixed by re-deriving, never re-fetching. This matters more here than in a typical pipeline because most sources cannot be re-fetched: rolling windows drop off, CPC realized files are overwritten in place, and FERC retention is three years.

```
Tier 0  CAPTURE      daily, GitHub Actions → data/raw/  (immutable, committed)
Tier 1  BACKFILL     one-time, idempotent, resumable
Tier 2  PARSE        versioned pure functions → typed records
Tier 3  PANEL        vintage-aware assembly → daily grain + event grain
Tier 4  ESTIMATE     threshold, event study, inference, spec log
Tier 5  OUTPUT       THE figure, tables, note, Matlab mirror
```

### Tier 0 — Capture

Runs business-daily on GitHub Actions. Captures **only** sources actively losing history:

| Source | Why it must be captured now |
|---|---|
| gasalberta live JSON (`aeco_c_futures`, `aeco_ng_current`, `aeco_ng_prior`) | Endpoint has no history parameter; today's curve only |
| TC DOP publication snapshots | New timestamps appear daily |
| TC `/chart/csv` | Rolling ~18-month window, silently drops older days |
| `ngtldash.csv` | Regime driver, no lag |
| CPC realized HDD | **Overwritten in place** — realized vintages are unrecoverable retroactively |
| CPC 7-day forecast | Vintage-stamped, but cheap insurance |
| dobenergy daily spot | Rolling window |
| GDSR daily CSV | Cheap, and the only deep Western Canada daily |
| Alliance EBB | FERC requires only 3-year retention |
| EIA storage / FRED HH | Cheap; release-time vintages matter |

Contract: writes raw bytes plus a `fetch_meta.json` (URL, UTC timestamp, HTTP status, content hash, bytes). **Never parses.** **Never swallows an error** — a silent capture failure is indistinguishable from "nothing was announced that day," which is precisely the failure mode that corrupts an event study.

### Tier 1 — Backfill

One-time, idempotent on file existence, resumable. Wayback harvests (gasalberta market-prices ×128, pricing-market ×37, NGX anchors ×25); full DOP JSON history (1,511 snapshots, 2020-06-24 →, concurrency ≤ 3); CER throughput; GDSR history; FRED/EIA/CPC archives.

### Tier 2 — Parse

One versioned parser per source-**era** (not per source — gasalberta alone has three incompatible eras). Output: typed records with `as_of`, `source`, `parser_version`, `raw_hash`.

### Tier 3 — Panel

Vintage-aware assembly. Every row carries `as_of`. Two grains: **daily** (basis, regime driver, controls) and **event** (one row per outage announcement, with CARs and covariates joined at announcement-date vintage). Look-ahead is structurally prevented: joins are as-of joins, not equality joins.

### Tier 4 — Estimate

`threshold.py` (Hansen 2000 from scratch — grid search + fixed-regressor bootstrap; the same grid loop yields sup-Wald, Andrews–Ploberger exp/ave-Wald, and unknown-break Chow), `eventstudy.py`, `inference.py` (HAC, one-way cluster on episode, bootstrap), `speclog.py` (machine-written record of every specification run — the multiple-testing count is generated, never hand-counted), `forward_mz.py`.

### Tier 5 — Output

**THE figure.** Top panel: daily AECO–Henry basis shaded by observable regime, NGTL maintenance windows as vertical bands, LNG Canada Train 1 marked. Bottom panel: event-study CARs against announced reduction size, so the reader sees whether response scales with treatment. **The 2022-09 → 2024-12 hole is drawn as a visible break — never interpolated.**

---

## 4. Storage layout and vintage model

```
data/
  raw/         # committed to git — immutable, timestamped, hashed
    {source}/{YYYY}/{MM}/{DD}/{artifact}
  external/    # gitignored — large, rebuildable (DOP JSON ~2-3 GB)
  derived/     # gitignored — fully rebuildable from raw + external
```

Committing `raw/` to git buys an immutable vintage trail with independent timestamps, for free. Two size rules keep that sustainable:

- Everything written to `raw/` is **gzipped**. The daily DOP snapshot is 0.5–2 MB uncompressed (~500 MB/year uncommitted); gzipped JSON of this shape compresses roughly 10:1, which keeps the annual commit volume in the tens of megabytes.
- The **DOP historical backfill** (1,511 snapshots, ~2–3 GB) goes to `external/`, not `raw/`, and is gitignored with a documented idempotent rebuild command. It is re-fetchable today; the daily captures are not, which is what earns them the git trail.

**Vintage rule.** Every derived record carries the `as_of` of the *latest-dated input* that fed it. Any join that would import a future-dated value is an error, not a warning.

---

## 5. Known traps → test matrix

Each verified trap becomes a named regression test. These are not hypothetical; every one was confirmed by an adversarial verification pass against live sources.

| # | Trap | Test |
|---|---|---|
| 1 | DOP CSV silently drops all RPTA/DPTA rows (79 vs 104 records) and omits `areaBaseCapability` | Parser rejects CSV as a source for outage size; asserts JSON record count ≥ CSV |
| 2 | DOP concurrency > 3 → ~40% HTTP 500, silent holes | Harvester capped at 3; asserts every published timestamp resolved |
| 3 | TC returns a 16,835-byte HTML *error page* on 404 | All fetches assert on status code, never response size |
| 4 | GDSR sign conventions **invert** at 2009-01-01 | Cross-era fixture test: Empress Border sign |
| 5 | GDSR filename date = publication date; content = **prior** gas day | Alignment test against the `.htm` twin |
| 6 | `ngtldash.csv` has 105 duplicate-date rows | Dedup assertion before any date-keyed join |
| 7 | `ngtldash.csv` BC column misspelled `Foorhills BC` | Column-name fixture |
| 8 | CSV `Table` vs JSON `area.acronym` vocabularies differ (`FHZ8`/`FHBC`) | Crosswalk table + join-completeness assertion |
| 9 | Alliance `oprCapQty` is **null** on 4 rows, 0 on 191 | Guard is `in (None, 0)`, not `== 0` |
| 10 | Alliance `designCapQty` is **seasonal**, not constant | No constant-denominator fallback |
| 11 | Wayback needs `id_` suffix or injected JS corrupts inline arrays | Parser fixture on a known capture |
| 12 | Forward curve row 1 is **not** always the prompt month | Prompt month read from label, never derived from timestamp |
| 13 | Curve length varies 28–48 | No hardcoded length; validity requires ≥ 24 rows |
| 14 | gasalberta daily array column order is swapped by site JS | Columns identified **behaviourally** (flat-within-month = monthly index) |
| 15 | `arch.bootstrap.RealityCheck` is `class RealityCheck(SPA): pass` — defaults give SPA, not White | Explicit `studentize=False, nested=False`; asserted in test |
| 16 | `wngsr.json` has a UTF-8 BOM; revision flags are the **strings** `"false"`/`"true"` | Parser fixture |
| 17 | StatCan 25-10-00{55,57,58,59} frozen at 2025-12; successor label has a **double space** | Migration to 25-10-0086 asserted |
| 18 | CER storage URL soft-404s: HTTP 200 with a "File not found" body | Content assertion, not status alone |

---

## 6. Estimation details

**Hansen (2000) threshold regression is written from scratch** — statsmodels has no implementation, and the only PyPI candidate implements the wrong model (Hansen 1999 fixed-effects panel). ~90 lines: concentrated-LS grid search over trimmed threshold candidates minimising SSR, plus heteroskedasticity-robust sup-Wald and a fixed-regressor bootstrap.

**Validation gate:** the implementation must reproduce Hansen's published Table II on his own `dur_john.txt` data (n=96, threshold 863, bootstrap p ≈ 0.005) before it is used on AECO data. This is a blocking test, not a nice-to-have.

**Inference.** `cov_type='cluster'` with `cov_kwds={'groups': df['episode']}`; HAC with `maxlags ≥ h−1` for overlapping windows; bootstrapped threshold significance. Harvey-Liu-Zhu **t ≈ 3** hurdle for the headline coefficient, stated up front. Deflated Sharpe implemented from the Bailey–López de Prado paper (the packaged version substitutes a different input for SR*) — but note that with H1 recast as an announcement-response test rather than a trading strategy, deflated Sharpe applies only to the secondary tradeable section.

**Multiple testing.** The specification log is machine-written on every estimation run. The count reported in the note is read from that log, never hand-tallied.

---

## 7. Matlab mirror

Deliverable: Matlab mirror of the two headline estimations (threshold regression, event-study regression), because that is QSR's stated tooling.

Approach: vendor Hansen's own published MATLAB (`users.ssc.wisc.edu/~behansen/progs/` — note the `be`; legacy hostnames only reach it via a redirect chain) as the canonical reference. It depends on exactly four Statistics-Toolbox functions across 11 call sites — `normcdf`, `chi2cdf`, `normrnd`, `unifrnd` — each replaceable by a one-line base shim:

```
chi2cdf(x,k) = gammainc(x/2, k/2)
normcdf(x)   = 0.5*erfc(-x/sqrt(2))
normrnd      = randn
unifrnd      = rand
```

With those on the path it runs in **bare Octave with zero toolboxes**, so the mirror is testable in CI without a Matlab licence. It doubles as an independent cross-check on the Python: both must agree on threshold and test statistic to a stated tolerance.

Note: Matlab's Econometrics Toolbox `hac()` does **not** support cluster-robust SEs, so the episode-clustered sandwich is hand-written in the mirror.

---

## 8. Environment and repo

**Python 3.12 via `uv`.** The machine's `/opt/anaconda3` cannot `import pandas` (numpy 2.4.6 ABI against pandas 2.1.4 built for numpy 1.x). It is left untouched, not repaired — a dedicated venv is cleaner and avoids collateral damage to other work.

```
pyproject.toml            uv-managed
.github/workflows/capture.yml
src/aeco/
  capture/     registry.py, runner.py, sources/
  backfill/    wayback.py, dop_history.py
  parse/       one module per source-era
  panel/       vintage.py, daily.py, events.py
  forward/     base.py (interface), gasalberta.py, icengx.py (stub)
  estimate/    threshold.py, eventstudy.py, inference.py, speclog.py, forward_mz.py
  figures/
matlab/        shims/, vendored Hansen, aeco_threshold.m, aeco_eventstudy.m
tests/traps/   one test per row of §5
docs/
data/          raw/ (committed), external/, derived/
```

**The forward-price loader sits behind an interface** (`forward/base.py`) even though the free path is chosen. It costs ~20 lines and means a later ICE NGX purchase is a drop-in adapter, not a rework. This is the one piece of deliberate future-proofing in the design; everything else is YAGNI'd.

---

## 9. Validation discipline → brief §7

| Brief requirement | How this design satisfies it |
|---|---|
| Point-in-time everything | Announcement dates directly observed from DOP publication timestamps; as-of joins only; CPC forecast vintages by issue date |
| Multiple testing | Machine-written spec log; HLZ t≈3 hurdle |
| Risk premium vs. mispricing | Every H1 result reported with and without season FE |
| Structural honesty | Two disjoint data blocks reported separately; the 28-month hole never interpolated |
| Spanning | Response regressed on seasonal-dummy and carry benchmarks |
| Costs | Applies to the secondary tradeable section only; assumed half-spread stated |
| Power | Episode count and constrained-regime day count stated on page one |

---

## 10. Out of scope

Cross-hub panel (Gate 1 failed — impossible, not deprioritised). H3 / LNG DiD and the control spread (author decision). Intraday. Physical transport optimisation. Options on basis. Latent-regime trading signals. Weather as a hypothesis rather than a control. Bai-Perron as a headline break test. Precise capacity numbers.

---

## 11. Pre-registered decision rules

Written before results are seen, per the brief's own discipline:

1. If the episode count is under ~15, the event study is framed as an identification demonstration and the t-stat hurdle is stated as 3.
2. If the season-FE intercept is significant and the reduction-size slope is not, the headline is **"risk premium, not mispricing."**
3. If `β₂` (drift) is indistinguishable from zero, the headline is **"the calendar is priced"** — a clean, publishable null.
4. Results are reported separately for the 2020–2022 and 2025–2026 blocks. No pooled coefficient that either block contradicts.
5. The secondary forward test is reported with its N (currently 13) and no extrapolation.

---

## 12. Open items

- **The 28-month hole (2022-09 → 2024-12).** Worth one bounded investigation during implementation: Wayback coverage of dobenergy, and any other free daily AECO redistributor. If it closes, the sample stops being split.
- **Index identity — partially resolved 2026-08-23.** The two free daily series were compared over their 13-day overlap (Gas Alberta `aeco_ng_current` vs dobenergy). Once denominated consistently they agree to a mean absolute error of **0.021 USD/GJ (~2%)**, with correlation 0.935 and no exact matches. Reading: they are near-identical objects from the same AB-NIT family, differing by index definition or posting timing (plausibly 2A same-day vs 4A/5A day-ahead), not by price level.

  **Decision: proceed, and state the ambiguity rather than resolve it.** Three reasons.
  1. The efficiency object is a *change* in the basis over a 1–3 day window. An index-definition difference is a level-and-averaging difference that largely differences out; it does not bias `β₁` or `β₂` toward or away from zero.
  2. The residual disagreement (~2%) is an order of magnitude below the daily basis variation the event study identifies off (mean |Δbasis| ≈ 0.34).
  3. Resolving it definitively requires ICE or Platts, both paywalled. Spending the project's one paid dependency here would be poor allocation versus spending it on the forward series.

  **Obligations this creates.** The note states which series is used per block and that the AB-NIT index code is unlabelled by both publishers. A robustness split re-runs the headline on each source separately where they overlap. And the blocks must never be pooled into a single coefficient without reporting the source change alongside the regime change — block A and block B use *different* publishers, so a block difference confounds source with period.
- **Licensing.** gasalberta and dobenergy carry no redistribution grant. Fine as private research inputs; the repo ships derived results and code, not redistributed raw vendor data.
