import gzip
import io
import tarfile
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from arxiv_daily.arxiv_client import (
    parse_search_html,
    extract_source_data,
    download_paper_source_or_pdf,
)
from arxiv_daily.cli import (
    _find_paper_date_locally,
    _fetch_paper_date_from_api,
)


def test_html_parser_excludes_revisions_from_submitted_date_batch():
    html = """
    <ol>
      <li class="arxiv-result">
        <p class="list-title is-inline-block">
          <a href="https://arxiv.org/abs/2512.18995v2">arXiv:2512.18995</a>
        </p>
        <p class="title is-5 mathjax">DeepQuantum</p>
        <p class="authors"><a>Author One</a></p>
        <div class="tags"><span class="tag is-small">quant-ph</span></div>
        <p class="abstract mathjax">Abstract: Revised software paper.</p>
        <p class="is-size-7">
          <span class="has-text-weight-semibold">Submitted</span> 14 May, 2026;
          <span class="has-text-weight-semibold">v1</span> submitted 21 December, 2025;
        </p>
      </li>
    </ol>
    """

    papers = parse_search_html(html, target_date=date(2026, 5, 14))

    assert papers == []


def test_html_parser_keeps_first_submissions_from_submitted_date_batch():
    html = """
    <ol>
      <li class="arxiv-result">
        <p class="list-title is-inline-block">
          <a href="https://arxiv.org/abs/2605.12345v1">arXiv:2605.12345</a>
        </p>
        <p class="title is-5 mathjax">New Quantum Paper</p>
        <p class="authors"><a>Author One</a><a>Author Two</a></p>
        <div class="tags"><span class="tag is-small">quant-ph</span></div>
        <p class="abstract mathjax">Abstract: First submission.</p>
        <p class="is-size-7">
          <span class="has-text-weight-semibold">Submitted</span> 14 May, 2026;
          <span class="has-text-weight-semibold">v1</span> submitted 14 May, 2026;
        </p>
      </li>
    </ol>
    """

    papers = parse_search_html(html, target_date=date(2026, 5, 14))

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2605.12345"
    assert papers[0].summary == "First submission."
    assert papers[0].published.startswith("2026-05-14")
    assert papers[0].updated.startswith("2026-05-14")


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


def test_find_paper_date_locally(tmp_path):
    # Set up mock raw arxiv output directory with date folder and json cache
    date_dir = tmp_path / "2026-05-14"
    date_dir.mkdir(parents=True)
    json_cache = date_dir / "quant-ph.json"

    import json

    cache_data = {
        "papers": [
            {"arxiv_id": "2605.12345", "title": "Paper 1"},
            {"arxiv_id": "2605.67890", "title": "Paper 2"},
        ]
    }
    json_cache.write_text(json.dumps(cache_data), encoding="utf-8")

    found_date = _find_paper_date_locally(tmp_path, "2605.12345")
    assert found_date == date(2026, 5, 14)

    not_found = _find_paper_date_locally(tmp_path, "non-existent")
    assert not_found is None


@patch("arxiv_daily.cli.fetch_url")
@patch("arxiv_daily.cli.parse_feed")
def test_fetch_paper_date_from_api(mock_parse, mock_fetch):
    # Mocking parser response
    from arxiv_daily.models import Paper

    mock_paper = Paper(
        arxiv_id="2605.12345",
        title="Title",
        authors=[],
        summary="",
        categories=[],
        primary_category=None,
        published="2026-05-14T12:00:00Z",
        updated="2026-05-14T12:00:00Z",
        abs_url="",
        pdf_url="",
    )
    mock_parse.return_value = [mock_paper]
    mock_fetch.return_value = b"<xml>...</xml>"

    found_date = _fetch_paper_date_from_api("2605.12345")
    assert found_date == date(2026, 5, 14)
