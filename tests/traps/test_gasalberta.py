import json

import pytest

from aeco.parse import gasalberta as G

INLINE_DAILY = b"""
<script>var d = google.visualization.arrayToDataTable([
 ['Date', 'Monthly Index', 'Daily Index'],
 ['1-Oct-16', 2.47, 2.63],
 ['2-Oct-16', 2.47, 2.55],
 ['3-Oct-16', 2.47, 2.71]]);</script>"""

INLINE_CURVE = b"""
<script>var c = google.visualization.arrayToDataTable([
 ['Month', 'One Year Ago','One Month Ago','Current'],
 ['Dec-16',2.83,2.74,2.42],
 ['Jan-17',2.90,2.80,2.55]]);</script>"""


def test_daily_series_identified_behaviourally_not_by_header_order():
    # The site's own JS swaps columns before charting, so header order is a trap.
    # The column that is FLAT within a calendar month is the monthly index.
    df = G.parse_inline_daily(INLINE_DAILY)
    assert df["monthly_cad_gj"].nunique() == 1
    assert df["daily_cad_gj"].tolist() == [2.63, 2.55, 2.71]


def test_curve_takes_the_last_numeric_as_current():
    assert G.parse_inline_curve(INLINE_CURVE, min_points=2)[0] == ("Dec-16", 2.42)


def test_prompt_month_comes_from_the_label_never_the_timestamp():
    # A 2017-06-08 capture starts at Jun-17, the CURRENT month, not the next one.
    assert G.parse_inline_curve(INLINE_CURVE, min_points=2)[0][0] == "Dec-16"


def test_short_curves_are_rejected():
    with pytest.raises(ValueError, match="too short"):
        G.parse_inline_curve(INLINE_CURVE, min_points=24)


def test_live_json_maps_index_three_to_current():
    raw = json.dumps([["Sep-26", 2.64, 1.46, 1.23]]).encode()
    assert G.parse_live_curve(raw)[0] == ("Sep-26", 1.23)


def test_empty_html_yields_empty_frame_not_a_crash():
    assert G.parse_inline_daily(b"<html/>").empty
