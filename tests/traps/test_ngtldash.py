import pandas as pd
import pytest

from aeco.parse import ngtldash as N

# Real header shape, including the source's 'Foorhills' misspelling.
CSV = (
    b"Date,USJR Current Gas Day IT**,EGAT Current Gas Day IT**,"
    b"Foorhills BC Current Gas Day IT**\n"
    b"2026-08-20,100,100,100\n"
    b"2026-08-21,45,100,100\n"
    b"2026-08-21,45,100,100\n"  # 105 such excess rows exist in the live file
)

CONFLICT = (
    b"Date,USJR Current Gas Day IT**\n"
    b"2026-08-21,45\n"
    b"2026-08-21,99\n"
)


def test_duplicate_dates_are_collapsed():
    df = N.parse(CSV)
    assert df.index.is_unique
    assert len(df) == 2


def test_misspelled_foothills_bc_column_is_mapped():
    assert "fh_bc_it" in N.parse(CSV).columns


def test_non_it_columns_are_dropped():
    assert set(N.parse(CSV).columns) == {"usjr_it", "egat_it", "fh_bc_it"}


def test_restricted_flag_is_it_below_one_hundred():
    df = N.parse(CSV)
    assert df.loc[pd.Timestamp("2026-08-21"), "usjr_it"] == 45
    assert N.restricted(df)["usjr"].tolist() == [False, True]


def test_conflicting_duplicates_resolve_to_last_and_are_reported():
    df = N.parse(CONFLICT)
    assert df.loc[pd.Timestamp("2026-08-21"), "usjr_it"] == 99
    assert df.attrs["conflicting_it_dates"] == [pd.Timestamp("2026-08-21")]


def test_strict_mode_raises_on_conflicting_duplicates():
    with pytest.raises(ValueError, match="conflicting"):
        N.parse(CONFLICT, strict=True)


def test_missing_it_columns_raise():
    with pytest.raises(ValueError, match="no 'Current Gas Day IT'"):
        N.parse(b"Date,Something Else\n2026-08-21,1\n")
