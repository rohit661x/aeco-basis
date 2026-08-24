"""Event panel: one row per (outage announcement, area) pair.

The event date is the ANNOUNCEMENT date, never the effective date. Two
windows: the response is measured between actual OBSERVATIONS, not calendar
dates. A calendar-day window silently deleted every Friday announcement in
block B (no weekend prints) and produced spurious exact-zero CARs on Friday
and Saturday in block A (the source reposts Friday's value on the weekend).

car_announce spans the first observation on/after the announcement and the
next one after it - Friday maps to Monday, not to a missing Saturday.
car_drift spans two observations after that to the last observation on/before
the effective start. Its horizon (car_drift_days) is emitted alongside the
value because announcement lead time ranges from days to months, so drift
values are not comparable across events without it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from aeco import config

MAX_GAP_DAYS = 5  # a normal weekend-plus-holiday gap; anything wider is a real hole


def _clean_basis(daily: pd.DataFrame) -> pd.Series:
    """Basis series with weekend carry-forward duplicates removed.

    A row is a carry-forward if it lands on a weekend, is exactly one calendar
    day after the previous row, and repeats that row's value bit-for-bit -
    which is how the block-A source reposts Friday's quote on Sat/Sun.
    """
    s = daily["basis_usd_mmbtu"].dropna()
    if s.empty:
        return s
    idx = s.index
    is_weekend = idx.weekday >= 5
    one_day_gap = idx.to_series().diff().dt.days.to_numpy() == 1
    repeats_prev = (s.to_numpy() == s.shift(1).to_numpy())
    carried = is_weekend & one_day_gap & repeats_prev
    return s[~carried]


def _window(basis: pd.Series, lo: pd.Timestamp, max_gap_days: int = MAX_GAP_DAYS):
    """Position of the first observation on/after lo, or None if too far away."""
    idx = basis.index
    i = idx.searchsorted(lo)
    if i >= len(idx) or (idx[i] - lo).days > max_gap_days:
        return None
    return i


def _car_announce(basis: pd.Series, d: pd.Timestamp):
    i = _window(basis, d)
    if i is None or i + 1 >= len(basis):
        return None
    if (basis.index[i + 1] - basis.index[i]).days > MAX_GAP_DAYS:
        return None
    return float(basis.iloc[i + 1] - basis.iloc[i])


def _car_drift(basis: pd.Series, d: pd.Timestamp, s: pd.Timestamp):
    i = _window(basis, d)
    if i is None:
        return None, None
    lo_pos = i + 2
    if lo_pos >= len(basis) or pd.isna(s):
        return None, None
    j = basis.index.searchsorted(s, side="right") - 1
    if j < lo_pos:
        return None, None
    days = int((basis.index[j] - basis.index[lo_pos]).days)
    return float(basis.iloc[j] - basis.iloc[lo_pos]), days


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

    basis = _clean_basis(daily_df)
    ev = events_df.copy()
    a = pd.to_datetime(ev["announced_utc"]).dt.normalize()
    s = pd.to_datetime(ev["start"])

    ev["car_announce"] = [_car_announce(basis, d) for d in a]
    drift = [_car_drift(basis, d, s_) for d, s_ in zip(a, s)]
    ev["car_drift"] = [x[0] for x in drift]
    ev["car_drift_days"] = [x[1] for x in drift]

    ev = ev[ev["car_announce"].notna()].copy()
    if ev.empty:
        return ev
    ev["episode_id"] = _episodes(ev)
    ev["season"] = pd.to_datetime(ev["start"]).dt.month
    a_kept = pd.to_datetime(ev["announced_utc"]).dt.normalize()
    ev["block"] = [
        daily_df.loc[daily_df.index <= d, "block"].iloc[-1]
        if (daily_df.index <= d).any()
        else None
        for d in a_kept
    ]
    out = config.DERIVED / "event_panel.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    ev.to_parquet(out)
    return ev
