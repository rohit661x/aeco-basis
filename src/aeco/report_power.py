"""Emit the power and coverage numbers the note must state up front."""

from __future__ import annotations

from pathlib import Path

from aeco.panel.daily import build as build_daily
from aeco.panel.events import build as build_events


def main() -> int:
    d = build_daily()
    e = build_events(d)
    n_events = len(e)
    n_epi = int(e["episode_id"].nunique()) if n_events else 0
    lines = [
        "# Power and Coverage Report",
        "",
        f"- Daily basis observations: **{int(d['basis_usd_mmbtu'].notna().sum())}**",
        f"- Coverage by block: {d.groupby('block', dropna=False).size().to_dict()}",
        f"- Outage announcements with usable price windows: **{n_events}**",
        f"- Distinct maintenance episodes: **{n_epi}**",
        f"- Events by block: {e['block'].value_counts().to_dict() if n_events else {}}",
        "",
        "Pre-registered rule: under ~15 episodes, the event study is framed as an",
        "identification demonstration and the t-stat hurdle is stated as 3.",
    ]
    Path("docs/power-report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
