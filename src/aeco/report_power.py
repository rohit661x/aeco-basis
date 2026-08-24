"""Emit the power and coverage numbers the note must state up front.

Reports DOP archive coverage alongside the episode count: an episode count is
meaningless without saying how much of the announcement archive it was drawn
from, and the archive is backfilled newest-first.
"""

from __future__ import annotations

from pathlib import Path

from aeco import config
from aeco.backfill.dop import snapshot_path
from aeco.panel.daily import BLOCKS, build as build_daily
from aeco.panel.events import build as build_events

TOTAL_PUBLICATIONS = 1513  # index length as of 2026-08-23; 2 are permanently 504


def dop_coverage() -> dict:
    d = config.EXTERNAL / "dop"
    files = sorted(d.glob("*.json.gz")) if d.exists() else []
    stems = [f.name[: -len(".json.gz")] for f in files]
    days = sorted({s.split("T")[0] for s in stems})
    return {
        "snapshots": len(files),
        "of_total": TOTAL_PUBLICATIONS,
        "earliest": days[0] if days else None,
        "latest": days[-1] if days else None,
    }


def main() -> int:
    d = build_daily()
    e = build_events(d)
    cov = dop_coverage()
    n_events = len(e)
    n_epi = int(e["episode_id"].nunique()) if n_events else 0
    blocks_present = sorted(e["block"].dropna().unique()) if n_events else []

    pct = 100 * cov["snapshots"] / cov["of_total"] if cov["of_total"] else 0
    lines = [
        "# Power and Coverage Report",
        "",
        "## Announcement archive (DOP)",
        f"- Snapshots loaded: **{cov['snapshots']} of {cov['of_total']}** ({pct:.0f}%)",
        f"- Covering publications: {cov['earliest']} to {cov['latest']}",
        "",
        "## Price panel",
        f"- Daily basis observations: **{int(d['basis_usd_mmbtu'].notna().sum())}**",
        f"- Coverage by block: {d.groupby('block', dropna=False).size().to_dict()}",
        f"- Block definitions: {BLOCKS}",
        "",
        "## Event study power",
        f"- Announcements with usable price windows: **{n_events}**",
        f"- Distinct maintenance episodes: **{n_epi}**",
        f"- Events by block: {e['block'].value_counts().to_dict() if n_events else {}}",
        "",
        "## Sample statement for the note",
    ]
    if len(blocks_present) < 2:
        only = blocks_present[0] if blocks_present else "none"
        lines += [
            f"> The estimation sample is **block {only} only**. The DOP archive is "
            f"backfilled newest-first and is {pct:.0f}% loaded, so the "
            "2020-2022 window is not yet represented. Pre-registered rule 4 "
            "(report blocks separately) is satisfied vacuously until the "
            "remaining snapshots are harvested; the two-block comparison is "
            "outstanding, not negative.",
        ]
    else:
        lines += ["> Both blocks are represented; report coefficients separately per rule 4."]
    lines += [
        "",
        "Pre-registered rule 1: under ~15 episodes, the event study is framed as an",
        "identification demonstration and the t-stat hurdle is stated as 3.",
    ]
    Path("docs/power-report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
