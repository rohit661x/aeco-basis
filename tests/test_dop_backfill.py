import json

import pytest

from aeco import fetch as F
from aeco.backfill import dop

ENVELOPE = json.dumps({"message": "Success", "data": ["2026-08-21 21:31:35"]}).encode()


def test_published_dates_unwraps_the_envelope(monkeypatch):
    monkeypatch.setattr(dop, "fetch", lambda url, **k: ENVELOPE)
    assert dop.published_dates() == ["2026-08-21 21:31:35"]


def test_snapshot_path_is_filesystem_safe(tmp_path, monkeypatch):
    monkeypatch.setattr(dop.config, "EXTERNAL", tmp_path)
    p = dop.snapshot_path("2026-08-21 21:31:35")
    assert " " not in p.name and ":" not in p.name
    assert p.name.endswith(".json.gz")


def test_harvest_is_idempotent_and_skips_existing(tmp_path, monkeypatch):
    monkeypatch.setattr(dop.config, "EXTERNAL", tmp_path)
    calls = []

    def spy(url, **k):
        calls.append(url)
        return json.dumps({"message": "Success", "data": [{"outageId": 1}]}).encode()

    monkeypatch.setattr(dop, "fetch", spy)
    dop.harvest(["2026-08-21 21:31:35"], concurrency=1)
    assert len(calls) == 1
    dop.harvest(["2026-08-21 21:31:35"], concurrency=1)
    assert len(calls) == 1


def test_harvest_records_failure_without_writing_a_file(tmp_path, monkeypatch):
    monkeypatch.setattr(dop.config, "EXTERNAL", tmp_path)

    def boom(url, **k):
        raise F.FetchError("504 timeout")

    monkeypatch.setattr(dop, "fetch", boom)
    res = dop.harvest(["2019-10-07 13:18:28"], concurrency=1)
    assert res["2019-10-07 13:18:28"].startswith("FAILED")
    assert not dop.snapshot_path("2019-10-07 13:18:28").exists()


def test_concurrency_is_capped_at_three():
    with pytest.raises(ValueError, match="concurrency"):
        dop.harvest([], concurrency=8)
