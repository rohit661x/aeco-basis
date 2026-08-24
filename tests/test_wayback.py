import gzip
import json

from aeco.backfill import wayback as W

CDX = json.dumps(
    [["timestamp", "statuscode"],
     ["20161107165832", "200"],
     ["20170101000000", "301"],
     ["20170608120000", "200"]]
).encode()


def test_captures_filters_to_status_200_and_drops_the_header_row(monkeypatch):
    monkeypatch.setattr(W, "fetch", lambda url, **k: CDX)
    assert W.captures("http://x") == ["20161107165832", "20170608120000"]


def test_snapshot_url_uses_the_id_suffix(monkeypatch):
    # Without `id_`, Wayback injects a toolbar and rewrites URLs, which corrupts
    # the inline arrayToDataTable blocks we parse.
    seen = {}

    def spy(url, **k):
        seen["url"] = url
        return b"<html/>"

    monkeypatch.setattr(W, "fetch", spy)
    W.snapshot("http://example.com/p", "20161107165832")
    assert "/20161107165832id_/" in seen["url"]


def test_gzipped_archived_body_is_decompressed(monkeypatch):
    monkeypatch.setattr(W, "fetch", lambda url, **k: gzip.compress(b"<html>hi</html>"))
    assert b"hi" in W.snapshot("http://x", "20230216110811")


def test_harvest_skips_already_downloaded(tmp_path, monkeypatch):
    monkeypatch.setattr(W.config, "EXTERNAL", tmp_path)
    monkeypatch.setattr(W, "captures", lambda url, **k: ["20161107165832"])
    calls = []
    monkeypatch.setattr(W, "snapshot", lambda u, t: calls.append(t) or b"<html/>")
    monkeypatch.setattr(W.time, "sleep", lambda s: None)
    W.harvest("http://x", "ga")
    W.harvest("http://x", "ga")
    assert len(calls) == 1
