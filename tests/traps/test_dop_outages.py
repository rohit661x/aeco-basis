import json

import pandas as pd
import pytest

from aeco.parse import dop_outages as P


def _rec(**kw):
    base = dict(
        outageId=20216786,
        publishedDateTimeUtc="2026-08-21 21:31:35",
        startDateTime="2026-10-01 00:00:00",
        endDateTime="2026-10-02 00:00:00",
        areaBaseCapability=385000.0,
        flowCapability=368000,
        description=" Meikle River C - Compressor Station Maintenance",
        impact=" Potential impact to FT-R; USJR ",
        area={"acronym": "USJR"},
    )
    base.update(kw)
    return base


def _env(recs):
    return json.dumps({"message": "Success", "data": recs}).encode()


def test_reduction_is_base_minus_flow_and_converts_to_bcfd():
    r = P.parse_snapshot(_env([_rec()]), "2026-08-21 21:31:35")[0]
    assert r["reduction_e3m3d"] == pytest.approx(17000.0)
    assert r["reduction_bcfd"] == pytest.approx(17000 * 35.3147 / 1e6, rel=1e-6)


def test_na_base_capability_yields_null_reduction_not_a_crash():
    r = P.parse_snapshot(_env([_rec(areaBaseCapability="N/A")]), "2026-08-21 21:31:35")[0]
    assert r["reduction_e3m3d"] is None


def test_plant_turnaround_rows_with_negative_ids_are_retained():
    recs = [_rec(outageId=-1788588011, area={"acronym": "RPTA"}), _rec()]
    out = P.parse_snapshot(_env(recs), "2026-08-21 21:31:35")
    assert {r["area"] for r in out} == {"RPTA", "USJR"}


def test_description_and_impact_are_stripped():
    r = P.parse_snapshot(_env([_rec()]), "2026-08-21 21:31:35")[0]
    assert r["description"].startswith("Meikle") and not r["impact"].endswith(" ")


def test_bare_array_without_envelope_is_rejected():
    with pytest.raises(ValueError, match="envelope"):
        P.parse_snapshot(json.dumps([_rec()]).encode(), "2026-08-21 21:31:35")


def test_build_events_takes_earliest_appearance_as_announcement(tmp_path):
    import gzip

    d = tmp_path / "dop"
    d.mkdir()
    (d / "2026-08-20T213145.json.gz").write_bytes(gzip.compress(_env([_rec()])))
    (d / "2026-08-21T213135.json.gz").write_bytes(gzip.compress(_env([_rec()])))
    ev = P.build_events(d)
    assert len(ev) == 1
    assert ev.iloc[0]["announced_utc"] == pd.Timestamp("2026-08-20 21:31:45")


def test_multi_area_outage_is_not_collapsed_by_first():
    # groupby('outage_id').first() splices columns from DIFFERENT area records
    # into one row via per-column NaN skipping. Real archive: one outageId
    # carrying 5 area records collapsed to a single row whose area/capability
    # came from different source records than its reduction size.
    recs = [
        _rec(outageId=1, area={"acronym": "USJR"}, areaBaseCapability=380000.0, flowCapability=366000),
        _rec(outageId=1, area={"acronym": "WGAT"}, areaBaseCapability=88000.0, flowCapability=87000),
        _rec(outageId=1, area={"acronym": "EGAT"}, areaBaseCapability=158000.0, flowCapability=148000),
    ]
    import gzip
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "2026-08-05T213758.json.gz").write_bytes(gzip.compress(_env(recs)))
        ev = P.build_events(d)
        assert len(ev) == 3
        assert set(ev["area"]) == {"USJR", "WGAT", "EGAT"}
        usjr = ev[ev["area"] == "USJR"].iloc[0]
        assert usjr["reduction_e3m3d"] == pytest.approx(14000.0)


def test_every_emitted_row_satisfies_base_minus_flow_equals_reduction():
    recs = [
        _rec(outageId=1, area={"acronym": "USJR"}, areaBaseCapability=380000.0, flowCapability=366000),
        _rec(outageId=2, area={"acronym": "WGAT"}, areaBaseCapability=88000.0, flowCapability=87000),
    ]
    import gzip
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "2026-08-05T213758.json.gz").write_bytes(gzip.compress(_env(recs)))
        ev = P.build_events(d)
        ok = (ev["base_capability"] - ev["flow_capability"] == ev["reduction_e3m3d"])
        assert ok.all()
