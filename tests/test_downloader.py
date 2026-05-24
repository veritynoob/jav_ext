import os
import sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.downloader import download_cover


def test_download_cover_returns_path(tmp_path, requests_mock):
    code = "ABC-001"
    url = "http://example.com/cover.jpg"
    requests_mock.get(url, content=b"fake-image-data")

    result = download_cover(code, url, str(tmp_path))
    assert result is not None
    assert result.endswith("ABC-001.jpg")


def test_download_cover_saves_file(tmp_path, requests_mock):
    code = "ABC-001"
    url = "http://example.com/cover.jpg"
    requests_mock.get(url, content=b"fake-image-data")

    result = download_cover(code, url, str(tmp_path))
    assert os.path.exists(result)
    with open(result, "rb") as f:
        assert f.read() == b"fake-image-data"


def test_download_cover_returns_none_on_failure(tmp_path):
    code = "ABC-001"
    url = "http://invalid-url-that-does-not-exist.xyz/cover.jpg"
    result = download_cover(code, url, str(tmp_path))
    assert result is None


def test_download_cover_empty_url(tmp_path):
    result = download_cover("ABC-001", "", str(tmp_path))
    assert result is None
