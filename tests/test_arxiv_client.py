import gzip
import io
import tarfile
import zipfile
from unittest.mock import patch
from urllib.error import HTTPError

import pytest
import requests

from arxiv_daily.arxiv_client import (
    BROWSER_REQUEST_HEADERS,
    BROWSER_USER_AGENT,
    download_paper_source_or_pdf,
    extract_source_data,
    fetch_url,
    strip_version,
)


def test_fetch_url_uses_browser_like_headers(monkeypatch):
    captured = {}

    class FakeResponse:
        content = b"ok"

        def raise_for_status(self):
            return None

    def fake_get(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("arxiv_daily.arxiv_client.requests.get", fake_get)

    assert fetch_url("https://arxiv.org", timeout_seconds=12) == b"ok"

    headers = {key.lower(): value for key, value in captured["headers"].items()}
    assert headers["user-agent"] == BROWSER_USER_AGENT
    for key, value in BROWSER_REQUEST_HEADERS.items():
        assert headers[key.lower()] == value
    assert captured["url"] == "https://arxiv.org"
    assert captured["timeout"] == 12


def test_fetch_url_keeps_the_http_status_code(monkeypatch):
    class FakeResponse:
        status_code = 400

        def raise_for_status(self):
            raise requests.HTTPError("400 Client Error: Bad Request", response=self)

    monkeypatch.setattr(
        "arxiv_daily.arxiv_client.requests.get", lambda url, headers, timeout: FakeResponse()
    )

    with pytest.raises(HTTPError) as excinfo:
        fetch_url("https://arxiv.org/catchup/quant-ph/2025-01-15", timeout_seconds=5)
    assert excinfo.value.code == 400


def test_strip_version():
    assert strip_version("2610.11111v3") == "2610.11111"
    assert strip_version("2610.11111") == "2610.11111"


def test_extract_source_data_tar_gz(tmp_path):
    # Create an in-memory gzipped tar file
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w:gz") as tar:
        # Add a simple text file
        content = b"hello world"
        tarinfo = tarfile.TarInfo(name="test.tex")
        tarinfo.size = len(content)
        tar.addfile(tarinfo, io.BytesIO(content))

    tar_bytes = tar_stream.getvalue()
    extract_source_data(tar_bytes, "2605.12345", tmp_path)

    extracted_file = tmp_path / "test.tex"
    assert extracted_file.exists()
    assert extracted_file.read_bytes() == b"hello world"


def test_extract_source_data_gz_single_file(tmp_path):
    # Create in-memory gzipped single file
    content = b"\\documentclass{article}\n\\begin{document}\nhello\n\\end{document}"
    gz_bytes = gzip.compress(content)

    extract_source_data(gz_bytes, "2605.12345", tmp_path)

    extracted_file = tmp_path / "2605.12345.tex"
    assert extracted_file.exists()
    assert extracted_file.read_bytes() == content


def test_extract_source_data_zip(tmp_path):
    # Create in-memory zip file
    zip_stream = io.BytesIO()
    with zipfile.ZipFile(zip_stream, "w") as zf:
        zf.writestr("main.tex", "zip content")

    zip_bytes = zip_stream.getvalue()
    extract_source_data(zip_bytes, "2605.12345", tmp_path)

    extracted_file = tmp_path / "main.tex"
    assert extracted_file.exists()
    assert extracted_file.read_text() == "zip content"


def test_extract_source_data_pdf(tmp_path):
    # PDF bytes
    pdf_bytes = b"%PDF-1.4\n%..."

    extract_source_data(pdf_bytes, "2605.12345", tmp_path)

    extracted_file = tmp_path / "2605.12345.pdf"
    assert extracted_file.exists()
    assert extracted_file.read_bytes() == pdf_bytes


@patch("arxiv_daily.arxiv_client.fetch_url")
def test_download_paper_source_success(mock_fetch, tmp_path):
    # Mock source fetch returning tar.gz content
    tar_stream = io.BytesIO()
    with tarfile.open(fileobj=tar_stream, mode="w:gz") as tar:
        content = b"tar content"
        tarinfo = tarfile.TarInfo(name="main.tex")
        tarinfo.size = len(content)
        tar.addfile(tarinfo, io.BytesIO(content))

    mock_fetch.return_value = tar_stream.getvalue()

    download_type, success = download_paper_source_or_pdf("2605.12345", tmp_path)
    assert success
    assert download_type == "source"
    assert (tmp_path / "main.tex").exists()


@patch("arxiv_daily.arxiv_client.fetch_url")
def test_download_paper_source_failed_fallback_pdf_success(mock_fetch, tmp_path):
    # First call (source) raises Exception, second call (PDF) succeeds
    mock_fetch.side_effect = [Exception("ArXiv source 404"), b"%PDF-1.4\npdf content"]

    download_type, success = download_paper_source_or_pdf("2605.12345", tmp_path)
    assert success
    assert download_type == "pdf"
    assert (tmp_path / "2605.12345.pdf").exists()
    assert (tmp_path / "2605.12345.pdf").read_bytes() == b"%PDF-1.4\npdf content"
