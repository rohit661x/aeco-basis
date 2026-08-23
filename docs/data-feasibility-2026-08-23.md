# Data Feasibility Findings — AECO Basis Project

**Date:** 2026-08-23 · **Method:** 7 parallel recon agents, each adversarially verified by a second agent that re-fetched every claimed URL. 844 tool calls. Findings below are marked by verification status.

This resolves the go/no-go gates in §5 of the project brief. It replaces the brief's speculative data table with measured facts.

---

## Executive summary

| Gate | Brief's assumption | Measured reality | Status |
|---|---|---|---|
| **Gate 1** — AECO in EIA/ICE daily hub table | "Unconfirmed" | Table's natural-gas half **discontinued after 2017**; never contained AECO, Waha, Rockies, or Dominion South | ❌ **Failed** |
| **Gate 2** — AECO prompt basis swap history | "No deep free history" | Correct. But ~97 point-in-time forward curves are reconstructable 2016-06→2022-08 | ⚠️ **Partial** |
| **H1 backbone** — NGTL maintenance calendar | "Yes, public, ex ante" | **Better than hoped.** Announcement dates *directly observed*, not inferred | ✅ **Feasible** |
| **Regime driver** — Alliance utilization | "Utilization = scheduled/capacity" | Feasible but **nearly degenerate**. A better free driver exists | ⚠️ **Redirect** |
| **Dependent variable** — AB-NIT monthly index | Assumed obtainable | The settlement index (7A) is **paywalled**; free candidates are a *different* index | ❌ **Blocked** |

**The binding constraint is not any single gate. It is the overlap between them** — see "The N=2 problem" below.

---

## 1. Gate 1: FAILED (hard)

The EIA "Wholesale Electricity and Natural Gas Market Data" product is real, but:

- Natural-gas files **stop at `ice_natgas-2017final.xlsx`** (last trade date 2017-12-28). Every later year 404s. The electricity half is still live and updated 2026-08-19 — the ICE licence was narrowed to power only.
- Even when alive, the hub list was **eight US hubs**: Algonquin Citygates, Chicago Citygates, Henry, Malin, PG&E Citygate, SoCal Citygate, SoCal Ehrenberg, TETCO-M3. Read directly from the workbook's shared-string table. **No AECO, no Waha, no Rockies, no Dominion South.**
- EIA API v2 `/natural-gas/pri/fut` carries exactly five series: `RNGWHHD` (Henry Hub daily spot, 1997-01-07→present, 7,442 obs) and `RNGC1`–`RNGC4`.

**Consequence:** the brief's fallback applies — primary spread is AECO–Henry using whatever daily AECO is obtainable, stated in the first paragraph of the data section. The cross-hub panel (§6.5) is dead on arrival regardless of scope decisions, since no free daily source covers the control hubs either.

**Collateral damage:** `RNGC1`–`RNGC4` are **frozen at 2024-04-05** (verified by parsing all four XLS files; EIA's own banner confirms). Any Henry Hub *forward* leg after April 2024 must come from CME or a vendor. This matters because a derived AECO *basis* needs a same-vintage Henry Hub forward.

## 2. Gate 2: PARTIAL — reconstruction works, but is timing-misaligned

**What exists.** `gasalberta.com/gas-market/market-prices` shipped its full 47–48-month AECO C forward curve inline in the HTML as a Google Charts `arrayToDataTable` block. Both agents independently harvested the Wayback captures and parsed them:

- **97 complete forward curves**, 2016-06-26 → 2022-08-31, CDN$/GJ, vintage = capture timestamp.
- Reproduced independently by the verifier (97 curves vs. the recon's claimed 94 — an *under*-count).
- These are genuine point-in-time observations, not proxies: a capture of a page that displayed the posted quote, with a verifiable timestamp and no revision mechanism.

**Ground-truth anchors.** 25 distinct dated NGX **basis swap** curves in the correct units (US$/MMBtu) survive in Wayback across two defunct pages (`ABSETTLE.html` ×11, `NGXSETTLE.html` ×15, minus overlap), 2003–2012. Enough to *validate* a derived basis, nowhere near enough to be the series. **Note:** these are two different page formats; a parser written to one silently drops the other.

**What's closed.**
- **ICE Report Center (reports 250–255)** — resolved in this session with a real browser. The metadata endpoint returns `"recaptchaRequired": true`, which is why every scripted request returns HTTP 409. Its terms state you "shall not disclose, transmit, distribute or disseminate... the market data." **Not automatable, and not redistributable in published research.** Closed.
- **CME/NYMEX** — AECO/NIT Basis Swap (code `NA`) delisted 2009-08-31 per notice SER-4982, confirmed verbatim. Never relisted. The live successor is ICE Futures U.S. `AEC`, whose settlements are subscription-only.
- **NGI free snapshots** — every archived capture masks prices as literal `x.xxx`. Confirmed dead end.

**Known traps for the loader.** Fetch with the `id_` suffix (`web.archive.org/web/{ts}id_/{url}`) or Wayback's injected JS corrupts the inline arrays. Never assume row 1 is the prompt month — read the label (the 2017-06-08 capture starts at the *current* month). Never hardcode curve length (28–48 observed). Some archived responses return undecoded gzip.

## 3. H1 backbone: FEASIBLE — and stronger than the brief assumed

TC Energy's Customer Express NGTL Daily Operating Plan is a React SPA backed by an **unauthenticated AWS API Gateway**. This is the single best finding in the recon.

- `/outages/publisheddates` returns **1,513 exact publication timestamps**, business-daily, 2019-10-07 → 2026-08-21.
- `/outages/history/{ts}` returns the complete outage table *as it stood at that moment*.
- **Therefore the announcement date is directly observable**: it is the timestamp of the earliest publication containing a given `outageId`. Not inferred from page mtimes, not reconstructed from Wayback. This is exactly what the identification strategy requires and it is better than the brief hoped for.
- Reduction size is quantified: `areaBaseCapability − flowCapability`, in 10³m³/d (÷ ~28,300 for Bcf/d).
- Revisions are recoverable by keying on `(outageId, start, end, area)` instead of `outageId` alone.

**Hard floor: 2020-06-24.** The two October-2019 index entries return HTTP 504 on every retry. Before mid-2020 only irregularly-named monthly PDFs survive, with no posting timestamp — announcement date inferable only to the month.

**Traps (both verified, both silent):**
- **Do not harvest the CSV endpoint.** For an identical timestamp, JSON returns 104 records and CSV returns 79 — CSV silently drops *every* plant-turnaround (RPTA/DPTA) row, 24% of the panel. The CSV also omits `areaBaseCapability`, so reduction size isn't computable from it at all.
- Concurrency above ~3 causes silent data loss (~40% HTTP 500 at concurrency 8). A naive parallel harvester produces holes that look like "no outages announced that day."
- The site returns a 16,835-byte HTML *error page* on 404 — check status codes, not response size.
- CSV `Table` and JSON `area.acronym` use different vocabularies (`FHZ8` vs `FHBC`). Cross-format joins break on Foothills.

## 4. Regime driver: REDIRECT away from Alliance

Alliance's EBB was rebuilt by Pembina with an open JSON API; full history retrievable in a single POST (25,627 rows, 2023-01-16 → present). But:

> **Alliance border utilization is nearly degenerate**: mean 97.7%, 70% of days above 98%, only 5.6% below 90%. The pipe is essentially always full.

A slack/constrained classifier built on this has almost no variance to work with. **Use `tccustomerexpress.com/alberta/dashboard/ngtldash.csv` instead** — a public plain-GET CSV of daily FT/IT nomination-acceptance percentages per gate, 2019-10-24 → today, no publication lag. Restriction frequency: USJR 30.3% of days, EGAT 10.6%, WGAT 9.3%, OSDA 7.6%. That is a genuinely variable, same-day, free regime driver that aligns with the maintenance data's own era.

Traps: 105 duplicate-date rows (2,583 rows, 2,478 unique dates); the BC column header is **misspelled `Foorhills BC`** in the source. Also, Alliance history begins 2023-01-16 and FERC only requires 3-year retention — back-fill and persist now rather than assuming it stays available.

## 5. Dependent variable: BLOCKED — and this is subtle

The object AECO basis swaps settle against is the **ICE NGX AB-NIT Month Ahead Index (7A)**: the volume-weighted average of on-screen *prompt-month fixed-price* trades executed in the *prior* calendar month. It is published by S&P Global Platts' Canadian Gas Price Reporter. **It is paywalled, with no free deep history anywhere.**

Three free candidates exist and **none of them is the 7A**:

| Series | What it actually is | Free coverage |
|---|---|---|
| **AMP** (Alberta Market Price) | VWA of **all** physically delivered AB-NIT gas in the **delivery** month — blends dailies, monthlies, index and basis deals | 2011-01 → 2026-06, Alberta govt PDFs (186 obs) |
| **Alberta Reference Price** | AMP minus transport deduction × fuel factor — a **royalty netback**, ~15–20% below AMP | 1988-01 → 2026-06, clean JSON |
| **gasalberta "Monthly Index"** | Publisher's own captions describe it in **AMP terms**, not 7A terms | rolling ~13 months |

Substituting AMP for 7A introduces a systematic, volume-mix-dependent error that will be **worst precisely in the months where daily and monthly markets diverged** — i.e. the constrained months the study is about. This is not a nuisance; it is correlated with the treatment.

**Also blocked:** no free EIA storage consensus/survey series (all candidates 403). No free daily LNG Canada feedgas series *at all* — Coastal GasLink is BC-provincially regulated, so it carries no federal informational-posting obligation and is absent from CER pipeline profiles. Free official data tops out at monthly LNG exports measured at the loading arm.

## 6. Unexpected wins

- **CPC publishes a vintage-stamped forecast archive** of its gas-customer-weighted HDD product, keyed by issue date (`daily_forecasts_7day/{YYYY}/{MM}/{DD}/UtilityGas.Heating.txt`, daily from 2014). Forecast *revisions* — exactly what the brief wants — fall out by differencing consecutive issue dates. No reconstruction work.
- **The September 2021 CPC discontinuity the brief flags is a map-graphics change, not a data break** — verified by diffing DBF schemas across the boundary. There *is* a real undocumented break, but it's polygon geometry on **2025-08-22** (.shp 99KB → 4.97MB, two columns dropped). Different date, different variable.
- **TC Energy GDSR** gives daily NGTL border flows, storage and linepack back to ~1999-10 as public date-templated CSV.
- **`dobenergy.com/data/markets/prices/`** serves ~20 months of daily AECO spot in one anonymous fetch (2025-01→2026-08) — missed by the first recon pass.

⚠️ GDSR caveats: the modern parseable schema only starts ~2009-01-01, and **sign conventions invert across that boundary** (Empress Border +183.3 in 2000 vs −118.6 in 2026). Naive concatenation silently produces wrong-signed series. Filename date is the *publication* date; content is the *prior* gas day — a silent one-day shift.

## 7. Estimation stack

- **Hansen (2000) threshold regression is absent from statsmodels** (confirmed by source grep), and the only PyPI candidate (`pyxthreg`, 19 days old, 2 releases, one author) implements the *wrong model* — Hansen (1999) fixed-effects panel. **Write from scratch**: a ~90-line grid search plus fixed-regressor bootstrap reproduced Hansen's published Table II numbers on his own data (threshold 863, bootstrap p=0.005).
- **Hansen's official MATLAB code** (`users.ssc.wisc.edu/~behansen/progs/` — note the `be`) depends on only four Statistics-Toolbox functions across 11 call sites: `normcdf`, `chi2cdf`, `normrnd`, `unifrnd`. Each replaceable by a one-line base shim, after which it runs in **bare Octave with zero toolboxes**. That is the Matlab mirror, and it doubles as the cross-check on the Python.
- **Live correctness trap:** `arch`'s `RealityCheck` is literally `class RealityCheck(SPA): pass`. With defaults it gives Hansen's studentized SPA, *not* White's Reality Check. Must pass `studentize=False, nested=False`.
- **Deflated Sharpe:** the one packaged implementation (`overfitguard`) substitutes a different input for Bailey–López de Prado's SR* threshold. Implement from the paper.
- Also absent from statsmodels: Andrews–Ploberger, sup-Wald/Quandt, Chow. All fall out of the same grid loop as the threshold test (~120 lines total).
- **`tsDyn` was archived from CRAN on 2026-08-21.** Pin `remotes::install_version('tsDyn','11.0.5.2')` if threshold cointegration is needed.
- ⚠️ **The machine's conda env is broken**: `/opt/anaconda3` cannot `import pandas` (numpy 2.4.6 ABI vs pandas 2.1.4 built for numpy 1.x). A dedicated venv is required before any estimation work.

---

## 8. The N=2 problem

This is the finding that governs the design.

H1 needs, for each delivery month: an announced NGTL capacity reduction (treatment) and a prompt basis swap quote observed at a fixed point before the month (forecast). Those two requirements are satisfied on **disjoint eras**:

- Maintenance announcement data: **2020-06-24 → present**
- Reconstructable forward quotes: **2016-06-26 → 2022-08-31**, then a hard gap to today

Intersecting them, and applying the brief's own observation rule:

| Observation rule | Full reconstruction era | **Overlapping the maintenance era** |
|---|---|---|
| Capture on day 14–24 of prior month (≈5 bd before bidweek) | 18 months | **2 months** |
| Any capture in the prior month | 49 months | **13 months** |

The two qualifying months under the canonical rule are **2020-10 and 2021-02**.

Captures cluster around month boundaries — the wrong part of the month for this design. And the site moved to an AJAX endpoint in late 2022 that Wayback caught **twice**, so nothing free fills 2022-09 → 2025-08.

**This cannot be engineered around.** No storage schema, estimation choice, or inference correction produces a testable H1 from 2 observations. The design must change, the data source must change, or the study becomes prospective.

---

## 9. What this costs to fix

One month of **ICE NGX Data Access at US$675** provides 20+ years of daily AB-NIT settlement curves and 20+ years of index history — including the 7A. Downloaded once, it converts H1 from N=2 to N in the hundreds, resolves the dependent-variable identity problem outright, and eliminates the FX/units derivation entirely.

Redistribution is restricted, so the repo would ship code and derived results rather than raw data — which is normal for vendor-sourced research and does not impair reproducibility of the *method*.

This is stated as a measured fact, not a recommendation. The free path remains viable with a changed research design (see the architecture decision).
