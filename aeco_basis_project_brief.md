# Project Brief: Does the AECO Forward Basis Price Public Capacity Information?
### Regime-dependent efficiency of the Western Canadian gas basis around posted NGTL maintenance, with the LNG Canada ramp as a natural experiment

**Author:** Rohit Suryadevara · **Audience:** OTPP Quantitative Strategies & Research · **Stack:** Python core, Matlab mirror of the two headline estimations

---

## 1. Headline question

> Does the prompt-month AECO basis swap fully impound the NGTL maintenance calendar, which is public and posted in advance, or does the forward's error around maintenance windows remain predictable from that calendar after controlling for a constant risk premium?
- **Home-market hub for a Toronto fund.** Nobody else applying will model it.

---

## 3. Market structure

**Pricing point.** AECO C / NIT on TC Energy's NGTL system. Daily index set on ICE NGX, reported by NGI and Canadian Gas Price Reporter.

**Takeaway paths that matter for the basis:**

- **Alliance Pipeline:** roughly 1.6 Bcf/d in summer rising to about 1.8 Bcf/d in winter (capacity is temperature-dependent). Wet gas, terminates at Aux Sable near Chicago, so Alliance economics load partly on NGL extraction margins, not only the gas basis. Wholly owned by Pembina since December 2023.
- **TC Mainline to Emerson, then Viking / Great Lakes into Chicago,** competing at Dawn. Eastern-path economics shifted after the 2025-26 Mainline toll changes; treat pre and post toll change as a robustness split.
- **Coastal GasLink to LNG Canada:** about 2.1 Bcf/d, expandable toward 5 Bcf/d with compression contingent on Phase 2 FID (FEED awarded April 2026, commercial terms agreed March 2026, FID pending as of this writing).

**What sets the spread:**

- **Slack regime:** spare takeaway; basis trades inside a band bounded by variable transport cost (fuel plus tolls); mean-reverting, low variance; forward should be near-unbiased.
- **Constrained regime:** takeaway full or NGTL under maintenance; AECO decouples and must fall until production shuts in; variance explodes; Chicago-end weather is nearly irrelevant because the constraint binds at the Alberta end. This produced the 2017-2019 negative prints and recurred in 2021-2022. Threshold-cointegration models of pipeline-constrained hubs (the locational-spreads literature, and Luong 2023 on crude analogues) are the published foundation for this; cite them, do not reinvent them.
- **Demand leg:** Chicago citygate loads on Midwest HDD; AECO does not. The two legs do not cancel on weather. Model the ends separately.
- **Supply-side weather:** Western Canada cold snaps cause freeze-offs that cut supply and can spike AECO. This is a different mechanism from Midwest heating demand and must not be pooled with it.
- **Structural break:** the LNG ramp is gradual, not a date. Model feedgas as a continuous covariate.

**Model implication:** an observable-threshold regime model with regime-conditional efficiency tests. Latent Markov switching is a robustness check only, because with an observable regime driver a latent model invites the criticism that the "regimes" are just fitted heteroskedasticity.

---

## 4. Hypotheses, nulls, and the confound each must beat

**H1 (headline, semi-strong efficiency).** Conditional on the announced NGTL capacity reduction being public at time t, the prompt basis swap's forecast error over the maintenance window is predictable from the announced reduction size.
- Null: the forward encompasses the calendar; adding the announced-reduction variable to a Mincer-Zarnowitz regression adds nothing.
- Confound to beat: a constant or seasonal risk premium (Bessembinder and Lemmon 2002). A forward that is on average too high every maintenance season is a premium for bearing constrained-regime tail risk, not a mispricing. Predictability must come from the cross-sectional or time-series variation in announced reduction size, not from the average.

**H2 (regime-conditional efficiency).** The forward is unbiased in the slack regime and biased in the constrained regime.
- Null: Mincer-Zarnowitz intercept zero and slope one in both regimes.
- Confound: regime defined with look-ahead. Use the observable utilization indicator, or filtered (never smoothed) regime probabilities.

**H3 (structural change, natural experiment).** Post-LNG-Canada, the constrained regime is less frequent and the forward's constrained-regime bias shrinks, relative to a control spread (Waha–Henry or Rockies–Henry).
- Null: no differential change versus control.
- Confound: record 2025 supply and storage growth working in the opposite direction. This is why a control spread and a continuous feedgas covariate are required; a pre/post dummy on AECO alone cannot separate LNG pull from supply push.

**Explicit expectation management:** any of the four outcomes (calendar priced / not priced, regime bias present / absent) is a publishable result. A well-identified null is the more credible email.

---

## 5. Data plan with go/no-go gates

The single largest execution risk. Every series below is labelled by what is actually free.

| Series | Free and daily and deep? | Source | Gate |
|---|---|---|---|
| Henry Hub spot | Yes (1997+) | FRED `DHHNGSP` | none |
| NYMEX HH futures settlements | Yes | EIA `RNGC1`-`RNGC4`; CME daily file (latest only) | none |
| **AECO daily spot** | **Unconfirmed.** Alberta govt and AER are monthly; NGI daily history is paywalled | EIA's ICE-republished daily hub table (2014+) if AECO is in the hub set; otherwise gasalberta / NGI snapshot captures forward only | **Gate 1:** confirm EIA-ICE coverage before anything else. If no, primary spread becomes AECO–Henry using whatever daily AECO is obtainable, and the project states the limitation in the first paragraph of the data section |
| **AECO prompt basis swap settlements** | **No deep free history.** ICE AB-NIT settlement history is a paid subscription; NYMEX AECO swap (code NA) delisted 2009; NGI Forward Look paywalled | ICE latest-day reports archived daily from now; NGI free snapshots; gasalberta current and prior month | **Gate 2:** if forward history is shorter than about three maintenance seasons, H1 is run on the available window and reported with that sample size; do not backfill from proxies |
| Chicago citygate | Monthly free (EIA); daily paywalled | EIA monthly; ICE Chicago basis future (paid history) | Chicago is a monthly robustness section only |
| Midwest and Western Canada degree days | Yes | NOAA CPC population- and gas-customer-weighted HDD (2013+ files, longer underlying) | none |
| Point-in-time weather forecasts | Yes, with breaks | CPC 6-10 and 8-14 day outlook archive (2001+, discontinuity Sept 2021); GEFSv12 reforecast (2000-2019) plus operational (2020+) | Use forecast revisions, not levels |
| EIA weekly storage with release times | Yes | EIA | Surprise = actual minus consensus if obtainable, else minus five-year-norm model (weaker; say so) |
| Western Canada storage | Monthly free; daily partial | CER snapshots; StatCan 25-10-0057 (2016+); TC Energy NGTL storage postings | Monthly is adequate for a control |
| **NGTL maintenance calendar and operational capacity** | Yes, public, ex ante | TC Energy Customer Express informational postings | **Backbone of H1.** Archive announcement date, effective dates, announced reduction, location. Announcement date is the event date, not the effective date |
| Alliance scheduled quantities and capacity | Yes | Alliance EBB (FERC-mandated) | Utilization = scheduled / capacity; regime driver |
| Control-spread hubs (Waha, Rockies, Dominion South) | Same paywall issue as AECO | EIA-ICE table if covered | Determines whether H3 control and the panel stretch goal are feasible |

**Liquidity and cost inputs:** ICE reported record North American gas open interest on July 1, 2026 with AB-NIT basis OI up 13% year over year, but contract-level OI and bid-ask are not public. All cost and capacity numbers are stated assumptions (a conservative assumed half-spread, wider in the constrained regime) and labelled as such. No precise capacity number is presented.

---

## 6. Identification and model design

### 6.1 Target variable

The tradeable instrument is the prompt-month AECO basis swap, settling monthly against the NGX AB-NIT monthly index minus NYMEX Henry Hub final settlement. Therefore:

- **Efficiency object:** forward error e_m = realized monthly index basis for month m minus the prompt basis swap price observed at a fixed point before the month (e.g., five business days before bidweek). One observation per month per roll convention. This is the Mincer-Zarnowitz object.
- **Tradeable object:** P&L of holding the prompt basis swap from observation date to settlement, net of assumed half-spread. Reported separately from the efficiency test.
- Daily spot changes are used only for regime classification and for the event-study reaction of the forward, never as the forecast target. Weekly ICs on a monthly-settled instrument are not reported because they overstate what can be captured.

### 6.2 Headline: maintenance-calendar event study on the forward

For each posted NGTL capacity reduction with announcement date a and effective window [s, t]:
1. Measure the prompt basis swap change in a short window around a (the announcement reaction).
2. Measure the forward error over the effective window (was the reaction complete?).
3. Regress forward error on announced reduction size (in Bcf/d, and as a share of NGTL operational capacity), with season fixed effects to absorb the average premium, and utilization at announcement as an interaction.
4. Cluster standard errors by maintenance episode. Count episodes and report the count; power rests on this number.

A positive, significant coefficient on announced reduction size after season fixed effects is underreaction to public information. A significant intercept with an insignificant slope is a risk premium. Report both, plainly.

### 6.3 Regime identification (S1)

- Primary: observable threshold on Alliance plus NGTL utilization (Hansen threshold regression with bootstrapped threshold-significance test).
- Regime-conditional Mincer-Zarnowitz: realized = a_r + b_r × forward + fundamentals, by regime r; test a = 0, b = 1; then forward-encompassing by adding maintenance indicator, utilization, storage surprise, HDD forecast revision, feedgas.
- Robustness: two-state Markov switching, filtered probabilities only.
- Errors: Newey-West for overlapping windows, episode clustering for the event study.

### 6.4 Structural change (S2)

- Treat LNG Canada feedgas (NGTL deliveries to Coastal GasLink) as a continuous covariate.
- Difference-in-differences: constrained-regime frequency and constrained-regime forward bias for AECO–Henry versus Waha–Henry (or Rockies–Henry), pre and post Train 1, with the feedgas covariate. Waha is the natural control because it is another producer-dominated, takeaway-constrained hub with its own negative-print history and no LNG-Canada treatment.
- Known-date Chow / Andrews-Ploberger as supplementary. Bai-Perron is not used as a headline test; with roughly one year of post-treatment monthly data it is underpowered and may not satisfy minimum trimming. Say this in one sentence.
- Rolling-window betas as the visual.

### 6.5 Stretch goal, contingent on Gate 1 and the control-hub check

Cross-hub panel (AECO, Waha, Rockies, Dominion South, Algonquin versus Henry) with a common constraint factor and hub-specific loadings, testing whether the forward's error loads on posted maintenance across hubs. One factor tested across many hubs is both more in QSR's house style and a partial answer to the multiple-testing problem. If the data are not there, this section does not exist.

### 6.6 Out of scope

Intraday, physical transport optimization, options on basis, Dawn and Malin as primary spreads, latent-regime trading signals, and any weather-level signal presented as an edge.

---

## 7. Validation discipline

1. **Point-in-time everything.** Maintenance announcement dates, not effective dates. Forecast vintages, not realizations. Storage release timestamps. Filtered regime probabilities. One paragraph documents each input's availability lag.
2. **Multiple testing.** Log every specification. Report the count. Use the Harvey-Liu-Zhu hurdle (t about 3) for the headline coefficient and a deflated Sharpe ratio (Bailey and Lopez de Prado) or White reality check for any tradeable P&L.
3. **Risk premium vs. mispricing.** Every claim of inefficiency is accompanied by the intercept-only alternative and the season-fixed-effects version.
4. **Structural honesty.** Pre and post Train 1 reported separately; no full-sample coefficient that the post-sample kills.
5. **Spanning.** Regress signal P&L on a seasonal-dummy strategy and on forward carry; report what survives.
6. **Costs.** Assumed half-spread stated; result reported dead if it dies at that cost.
7. **Power.** Number of maintenance episodes and number of constrained-regime months stated up front. If the count is small, the write-up says the design is an identification demonstration on a small sample.

---

## 8. Deliverables

- Aligned point-in-time panel with a vintage table.
- **THE figure:** top panel, daily AECO–Henry basis shaded by observable regime with NGTL maintenance windows as vertical bands and Train 1 / Train 2 marked; bottom panel, monthly forward error so the reader sees whether errors cluster in maintenance windows.
- Event-study table: forward error on announced reduction size, with and without season fixed effects, clustered by episode, with the episode count.
- Regime-conditional Mincer-Zarnowitz and encompassing tables.
- DiD table versus the control spread.
- 4-6 page note: question, market structure, data and vintages, identification, results, what three more months would buy.
- Reproducible repo; Matlab mirror of the threshold regression and the event-study regression.
- One paragraph plus THE figure for the outreach email; three sentences of results for the video interview.

---

## 9. Reviewer pre-empts

- "Isn't this just a risk premium?" → Season fixed effects absorb the average; the test is on variation in announced reduction size. If only the intercept survives, the note says risk premium, not mispricing.
- "Weather is crowded." → Weather is a control. The information set under test is the maintenance calendar, which is public but not in any vendor feed in usable form.
- "One year post-break is nothing." → Agreed; that is why the break is a continuous covariate plus a control-spread DiD, not a Bai-Perron test.
- "How many events?" → Stated on page one. Small-sample identification is presented as such.
- "Can you trade it?" → Prompt basis swap, monthly settlement, assumed costs stated, capacity modest and unverified. This is a research capability demonstration, not a capital pitch.
- "Why would this persist?" → Segmented, producer-hedger-dominated market; hedgers sell the forward irrespective of the calendar; index-flow rebalancing at bidweek. The note commits to whichever mechanism the results support.

---

## 10. Actionable insights

**Do first, in this order**

1. Open the EIA ICE-republished daily hub table and check whether AECO, Waha, Rockies, and Dominion South are in it. This single check determines the primary spread, whether H3 has a control, and whether the panel stretch goal exists. Nothing else should start until this is known.
2. Start archiving ICE AB-NIT and Chicago basis latest-day settlement reports and NGI free snapshots today. Forward history cannot be bought back later; every day not archived is a lost observation.
3. Scrape the TC Energy Customer Express informational postings and build the maintenance-event table (announcement date, effective window, announced reduction, location). This is the paper's backbone and it is free.
4. Pull Alliance EBB scheduled quantities and capacity and compute daily utilization. This is the regime driver.

**Decision rules to write down before seeing results**

- If forward history covers fewer than three maintenance seasons, H1 is reported on that window with the count and no extrapolation.
- If the maintenance-event count is under about fifteen, the event study is framed as an identification demonstration and the t-stat hurdle is stated as 3.
- If AECO daily is unobtainable, the primary spread is AECO–Henry from whatever daily AECO exists, and the first paragraph of the data section says so.
- If the season-fixed-effects intercept is significant and the reduction-size slope is not, the headline is "risk premium, not mispricing."

**What to cut without regret**

- Latent Markov switching as a primary model.
- Any attempt to reconstruct a 2015+ forward-basis history from proxies.
- Weather as a hypothesis.
- Precise capacity numbers.
- Bai-Perron as a headline break test.

**What the reviewer will actually read**

THE figure, the three-sentence result, the identification paragraph (Section 6.2), and the power and multiple-testing paragraph. Write those four things first and let everything else serve them.

**The three-sentence result, template**

"In the slack regime the AECO–Henry prompt basis swap is an unbiased predictor of the settled basis. In the constrained regime the forward's error is predictable from the size of publicly posted NGTL capacity reductions after season fixed effects, at [t-stat], across [N] episodes, consistent with underreaction to public capacity information rather than a constant premium. Relative to a Waha–Henry control, constrained-regime frequency and forward bias [fell / did not fall] as LNG Canada feedgas ramped, with record 2025 supply and storage growth the identified offset." Fill in the brackets with whatever the data say, including the negative versions.

**What this project signals to QSR**

Scientific method as they describe it: one hypothesis with a clean null, a stated information set, pre-registered decision rules, deflated inference, a natural experiment with a control, and a negative result treated as a result. Matlab mirror of the two headline estimations, because that is their stated tooling. Canadian home-market hub, because that is their book.
