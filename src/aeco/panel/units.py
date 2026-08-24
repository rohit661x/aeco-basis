"""Unit conversions.

Sources differ in denomination and the difference is invisible in the numbers:
Gas Alberta quotes CAD/GJ, dobenergy quotes USD/GJ. Treating one as the other
is a ~28% level error that still looks like a plausible gas price, so every
AECO source must declare its native unit and convert through here.
"""

from __future__ import annotations

import pandas as pd

GJ_PER_MMBTU = 1.055056


def cad_gj_to_usd_mmbtu(s: pd.Series, fx_usdcad: pd.Series) -> pd.Series:
    """CAD/GJ -> USD/MMBtu. fx_usdcad is CAD per USD, so divide."""
    fx = fx_usdcad.reindex(s.index, method="ffill")
    return (s * GJ_PER_MMBTU / fx).rename("aeco_usd_mmbtu")


def usd_gj_to_usd_mmbtu(s: pd.Series) -> pd.Series:
    """USD/GJ -> USD/MMBtu. No FX involved; applying one is the classic bug."""
    return (s * GJ_PER_MMBTU).rename("aeco_usd_mmbtu")
