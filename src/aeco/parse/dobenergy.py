"""Daily AECO spot from dobenergy.com (block B, 2025-01 onward).

The page embeds Highcharts series as JSON. Timestamps are epoch-ms at Mountain
midnight, so they are converted through America/Edmonton to land on the correct
gas day.

UNITS: this series is denominated in **USD/GJ**, not CAD/GJ. Verified against
overlapping Gas Alberta quotes (mean |error| 0.021 as USD/GJ vs 0.394 as CAD/GJ;
mean ratio 0.7210 against 1/FX = 0.7181). Treating it as CAD and applying FX
understates AECO by ~28% while still producing a plausible-looking gas price.

Provenance caveat: this is an unlicensed redistribution attributed to
'LSEG, One Exchange, & ICE' with no index-code label, and the window is very
likely rolling. Treat as a private research input, not a redistributable series.
"""

from __future__ import annotations

import json
import re

import pandas as pd

SERIES = "AECO/NGX Spot Price"
# Exact-name match: SERIES is a prefix of 'AECO/NGX Spot Price - Same Day Volume'.
_BLOCK = re.compile(
    r'"name"\s*:\s*"' + re.escape(SERIES) + r'"\s*,\s*"data"\s*:\s*(\[\[.*?\]\])',
    re.DOTALL,
)


def parse(html: bytes) -> pd.Series:
    text = html.decode("utf-8", errors="replace")
    m = _BLOCK.search(text)
    if not m:
        raise ValueError(f"series {SERIES!r} not found in dobenergy page")
    pairs = json.loads(m.group(1))
    idx = (
        pd.to_datetime([p[0] for p in pairs], unit="ms", utc=True)
        .tz_convert("America/Edmonton")
        .tz_localize(None)
        .normalize()
    )
    s = pd.Series([float(p[1]) for p in pairs], index=idx, name="aeco_usd_gj").sort_index()
    return s[~s.index.duplicated(keep="last")]


def parse_all(bodies) -> pd.Series:
    """Concatenate every capture rather than trusting only the newest.

    The embedded window is very likely rolling, so a day that has scrolled
    off the front of today's capture may still be on disk in an older one.
    Later captures win on overlap (a revision), earlier ones keep days that
    have since fallen out of the live window.
    """
    frames = [parse(b) for b in bodies]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.Series(dtype=float, name="aeco_usd_gj")
    s = pd.concat(frames).sort_index()
    return s[~s.index.duplicated(keep="last")]
