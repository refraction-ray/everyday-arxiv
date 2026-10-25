import json
from datetime import date

import pytest

from arxiv_daily.announcement_batch import CatchupOutOfRange
from arxiv_daily.cli import _fetch_paper_date_from_api, _find_paper_date_locally, main
from arxiv_daily.models import Paper
from arxiv_daily.submitted_slice import build_submitted_slice_query, fetch_submitted_slice

OUT_OF_RANGE = CatchupOutOfRange("arXiv serves catch-up listings for the past 90 days only.")


def _paper(arxiv_id: str) -> Paper:
    return Paper(
        arxiv_id=arxiv_id,
        title=f"Title {arxiv_id}",
        authors=["A"],
        summary="abstract",
        categories=["quant-ph"],
        primary_category="quant-ph",
        published="2026-10-21T00:00:00+00:00",
        updated="2026-10-21T00:00:00+00:00",
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
    )


def _stub_batch(monkeypatch, papers):
    captured = {}

    def fake_batch(**kwargs):
        captured.update(kwargs)
        return "batch-url", papers, "catchup"

    monkeypatch.setattr("arxiv_daily.cli.fetch_papers_from_announcement_batch", fake_batch)
    return captured


def _stub_out_of_range(monkeypatch, slice_papers=None):
    def raise_out_of_range(**kwargs):
        raise OUT_OF_RANGE

    def fake_slice(**kwargs):
        if slice_papers is None:
            raise AssertionError("the submitted slice must not be fetched here")
        return "cat:quant-ph AND submittedDate", slice_papers

    monkeypatch.setattr("arxiv_daily.cli.fetch_papers_from_announcement_batch", raise_out_of_range)
    monkeypatch.setattr("arxiv_daily.cli.fetch_submitted_slice", fake_slice)


def _fetch(tmp_path, date_text, *extra):
    return main(
        [
            "fetch",
            "--date",
            date_text,
            "--category",
            "quant-ph",
            "--output-dir",
            str(tmp_path),
            *extra,
        ]
    )


def _read_cache(tmp_path, date_text):
    return json.loads((tmp_path / date_text / "quant-ph.json").read_text(encoding="utf-8"))


def test_cli_fetch_writes_the_whole_batch(monkeypatch, tmp_path):
    captured = _stub_batch(monkeypatch, [_paper("2610.00001"), _paper("2610.00002")])

    assert _fetch(tmp_path, "2026-10-22") == 0

    cache = _read_cache(tmp_path, "2026-10-22")
    assert cache["count"] == 2
    assert cache["source"] == "catchup"
    assert cache["date_convention"] == "announcement_batch"
    assert captured["base_url"] == "https://export.arxiv.org/api/query"


def test_cli_no_api_passes_no_base_url(monkeypatch, tmp_path):
    captured = _stub_batch(monkeypatch, [_paper("2610.00001")])

    assert _fetch(tmp_path, "2026-10-22", "--no-api") == 0

    assert captured["base_url"] is None


def test_cli_reports_an_explicit_max_results_cap(monkeypatch, tmp_path, capsys):
    _stub_batch(monkeypatch, [_paper("2610.00001"), _paper("2610.00002"), _paper("2610.00003")])

    assert _fetch(tmp_path, "2026-10-22", "--max-results", "2") == 0

    assert "keeping the first 2" in capsys.readouterr().out
    cache = _read_cache(tmp_path, "2026-10-22")
    assert cache["count"] == 2
    assert "truncated to 2 of 3 papers" in cache["query"]


def test_out_of_range_falls_back_to_a_submitted_slice(monkeypatch, tmp_path, capsys):
    _stub_out_of_range(monkeypatch, slice_papers=[_paper("2501.00001")])

    assert _fetch(tmp_path, "2025-01-15") == 0

    assert "NOT the announcement batch" in capsys.readouterr().out
    cache = _read_cache(tmp_path, "2025-01-15")
    assert cache["source"] == "api-submitted-slice"
    assert cache["date_convention"] == "submitted_date_slice"


def test_submitted_slice_reports_an_explicit_max_results_cap(monkeypatch, tmp_path, capsys):
    _stub_out_of_range(
        monkeypatch, slice_papers=[_paper("2501.00001"), _paper("2501.00002"), _paper("2501.00003")]
    )

    assert _fetch(tmp_path, "2025-01-15", "--max-results", "2") == 0

    assert "keeping the first 2" in capsys.readouterr().out
    cache = _read_cache(tmp_path, "2025-01-15")
    assert cache["count"] == 2
    assert "truncated to 2 of 3 papers" in cache["query"]


def test_out_of_range_does_not_overwrite_an_existing_cache(monkeypatch, tmp_path):
    existing = tmp_path / "2025-01-15" / "quant-ph.json"
    existing.parent.mkdir(parents=True)
    existing.write_text('{"count": 7}', encoding="utf-8")
    _stub_out_of_range(monkeypatch)

    with pytest.raises(RuntimeError, match="cache already exists"):
        _fetch(tmp_path, "2025-01-15")

    assert existing.read_text(encoding="utf-8") == '{"count": 7}'


def test_out_of_range_with_no_api_explains_the_dead_end(monkeypatch, tmp_path):
    _stub_out_of_range(monkeypatch)

    with pytest.raises(RuntimeError, match="drop --no-api"):
        _fetch(tmp_path, "2025-01-15", "--no-api")


def test_submitted_slice_query_pins_one_utc_day():
    assert (
        build_submitted_slice_query(["quant-ph"], date(2025, 1, 15))
        == "cat:quant-ph AND submittedDate:[202501150000 TO 202501152359]"
    )
    assert (
        build_submitted_slice_query(["quant-ph", "cond-mat"], date(2025, 1, 15))
        == "(cat:quant-ph OR cat:cond-mat) AND submittedDate:[202501150000 TO 202501152359]"
    )


def test_submitted_slice_pages_until_a_short_page(monkeypatch):
    starts = []

    def fake_fetch(url, timeout_seconds):
        start = int(url.split("start=")[1].split("&")[0])
        starts.append(start)
        return str(start).encode()

    def fake_parse(xml_bytes):
        start = int(xml_bytes.decode())
        size = 100 if start < 200 else 7
        return [_paper(f"2501.{start + index:05d}") for index in range(size)]

    monkeypatch.setattr("arxiv_daily.submitted_slice.fetch_url", fake_fetch)
    monkeypatch.setattr("arxiv_daily.submitted_slice.parse_feed", fake_parse)

    _, papers = fetch_submitted_slice(
        base_url="https://example.org/api/query",
        categories=["quant-ph"],
        target_date=date(2025, 1, 15),
        timeout_seconds=5,
    )

    assert starts == [0, 100, 200]
    assert len(papers) == 207


def _write_cache(root, date_text, source, arxiv_ids):
    date_dir = root / date_text
    date_dir.mkdir(parents=True, exist_ok=True)
    payload = {"source": source, "papers": [{"arxiv_id": item} for item in arxiv_ids]}
    (date_dir / "quant-ph.json").write_text(json.dumps(payload), encoding="utf-8")


def test_find_paper_date_locally(tmp_path):
    _write_cache(tmp_path, "2026-05-14", "list", ["2605.12345", "2605.67890"])

    assert _find_paper_date_locally(tmp_path, "2605.12345") == date(2026, 5, 14)
    assert _find_paper_date_locally(tmp_path, "non-existent") is None


def test_find_paper_date_locally_ignores_version_suffixes(tmp_path):
    _write_cache(tmp_path, "2026-05-14", "api", ["2605.12345v1"])

    assert _find_paper_date_locally(tmp_path, "2605.12345") == date(2026, 5, 14)
    assert _find_paper_date_locally(tmp_path, "2605.12345v3") == date(2026, 5, 14)


def test_find_paper_date_locally_prefers_the_announcement_batch(tmp_path):
    _write_cache(tmp_path, "2026-05-13", "api", ["2605.12345v1"])
    _write_cache(tmp_path, "2026-05-14", "html", ["2605.12345"])
    _write_cache(tmp_path, "2026-05-15", "catchup", ["2605.12345"])

    assert _find_paper_date_locally(tmp_path, "2605.12345") == date(2026, 5, 15)


def test_find_paper_date_locally_takes_the_earliest_legacy_cache(tmp_path):
    _write_cache(tmp_path, "2026-05-15", "api", ["2605.12345v1"])
    _write_cache(tmp_path, "2026-05-14", "html", ["2605.12345"])

    assert _find_paper_date_locally(tmp_path, "2605.12345") == date(2026, 5, 14)


def test_find_paper_date_locally_falls_back_to_downloaded_sources(tmp_path):
    (tmp_path / "2018-03-26" / "sources" / "1803.09999").mkdir(parents=True)
    _write_cache(tmp_path, "2026-05-14", "list", ["2605.12345"])

    assert _find_paper_date_locally(tmp_path, "1803.09999v2") == date(2018, 3, 26)
    assert _find_paper_date_locally(tmp_path, "2605.12345") == date(2026, 5, 14)


def test_download_files_every_version_under_the_bare_id(monkeypatch, tmp_path, capsys):
    _write_cache(tmp_path, "2026-05-14", "list", ["2605.12345"])
    existing = tmp_path / "2026-05-14" / "sources" / "2605.12345"
    existing.mkdir(parents=True)
    (existing / "main.tex").write_text("v1 source", encoding="utf-8")

    def forbidden_download(*args, **kwargs):
        raise AssertionError("an existing bare-ID folder must not be downloaded again")

    monkeypatch.setattr("arxiv_daily.cli.download_paper_source_or_pdf", forbidden_download)

    exit_code = main(
        ["download", "2605.12345v2", "--output-dir", str(tmp_path), "--delay-seconds", "0"]
    )

    assert exit_code == 0
    assert f"already has files in {existing}" in capsys.readouterr().out
    assert not (tmp_path / "2026-05-14" / "sources" / "2605.12345v2").exists()


def test_fetch_paper_date_from_api(monkeypatch):
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
    captured = {}

    def fake_by_ids(*, base_url, ids, timeout_seconds):
        captured["base_url"] = base_url
        captured["ids"] = ids
        return {"2605.12345": mock_paper}

    monkeypatch.setattr("arxiv_daily.cli.fetch_papers_by_ids", fake_by_ids)

    found_date = _fetch_paper_date_from_api(
        "2605.12345v2", base_url="https://example.org/api/query", timeout_seconds=5
    )

    assert found_date == date(2026, 5, 14)
    assert captured["base_url"] == "https://example.org/api/query"
    assert captured["ids"] == ["2605.12345v2"]
