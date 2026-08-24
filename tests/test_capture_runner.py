import httpx
from aeco import fetch as F
from aeco.capture import runner, sources


def test_run_all_reports_per_source_status(tmp_path, monkeypatch):
    monkeypatch.setattr(F.config, "RAW", tmp_path)
    monkeypatch.setattr(F, "_get", lambda u, t, h: httpx.Response(200, content=b"{}"))
    srcs = [
        sources.CaptureSource("a", "http://a", "a.json"),
        sources.CaptureSource("b", "http://b", "b.json"),
    ]
    assert runner.run_all(srcs, day="2026-08-23") == {"a": "ok", "b": "ok"}


def test_one_failure_does_not_abort_the_others_but_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(F.config, "RAW", tmp_path)

    def flaky(u, t, h):
        return httpx.Response(500 if "bad" in u else 200, content=b"{}")

    monkeypatch.setattr(F, "_get", flaky)
    srcs = [
        sources.CaptureSource("bad", "http://bad", "x.json"),
        sources.CaptureSource("good", "http://good", "y.json"),
    ]
    res = runner.run_all(srcs, day="2026-08-23")
    assert res["good"] == "ok"
    assert res["bad"].startswith("FAILED")


def test_registry_covers_the_perishable_sources():
    names = {s.name for s in sources.SOURCES}
    assert {
        "gasalberta_futures",
        "gasalberta_index_current",
        "ngtldash",
        "dop_publisheddates",
        "gdsr",
        "dobenergy",
    } <= names
