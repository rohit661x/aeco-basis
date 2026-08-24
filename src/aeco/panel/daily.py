"""Daily AECO-Henry basis panel.

Coverage is two disjoint blocks separated by a 28-month hole with no free data.
The hole is labelled, never interpolated, and results are reported per block.
"""

from __future__ import annotations

import gzip

import pandas as pd

from aeco import config
from aeco.panel import units
from aeco.parse import fx as fxmod
from aeco.parse import dobenergy, gasalberta, henryhub, ngtldash

GJ_PER_MMBTU = 1.055056
BLOCKS = {"A": ("2020-06-24", "2022-08-30"), "B": ("2025-01-01", None)}


def to_usd_mmbtu(cad_per_gj: float, fx_usdcad: float) -> float:
    return cad_per_gj * GJ_PER_MMBTU / fx_usdcad


def _block(ts: pd.Timestamp):
    for name, (lo, hi) in BLOCKS.items():
        if pd.Timestamp(lo) <= ts and (hi is None or ts <= pd.Timestamp(hi)):
            return name
    return None


def assemble(aeco_usd_mmbtu: pd.Series, hh: pd.Series, fx: pd.Series) -> pd.DataFrame:
    """Assemble the basis panel from AECO already normalised to USD/MMBtu.

    AECO must arrive in USD/MMBtu because sources differ in denomination
    (Gas Alberta CAD/GJ, dobenergy USD/GJ); conversion belongs at the source,
    not here.
    """
    df = pd.DataFrame({"aeco_usd_mmbtu": aeco_usd_mmbtu}).sort_index()
    # as-of joins: never import a future-dated value
    df["hh_usd_mmbtu"] = (
        hh.reindex(df.index, method="ffill") if len(hh) else pd.Series(pd.NA, index=df.index)
    )
    df["fx_usdcad"] = (
        fx.reindex(df.index, method="ffill") if len(fx) else pd.Series(pd.NA, index=df.index)
    )
    df["basis_usd_mmbtu"] = df["aeco_usd_mmbtu"] - df["hh_usd_mmbtu"]
    df["block"] = pd.Series([_block(t) for t in df.index], index=df.index, dtype="object")
    return df


def _aeco_from_wayback() -> pd.Series:
    d = config.EXTERNAL / "wayback" / "gasalberta_market_prices"
    if not d.exists():
        return pd.Series(dtype=float)
    frames = [
        gasalberta.parse_inline_daily(gzip.decompress(f.read_bytes()))
        for f in sorted(d.glob("*.html.gz"))
    ]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.Series(dtype=float)
    all_ = (
        pd.concat(frames).drop_duplicates("date").set_index("date").sort_index()
    )
    return all_["daily_cad_gj"]


def _aeco_from_dobenergy() -> pd.Series:
    files = sorted((config.RAW / "dobenergy").rglob("prices.html.gz"))
    if not files:
        return pd.Series(dtype=float)
    return dobenergy.parse(gzip.decompress(files[-1].read_bytes()))


def _aeco_all(fx: pd.Series) -> pd.Series:
    """Block A from Wayback captures (CAD/GJ), block B from dobenergy (USD/GJ).

    Each is converted to USD/MMBtu by its OWN rule before concatenation. The two
    blocks are disjoint in time, so concatenation cannot splice across the
    28-month hole. Overlaps (none expected) resolve to the Wayback value.
    """
    a_raw, b_raw = _aeco_from_wayback(), _aeco_from_dobenergy()
    a = units.cad_gj_to_usd_mmbtu(a_raw, fx) if not a_raw.empty else a_raw
    b = units.usd_gj_to_usd_mmbtu(b_raw) if not b_raw.empty else b_raw
    if a.empty:
        return b
    if b.empty:
        return a
    return pd.concat([a, b[~b.index.isin(a.index)]]).sort_index()


def build() -> pd.DataFrame:
    fx = fxmod.load()
    df = assemble(_aeco_all(fx), henryhub.load(), fx)
    latest = sorted((config.RAW / "ngtldash").rglob("ngtldash.csv.gz"))
    if latest:
        nd = ngtldash.parse(gzip.decompress(latest[-1].read_bytes()))
        df = df.join(nd[["usjr_it"]], how="left")
        df["restricted"] = df["usjr_it"] < 100
    out = config.DERIVED / "daily_panel.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    return df
