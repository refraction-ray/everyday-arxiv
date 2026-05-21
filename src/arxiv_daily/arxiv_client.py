from __future__ import annotations

from datetime import date
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .models import Paper

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
NS = {"atom": ATOM_NS, "arxiv": ARXIV_NS}


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


def fetch_url(url: str, *, timeout_seconds: int) -> bytes:
    request = Request(url, headers={"User-Agent": "arxiv-daily/0.1"})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


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
