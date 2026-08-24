import pandas as pd

from aeco.parse import fx as X

FXCSV = (
    b'"OBSERVATIONS"\n"date","FXUSDCAD"\n'
    b'"2026-08-19","1.3824"\n"2026-08-20","1.3785"\n"2026-08-21","1.3760"\n'
)


def test_fx_parses_bank_of_canada_valet_csv(monkeypatch):
    monkeypatch.setattr(X, "fetch", lambda url, **k: FXCSV)
    s = X.load()
    assert s.name == "fx_usdcad"
    assert s.loc[pd.Timestamp("2026-08-21")] == 1.3760
    assert s.index.is_monotonic_increasing


def test_fx_is_cad_per_usd_orientation(monkeypatch):
    # A CAD/GJ price divided by this must give USD. Values near 1.3-1.4 confirm
    # the orientation; an inverted series would sit near 0.7.
    monkeypatch.setattr(X, "fetch", lambda url, **k: FXCSV)
    assert X.load().between(1.0, 2.0).all()
