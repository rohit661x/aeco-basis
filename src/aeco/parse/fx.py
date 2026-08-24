"""CAD/USD from the Bank of Canada Valet API (keyless).

FXUSDCAD is CAD per USD, so USD = CAD / FXUSDCAD.
"""

from __future__ import annotations

import io

import pandas as pd

from aeco.fetch import fetch

URL = "https://www.bankofcanada.ca/valet/observations/FXUSDCAD/csv"


def load() -> pd.Series:
    raw = fetch(URL, timeout=60).decode("utf-8", errors="replace")
    body = raw.split("OBSERVATIONS", 1)[-1].lstrip('"\r\n')
    df = pd.read_csv(io.StringIO(body))
    df.columns = [c.strip().strip('"').lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date")["fxusdcad"].astype(float).sort_index().rename("fx_usdcad")
    return s[~s.index.duplicated(keep="last")]
