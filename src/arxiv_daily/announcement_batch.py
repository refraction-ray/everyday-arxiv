"""Announcement-batch selection: the papers arXiv announced on one date.

arXiv announces papers in daily batches: a paper becomes visible on the day its
batch is announced, not on the day it was submitted. ``arxiv.org/list/<category>/new``
shows the most recent batch only, while ``arxiv.org/catchup/<category>/<date>``
serves one specific past day (the past 90 days). Both are read with ``abs=True``,
so the page itself carries titles, authors, comments, subjects and abstracts.

A batch is the page's new submissions plus its cross-lists, i.e. every paper first
announced that day whose subjects include the category. Replacements are left
out, and so are cross-lists of papers announced on an earlier day that only now
gained the category (see ``_drop_cross_lists_of_earlier_papers``).

This is the primary selection of the package. arXiv publishes no API field for
the announcement date, so a batch older than the catch-up window cannot be
rebuilt; ``submitted_slice`` is the labelled, degraded fallback for that case.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Callable
from urllib.error import HTTPError
from urllib.parse import urlencode
from xml.etree.ElementTree import ParseError

from .arxiv_client import clean_text, fetch_html_page, fetch_papers_by_ids, strip_version
from .models import Paper

ARXIV_LISTING_URL_TEMPLATE = "https://arxiv.org/list/{category}/new"
ARXIV_CATCHUP_URL_TEMPLATE = "https://arxiv.org/catchup/{category}/{date}"
DEFAULT_LISTING_PAGE_SIZE = 2000
LISTING_ANNOUNCEMENT_PATTERN = (
    r"Showing new listings for\s+[A-Za-z]+,\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})"
)
CATCHUP_ANNOUNCEMENT_PATTERN = (
    r"Catchup results for [^<]*?\s+on\s+[A-Za-z]+,\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})"
)
# Paged listings say "showing first 25 of 47" and "continued, showing last 22 of 47".
SECTION_HEADER_PATTERN = (
    r"(New|Cross|Replacement) submissions "
    r"\((?:continued, )?showing (?:first |last )?\d+ of (\d+) entries\)"
)
TOTAL_ENTRIES_PATTERN = r"Total of (\d+) entries"
BATCH_SECTIONS = {"New": "new", "Cross": "cross"}
PREVIOUS_BATCH_LOOKBACK_DAYS = 10

# Section kind -> (entries the section announces in total, entries read so far).
Sections = dict[str, tuple[int, list[tuple[str, str]]]]
# Collects one category into the shared ``papers_by_id`` and returns the URLs it read.
CategoryCollector = Callable[[str, dict[str, Paper]], list[str]]


class CatchupOutOfRange(RuntimeError):
    """The requested date is older than arXiv's catch-up window."""


def build_listing_url(
    *, category: str, start: int = 0, show: int = DEFAULT_LISTING_PAGE_SIZE
) -> str:
    base = ARXIV_LISTING_URL_TEMPLATE.format(category=category)
    params = {"skip": str(start), "show": str(show), "abs": "True"}
    return f"{base}?{urlencode(params)}"


def build_catchup_url(*, category: str, target_date: date) -> str:
    base = ARXIV_CATCHUP_URL_TEMPLATE.format(category=category, date=target_date.isoformat())
    return f"{base}?abs=True&page=1"


def parse_listing_announcement_date(html: str) -> date | None:
    return _parse_announcement_date(LISTING_ANNOUNCEMENT_PATTERN, html)


def parse_catchup_announcement_date(html: str) -> date | None:
    return _parse_announcement_date(CATCHUP_ANNOUNCEMENT_PATTERN, html)


def fetch_papers_from_announcement_batch(
    *,
    base_url: str | None,
    categories: list[str],
    target_date: date,
    timeout_seconds: int,
) -> tuple[str, list[Paper], str]:
    """Fetch the batch announced on ``target_date`` from ``/new`` or from catch-up.

    Returns the query, the papers and the page kind used (``list`` or
    ``catchup``). ``base_url`` is the arXiv API used to enrich submission
    timestamps; ``None`` skips enrichment. Raises ``CatchupOutOfRange`` when the
    date is older than the catch-up window.
    """
    first_category = categories[0]
    first_html = fetch_html_page(
        build_listing_url(category=first_category), timeout_seconds=timeout_seconds
    )
    listing_date = _read_announcement_date(
        first_html,
        pattern=LISTING_ANNOUNCEMENT_PATTERN,
        page=f"new-listing page for {first_category}",
    )

    if listing_date == target_date:
        query, papers = fetch_papers_from_listing(
            base_url=base_url,
            categories=categories,
            target_date=target_date,
            timeout_seconds=timeout_seconds,
            first_pages={first_category: first_html},
        )
        return query, papers, "list"
    if listing_date < target_date:
        raise RuntimeError(
            f"arxiv.org has no announcement batch for {target_date.isoformat()}; the newest "
            f"batch is {listing_date.isoformat()}. If {target_date.isoformat()} is today, its "
            "batch appears only after the 20:00 ET announcement."
        )
    query, papers = fetch_papers_from_catchup(
        base_url=base_url,
        categories=categories,
        target_date=target_date,
        timeout_seconds=timeout_seconds,
    )
    return query, papers, "catchup"


def fetch_papers_from_listing(
    *,
    base_url: str | None,
    categories: list[str],
    target_date: date,
    timeout_seconds: int,
    first_pages: dict[str, str] | None = None,
) -> tuple[str, list[Paper]]:
    """Fetch the current batch from ``/new``, which only ever holds the newest one.

    ``first_pages`` hands over page zero of a category that the caller already
    fetched, so it is not fetched twice.
    """
    first_pages = first_pages or {}
    return _fetch_batch(
        base_url=base_url,
        categories=categories,
        target_date=target_date,
        timeout_seconds=timeout_seconds,
        collect=lambda category, papers_by_id: _collect_listing_category(
            category,
            target_date=target_date,
            papers_by_id=papers_by_id,
            timeout_seconds=timeout_seconds,
            first_page_html=first_pages.get(category),
        ),
    )


def fetch_papers_from_catchup(
    *,
    base_url: str | None,
    categories: list[str],
    target_date: date,
    timeout_seconds: int,
) -> tuple[str, list[Paper]]:
    """Fetch a past batch from its catch-up page."""
    return _fetch_batch(
        base_url=base_url,
        categories=categories,
        target_date=target_date,
        timeout_seconds=timeout_seconds,
        collect=lambda category, papers_by_id: _collect_catchup_category(
            category,
            target_date=target_date,
            papers_by_id=papers_by_id,
            timeout_seconds=timeout_seconds,
        ),
    )


def _fetch_batch(
    *,
    base_url: str | None,
    categories: list[str],
    target_date: date,
    timeout_seconds: int,
    collect: CategoryCollector,
) -> tuple[str, list[Paper]]:
    papers_by_id: dict[str, Paper] = {}
    urls: list[str] = []
    for category in categories:
        urls.extend(collect(category, papers_by_id))

    papers, cross_list_note = _drop_cross_lists_of_earlier_papers(
        list(papers_by_id.values()),
        category=categories[0],
        target_date=target_date,
        timeout_seconds=timeout_seconds,
    )
    papers, enrichment_error = _enrich_submission_timestamps(
        base_url=base_url,
        papers=papers,
        timeout_seconds=timeout_seconds,
    )
    papers.sort(key=lambda paper: (paper.updated, paper.arxiv_id), reverse=True)

    query = " | ".join(urls)
    if cross_list_note is not None:
        query = f"{query} {cross_list_note}"
    if enrichment_error is not None:
        query = f"{query} [submission timestamps not enriched by the arXiv API: {enrichment_error}]"
    return query, papers


def _collect_listing_category(
    category: str,
    *,
    target_date: date,
    papers_by_id: dict[str, Paper],
    timeout_seconds: int,
    first_page_html: str | None,
) -> list[str]:
    page = f"new-listing page for {category}"
    urls: list[str] = []
    sections: Sections = {}
    start = 0
    while True:
        url = build_listing_url(category=category, start=start)
        urls.append(url)
        if start == 0 and first_page_html is not None:
            html = first_page_html
        else:
            html = fetch_html_page(url, timeout_seconds=timeout_seconds)

        _require_announcement_date(
            html, pattern=LISTING_ANNOUNCEMENT_PATTERN, page=page, target_date=target_date
        )
        # skip/show count every entry on the page, replacements included.
        page_entries = _merge_page_sections(sections, html)
        start += page_entries
        total = _total_entries(html)
        if page_entries == 0 or total is None or start >= total:
            break

    _store_sections(sections, target_date=target_date, papers_by_id=papers_by_id, page=page)
    return urls


def _collect_catchup_category(
    category: str,
    *,
    target_date: date,
    papers_by_id: dict[str, Paper],
    timeout_seconds: int,
) -> list[str]:
    url = build_catchup_url(category=category, target_date=target_date)
    page = f"catch-up page for {category} on {target_date.isoformat()}"
    sections = _read_catchup_sections(
        category, target_date=target_date, page=page, timeout_seconds=timeout_seconds
    )
    if sections is None:
        raise RuntimeError(
            f"arXiv published no announcement batch for {category} on "
            f"{target_date.isoformat()}; it announces no papers on weekends and holidays, so no "
            "batch cache is written. Pick a date that has a batch: the newest one is whatever "
            "the /new listing currently shows."
        )
    _store_sections(sections, target_date=target_date, papers_by_id=papers_by_id, page=page)
    return [url]


def _read_catchup_sections(
    category: str, *, target_date: date, page: str, timeout_seconds: int
) -> Sections | None:
    """Read one catch-up page; ``None`` means arXiv announced nothing that day."""
    url = build_catchup_url(category=category, target_date=target_date)
    try:
        html = fetch_html_page(url, timeout_seconds=timeout_seconds)
    except HTTPError as exc:
        if exc.code != 400:
            raise
        raise CatchupOutOfRange(
            "arXiv rejected the catch-up request (HTTP 400), which is what it returns for a "
            f"date outside the catch-up window of the past 90 days. The "
            f"{target_date.isoformat()} announcement batch for {category} is therefore out of "
            "reach: arXiv exposes no announcement-date field, so the batch cannot be rebuilt "
            "from the API."
        ) from exc

    _require_announcement_date(
        html, pattern=CATCHUP_ANNOUNCEMENT_PATTERN, page=page, target_date=target_date
    )
    if _total_entries(html) == 0:
        return None
    sections: Sections = {}
    _merge_page_sections(sections, html)
    return sections


def _merge_page_sections(sections: Sections, html: str) -> int:
    """Add one page's entries to ``sections``; return how many entries the page held."""
    page_entries = 0
    for part in re.split(r"<h3>", html)[1:]:
        header, _, body = part.partition("</h3>")
        match = re.match(SECTION_HEADER_PATTERN, header.strip())
        if match is None:
            continue
        kind, total = match.group(1), int(match.group(2))
        entries = re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", body, flags=re.S)
        sections.setdefault(kind, (total, []))[1].extend(entries)
        page_entries += len(entries)
    return page_entries


def _store_sections(
    sections: Sections, *, target_date: date, papers_by_id: dict[str, Paper], page: str
) -> None:
    if not sections:
        raise RuntimeError(
            f"The arXiv {page} contained no 'New submissions' or 'Cross submissions' section; "
            "the page structure may have changed."
        )
    for kind, listing_section in BATCH_SECTIONS.items():
        total, entries = sections.get(kind, (0, []))
        papers = [
            paper
            for dt_block, dd_block in entries
            if (paper := _parse_entry(dt_block, dd_block, announcement_date=target_date))
            is not None
        ]
        read = len({paper.arxiv_id for paper in papers})
        if read != total:
            raise RuntimeError(
                f"The arXiv {page} yielded {read} of {total} {kind.lower()} submissions; "
                "refusing incomplete metadata."
            )
        for paper in papers:
            existing = papers_by_id.get(paper.arxiv_id)
            # A paper new in one requested category and cross-listed in another is "new".
            if existing is None or (existing.listing_section == "cross" and kind == "New"):
                papers_by_id[paper.arxiv_id] = replace(paper, listing_section=listing_section)


def _drop_cross_lists_of_earlier_papers(
    papers: list[Paper], *, category: str, target_date: date, timeout_seconds: int
) -> tuple[list[Paper], str | None]:
    """Keep a cross-list only when the paper itself is new in this batch.

    The cross-list section also carries papers announced on an earlier day that
    have only now been cross-listed into the category. arXiv numbers submissions
    in one sequence across all archives, so a paper submitted after the previous
    batch closed has a higher ID than every new submission of that batch, while
    an earlier paper does not. Returns the kept papers and a note for the query.
    """
    if not any(paper.listing_section == "cross" for paper in papers):
        return papers, None

    previous_last = _previous_batch_last_id(
        category, target_date=target_date, timeout_seconds=timeout_seconds
    )
    if previous_last is not None:
        floor, inclusive, note = previous_last, False, ""
    else:
        new_keys = [_id_key(paper.arxiv_id) for paper in papers if paper.listing_section == "new"]
        if not new_keys:
            return (
                papers,
                "[cross-lists unfiltered: no previous batch or new submission to compare]",
            )
        floor, inclusive = min(new_keys), True
        note = (
            "[previous batch unavailable, so cross-lists were kept from this batch's first new "
            "submission ID on, which can drop a few new ones]"
        )

    kept: list[Paper] = []
    dropped: list[str] = []
    for paper in papers:
        key = _id_key(paper.arxiv_id)
        if paper.listing_section != "cross" or key > floor or (inclusive and key == floor):
            kept.append(paper)
        else:
            dropped.append(paper.arxiv_id)
    if dropped:
        note = (
            f"{note} [excluded {len(dropped)} cross-lists of papers announced earlier: "
            f"{', '.join(sorted(dropped))}]"
        ).strip()
    return kept, note or None


def _previous_batch_last_id(
    category: str, *, target_date: date, timeout_seconds: int
) -> tuple[int, int] | None:
    """Return the highest new-submission ID of the batch before ``target_date``."""
    for days_back in range(1, PREVIOUS_BATCH_LOOKBACK_DAYS + 1):
        day = target_date - timedelta(days=days_back)
        try:
            sections = _read_catchup_sections(
                category,
                target_date=day,
                page=f"catch-up page for {category} on {day.isoformat()}",
                timeout_seconds=timeout_seconds,
            )
        except CatchupOutOfRange:
            return None
        if sections is None:
            continue
        ids = [
            arxiv_id
            for dt_block, _ in sections.get("New", (0, []))[1]
            if (arxiv_id := _first_match(r'href\s*=\s*"/abs/([^"]+)"', dt_block)) is not None
        ]
        if ids:
            return max(_id_key(arxiv_id) for arxiv_id in ids)
    return None


def _id_key(arxiv_id: str) -> tuple[int, int]:
    """Order new-style IDs (``YYMM.NNNNN``) by submission; old-style IDs sort first."""
    match = re.match(r"(\d{4})\.(\d{4,5})", arxiv_id)
    if match is None:
        return (0, 0)
    return (int(match.group(1)), int(match.group(2)))


def _total_entries(html: str) -> int | None:
    match = re.search(TOTAL_ENTRIES_PATTERN, html)
    return int(match.group(1)) if match else None


def _parse_announcement_date(pattern: str, html: str) -> date | None:
    match = re.search(pattern, html)
    if match is None:
        return None
    day, month_name, year = match.groups()
    for month_format in ("%B", "%b"):
        try:
            return datetime.strptime(f"{day} {month_name} {year}", f"%d {month_format} %Y").date()
        except ValueError:
            continue
    return None


def _read_announcement_date(html: str, *, pattern: str, page: str) -> date:
    announcement_date = _parse_announcement_date(pattern, html)
    if announcement_date is None:
        raise RuntimeError(
            f"Could not read the announcement date from the arXiv {page}; "
            "refusing to emit metadata of ambiguous date."
        )
    return announcement_date


def _require_announcement_date(html: str, *, pattern: str, page: str, target_date: date) -> None:
    announcement_date = _read_announcement_date(html, pattern=pattern, page=page)
    if announcement_date != target_date:
        raise RuntimeError(
            f"The arXiv {page} lists submissions for {announcement_date.isoformat()}, "
            f"not the requested {target_date.isoformat()}."
        )


def _parse_entry(dt_block: str, dd_block: str, *, announcement_date: date) -> Paper | None:
    arxiv_id = _first_match(r'href\s*=\s*"/abs/([^"]+)"', dt_block)
    if arxiv_id is None:
        return None
    bare_id = strip_version(arxiv_id)

    title = _html_text(
        _first_match(
            r"list-title mathjax'>\s*<span class='descriptor'>Title:</span>\s*(.*?)\s*</div>",
            dd_block,
        )
    )
    summary = _html_text(_first_match(r"<p class='mathjax'>\s*(.*?)\s*</p>", dd_block))
    authors_block = _first_match(r"<div class='list-authors'>(.*?)</div>", dd_block) or ""
    authors = [
        _html_text(author)
        for author in re.findall(r"<a\b[^>]*>(.*?)</a>", authors_block, flags=re.S)
    ]
    authors = [author for author in authors if author]

    subjects_block = _first_match(r"<div class='list-subjects'>(.*?)</div>", dd_block) or ""
    categories = re.findall(r"\(([A-Za-z][A-Za-z\-]*(?:\.[A-Za-z\-]+)?)\)", subjects_block)
    primary = _first_match(r'<span class="primary-subject">.*?\(([^)]+)\)</span>', subjects_block)
    comment = _html_text(
        _first_match(
            r"list-comments mathjax'>\s*<span class='descriptor'>Comments:</span>\s*(.*?)\s*</div>",
            dd_block,
        )
    )

    # Listing pages carry no per-paper submission timestamp. The announcement
    # date is the best available placeholder and is replaced by
    # _enrich_submission_timestamps when the arXiv API is reachable.
    timestamp = datetime.combine(announcement_date, datetime.min.time(), timezone.utc).isoformat()
    return Paper(
        arxiv_id=bare_id,
        title=title,
        authors=authors,
        summary=summary,
        categories=categories,
        primary_category=primary or (categories[0] if categories else None),
        published=timestamp,
        updated=timestamp,
        abs_url=f"https://arxiv.org/abs/{bare_id}",
        pdf_url=f"https://arxiv.org/pdf/{bare_id}",
        comment=comment or None,
    )


def _enrich_submission_timestamps(
    *, base_url: str | None, papers: list[Paper], timeout_seconds: int
) -> tuple[list[Paper], str | None]:
    """Copy real submission timestamps from the API onto the listing records.

    Only ``published`` and ``updated`` are taken: the API record carries a
    versioned ID and the latest version's text, while the cache keeps the bare ID
    and the paper as it was announced.
    """
    if not base_url or not papers:
        return papers, None
    try:
        api_papers = fetch_papers_by_ids(
            base_url=base_url,
            ids=[paper.arxiv_id for paper in papers],
            timeout_seconds=timeout_seconds,
        )
    except (OSError, ParseError, ValueError) as exc:
        return papers, str(exc)

    enriched: list[Paper] = []
    for paper in papers:
        api_paper = api_papers.get(paper.arxiv_id)
        if api_paper is not None:
            paper = replace(paper, published=api_paper.published, updated=api_paper.updated)
        enriched.append(paper)
    return enriched, None


def _first_match(pattern: str, value: str) -> str | None:
    match = re.search(pattern, value, flags=re.S)
    if match is None:
        return None
    return match.group(1)


def _html_text(value: str | None) -> str:
    if not value:
        return ""
    without_scripts = re.sub(r"<script\b.*?</script>", " ", value, flags=re.S | re.I)
    without_anchors = re.sub(r"<a\b.*?</a>", " ", without_scripts, flags=re.S | re.I)
    without_tags = re.sub(r"<[^>]+>", " ", without_anchors)
    return clean_text(unescape(without_tags))
