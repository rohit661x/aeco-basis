import numpy as np
import pandas as pd
import pytest

from aeco.panel import events as E


def _daily():
    idx = pd.date_range("2026-09-25", "2026-10-05", freq="D")
    return pd.DataFrame(
        {"basis_usd_mmbtu": np.arange(len(idx), dtype=float), "block": "B"}, index=idx
    )


def _events():
    return pd.DataFrame(
        [{"outage_id": 1, "announced_utc": pd.Timestamp("2026-09-28 21:31:35"),
          "start": pd.Timestamp("2026-10-03"), "end": pd.Timestamp("2026-10-05"),
          "area": "USJR", "reduction_bcfd": 0.6}]
    )


def test_announcement_window_is_a_to_a_plus_one():
    # basis rises 1.0/day; [2026-09-28, 2026-09-29] spans one step
    assert E.build(_daily(), _events())["car_announce"].iloc[0] == pytest.approx(1.0)


def test_drift_window_runs_from_a_plus_two_to_effective_start():
    # [2026-09-30, 2026-10-03] spans three steps
    assert E.build(_daily(), _events())["car_drift"].iloc[0] == pytest.approx(3.0)


def test_announcement_date_is_used_never_the_effective_date():
    shifted = _events().assign(start=pd.Timestamp("2026-10-05"))
    assert E.build(_daily(), shifted)["car_announce"].iloc[0] == pytest.approx(1.0)


def test_events_outside_covered_days_are_dropped_not_interpolated():
    ev = _events().assign(
        announced_utc=pd.Timestamp("2023-05-01"), start=pd.Timestamp("2023-05-10")
    )
    assert E.build(_daily(), ev).empty


def test_overlapping_outages_in_one_area_share_an_episode_id():
    two = pd.DataFrame([
        {"outage_id": 1, "announced_utc": pd.Timestamp("2026-09-28"),
         "start": pd.Timestamp("2026-10-01"), "end": pd.Timestamp("2026-10-04"),
         "area": "USJR", "reduction_bcfd": 0.6},
        {"outage_id": 2, "announced_utc": pd.Timestamp("2026-09-29"),
         "start": pd.Timestamp("2026-10-03"), "end": pd.Timestamp("2026-10-05"),
         "area": "USJR", "reduction_bcfd": 0.2}])
    assert E.build(_daily(), two)["episode_id"].nunique() == 1


def test_non_overlapping_outages_get_distinct_episodes():
    two = pd.DataFrame([
        {"outage_id": 1, "announced_utc": pd.Timestamp("2026-09-26"),
         "start": pd.Timestamp("2026-09-27"), "end": pd.Timestamp("2026-09-28"),
         "area": "USJR", "reduction_bcfd": 0.6},
        {"outage_id": 2, "announced_utc": pd.Timestamp("2026-09-29"),
         "start": pd.Timestamp("2026-10-03"), "end": pd.Timestamp("2026-10-05"),
         "area": "USJR", "reduction_bcfd": 0.2}])
    assert E.build(_daily(), two)["episode_id"].nunique() == 2
