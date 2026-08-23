import pandas as pd
import pytest

from aeco.panel import daily as D


def test_unit_conversion_matches_the_documented_formula():
    # USD/MMBtu = (CAD/GJ * 1.055056) / FXUSDCAD
    assert D.to_usd_mmbtu(2.00, 1.3760) == pytest.approx(2.00 * 1.055056 / 1.3760)


def test_basis_is_aeco_minus_henry_in_common_units():
    idx = pd.to_datetime(["2026-08-20"])
    df = D.assemble(
        aeco_cad=pd.Series([2.00], index=idx),
        hh=pd.Series([2.82], index=idx),
        fx=pd.Series([1.3760], index=idx),
    )
    exp = 2.00 * 1.055056 / 1.3760 - 2.82
    assert df["basis_usd_mmbtu"].iloc[0] == pytest.approx(exp)


def test_the_28_month_gap_is_labelled_and_never_interpolated():
    idx = pd.to_datetime(["2022-08-30", "2025-01-02"])
    df = D.assemble(
        aeco_cad=pd.Series([2.0, 1.5], index=idx),
        hh=pd.Series([8.0, 3.0], index=idx),
        fx=pd.Series([1.30, 1.43], index=idx),
    )
    assert df["block"].tolist() == ["A", "B"]
    assert df["basis_usd_mmbtu"].notna().all()
    assert len(df) == 2  # no rows manufactured across the hole


def test_missing_fx_yields_null_basis_rather_than_a_forward_filled_guess():
    idx = pd.to_datetime(["2026-08-20"])
    df = D.assemble(
        aeco_cad=pd.Series([2.00], index=idx),
        hh=pd.Series([2.82], index=idx),
        fx=pd.Series(dtype=float),
    )
    assert df["basis_usd_mmbtu"].isna().all()


def test_days_outside_both_blocks_get_no_block_label():
    idx = pd.to_datetime(["2023-06-01"])
    df = D.assemble(
        aeco_cad=pd.Series([2.0], index=idx),
        hh=pd.Series([3.0], index=idx),
        fx=pd.Series([1.35], index=idx),
    )
    assert df["block"].isna().all()
