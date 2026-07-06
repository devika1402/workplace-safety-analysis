"""Unit tests for ingestion.download."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from config.settings import Settings
from ingestion import download


class _FakeResponse:
    """Minimal stand-in for a streaming requests.Response."""

    def __init__(self, chunks: list[bytes], status_ok: bool = True) -> None:
        self._chunks = chunks
        self._status_ok = status_ok

    def raise_for_status(self) -> None:
        if not self._status_ok:
            raise requests.HTTPError("simulated HTTP error")

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return self._chunks


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        raw_data_dir=tmp_path,
        osha_data_url="https://example.test/case_detail.zip",
        osha_case_detail_filename="case_detail.zip",
    )


def test_fetch_downloads_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def fake_get(url: str, stream: bool, timeout: float) -> _FakeResponse:
        assert url == settings.osha_data_url
        assert stream is True
        return _FakeResponse([b"hello ", b"world"])

    monkeypatch.setattr(download.requests, "get", fake_get)

    result = download.fetch(settings)

    assert result == settings.case_detail_download_path
    assert result.read_bytes() == b"hello world"


def test_fetch_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.case_detail_download_path.write_bytes(b"already here")

    def fail_get(*args: object, **kwargs: object) -> _FakeResponse:
        raise AssertionError("network must not be called when the file exists")

    monkeypatch.setattr(download.requests, "get", fail_get)

    result = download.fetch(settings)

    assert result.read_bytes() == b"already here"


def test_fetch_force_redownloads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.case_detail_download_path.write_bytes(b"stale")

    def fake_get(url: str, stream: bool, timeout: float) -> _FakeResponse:
        return _FakeResponse([b"fresh"])

    monkeypatch.setattr(download.requests, "get", fake_get)

    result = download.fetch(settings, force=True)

    assert result.read_bytes() == b"fresh"


def test_fetch_raises_on_http_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def fake_get(url: str, stream: bool, timeout: float) -> _FakeResponse:
        return _FakeResponse([], status_ok=False)

    monkeypatch.setattr(download.requests, "get", fake_get)

    with pytest.raises(requests.HTTPError):
        download.fetch(settings)


def test_fetch_raises_on_empty_download(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def fake_get(url: str, stream: bool, timeout: float) -> _FakeResponse:
        return _FakeResponse([])

    monkeypatch.setattr(download.requests, "get", fake_get)

    with pytest.raises(RuntimeError):
        download.fetch(settings)


def test_fetch_requires_url_or_local_file(tmp_path: Path) -> None:
    settings = Settings(
        raw_data_dir=tmp_path,
        osha_data_url="",
        osha_case_detail_filename="case_detail.zip",
    )
    with pytest.raises(RuntimeError):
        download.fetch(settings)
