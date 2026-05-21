from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GOOGLE_SCHOLAR_BASE_URL = "https://scholar.google.com"
ARXIV_ID_RE = re.compile(r"arXiv:?\s*([a-z-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?", re.I)
NON_ARTICLE_PATTERNS = [
    "aps march meeting abstracts",
    "bulletin of the american physical society",
    "us patent",
    "patent app",
    "patent",
]


@dataclass
class ScholarPaper:
    title: str
    year: int | None
    authors: list[str]
    venue: str | None
    abstract: str
    arxiv_id: str
    doi: str
    citation_count: int | None
    scholar_url: str
    source_url: str
    publication_date: str
    record_type: str
    include_in_profile: bool
    exclusion_reason: str
    keywords: list[str] = field(default_factory=list)
    notes: str = ""

    def to_profile_record(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "year": self.year,
            "authors": self.authors,
            "abstract": self.abstract,
            "arxiv_id": self.arxiv_id,
            "doi": self.doi,
            "keywords": self.keywords,
            "notes": self.notes,
            "venue": self.venue,
            "publication_date": self.publication_date,
            "citation_count": self.citation_count,
            "scholar_url": self.scholar_url,
            "source_url": self.source_url,
            "record_type": self.record_type,
            "include_in_profile": self.include_in_profile,
            "exclusion_reason": self.exclusion_reason,
        }


def bootstrap_scholar_profile(
    *,
    scholar_url: str,
    user_id: str | None,
    from_html: Path | None,
    output_jsonl: Path,
    raw_output: Path,
    pagesize: int,
    limit: int | None,
    include_details: bool,
    delay_seconds: float,
    timeout_seconds: int,
    include_non_articles: bool,
) -> dict[str, Any]:
    resolved_user_id = user_id or extract_user_id(scholar_url)
    if not resolved_user_id:
        raise ValueError(
            "Could not find a Google Scholar user id in the URL. "
            "Pass --user-id or use a profile URL containing ?user=..."
        )

    if from_html is None:
        profile_html = fetch_text(
            build_profile_url(resolved_user_id, cstart=0, pagesize=pagesize),
            timeout_seconds=timeout_seconds,
        )
    else:
        profile_html = from_html.read_text(encoding="utf-8")
    listed_papers = parse_profile_page(profile_html)
    if not listed_papers:
        if "Our systems have detected unusual traffic" in profile_html:
            raise RuntimeError(
                "Google Scholar returned an unusual-traffic page. "
                "Wait for the block to expire or provide a saved complete profile HTML "
                "via --from-html."
            )
        raise RuntimeError("No Google Scholar paper rows found in the profile HTML.")
    if limit is not None:
        listed_papers = listed_papers[:limit]

    all_papers: list[ScholarPaper] = []
    raw_details: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, listed in enumerate(listed_papers):
        detail: dict[str, Any] = {}
        if include_details and listed.get("scholar_url"):
            if index > 0 and delay_seconds > 0:
                time.sleep(delay_seconds)
            try:
                detail_html = fetch_text(
                    str(listed["scholar_url"]),
                    timeout_seconds=timeout_seconds,
                )
                detail = parse_detail_page(detail_html)
            except (HTTPError, URLError, TimeoutError) as exc:
                detail = {"detail_error": f"{type(exc).__name__}: {exc}"}
                errors.append(
                    {
                        "title": listed.get("title"),
                        "scholar_url": listed.get("scholar_url"),
                        "error": detail["detail_error"],
                    }
                )
            raw_details.append(
                {
                    "title": listed.get("title"),
                    "scholar_url": listed.get("scholar_url"),
                    "detail": detail,
                }
            )

        all_papers.append(merge_scholar_record(listed, detail))

    profile_papers = [
        paper for paper in all_papers if include_non_articles or paper.include_in_profile
    ]

    raw_payload = {
        "schema_version": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "input_url": scholar_url,
        "user_id": resolved_user_id,
        "profile_url": build_profile_url(resolved_user_id, cstart=0, pagesize=pagesize),
        "from_html": str(from_html) if from_html else "",
        "count": len(profile_papers),
        "raw_count": len(all_papers),
        "include_details": include_details,
        "include_non_articles": include_non_articles,
        "detail_error_count": len(errors),
        "detail_errors": errors,
        "papers": [asdict(paper) for paper in profile_papers],
        "all_records": [asdict(paper) for paper in all_papers],
        "details": raw_details,
    }

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_jsonl, [paper.to_profile_record() for paper in profile_papers])
    raw_output.write_text(
        json.dumps(raw_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return raw_payload


def extract_user_id(url: str) -> str | None:
    query = parse_qs(urlparse(url).query)
    user_values = query.get("user")
    if user_values:
        return user_values[0]
    match = re.search(r"[?&]user=([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else None


def build_profile_url(user_id: str, *, cstart: int, pagesize: int) -> str:
    params = {
        "hl": "en",
        "user": user_id,
        "cstart": str(cstart),
        "pagesize": str(pagesize),
    }
    return f"{GOOGLE_SCHOLAR_BASE_URL}/citations?{urlencode(params)}"


def fetch_text(url: str, *, timeout_seconds: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36 arxiv-daily/0.1"
            )
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_profile_page(html: str) -> list[dict[str, Any]]:
    rows = re.findall(r'<tr class="gsc_a_tr">(.*?)</tr>', html, flags=re.S)
    papers: list[dict[str, Any]] = []
    for row in rows:
        title_match = re.search(r'<a href="([^"]+)" class="gsc_a_at">(.*?)</a>', row, flags=re.S)
        if not title_match:
            continue
        gray_values = re.findall(r'<div class="gs_gray">(.*?)</div>', row, flags=re.S)
        citation_match = re.search(r'class="gsc_a_ac gs_ibl">(\d*)</a>', row)
        year_match = re.search(r'class="gsc_a_h gsc_a_hc gs_ibl">(\d{4})</span>', row)
        title = clean_html(title_match.group(2))
        venue = clean_html(gray_values[1]) if len(gray_values) > 1 else ""
        source_text = " ".join([title, venue])

        papers.append(
            {
                "title": title,
                "authors": split_authors(clean_html(gray_values[0])) if gray_values else [],
                "venue": venue,
                "year": int(year_match.group(1)) if year_match else None,
                "citation_count": parse_int(citation_match.group(1)) if citation_match else None,
                "scholar_url": urljoin(GOOGLE_SCHOLAR_BASE_URL, unescape(title_match.group(1))),
                "arxiv_id": extract_arxiv_id(source_text),
            }
        )
    return papers


def parse_detail_page(html: str) -> dict[str, Any]:
    detail: dict[str, Any] = {}
    title_link = re.search(r'<a class="gsc_oci_title_link" href="([^"]+)".*?>(.*?)</a>', html, re.S)
    if title_link:
        detail["source_url"] = unescape(title_link.group(1))
        detail["title"] = clean_html(title_link.group(2))

    description = re.search(
        r'id="gsc_oci_descr"><div class="gsh_small">(.*?)</div>',
        html,
        flags=re.S,
    )
    if description:
        detail["abstract"] = clean_html(description.group(1))

    for field_name in ["Authors", "Publication date", "Journal", "Conference", "Book"]:
        value = extract_detail_field(html, field_name)
        if value:
            detail[field_name.lower().replace(" ", "_")] = value

    text_for_arxiv = " ".join(str(value) for value in detail.values())
    detail["arxiv_id"] = extract_arxiv_id(text_for_arxiv)
    return detail


def extract_detail_field(html: str, field_name: str) -> str:
    escaped = re.escape(field_name)
    pattern = (
        r'<div class="gs_scl"><div class="gsc_oci_field">'
        + escaped
        + r'</div><div class="gsc_oci_value">(.*?)</div></div>'
    )
    match = re.search(pattern, html, flags=re.S)
    return clean_html(match.group(1)) if match else ""


def merge_scholar_record(listed: dict[str, Any], detail: dict[str, Any]) -> ScholarPaper:
    venue = (
        detail.get("journal")
        or detail.get("conference")
        or detail.get("book")
        or listed.get("venue")
        or ""
    )
    source_url = detail.get("source_url", "")
    arxiv_id = detail.get("arxiv_id") or listed.get("arxiv_id") or extract_arxiv_id(source_url)
    authors = split_authors(str(detail.get("authors", ""))) or list(listed.get("authors", []))
    record_type, include_in_profile, exclusion_reason = classify_record(
        title=str(detail.get("title") or listed.get("title") or ""),
        venue=str(venue),
        source_url=str(source_url),
    )

    return ScholarPaper(
        title=str(detail.get("title") or listed.get("title") or ""),
        year=listed.get("year"),
        authors=authors,
        venue=venue or None,
        abstract=str(detail.get("abstract") or ""),
        arxiv_id=arxiv_id,
        doi="",
        citation_count=listed.get("citation_count"),
        scholar_url=str(listed.get("scholar_url") or ""),
        source_url=source_url,
        publication_date=str(detail.get("publication_date") or ""),
        record_type=record_type,
        include_in_profile=include_in_profile,
        exclusion_reason=exclusion_reason,
    )


def classify_record(title: str, venue: str, source_url: str) -> tuple[str, bool, str]:
    text = " ".join([title, venue, source_url]).lower()
    for pattern in NON_ARTICLE_PATTERNS:
        if pattern in text:
            if "patent" in pattern:
                return (
                    "patent",
                    False,
                    "Patent entries are excluded from the paper profile by default.",
                )
            return (
                "conference_abstract",
                False,
                "Conference abstracts are excluded from the paper profile by default.",
            )
    if not venue.strip() and not source_url.strip():
        return "unknown", False, "Records without venue or source URL need manual review."
    return "article", True, ""


def split_authors(value: str) -> list[str]:
    if not value:
        return []
    return [
        author.strip() for author in value.split(",") if author.strip() and author.strip() != "..."
    ]


def extract_arxiv_id(value: str) -> str:
    match = ARXIV_ID_RE.search(value)
    return match.group(1) if match else ""


def parse_int(value: str) -> int | None:
    return int(value) if value.isdigit() else None


def clean_html(value: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", value)
    return " ".join(unescape(no_tags).split())


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file_handle:
        for record in records:
            file_handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
