"""Event panel: one row per NGTL outage announcement.

The event date is the ANNOUNCEMENT date, never the effective date. Two windows:
[a, a+1] measures whether the announcement is priced; [a+2, s] measures whether
the reaction was complete.
"""

from __future__ import annotations

import pandas as pd

from aeco import config


def _car(daily: pd.DataFrame, lo, hi):
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


def build(daily_df: pd.DataFrame | None = None, events_df: pd.DataFrame | None = None):
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
    ev["car_drift"] = [
        _car(daily_df, d + pd.Timedelta(days=2), s)
        for d, s in zip(a, pd.to_datetime(ev["start"]))
    ]
    ev = ev[ev["car_announce"].notna()].copy()
    if ev.empty:
        return ev
    ev["episode_id"] = _episodes(ev)
    ev["season"] = pd.to_datetime(ev["start"]).dt.month
    ev["block"] = [
        daily_df.loc[daily_df.index <= d, "block"].iloc[-1]
        if (daily_df.index <= d).any()
        else None
        for d in pd.to_datetime(ev["announced_utc"]).dt.normalize()
    ]
    out = config.DERIVED / "event_panel.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    ev.to_parquet(out)
    return ev
