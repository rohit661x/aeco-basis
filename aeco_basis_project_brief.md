# Project Brief: Does the AECO Basis Price Public Capacity Information?
### Announcement-response evidence from posted NGTL maintenance, with a regime-dependent test of price discovery in the Western Canadian gas basis

**Author:** Rohit Suryadevara · **Audience:** OTPP Quantitative Strategies & Research · **Stack:** Python core, Matlab mirror of the two headline estimations

> **Revision note (2026-08-23).** This brief was rewritten after the data-feasibility gates in the original §5 were resolved empirically. Three findings forced a redesign: EIA's ICE-republished daily hub table was discontinued after 2017 and never carried AECO (original Gate 1 failed); the prompt-forward quote series and the maintenance-announcement series overlap in **two** delivery months, which makes the original H1 unestimable; and the free monthly index is a different object from the 7A index that basis swaps settle against. Full evidence: `docs/data-feasibility-2026-08-23.md`. Design: `docs/superpowers/specs/2026-08-23-aeco-basis-system-design.md`.

---

## 1. Headline question

> When TC Energy posts an NGTL capacity reduction — public, dated, and announced in advance — does the AECO–Henry basis impound it at announcement, or does the price continue to drift toward the effective window in a way that is predictable from the announced reduction size?

The information set under test is the NGTL maintenance calendar: public, posted ex ante, and not available in any vendor feed in usable form. The test is whether the market prices it when it is announced, or only when it binds.

## 2. Why this project

- **Home-market hub for a Toronto fund.** Nobody else applying will model it.
- **A clean, dated, public information event.** Most efficiency tests fight over what was knowable when. Here the announcement timestamp is directly observed from the publisher's own archive — not inferred from page modification times, not reconstructed from news coverage.
- **A well-identified question survives a hostile data environment.** The original design died on data availability. Documenting that honestly, and rebuilding a powered test around what actually exists, is itself the demonstration.

> *Reconstructed section — the original §2 was absent from the source file. Rewritten from the surviving orphan bullet and §10's "what this project signals" content. Replace if the original text is recoverable.*

---

## 3. Market structure

**Pricing point.** AECO C / NIT on TC Energy's NGTL system. Daily index set on ICE NGX, reported by NGI and Canadian Gas Price Reporter.

**Takeaway paths that matter for the basis:**

- **Alliance Pipeline:** roughly 1.6 Bcf/d in summer rising to about 1.8 Bcf/d in winter (capacity is temperature-dependent). Wet gas, terminates at Aux Sable near Chicago, so Alliance economics load partly on NGL extraction margins, not only the gas basis. Wholly owned by Pembina since December 2023.
- **TC Mainline to Emerson, then Viking / Great Lakes into Chicago,** competing at Dawn. Eastern-path economics shifted after the 2025-26 Mainline toll changes; treat pre and post toll change as a robustness split.
- **Coastal GasLink to LNG Canada:** about 2.1 Bcf/d, expandable toward 5 Bcf/d with compression contingent on Phase 2 FID.

**What sets the spread:**

- **Slack regime:** spare takeaway; basis trades inside a band bounded by variable transport cost (fuel plus tolls); mean-reverting, low variance.
- **Constrained regime:** takeaway full or NGTL under maintenance; AECO decouples and must fall until production shuts in; variance explodes; Chicago-end weather is nearly irrelevant because the constraint binds at the Alberta end. This produced the 2017-2019 negative prints and recurred in 2021-2022. Threshold-cointegration models of pipeline-constrained hubs (the locational-spreads literature, and Luong 2023 on crude analogues) are the published foundation; cite them, do not reinvent them.
- **Demand leg:** Chicago citygate loads on Midwest HDD; AECO does not. The two legs do not cancel on weather. Model the ends separately.
- **Supply-side weather:** Western Canada cold snaps cause freeze-offs that cut supply and can spike AECO. A different mechanism from Midwest heating demand; must not be pooled with it.

**Model implication:** an observable-threshold regime model with regime-conditional response tests. Latent Markov switching is a robustness check only, because with an observable regime driver a latent model invites the criticism that the "regimes" are just fitted heteroskedasticity.

---

## 4. Hypotheses, nulls, and the confound each must beat

**H1 (headline, price discovery around public information).** The daily AECO–Henry basis response to a posted NGTL capacity reduction is complete at announcement. Formally, the immediate response scales with announced reduction size (β₁ > 0) and the subsequent drift to the effective window does not (β₂ = 0).
- Null: β₂ = 0. The calendar is priced at announcement.
- Alternative: β₂ ≠ 0 is underreaction to public information.
- Confound to beat: a constant or seasonal risk premium (Bessembinder and Lemmon 2002). Season fixed effects absorb the average; the test is on cross-sectional variation in announced reduction size. If only the intercept survives, the finding is a premium, not a mispricing.

**H2 (regime-conditional price discovery).** The response is complete in the slack regime and incomplete in the constrained regime.
- Null: β₁ and β₂ are equal across regimes.
- Confound: regime defined with look-ahead. The regime driver is the observable NGTL restriction indicator at the announcement date; the Markov robustness check uses **predicted** (not filtered, never smoothed) probabilities, since filtered probabilities still condition on time-*t* information.

**Secondary (original forward-efficiency test, small sample).** Regime-conditional Mincer-Zarnowitz on the reconstructed prompt-forward series. Reported with N = 13 and no extrapolation, as an identification demonstration rather than a result.

**Explicit expectation management:** any of the four outcomes (calendar priced / not priced, regime dependence present / absent) is a publishable result. A well-identified null is the more credible email.

**What was cut, and why.** The original H3 (LNG Canada as a natural experiment, difference-in-differences against a Waha–Henry control) is dropped as a scope decision. No free daily source covers any control hub — the same failure that killed Gate 1 — and no free daily LNG Canada feedgas series exists at all, because Coastal GasLink is BC-provincially regulated and carries no federal informational-posting obligation. Feedgas survives as a monthly covariate. The cross-hub panel is dropped for the same reason.

---

## 5. Data plan — gates resolved

The original §5 listed gates as open questions. They have been checked. Every row below was verified by fetching the source, then adversarially re-verified.

| Series | Status | Source | Coverage |
|---|---|---|---|
| **NGTL maintenance calendar** | ✅ **Backbone.** Announcement dates *directly observed* | TC Customer Express DOP API (unauthenticated) | 1,511 dated snapshots, 2020-06-24 → present |
| **NGTL regime driver** | ✅ Free, same-day, no lag | `ngtldash.csv` — daily FT/IT nomination acceptance per gate | 2019-10-24 → present |
| Henry Hub daily spot | ✅ | FRED `DHHNGSP` + ALFRED vintages | 1997 → present |
| **AECO daily spot** | ⚠️ **Two disjoint blocks, 28-month hole** | Wayback captures + dobenergy | 494 days 2020-06→2022-08; ~600 days 2025-01→2026-08 |
| Midwest HDD + **vintage-stamped forecasts** | ✅ Better than assumed | CPC gas-customer-weighted, forecast archive keyed by issue date | realized 1981+, forecasts 2014+ |
| Western Canada storage / linepack | ✅ | TC GDSR daily CSV | ~1999-10 → present (schema break at 2009) |
| Alliance utilization | ⚠️ Nearly degenerate (97.7% mean) | Pembina EBB JSON API | 2023-01-16 → present |
| **AECO prompt basis swap** | ❌ **No usable free history** | Reconstructed from Wayback | 97 curves 2016-2022; **2 usable months overlap the treatment era** |
| **AB-NIT 7A settlement index** | ❌ **Paywalled** | Platts CGPR / ICE NGX (US$675/mo) | free candidates are a *different* index |
| EIA storage consensus | ❌ Not free | — | modelled 5-year-norm proxy, flagged weaker |
| Daily LNG Canada feedgas | ❌ Does not exist free | — | monthly exports only |
| Cross-hub controls (Waha, Rockies) | ❌ Gate 1 failed | — | EIA/ICE gas table dead after 2017 |

**The arithmetic that drove the redesign.** The treatment (announcements, 2020-06 →) and the original outcome (prompt-forward quotes, → 2022-08) overlap in 26 months. Applying the brief's own observation rule — a quote about five business days before bidweek — leaves **2 delivery months**. Relaxing to any quote in the prior month leaves 13. No estimator recovers a test from that. The daily basis, by contrast, covers ~1,100 days against roughly 20 announcements per month.

**Cost of removing the constraint.** One month of ICE NGX Data Access (US$675) supplies 20+ years of AB-NIT settlement curves and index history, which would restore the original forward-efficiency design outright. Stated as a measured fact; the free path is the chosen path.

---

## 6. Identification and model design

### 6.1 Target variable

- **Efficiency object:** cumulative change in the daily AECO–Henry basis around a posted capacity reduction. Two windows per event: the announcement window `[a, a+1]` and the drift window `[a+2, s]`, where `a` is the announcement timestamp and `s` the effective start.
- **Treatment:** announced reduction size, `areaBaseCapability − flowCapability`, in Bcf/d and as a share of area capability.
- Announcement date is the event date, never the effective date.

### 6.2 Headline: maintenance-calendar event study

For each posted reduction with announcement `a` and effective window `[s, t]`:

1. `CAR[a, a+1] = β₁·ΔCap + α_season + γ'X + ε` — is the announcement priced?
2. `CAR[a+2, s] = β₂·ΔCap + α_season + γ'X + ε` — was the reaction complete?
3. Cluster standard errors by maintenance episode. Report the episode count; power rests on it.

β₁ > 0 with β₂ = 0 is efficient price discovery. β₂ > 0 is underreaction to public information. A significant intercept with insignificant slopes is a risk premium. Report all three, plainly.

### 6.3 Regime identification

- Primary: observable threshold on the NGTL IT-acceptance percentage at Upstream James River (restricted 30.3% of days — the gate with real variation). Hansen (2000) threshold regression with a bootstrapped threshold-significance test.
- Alliance utilization is a corroborating signal only, not the driver: it averages 97.7% with 70% of days above 98%, and disagrees with the Canadian-side series by ~13 points on the same gas day.
- Robustness: two-state Markov switching, predicted probabilities only.
- Errors: Newey-West for overlapping windows, episode clustering for the event study.

### 6.4 Out of scope

Cross-hub panel (impossible, not deprioritised — Gate 1 failed). LNG difference-in-differences and any control spread. Intraday. Physical transport optimisation. Options on basis. Dawn and Malin as primary spreads. Latent-regime trading signals. Any weather-level signal presented as an edge. Bai-Perron as a headline break test.

---

## 7. Validation discipline

1. **Point-in-time everything.** Announcement timestamps from the publisher's own archive. Forecast vintages, not realizations. Storage release timestamps. Predicted regime probabilities. One paragraph documents each input's availability lag.
2. **Multiple testing.** Every specification is logged by the code, not by hand. Report the count. Harvey-Liu-Zhu hurdle (t ≈ 3) for the headline coefficient.
3. **Risk premium vs. mispricing.** Every claim of inefficiency is accompanied by the intercept-only alternative and the season-fixed-effects version.
4. **Structural honesty.** The 2020-2022 and 2025-2026 blocks are reported separately. The 28-month gap is never interpolated across, and appears as a visible break in every figure.
5. **Spanning.** Regress the response on a seasonal-dummy benchmark and on forward carry; report what survives.
6. **Power.** Number of maintenance episodes and number of constrained-regime days stated up front.
7. **Provenance.** Free redistributed sources (gasalberta, dobenergy) carry no licence grant and no index-code label. The repo ships code and derived results, not redistributed raw vendor data, and the note states which AB-NIT object the series is — or states that it is unresolved.

---

## 8. Deliverables

- Aligned point-in-time panel with a vintage table.
- **THE figure:** top panel, daily AECO–Henry basis shaded by observable regime with NGTL maintenance windows as vertical bands and Train 1 marked, the data gap drawn as a break; bottom panel, event-study CARs against announced reduction size, so the reader sees whether the response scales with the treatment.
- Event-study table: CAR on announced reduction size, announcement and drift windows, with and without season fixed effects, clustered by episode, with the episode count.
- Regime-conditional threshold-regression table.
- 4-6 page note: question, market structure, **what the data permitted and what it did not**, identification, results, what three more months would buy.
- Reproducible repo; Matlab mirror of the threshold regression and the event-study regression, runnable in Octave.
- One paragraph plus THE figure for the outreach email; three sentences of results for the video interview.

---

## 9. Reviewer pre-empts

- **"Why aren't you testing the forward? Your title used to."** → Because the data does not exist. The forward-quote series and the announcement series overlap in two delivery months. The arithmetic is in §5 and the raw counts are in the repo. The forward test is still reported, at N = 13, labelled as such.
- **"Isn't this just a risk premium?"** → Season fixed effects absorb the average; the test is on variation in announced reduction size. If only the intercept survives, the note says risk premium, not mispricing.
- **"Daily spot isn't the tradeable instrument."** → Correct, and the note does not claim a tradeable edge. This is a price-discovery test on public information, not a strategy. The tradeable object is discussed only in the small-N secondary section.
- **"Weather is crowded."** → Weather is a control. The information set under test is the maintenance calendar.
- **"How many events?"** → Stated on page one. Small-sample identification is presented as such.
- **"Why would this persist?"** → Segmented, producer-hedger-dominated market; the calendar is public but is not in any vendor feed in usable form, so acting on it requires building exactly this dataset. The note commits to whichever mechanism the results support.
- **"Your price series has a 28-month hole."** → Yes. The two blocks are reported separately and never pooled into a coefficient that either block contradicts.

---

## 10. Actionable insights

**Do first, in this order**

1. **Stand up the daily capture tier.** Several sources are losing history every day: the CPC realized-HDD files are overwritten in place, TC's `/chart/csv` is a rolling 18-month window, Alliance retains only three years, and the gasalberta forward endpoint has no history parameter. Every day not captured is a lost observation, and unlike the Wayback material it cannot be recovered later.
2. **Backfill the DOP archive** — 1,511 JSON snapshots, concurrency ≤ 3. This is the paper's backbone and it is free.
3. **Harvest the Wayback material** — 128 gasalberta captures, 37 legacy tables, 25 NGX basis-swap anchor curves for validating the derived basis.
4. **Build the regime driver** from `ngtldash.csv`.

**Decision rules, written before results are seen**

- If the episode count is under about fifteen, the event study is framed as an identification demonstration and the t-stat hurdle is stated as 3.
- If the season-fixed-effects intercept is significant and the reduction-size slope is not, the headline is "risk premium, not mispricing."
- If β₂ is indistinguishable from zero, the headline is "the calendar is priced" — a clean, publishable null.
- Results are reported separately for the 2020-2022 and 2025-2026 blocks.
- The secondary forward test is reported with its N and no extrapolation.

**What to cut without regret**

- Latent Markov switching as a primary model.
- Any attempt to reconstruct a continuous forward-basis history from proxies.
- Weather as a hypothesis.
- Precise capacity numbers.
- Bai-Perron as a headline break test.

**What the reviewer will actually read**

THE figure, the three-sentence result, the identification paragraph (§6.2), and the power and multiple-testing paragraph. Write those four things first and let everything else serve them.

**The three-sentence result, template**

"Posted NGTL capacity reductions move the AECO–Henry basis at announcement, scaling with announced reduction size at [t-stat] across [N] episodes. [The reaction is complete / A further drift of [x] toward the effective window remains predictable from the same public number], after season fixed effects. The [drift / completeness] is [concentrated in / invariant to] the constrained regime, identified by an observable threshold on NGTL restriction intensity at [τ]." Fill in the brackets with whatever the data say, including the negative versions.

**What this project signals to QSR**

Scientific method as they describe it: one hypothesis with a clean null, a stated information set, pre-registered decision rules, deflated inference, and a negative result treated as a result. It also signals something the original design could not: that the author checks whether the data exists before building on it, reports the failure in the first paragraph, and rebuilds a powered test around what is actually there. Matlab mirror of the two headline estimations, because that is their stated tooling. Canadian home-market hub, because that is their book.
