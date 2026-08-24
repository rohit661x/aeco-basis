import pandas as pd
import pytest

from aeco.panel import daily as D


def test_basis_is_aeco_minus_henry_in_common_units():
    idx = pd.to_datetime(["2026-08-20"])
    df = D.assemble(
        aeco_usd_mmbtu=pd.Series([1.079], index=idx),
        hh=pd.Series([2.82], index=idx),
        fx=pd.Series([1.3760], index=idx),
    )
    assert df["basis_usd_mmbtu"].iloc[0] == pytest.approx(1.079 - 2.82)


def test_assemble_does_not_apply_fx_to_an_already_converted_series():
    # AECO arrives in USD/MMBtu. Applying FX here would double-convert the
    # dobenergy block, understating it by ~28% while still looking plausible.
    idx = pd.to_datetime(["2026-08-20"])
    df = D.assemble(
        aeco_usd_mmbtu=pd.Series([1.079], index=idx),
        hh=pd.Series([0.0], index=idx),
        fx=pd.Series([1.3760], index=idx),
    )
    assert df["basis_usd_mmbtu"].iloc[0] == pytest.approx(1.079)


def test_the_28_month_gap_is_labelled_and_never_interpolated():
    idx = pd.to_datetime(["2022-08-30", "2025-01-02"])
    df = D.assemble(
        aeco_usd_mmbtu=pd.Series([1.6, 1.1], index=idx),
        hh=pd.Series([8.0, 3.0], index=idx),
        fx=pd.Series([1.30, 1.43], index=idx),
    )
    assert df["block"].tolist() == ["A", "B"]
    assert df["basis_usd_mmbtu"].notna().all()
    assert len(df) == 2  # no rows manufactured across the hole


def test_days_outside_both_blocks_get_no_block_label():
    idx = pd.to_datetime(["2023-06-01"])
    df = D.assemble(
        aeco_usd_mmbtu=pd.Series([1.5], index=idx),
        hh=pd.Series([3.0], index=idx),
        fx=pd.Series([1.35], index=idx),
    )
    assert df["block"].isna().all()


def test_missing_henry_hub_yields_null_basis():
    idx = pd.to_datetime(["2026-08-20"])
    df = D.assemble(
        aeco_usd_mmbtu=pd.Series([1.079], index=idx),
        hh=pd.Series(dtype=float),
        fx=pd.Series([1.376], index=idx),
    )
    assert df["basis_usd_mmbtu"].isna().all()
