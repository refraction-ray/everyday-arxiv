from datetime import date
from urllib.error import HTTPError, URLError

import pytest

from arxiv_daily.announcement_batch import (
    CatchupOutOfRange,
    NoAnnouncementBatch,
    build_catchup_url,
    build_listing_url,
    fetch_papers_from_announcement_batch,
    fetch_papers_from_catchup,
    fetch_papers_from_listing,
    parse_catchup_announcement_date,
    parse_listing_announcement_date,
)
from arxiv_daily.models import Paper

TUE = date(2026, 10, 20)
MON = date(2026, 10, 19)
LISTING_URL = "https://arxiv.org/list/quant-ph/new?skip=0&show=2000&abs=True"


def _entry(arxiv_id, *, title=None, comment=None, cross_from=None, subjects=None):
    cross = f" (cross-list from {cross_from})" if cross_from else ""
    comment_html = (
        f"<div class='list-comments mathjax'><span class='descriptor'>Comments:</span> "
        f"{comment}</div>"
        if comment
        else ""
    )
    subjects = subjects or '<span class="primary-subject">Quantum Physics (quant-ph)</span>'
    return f"""
  <dt>
    <a name='item1'>[1]</a> <a href ="/abs/{arxiv_id}" title="Abstract" id="{arxiv_id}">arXiv:{arxiv_id}</a>{cross}
  </dt>
  <dd>
    <div class='meta'>
      <div class='list-title mathjax'><span class='descriptor'>Title:</span>
        {title or f"Title of {arxiv_id}"}
      </div>
      <div class='list-authors'><a href="https://arxiv.org/search/quant-ph?query=A">Alice A</a>, <a href="https://arxiv.org/search/quant-ph?query=B">Bob B</a></div>
      {comment_html}
      <div class='list-subjects'><span class='descriptor'>Subjects:</span>
        {subjects}
      </div>
      <p class='mathjax'>
        Abstract of {arxiv_id}.
      </p>
    </div>
  </dd>"""


def _section(kind, entries, *, total=None, continued=False, which=""):
    total = len(entries) if total is None else total
    lead = "continued, " if continued else ""
    header = f"<h3>{kind} submissions ({lead}showing {which}{len(entries)} of {total} entries)</h3>"
    return header + "".join(entries)


def _listing_page(day, *sections, total):
    header = f"<h3>Showing new listings for {day:%A}, {day.day} {day:%B %Y}</h3>"
    return (
        f"<div id='dlpage'><div>Total of {total} entries</div>"
        f"<dl id='articles'>{header}{''.join(sections)}</dl></div>"
    )


def _catchup_page(day, *sections, total):
    stamp = f"{day:%a}, {day.day} {day:%b %Y}"
    return (
        f"<div id='dlpage'><h1>Catchup results for Quantum Physics on {stamp}</h1>"
        f"<div>Total of {total} entries for {stamp}</div>"
        f"<dl id='articles'>{''.join(sections)}</dl></div>"
    )


def _catchup_url(day, category="quant-ph"):
    return build_catchup_url(category=category, target_date=day)


def _serve(monkeypatch, pages):
    """Serve ``pages`` (URL -> HTML or exception) and record the URLs asked for."""
    requested = []

    def fake_fetch(url, timeout_seconds):
        requested.append(url)
        if url not in pages:
            raise AssertionError(f"unexpected request: {url}")
        page = pages[url]
        if isinstance(page, Exception):
            raise page
        return page.encode()

    monkeypatch.setattr("arxiv_daily.arxiv_client.fetch_url", fake_fetch)
    return requested


# Tuesday's batch: two new papers, one cross-list of a new paper, one cross-list of a
# September paper that only now gained quant-ph, and a replacement.
TUESDAY_LISTING = _listing_page(
    TUE,
    _section(
        "New",
        [
            _entry(
                "2610.11111",
                title="A test title on block listings",
                comment="12 pages, 3 figures",
                subjects='<span class="primary-subject">Quantum Physics (quant-ph)</span>; '
                "Information Theory (cs.IT)",
            ),
            _entry("2610.22222"),
        ],
    ),
    _section(
        "Cross",
        [
            _entry("2610.15555", cross_from="cond-mat.str-el"),
            _entry("2609.00001", cross_from="math-ph"),
        ],
    ),
    _section("Replacement", [_entry("2608.99999")]),
    total=5,
)
MONDAY_CATCHUP = _catchup_page(
    MON,
    _section("New", [_entry("2610.09999"), _entry("2610.10000")]),
    _section("Replacement", [_entry("2607.12345")]),
    total=3,
)
# The same batch as TUESDAY_LISTING, read the way a catch-up page presents it.
TUESDAY_CATCHUP = _catchup_page(
    TUE,
    _section("New", [_entry("2610.11111"), _entry("2610.22222")]),
    _section(
        "Cross",
        [
            _entry("2610.15555", cross_from="cond-mat.str-el"),
            _entry("2609.00001", cross_from="math-ph"),
        ],
    ),
    total=4,
)
TUESDAY_PAGES = {LISTING_URL: TUESDAY_LISTING, _catchup_url(MON): MONDAY_CATCHUP}


def _fetch_tuesday(**kwargs):
    return fetch_papers_from_listing(
        base_url=kwargs.pop("base_url", None),
        categories=kwargs.pop("categories", ["quant-ph"]),
        target_date=TUE,
        timeout_seconds=5,
        **kwargs,
    )


def test_listing_url_requests_abstracts():
    url = build_listing_url(category="quant-ph")
    assert url.startswith("https://arxiv.org/list/quant-ph/new?")
    assert "abs=True" in url
    assert "show=2000" in url
    assert "skip=0" in url


def test_catchup_url_requests_one_day_with_abstracts():
    url = build_catchup_url(category="quant-ph", target_date=date(2026, 10, 22))
    assert url.startswith("https://arxiv.org/catchup/quant-ph/2026-10-22?")
    assert "abs=True" in url
    assert "page=1" in url


def test_page_parsers_read_the_announcement_date():
    assert parse_listing_announcement_date(TUESDAY_LISTING) == TUE
    assert parse_catchup_announcement_date(MONDAY_CATCHUP) == MON
    assert parse_listing_announcement_date("<html>no listing header</html>") is None
    assert parse_catchup_announcement_date("<html>no catchup header</html>") is None


def test_listing_batch_keeps_new_papers_and_new_cross_lists(monkeypatch):
    requested = _serve(monkeypatch, {LISTING_URL: TUESDAY_LISTING})

    query, papers = _fetch_tuesday()

    assert requested == [LISTING_URL]
    by_id = {paper.arxiv_id: paper for paper in papers}
    assert set(by_id) == {"2610.11111", "2610.22222", "2610.15555"}
    assert by_id["2610.11111"].listing_section == "new"
    assert by_id["2610.15555"].listing_section == "cross"
    assert query == (
        f"{LISTING_URL} [excluded 1 cross-lists of papers announced earlier: 2609.00001]"
    )

    first = by_id["2610.11111"]
    assert first.title == "A test title on block listings"
    assert first.authors == ["Alice A", "Bob B"]
    assert first.summary == "Abstract of 2610.11111."
    assert first.categories == ["quant-ph", "cs.IT"]
    assert first.primary_category == "quant-ph"
    assert first.comment == "12 pages, 3 figures"
    assert first.abs_url == "https://arxiv.org/abs/2610.11111"
    assert first.published.startswith("2026-10-20")
    assert by_id["2610.22222"].comment is None


def test_listing_batch_follows_pagination_across_sections(monkeypatch):
    first_page = _listing_page(
        TUE,
        _section("New", [_entry("2610.11111"), _entry("2610.22222")], total=3, which="first "),
        total=4,
    )
    second_page = _listing_page(
        TUE,
        _section("New", [_entry("2610.33333")], total=3, continued=True, which="last "),
        _section("Cross", [_entry("2610.15555", cross_from="hep-th")]),
        total=4,
    )
    second_url = LISTING_URL.replace("skip=0", "skip=2")
    requested = _serve(monkeypatch, {LISTING_URL: first_page, second_url: second_page})

    query, papers = _fetch_tuesday()

    assert requested == [LISTING_URL, second_url]
    assert sorted(paper.arxiv_id for paper in papers) == [
        "2610.11111",
        "2610.15555",
        "2610.22222",
        "2610.33333",
    ]
    assert query == f"{LISTING_URL} | {second_url}"


def test_listing_batch_rejects_an_incomplete_section(monkeypatch):
    html = _listing_page(
        TUE, _section("New", [_entry("2610.11111"), _entry("2610.22222")], total=3), total=2
    )
    _serve(monkeypatch, {LISTING_URL: html})

    with pytest.raises(RuntimeError, match="yielded 2 of 3 new submissions"):
        _fetch_tuesday()


def test_listing_batch_merges_categories_and_prefers_new(monkeypatch):
    quant_ph = _listing_page(
        TUE,
        _section("New", [_entry("2610.11111")]),
        _section("Cross", [_entry("2610.33333", cross_from="cond-mat.str-el")]),
        total=2,
    )
    cond_mat = _listing_page(TUE, _section("New", [_entry("2610.33333")]), total=1)
    cond_mat_url = build_listing_url(category="cond-mat.str-el")
    requested = _serve(
        monkeypatch,
        {LISTING_URL: quant_ph, cond_mat_url: cond_mat, _catchup_url(MON): MONDAY_CATCHUP},
    )

    query, papers = _fetch_tuesday(categories=["quant-ph", "cond-mat.str-el"])

    assert requested == [LISTING_URL, cond_mat_url]
    assert {paper.arxiv_id: paper.listing_section for paper in papers} == {
        "2610.11111": "new",
        "2610.33333": "new",
    }
    assert query == f"{LISTING_URL} | {cond_mat_url}"


def test_cross_list_floor_comes_from_this_batchs_first_new_id(monkeypatch):
    """The floor is derived from this batch, so no other page is ever requested.

    A cross-list above the batch's first new-submission ID is kept, one whose paper
    predates the batch is dropped. Reading the previous batch instead would cost an
    extra catch-up page (three of them on a Monday) and would be skewed by a stale
    CDN copy of that page.
    """
    monday = _listing_page(
        MON,
        _section("New", [_entry("2610.20000")]),
        _section(
            "Cross",
            [_entry("2610.21000", cross_from="hep-th"), _entry("2609.17000", cross_from="hep-th")],
        ),
        total=3,
    )
    requested = _serve(monkeypatch, {LISTING_URL: monday})

    query, papers = fetch_papers_from_listing(
        base_url=None, categories=["quant-ph"], target_date=MON, timeout_seconds=5
    )

    assert requested == [LISTING_URL]
    assert sorted(paper.arxiv_id for paper in papers) == ["2610.20000", "2610.21000"]
    assert "excluded 1 cross-lists of papers announced earlier: 2609.17000" in query


def test_same_month_cross_list_below_the_batch_floor_is_kept(monkeypatch):
    """Regression test for 2026-11-16.

    2611.17366 was submitted after the Friday cut-off and announced with the Monday
    batch as a cross-list, but its ID sits below every new submission of that batch,
    so an ID-floor-only filter silently dropped a genuine paper. Sharing the batch's
    own month keeps it, at the accepted cost of occasionally keeping a same-month
    paper that was announced earlier.
    """
    page = _listing_page(
        MON,
        _section("New", [_entry("2610.21000")]),
        _section(
            "Cross",
            [
                _entry("2610.19000", cross_from="physics.ins-det"),
                _entry("2609.17000", cross_from="hep-th"),
            ],
        ),
        total=3,
    )
    _serve(monkeypatch, {LISTING_URL: page})

    _, papers = fetch_papers_from_listing(
        base_url=None, categories=["quant-ph"], target_date=MON, timeout_seconds=5
    )

    assert sorted(paper.arxiv_id for paper in papers) == ["2610.19000", "2610.21000"]


def test_cross_list_floor_survives_a_month_boundary(monkeypatch):
    """A first-of-month batch is mostly last month's submissions; keep its cross-lists.

    Filtering by "same YYMM as the batch" would drop every cross-list here, which on
    2026-11-02 would have been 22 entries: that day's 74 new submissions were all
    2610.* IDs. The batch's own ID range has no such boundary.
    """
    boundary = date(2026, 11, 2)
    page = _listing_page(
        boundary,
        _section("New", [_entry("2610.24444"), _entry("2610.24555")]),
        _section(
            "Cross",
            [
                _entry("2610.24777", cross_from="cond-mat.str-el"),
                _entry("2608.11111", cross_from="hep-th"),
            ],
        ),
        total=4,
    )
    _serve(monkeypatch, {LISTING_URL: page})

    _, papers = fetch_papers_from_listing(
        base_url=None, categories=["quant-ph"], target_date=boundary, timeout_seconds=5
    )

    assert sorted(paper.arxiv_id for paper in papers) == [
        "2610.24444",
        "2610.24555",
        "2610.24777",
    ]


def test_cross_list_filter_never_reads_another_page(monkeypatch):
    requested = _serve(monkeypatch, {LISTING_URL: TUESDAY_LISTING})

    query, papers = _fetch_tuesday()

    assert requested == [LISTING_URL]
    assert sorted(paper.arxiv_id for paper in papers) == ["2610.11111", "2610.15555", "2610.22222"]
    assert "excluded 1 cross-lists of papers announced earlier: 2609.00001" in query


def test_a_batch_without_cross_lists_needs_no_previous_batch(monkeypatch):
    html = _listing_page(TUE, _section("New", [_entry("2610.11111")]), total=1)
    requested = _serve(monkeypatch, {LISTING_URL: html})

    query, papers = _fetch_tuesday()

    assert requested == [LISTING_URL]
    assert [paper.arxiv_id for paper in papers] == ["2610.11111"]
    assert query == LISTING_URL


def test_enrichment_takes_only_timestamps_from_the_api(monkeypatch):
    _serve(monkeypatch, TUESDAY_PAGES)

    def fake_by_ids(*, base_url, ids, timeout_seconds):
        assert base_url == "https://example.org/api/query"
        return {
            "2610.11111": Paper(
                arxiv_id="2610.11111v2",
                title="A revised title from v2",
                authors=["Alice A", "Bob B"],
                summary="A revised abstract from v2.",
                categories=["quant-ph", "cs.IT"],
                primary_category="quant-ph",
                published="2026-10-18T09:00:00+00:00",
                updated="2026-10-23T09:00:00+00:00",
                abs_url="http://arxiv.org/abs/2610.11111v2",
                pdf_url="http://arxiv.org/pdf/2610.11111v2",
            )
        }

    monkeypatch.setattr("arxiv_daily.announcement_batch.fetch_papers_by_ids", fake_by_ids)

    _, papers = _fetch_tuesday(base_url="https://example.org/api/query")

    by_id = {paper.arxiv_id: paper for paper in papers}
    assert set(by_id) == {"2610.11111", "2610.22222", "2610.15555"}
    first = by_id["2610.11111"]
    assert first.published == "2026-10-18T09:00:00+00:00"
    assert first.updated == "2026-10-23T09:00:00+00:00"
    assert first.title == "A test title on block listings"
    assert first.summary == "Abstract of 2610.11111."
    assert first.abs_url == "https://arxiv.org/abs/2610.11111"
    assert first.listing_section == "new"
    assert by_id["2610.22222"].published.startswith("2026-10-20")


def test_enrichment_failure_keeps_the_listing_metadata(monkeypatch):
    _serve(monkeypatch, TUESDAY_PAGES)

    def failing_by_ids(*, base_url, ids, timeout_seconds):
        raise URLError("api unreachable")

    monkeypatch.setattr("arxiv_daily.announcement_batch.fetch_papers_by_ids", failing_by_ids)

    query, papers = _fetch_tuesday(base_url="https://example.org/api/query")

    assert len(papers) == 3
    assert all(paper.summary for paper in papers)
    assert "not enriched by the arXiv API" in query


def test_no_base_url_skips_enrichment_entirely(monkeypatch):
    _serve(monkeypatch, TUESDAY_PAGES)

    def forbidden_by_ids(**kwargs):
        raise AssertionError("the arXiv API must not be called without a base_url")

    monkeypatch.setattr("arxiv_daily.announcement_batch.fetch_papers_by_ids", forbidden_by_ids)

    query, papers = _fetch_tuesday()

    assert len(papers) == 3
    assert "not enriched" not in query


def test_listing_fetch_rejects_other_announcement_date(monkeypatch):
    _serve(monkeypatch, TUESDAY_PAGES)

    with pytest.raises(RuntimeError, match="not the requested"):
        fetch_papers_from_listing(
            base_url=None,
            categories=["quant-ph"],
            target_date=date(2026, 10, 21),
            timeout_seconds=5,
        )


def test_catchup_fetch_keeps_new_papers_and_new_cross_lists(monkeypatch):
    tuesday = _catchup_page(
        TUE,
        _section("New", [_entry("2610.11111", comment="9 pages")]),
        _section("Cross", [_entry("2610.15555", cross_from="gr-qc")]),
        _section("Replacement", [_entry("2608.99999")]),
        total=3,
    )
    requested = _serve(monkeypatch, {_catchup_url(TUE): tuesday})

    query, papers = fetch_papers_from_catchup(
        base_url=None, categories=["quant-ph"], target_date=TUE, timeout_seconds=5
    )

    assert requested == [_catchup_url(TUE)]
    assert {paper.arxiv_id: paper.listing_section for paper in papers} == {
        "2610.11111": "new",
        "2610.15555": "cross",
    }
    assert {paper.arxiv_id: paper.comment for paper in papers}["2610.11111"] == "9 pages"
    assert query == _catchup_url(TUE)


def test_catchup_fetch_reports_empty_day(monkeypatch):
    saturday = date(2026, 10, 24)
    _serve(monkeypatch, {_catchup_url(saturday): _catchup_page(saturday, total=0)})

    with pytest.raises(RuntimeError, match="no announcement batch"):
        fetch_papers_from_catchup(
            base_url=None, categories=["quant-ph"], target_date=saturday, timeout_seconds=5
        )


def test_catchup_fetch_reports_http_400_as_out_of_range(monkeypatch):
    old_day = date(2025, 1, 15)
    url = _catchup_url(old_day)
    _serve(monkeypatch, {url: HTTPError(url, 400, "400 Client Error: Bad Request", None, None)})

    with pytest.raises(CatchupOutOfRange, match="past 90 days"):
        fetch_papers_from_catchup(
            base_url=None, categories=["quant-ph"], target_date=old_day, timeout_seconds=5
        )


def test_catchup_fetch_does_not_treat_other_errors_as_out_of_range(monkeypatch):
    url = _catchup_url(TUE)
    _serve(monkeypatch, {url: HTTPError(url, 503, "503 Server Error", None, None)})

    with pytest.raises(HTTPError) as excinfo:
        fetch_papers_from_catchup(
            base_url=None, categories=["quant-ph"], target_date=TUE, timeout_seconds=5
        )
    assert not isinstance(excinfo.value, CatchupOutOfRange)


def test_catchup_fetch_rejects_other_announcement_date(monkeypatch):
    _serve(monkeypatch, {_catchup_url(TUE): MONDAY_CATCHUP})

    with pytest.raises(RuntimeError, match="not the requested"):
        fetch_papers_from_catchup(
            base_url=None, categories=["quant-ph"], target_date=TUE, timeout_seconds=5
        )


def test_announcement_batch_reads_the_requested_date_from_catchup(monkeypatch):
    requested = _serve(monkeypatch, {_catchup_url(TUE): TUESDAY_CATCHUP})

    query, papers, source = fetch_papers_from_announcement_batch(
        base_url=None, categories=["quant-ph"], target_date=TUE, timeout_seconds=5
    )

    assert source == "catchup"
    assert {paper.arxiv_id for paper in papers} == {"2610.11111", "2610.22222", "2610.15555"}
    assert query.startswith(_catchup_url(TUE))
    assert "excluded 1 cross-lists of papers announced earlier: 2609.00001" in query
    # The listing page is not consulted at all when catch-up serves the date.
    assert requested == [_catchup_url(TUE)]


def test_announcement_batch_uses_catchup_when_the_listing_has_not_rolled_over(monkeypatch):
    """Regression test for 2026-11-16.

    The listing page still printed the previous batch's announcement date while the
    requested date's catch-up page already held the complete batch. The listing date
    must not be read as "this date has no announcement".
    """
    requested = _serve(
        monkeypatch,
        {
            _catchup_url(TUE): TUESDAY_CATCHUP,
            _catchup_url(MON): MONDAY_CATCHUP,
            LISTING_URL: _listing_page(MON, _section("New", [_entry("2610.09999")]), total=2),
        },
    )

    _, papers, source = fetch_papers_from_announcement_batch(
        base_url=None, categories=["quant-ph"], target_date=TUE, timeout_seconds=5
    )

    assert source == "catchup"
    assert len(papers) == 3
    assert LISTING_URL not in requested


def test_announcement_batch_reads_a_past_date_from_catchup_only(monkeypatch):
    requested = _serve(monkeypatch, {_catchup_url(MON): MONDAY_CATCHUP})

    query, papers, source = fetch_papers_from_announcement_batch(
        base_url=None, categories=["quant-ph"], target_date=MON, timeout_seconds=5
    )

    assert source == "catchup"
    assert sorted(paper.arxiv_id for paper in papers) == ["2610.09999", "2610.10000"]
    assert query == _catchup_url(MON)
    assert requested == [_catchup_url(MON)]


def test_announcement_batch_falls_back_to_the_listing_when_catchup_is_empty(monkeypatch):
    requested = _serve(
        monkeypatch,
        {
            _catchup_url(TUE): _catchup_page(TUE, total=0),
            LISTING_URL: TUESDAY_LISTING,
            _catchup_url(MON): MONDAY_CATCHUP,
        },
    )

    _, papers, source = fetch_papers_from_announcement_batch(
        base_url=None, categories=["quant-ph"], target_date=TUE, timeout_seconds=5
    )

    assert source == "list"
    assert len(papers) == 3
    assert requested[:2] == [_catchup_url(TUE), LISTING_URL]


def test_announcement_batch_rejects_unpublished_future_date(monkeypatch):
    future = date(2026, 10, 22)
    _serve(
        monkeypatch,
        {
            _catchup_url(future): HTTPError(
                _catchup_url(future), 400, "400 Client Error: Bad Request", None, None
            ),
            LISTING_URL: TUESDAY_LISTING,
            _catchup_url(MON): MONDAY_CATCHUP,
        },
    )

    with pytest.raises(NoAnnouncementBatch, match="has no announcement batch") as excinfo:
        fetch_papers_from_announcement_batch(
            base_url=None, categories=["quant-ph"], target_date=future, timeout_seconds=5
        )
    # A date newer than the newest batch must never look like an out-of-window date,
    # which would send the CLI down the submittedDate-slice path.
    assert not isinstance(excinfo.value, CatchupOutOfRange)


def test_announcement_batch_reports_out_of_window_date_as_out_of_range(monkeypatch):
    old_day = date(2025, 1, 15)
    _serve(
        monkeypatch,
        {
            _catchup_url(old_day): HTTPError(
                _catchup_url(old_day), 400, "400 Client Error: Bad Request", None, None
            ),
            LISTING_URL: TUESDAY_LISTING,
            _catchup_url(MON): MONDAY_CATCHUP,
        },
    )

    with pytest.raises(CatchupOutOfRange, match="past 90 days"):
        fetch_papers_from_announcement_batch(
            base_url=None, categories=["quant-ph"], target_date=old_day, timeout_seconds=5
        )


def test_announcement_batch_rejects_unreadable_listing_date(monkeypatch):
    _serve(
        monkeypatch,
        {_catchup_url(TUE): _catchup_page(TUE, total=0), LISTING_URL: "<html>maintenance</html>"},
    )

    with pytest.raises(RuntimeError, match="ambiguous date"):
        fetch_papers_from_announcement_batch(
            base_url=None, categories=["quant-ph"], target_date=TUE, timeout_seconds=5
        )
