import gzip, json, pytest, httpx
from aeco import fetch as F


def test_fetch_returns_body(monkeypatch):
    monkeypatch.setattr(F, "_get", lambda u, t, h: httpx.Response(200, content=b"hello"))
    assert F.fetch("http://x") == b"hello"


def test_fetch_raises_on_404_regardless_of_body_size(monkeypatch):
    # TC returns a 16,835-byte HTML error page on 404. Size must never imply success.
    big = b"<html>" + b"x" * 16_829
    monkeypatch.setattr(F, "_get", lambda u, t, h: httpx.Response(404, content=big))
    with pytest.raises(F.FetchError, match="404"):
        F.fetch("http://x", retries=1)


def test_fetch_validator_catches_soft_404(monkeypatch):
    # CER returns HTTP 200 with a "File not found" body.
    monkeypatch.setattr(F, "_get", lambda u, t, h: httpx.Response(200, content=b"File not found"))
    with pytest.raises(F.FetchError, match="validator"):
        F.fetch("http://x", validator=lambda b: b"File not found" not in b, retries=1)


def test_capture_writes_gzipped_body_and_meta(tmp_path, monkeypatch):
    monkeypatch.setattr(F.config, "RAW", tmp_path)
    monkeypatch.setattr(F, "_get", lambda u, t, h: httpx.Response(200, content=b"payload"))
    p = F.capture("http://x", source="demo", artifact="a.json", day="2026-08-23")
    assert gzip.decompress(p.read_bytes()) == b"payload"
    meta = json.loads(p.with_suffix(".meta.json").read_text())
    assert meta["status"] == 200 and meta["bytes"] == 7
    assert meta["sha256"] and meta["fetched_utc"].endswith("Z")
