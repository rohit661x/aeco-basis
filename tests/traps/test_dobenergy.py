import pandas as pd
import pytest

from aeco.parse import dobenergy as DB

HTML = (
    b'{"name": "AECO/NGX Spot Price - Same Day Volume", "data": [[1735801200000, 999]]}, '
    b'{"name": "AECO/NGX Spot Price", "data": [[1735801200000, 1.23], [1735887600000, 1.25]]}'
)


def test_exact_name_match_does_not_pick_up_the_volume_series():
    # 'AECO/NGX Spot Price' is a prefix of 'AECO/NGX Spot Price - Same Day Volume'.
    s = DB.parse(HTML)
    assert 999 not in s.values
    assert s.tolist() == [1.23, 1.25]


def test_epoch_ms_converts_to_the_mountain_gas_day():
    # 1735801200000 ms = 2025-01-02 07:00 UTC = 2025-01-02 00:00 MST
    s = DB.parse(HTML)
    assert s.index[0] == pd.Timestamp("2025-01-02")


def test_missing_series_raises_rather_than_returning_empty():
    with pytest.raises(ValueError, match="AECO/NGX Spot Price"):
        DB.parse(b"<html>nothing here</html>")
