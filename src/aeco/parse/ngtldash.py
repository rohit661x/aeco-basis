"""NGTL restriction dashboard - the regime driver.

IT nomination acceptance below 100% at a gate is a direct constrained flag.
USJR is restricted on ~30% of days, which is why it is the primary driver;
Alliance utilization averages 97.7% and has almost no variation to threshold on.

Two verified traps in this source:
  * 105 excess duplicate-date rows (2,583 rows / 2,478 unique dates).
  * The BC gate column is misspelled 'Foorhills BC' in the source header.

Columns are matched by pattern ('<GATE> Current Gas Day IT**') rather than a
hardcoded list, so the misspelling is handled without special-casing.
"""

from __future__ import annotations

import io
import re

import pandas as pd

_IT = re.compile(r"^(?P<gate>.+?)\s+Current Gas Day IT\**$")
_GATE_SLUG = {
    "egat": "egat", "wgat": "wgat", "osda": "osda", "usjr": "usjr",
    "foorhills bc": "fh_bc", "foothills bc": "fh_bc",
    "foothills sk": "fh_sk", "foorhills sk": "fh_sk",
}


def _slug(gate: str) -> str:
    g = gate.strip().lower()
    return _GATE_SLUG.get(g, re.sub(r"[^a-z0-9]+", "_", g))


def parse(raw: bytes, *, strict: bool = False) -> pd.DataFrame:
    """Return a date-indexed frame of IT acceptance percentages per gate.

    Duplicate dates are resolved to the LAST row (append order is revision
    order). Dates whose duplicate rows disagree on an IT value are recorded in
    ``df.attrs['conflicting_it_dates']`` so the count can be reported rather
    than silently absorbed. ``strict=True`` raises on any such conflict.
    """
    df = pd.read_csv(io.BytesIO(raw))  # pandas strips the UTF-8 BOM
    df.columns = [c.strip() for c in df.columns]
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], format="mixed")

    rename = {}
    for c in df.columns:
        m = _IT.match(c)
        if m:
            rename[c] = f"{_slug(m.group('gate'))}_it"
    if not rename:
        raise ValueError("no 'Current Gas Day IT' columns found in ngtldash.csv")

    keep = [date_col] + list(rename)
    out = df[keep].rename(columns={**rename, date_col: "date"})

    dup = out[out["date"].duplicated(keep=False)]
    conflicting: list[pd.Timestamp] = []
    if not dup.empty:
        n = dup.groupby("date").nunique()
        conflicting = list(n[(n > 1).any(axis=1)].index)
        if conflicting and strict:
            raise ValueError(
                f"conflicting duplicate dates in ngtldash.csv: {len(conflicting)} date(s)"
            )
    out = out.drop_duplicates("date", keep="last").set_index("date").sort_index()
    out.attrs["conflicting_it_dates"] = conflicting
    return out


def restricted(df: pd.DataFrame) -> pd.DataFrame:
    it = df[[c for c in df.columns if c.endswith("_it")]]
    return (it < 100).rename(columns=lambda c: c[: -len("_it")])
