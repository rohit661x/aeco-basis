"""Henry Hub daily spot from EIA's keyless dnav XLS mirror.

FRED is deliberately not used: fredgraph.csv was unreachable from the build
network. This mirror needs no API key.
"""

from __future__ import annotations

import io

import pandas as pd

from aeco.fetch import fetch

URL = "https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDd.xls"


def load() -> pd.Series:
    raw = fetch(URL, timeout=120)
    df = pd.read_excel(io.BytesIO(raw), sheet_name="Data 1", skiprows=2)
    df.columns = ["date", "hh"]
    df["date"] = pd.to_datetime(df["date"])
    return (
        df.dropna().set_index("date")["hh"].astype(float).sort_index().rename("hh_usd_mmbtu")
    )
