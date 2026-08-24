import pandas as pd
import pytest

from aeco.panel import units as U


def test_cad_gj_to_usd_mmbtu_divides_by_fx():
    idx = pd.to_datetime(["2026-08-20"])
    s = pd.Series([1.41], index=idx)
    fx = pd.Series([1.3785], index=idx)
    assert U.cad_gj_to_usd_mmbtu(s, fx).iloc[0] == pytest.approx(1.41 * 1.055056 / 1.3785)


def test_usd_gj_to_usd_mmbtu_does_not_touch_fx():
    # dobenergy is USD/GJ. Dividing by FX here understates AECO by ~28% and
    # still yields a plausible-looking gas price, so it fails silently.
    idx = pd.to_datetime(["2026-08-20"])
    s = pd.Series([1.02], index=idx)
    assert U.usd_gj_to_usd_mmbtu(s).iloc[0] == pytest.approx(1.02 * 1.055056)


def test_the_two_sources_agree_once_units_are_aligned():
    # Empirical: on 2026-08-20 Gas Alberta quoted 1.41 CAD/GJ and dobenergy
    # quoted 1.02 USD/GJ at FX 1.3785. Converted, they must land within a few
    # cents -- they are near-identical objects, not different price levels.
    idx = pd.to_datetime(["2026-08-20"])
    ga = U.cad_gj_to_usd_mmbtu(pd.Series([1.41], index=idx), pd.Series([1.3785], index=idx))
    db = U.usd_gj_to_usd_mmbtu(pd.Series([1.02], index=idx))
    assert abs(ga.iloc[0] - db.iloc[0]) < 0.05
