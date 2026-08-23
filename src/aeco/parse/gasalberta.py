"""Gas Alberta parsers.

Three incompatible page eras exist. This module covers the 2016-2022 inline
Google-Charts era and the current AJAX JSON era.

Column order is a trap in both: the site's own JS remaps columns before display,
so series are identified behaviourally, never by header position.
"""

from __future__ import annotations

import json
import re

import pandas as pd

_DAILY_ROW = re.compile(r"\['(\d{1,2}-[A-Z][a-z]{2}-\d{2})'\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\]")
_CURVE_ROW = re.compile(
    r"\['([A-Z][a-z]{2}-\d{2})'\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\]"
)


def parse_inline_daily(html: bytes) -> pd.DataFrame:
    text = html.decode("utf-8", errors="replace")
    rows = [(d, float(a), float(b)) for d, a, b in _DAILY_ROW.findall(text)]
    if not rows:
        return pd.DataFrame(columns=["date", "daily_cad_gj", "monthly_cad_gj"])
    df = pd.DataFrame(rows, columns=["date", "col1", "col2"])
    df["date"] = pd.to_datetime(df["date"], format="%d-%b-%y")
    # The monthly index is constant within a calendar month; the daily one moves.
    by_month = df.groupby(df["date"].dt.to_period("M"))
    flat1 = by_month["col1"].nunique().max() == 1
    monthly, daily = ("col1", "col2") if flat1 else ("col2", "col1")
    return (
        df.rename(columns={monthly: "monthly_cad_gj", daily: "daily_cad_gj"})[
            ["date", "daily_cad_gj", "monthly_cad_gj"]
        ]
        .drop_duplicates("date")
        .sort_values("date")
        .reset_index(drop=True)
    )


def parse_inline_curve(html: bytes, min_points: int = 24) -> list[tuple[str, float]]:
    text = html.decode("utf-8", errors="replace")
    # Raw row order is (month, oneYearAgo, oneMonthAgo, current): last numeric is live.
    curve = [(m, float(cur)) for m, _yr, _mo, cur in _CURVE_ROW.findall(text)]
    if len(curve) < min_points:
        raise ValueError(f"curve too short: {len(curve)} points (< {min_points})")
    return curve


def parse_live_curve(raw: bytes, min_points: int = 1) -> list[tuple[str, float]]:
    doc = json.loads(raw)
    rows = doc.get("data", doc) if isinstance(doc, dict) else doc
    curve = [(r[0], float(r[3])) for r in rows if isinstance(r, list) and len(r) >= 4]
    if len(curve) < min_points:
        raise ValueError(f"curve too short: {len(curve)} points (< {min_points})")
    return curve
