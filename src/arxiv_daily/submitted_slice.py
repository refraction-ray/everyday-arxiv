"""Submitted-date slice of a single UTC day, from the arXiv API.

This is a *degraded fallback*, never a primary source. arXiv publishes no
announcement-date field in its API, so an announcement batch older than the
catch-up window cannot be rebuilt. When such a batch is asked for and nothing is
cached locally, the CLI settles for this slice: ``submittedDate`` covers one UTC
day only, so it misses papers announced that day but submitted earlier (weekend
and moderator-held submissions) and includes papers whose batch comes tomorrow.

Every cache and report produced through this path must say so, and the slice must
never be compared against the ``(showing N of N entries)`` listing figure.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable
from urllib.parse import urlencode

from .arxiv_client import fetch_url, parse_feed
from .models import Paper

API_PAGE_SIZE = 100


def build_submitted_slice_query(categories: Iterable[str], target_date: date) -> str:
    clean_categories = [item.strip() for item in categories if item.strip()]
    if not clean_categories:
        raise ValueError("At least one arXiv category is required.")

    category_query = " OR ".join(f"cat:{category}" for category in clean_categories)
    if len(clean_categories) > 1:
        category_query = f"({category_query})"

    date_token = target_date.strftime("%Y%m%d")
    return f"{category_query} AND submittedDate:[{date_token}0000 TO {date_token}2359]"


def build_submitted_slice_url(*, base_url: str, search_query: str, start: int) -> str:
    params = {
        "search_query": search_query,
        "start": str(start),
        "max_results": str(API_PAGE_SIZE),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return f"{base_url}?{urlencode(params)}"


def fetch_submitted_slice(
    *, base_url: str, categories: list[str], target_date: date, timeout_seconds: int
) -> tuple[str, list[Paper]]:
    """Fetch the whole ``submittedDate`` slice of one UTC day, paging until exhausted."""
    search_query = build_submitted_slice_query(categories, target_date)
    papers: list[Paper] = []
    while True:
        url = build_submitted_slice_url(
            base_url=base_url, search_query=search_query, start=len(papers)
        )
        page = parse_feed(fetch_url(url, timeout_seconds=timeout_seconds))
        papers.extend(page)
        if len(page) < API_PAGE_SIZE:
            return search_query, papers
