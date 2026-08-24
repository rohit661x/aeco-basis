import numpy as np
import pandas as pd
import pytest

from aeco.panel import events as E


def _business_daily():
    """Block-B style: no rows on weekends at all (genuinely missing)."""
    idx = pd.bdate_range("2026-09-01", "2026-10-09")
    return pd.DataFrame(
        {"basis_usd_mmbtu": np.arange(len(idx), dtype=float), "block": "B"}, index=idx
    )


def _dense_daily_with_weekend_carry():
    """Block-A style: a row every calendar day, Sat/Sun repeating Friday's value."""
    idx = pd.date_range("2026-09-01", "2026-10-09", freq="D")
    vals = []
    last = 0.0
    for t in idx:
        if t.weekday() < 5:
            last = last + 1.0
        vals.append(last)
    return pd.DataFrame({"basis_usd_mmbtu": vals, "block": "A"}, index=idx)


def _events(announced, start, end, area="USJR", red=0.6):
    return pd.DataFrame(
        [{"outage_id": 1, "announced_utc": pd.Timestamp(announced),
          "start": pd.Timestamp(start), "end": pd.Timestamp(end),
          "area": area, "reduction_bcfd": red}]
    )


def test_friday_announcement_is_not_dropped_when_prices_are_business_daily():
    # 2026-09-25 is a Friday. The calendar-day window [Fri, Sat] used to have
    # only one observation and the row was silently deleted.
    daily = _business_daily()
    ev = _events("2026-09-25", "2026-10-05", "2026-10-08")
    out = E.build(daily, ev)
    assert len(out) == 1
    assert out["car_announce"].notna().all()


def test_friday_announcement_measures_friday_to_monday():
    daily = _business_daily()
    ev = _events("2026-09-25", "2026-10-05", "2026-10-08")
    out = E.build(daily, ev)
    fri = daily.loc["2026-09-25", "basis_usd_mmbtu"]
    mon = daily.loc["2026-09-28", "basis_usd_mmbtu"]
    assert out["car_announce"].iloc[0] == pytest.approx(mon - fri)


def test_weekend_carry_forward_does_not_produce_a_spurious_zero_car():
    # In block A the source reposts Friday's value on Sat/Sun. A calendar-day
    # window landing on a Friday used to measure Friday-vs-Saturday, which is
    # always exactly zero because Saturday just repeats Friday.
    daily = _dense_daily_with_weekend_carry()
    ev = _events("2026-09-25", "2026-10-05", "2026-10-08")
    out = E.build(daily, ev)
    assert out["car_announce"].iloc[0] != 0.0


def test_announcement_inside_a_long_data_hole_is_dropped_not_bridged():
    # If the nearest observation is many months away, the event must be
    # dropped, not silently paired with an unrelated future price.
    idx = pd.to_datetime(["2020-01-01", "2020-01-02", "2025-06-01", "2025-06-02"])
    daily = pd.DataFrame({"basis_usd_mmbtu": [1.0, 1.0, 5.0, 5.0], "block": "A"}, index=idx)
    ev = _events("2020-06-01", "2020-07-01", "2020-07-05")  # nearest obs is 2025
    out = E.build(daily, ev)
    assert out.empty


def test_drift_horizon_is_recorded_alongside_the_drift_value():
    daily = _business_daily()
    ev = _events("2026-09-01", "2026-10-01", "2026-10-05")
    out = E.build(daily, ev)
    assert "car_drift_days" in out.columns
    assert out["car_drift_days"].iloc[0] > 0


def test_announcement_date_is_used_never_the_effective_date():
    daily = _business_daily()
    shifted = _events("2026-09-01", "2026-10-08", "2026-10-09")
    out = E.build(daily, shifted)
    direct = _events("2026-09-01", "2026-09-10", "2026-09-11")
    out2 = E.build(daily, direct)
    assert out["car_announce"].iloc[0] == out2["car_announce"].iloc[0]


def test_overlapping_outages_in_one_area_share_an_episode_id():
    daily = _business_daily()
    two = pd.DataFrame([
        {"outage_id": 1, "announced_utc": pd.Timestamp("2026-09-01"),
         "start": pd.Timestamp("2026-10-01"), "end": pd.Timestamp("2026-10-04"),
         "area": "USJR", "reduction_bcfd": 0.6},
        {"outage_id": 2, "announced_utc": pd.Timestamp("2026-09-02"),
         "start": pd.Timestamp("2026-10-03"), "end": pd.Timestamp("2026-10-05"),
         "area": "USJR", "reduction_bcfd": 0.2}])
    out = E.build(daily, two)
    assert out["episode_id"].nunique() == 1
