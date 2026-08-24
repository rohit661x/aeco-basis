# AECO Basis: Does the Western Canadian gas basis price public capacity information?

Research system testing whether the AECO–Henry natural gas basis impounds posted NGTL maintenance at announcement, or continues to drift toward the effective window in a way that is predictable from the announced reduction size.

**Brief:** [`aeco_basis_project_brief.md`](aeco_basis_project_brief.md)
**Design:** [`docs/superpowers/specs/2026-08-23-aeco-basis-system-design.md`](docs/superpowers/specs/2026-08-23-aeco-basis-system-design.md)
**Data feasibility:** [`docs/data-feasibility-2026-08-23.md`](docs/data-feasibility-2026-08-23.md)
**Current power:** [`docs/power-report.md`](docs/power-report.md)

## Why the design looks like this

The original design tested the prompt-month AECO basis *swap*. That is not estimable on free data: the maintenance-announcement archive begins 2020-06-24, reconstructable forward quotes end 2022-08-31, and applying the canonical "five business days before bidweek" rule leaves **two** delivery months in the overlap. The efficiency object was therefore moved to the daily basis response around announcements, where coverage supports several hundred events. The forward test survives as a reported small-N secondary. Full arithmetic in the feasibility document.

## Quickstart

```bash
uv sync --extra dev
uv run pytest                          # 51 tests
uv run python -m aeco.capture.runner   # daily capture (business days)
uv run python -m aeco.backfill.dop     # one-time archive backfill, concurrency <= 3
uv run python -m aeco.report_power     # coverage and power
```

## Architecture

Six tiers with one invariant: **raw bytes are immutable and everything else is re-derivable.** Parsers are pure `raw → records` functions, so a parser bug is fixed by re-deriving, never re-fetching. That matters because most sources cannot be re-fetched — rolling windows drop off, CPC realized files are overwritten in place, and Alliance retains only three years.

```
capture/   daily, fails loudly     backfill/  one-time, idempotent
parse/     one module per era      panel/     vintage-aware assembly
```

`tests/traps/` holds one regression test per verified data trap — the DOP CSV endpoint that silently drops 24% of rows, the `Foorhills BC` misspelling, duplicate dates, behavioural column identification, and others. Each was confirmed against the live source.

## Data sources and attribution

All sources are free and keyless. Raw captures are committed for point-in-time reproducibility.

| Data | Source | Notes |
|---|---|---|
| NGTL outage announcements | TC Energy Customer Express | Announcement dates directly observed |
| NGTL restriction dashboard | TC Energy | Regime driver, 2019-10-24→ |
| NGTL gas day summary | TC Energy | Daily linepack, storage, border flows |
| AECO forward and index | Gas Alberta | No redistribution grant; "deemed reliable but not guaranteed" |
| AECO daily spot (2025+) | dobenergy.com | Attributed by the publisher to LSEG, One Exchange & ICE |
| Henry Hub daily spot | US EIA | Public domain |
| CAD/USD | Bank of Canada Valet | Open licence |

> **Provenance notice.** Raw captures from Gas Alberta and dobenergy.com are included for reproducibility of the point-in-time panel. Neither publisher grants redistribution rights, and neither series carries an index-code label identifying which AB-NIT object it represents. They are used here as research inputs. If you are a rights holder and want material removed, open an issue.

## Status

Phase 1 (capture, backfill, parse, panel) is complete. Phase 2 (Hansen threshold regression, event-study estimation, Matlab/Octave mirror) is not yet built.

The DOP archive is backfilled newest-first and is partially loaded, so the current estimation sample is block B only. The two-block comparison required by pre-registered rule 4 is outstanding, not negative — see the power report for the live count.
