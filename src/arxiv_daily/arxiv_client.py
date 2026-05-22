from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .models import Paper

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
NS = {"atom": ATOM_NS, "arxiv": ARXIV_NS}
ARXIV_WEB_SEARCH_URL = "https://arxiv.org/search/advanced"
MAX_WEB_SEARCH_PAGE_SIZE = 200
HTML_SEARCH_PAGE_SIZES = (25, 50, 100, 200)
MIN_HTML_TIMEOUT_SECONDS = 60
DEFAULT_USER_AGENT = "arxiv-daily/0.1"
HTML_USER_AGENT = "Mozilla/5.0 arxiv-daily/0.1"
PHYSICS_ARCHIVES = {
    "astro-ph",
    "cond-mat",
    "gr-qc",
    "hep-ex",
    "hep-lat",
    "hep-ph",
    "hep-th",
    "math-ph",
    "nlin",
    "nucl-ex",
    "nucl-th",
    "physics",
    "quant-ph",
}
CATEGORY_PREFIX_CLASSIFICATION = {
    "cs.": "classification-computer_science",
    "econ.": "classification-economics",
    "eess.": "classification-eess",
    "math.": "classification-mathematics",
    "q-bio.": "classification-q_biology",
    "q-fin.": "classification-q_finance",
    "stat.": "classification-statistics",
}


def build_search_query(categories: Iterable[str], target_date: date | None = None) -> str:
    clean_categories = [item.strip() for item in categories if item.strip()]
    if not clean_categories:
        raise ValueError("At least one arXiv category is required.")

    category_query = " OR ".join(f"cat:{category}" for category in clean_categories)
    if len(clean_categories) > 1:
        category_query = f"({category_query})"

    if target_date is None:
        return category_query

    date_token = target_date.strftime("%Y%m%d")
    date_query = f"submittedDate:[{date_token}0000 TO {date_token}2359]"
    return f"{category_query} AND {date_query}"


def build_query_url(
    *,
    base_url: str,
    search_query: str,
    start: int,
    max_results: int,
    sort_by: str,
    sort_order: str,
) -> str:
    params = {
        "search_query": search_query,
        "start": str(start),
        "max_results": str(max_results),
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    return f"{base_url}?{urlencode(params)}"


def build_html_search_url(*, category: str, target_date: date, max_results: int) -> str:
    page_size = _html_page_size(max_results)
    params = {
        "advanced": "1",
        "terms-0-operator": "AND",
        "terms-0-term": category,
        "terms-0-field": "all",
        "classification-include_cross_list": "include",
        "date-filter_by": "date_range",
        "date-from_date": target_date.isoformat(),
        # arXiv advanced search rejects identical start/end dates. Fetch a two-day
        # window and filter exact submitted dates after parsing each result.
        "date-to_date": (target_date + timedelta(days=1)).isoformat(),
        "date-date_type": "submitted_date",
        "abstracts": "show",
        "size": str(page_size),
        "order": "-submitted_date",
    }
    params.update(_classification_params(category))
    return f"{ARXIV_WEB_SEARCH_URL}?{urlencode(params)}"


def fetch_papers(
    *,
    base_url: str,
    categories: list[str],
    target_date: date | None,
    max_results: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    timeout_seconds: int,
) -> tuple[str, list[Paper]]:
    search_query = build_search_query(categories, target_date)
    papers: list[Paper] = []
    start = 0

    while len(papers) < max_results:
        current_page_size = min(page_size, max_results - len(papers))
        url = build_query_url(
            base_url=base_url,
            search_query=search_query,
            start=start,
            max_results=current_page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        xml_bytes = fetch_url(url, timeout_seconds=timeout_seconds)
        page = parse_feed(xml_bytes)
        if not page:
            break
        papers.extend(page)
        if len(page) < current_page_size:
            break
        start += current_page_size

    return search_query, papers[:max_results]


def fetch_papers_from_html(
    *,
    categories: list[str],
    target_date: date,
    max_results: int,
    timeout_seconds: int,
) -> tuple[str, list[Paper]]:
    papers_by_id: dict[str, Paper] = {}
    urls: list[str] = []

    for category in categories:
        url = build_html_search_url(
            category=category,
            target_date=target_date,
            max_results=max_results,
        )
        urls.append(url)
        html = fetch_url(
            url,
            timeout_seconds=max(timeout_seconds, MIN_HTML_TIMEOUT_SECONDS),
            user_agent=HTML_USER_AGENT,
        ).decode("utf-8", errors="replace")
        for paper in parse_search_html(html, target_date=target_date):
            papers_by_id.setdefault(paper.arxiv_id, paper)
            if len(papers_by_id) >= max_results:
                break
        if len(papers_by_id) >= max_results:
            break

    papers = sorted(
        papers_by_id.values(),
        key=lambda paper: (paper.updated, paper.arxiv_id),
        reverse=True,
    )
    return " | ".join(urls), papers[:max_results]


def fetch_url(url: str, *, timeout_seconds: int, user_agent: str = DEFAULT_USER_AGENT) -> bytes:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def parse_search_html(html: str, *, target_date: date) -> list[Paper]:
    results = re.findall(r'<li class="arxiv-result">(.*?)</li>', html, flags=re.S)
    papers: list[Paper] = []

    for result in results:
        paper = _parse_search_result(result, target_date)
        if paper is not None:
            papers.append(paper)

    return papers


def parse_feed(xml_bytes: bytes) -> list[Paper]:
    root = ElementTree.fromstring(xml_bytes)
    papers: list[Paper] = []

    for entry in root.findall("atom:entry", NS):
        abs_url = _required_text(entry, "atom:id")
        arxiv_id = abs_url.rstrip("/").split("/")[-1]
        title = _clean_text(_required_text(entry, "atom:title"))
        summary = _clean_text(_required_text(entry, "atom:summary"))
        authors = [
            _clean_text(name.text or "")
            for name in entry.findall("atom:author/atom:name", NS)
            if (name.text or "").strip()
        ]
        categories = [
            category.attrib["term"]
            for category in entry.findall("atom:category", NS)
            if category.attrib.get("term")
        ]
        primary = entry.find("arxiv:primary_category", NS)
        links = entry.findall("atom:link", NS)
        pdf_url = _extract_pdf_url(links)

        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                summary=summary,
                categories=categories,
                primary_category=primary.attrib.get("term") if primary is not None else None,
                published=_required_text(entry, "atom:published"),
                updated=_required_text(entry, "atom:updated"),
                abs_url=abs_url,
                pdf_url=pdf_url,
                doi=_optional_text(entry, "arxiv:doi"),
                journal_ref=_optional_text(entry, "arxiv:journal_ref"),
                comment=_optional_text(entry, "arxiv:comment"),
            )
        )

    return papers


def _extract_pdf_url(links: list[ElementTree.Element]) -> str | None:
    for link in links:
        if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
            return link.attrib.get("href")
    return None


def _required_text(entry: ElementTree.Element, path: str) -> str:
    text = _optional_text(entry, path)
    if text is None:
        raise ValueError(f"Missing required arXiv Atom field: {path}")
    return text


def _optional_text(entry: ElementTree.Element, path: str) -> str | None:
    found = entry.find(path, NS)
    if found is None or found.text is None:
        return None
    text = _clean_text(found.text)
    return text or None


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _classification_params(category: str) -> dict[str, str]:
    if category in PHYSICS_ARCHIVES:
        return {
            "classification-physics": "y",
            "classification-physics_archives": category,
        }
    for prefix, field_name in CATEGORY_PREFIX_CLASSIFICATION.items():
        if category.startswith(prefix):
            return {field_name: "y"}
    return {}


def _html_page_size(max_results: int) -> int:
    for page_size in HTML_SEARCH_PAGE_SIZES:
        if max_results <= page_size:
            return page_size
    return MAX_WEB_SEARCH_PAGE_SIZE


def _parse_search_result(result: str, target_date: date) -> Paper | None:
    arxiv_id = _first_match(r'href="https://arxiv\.org/abs/([^"]+)"', result)
    if arxiv_id is None:
        arxiv_id = _first_match(r'href="/abs/([^"]+)"', result)
    if arxiv_id is None:
        return None

    submitted_date = _parse_submitted_date(result)
    first_submission_date = _parse_v1_date(result) or submitted_date
    if first_submission_date != target_date:
        return None

    title = _html_text(_first_match(r'<p class="title is-5 mathjax">\s*(.*?)\s*</p>', result))
    summary = _extract_abstract(result)
    authors = _extract_authors(result)
    categories = _extract_categories(result)
    updated = _date_to_arxiv_timestamp(submitted_date)
    published = _date_to_arxiv_timestamp(first_submission_date)

    return Paper(
        arxiv_id=re.sub(r"v\d+$", "", arxiv_id),
        title=title,
        authors=authors,
        summary=summary,
        categories=categories,
        primary_category=categories[0] if categories else None,
        published=published,
        updated=updated,
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        doi=_extract_doi(result),
        journal_ref=_extract_labeled_paragraph(result, "Journal ref"),
        comment=_extract_labeled_paragraph(result, "Comments"),
    )


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
    return _clean_text(unescape(without_tags))


def _extract_authors(result: str) -> list[str]:
    authors_block = _first_match(r'<p class="authors">(.*?)</p>', result)
    if authors_block is None:
        return []
    return [
        _html_text(author)
        for author in re.findall(r"<a\b[^>]*>(.*?)</a>", authors_block, flags=re.S)
        if _html_text(author)
    ]


def _extract_categories(result: str) -> list[str]:
    tags = re.findall(r'<span class="tag[^"]*"[^>]*>(.*?)</span>', result, flags=re.S)
    return [tag for tag in (_html_text(item) for item in tags) if tag]


def _extract_abstract(result: str) -> str:
    full_abstract = _first_match(
        r'<span class="abstract-full[^"]*"[^>]*>\s*(.*?)\s*</span>',
        result,
    )
    if full_abstract is not None:
        return _html_text(full_abstract)

    abstract_block = _first_match(r'<p class="abstract mathjax">\s*(.*?)\s*</p>', result)
    if abstract_block is None:
        return ""
    return _html_text(abstract_block).removeprefix("Abstract :").strip()


def _parse_submitted_date(result: str) -> date | None:
    submitted = _first_match(r"<strong>Submitted</strong>\s*([^;<]+)", result)
    if submitted is None:
        submitted = _first_match(
            r"has-text-weight-semibold[^>]*>Submitted</span>\s*([^;<]+)",
            result,
        )
    return _parse_display_date(submitted)


def _parse_v1_date(result: str) -> date | None:
    v1_submitted = _first_match(r"<strong>v1</strong>\s*submitted\s*([^;<]+)", result)
    if v1_submitted is None:
        v1_submitted = _first_match(
            r"has-text-weight-semibold[^>]*>v1</span>\s*submitted\s*([^;<]+)",
            result,
        )
    return _parse_display_date(v1_submitted)


def _parse_display_date(value: str | None) -> date | None:
    if value is None:
        return None
    clean_value = _html_text(value)
    try:
        return datetime.strptime(clean_value, "%d %B, %Y").date()
    except ValueError:
        return None


def _date_to_arxiv_timestamp(value: date | None) -> str:
    if value is None:
        value = date(1970, 1, 1)
    return datetime.combine(value, datetime.min.time(), timezone.utc).isoformat()


def _extract_doi(result: str) -> str | None:
    doi = _first_match(r'href="https://doi\.org/([^"]+)"', result)
    return _html_text(doi) if doi else None


def _extract_labeled_paragraph(result: str, label: str) -> str | None:
    for paragraph in re.findall(r'<p class="comments is-size-7">\s*(.*?)\s*</p>', result, re.S):
        text = _html_text(paragraph)
        prefix = f"{label}:"
        if text.startswith(prefix):
            return text.removeprefix(prefix).strip() or None
    return None
