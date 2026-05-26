from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from xml.etree.ElementTree import ParseError

from .arxiv_client import (
    build_search_query,
    fetch_papers,
    fetch_papers_from_html,
    download_paper_source_or_pdf,
    fetch_url,
    parse_feed,
)
from .config import load_config
from .models import Paper
from .scholar_client import bootstrap_scholar_profile


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "fetch":
        return run_fetch(args)
    if args.command == "download":
        return run_download(args)
    if args.command == "profile":
        return run_profile(args)

    parser.error("No command provided.")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="arXiv Daily assistant tooling")
    subparsers = parser.add_subparsers(dest="command")

    fetch = subparsers.add_parser("fetch", help="Fetch arXiv metadata into a JSON cache")
    fetch.add_argument(
        "--date", default=None, help="Target arXiv submitted date, YYYY-MM-DD. Defaults to today."
    )
    fetch.add_argument(
        "--category",
        action="append",
        default=[],
        help="arXiv category, repeatable. Defaults to config.",
    )
    fetch.add_argument("--max-results", type=int, default=None, help="Maximum papers to fetch.")
    fetch.add_argument("--page-size", type=int, default=None, help="arXiv API page size.")
    fetch.add_argument("--config", default="config/default.toml", help="Path to TOML config.")
    fetch.add_argument(
        "--output-dir", default=None, help="Root output directory for raw arXiv caches."
    )
    fetch.add_argument(
        "--dry-run", action="store_true", help="Print query and output path without network access."
    )
    fetch.add_argument(
        "--source",
        choices=["auto", "api", "html"],
        default="auto",
        help="Metadata source. auto uses the arXiv API first, then arxiv.org HTML search.",
    )

    profile = subparsers.add_parser("profile", help="Initialize or update local user profile files")
    profile_subparsers = profile.add_subparsers(dest="profile_command")
    scholar = profile_subparsers.add_parser(
        "bootstrap-scholar",
        help="Bootstrap user_profile from a public Google Scholar profile",
    )
    scholar.add_argument(
        "url", help="Google Scholar profile URL. Use --user-id if URL has no user=..."
    )
    scholar.add_argument(
        "--user-id", default=None, help="Google Scholar user id, e.g. Ut8nVqIAAAAJ."
    )
    scholar.add_argument(
        "--from-html",
        default=None,
        help="Parse a saved Google Scholar profile HTML file instead of fetching the list page.",
    )
    scholar.add_argument(
        "--output-jsonl",
        default="user_profile/papers.local.jsonl",
        help="Private JSONL output for user papers.",
    )
    scholar.add_argument(
        "--raw-output",
        default="user_profile/google_scholar.local.json",
        help="Private raw JSON export.",
    )
    scholar.add_argument("--pagesize", type=int, default=100, help="Google Scholar list page size.")
    scholar.add_argument("--limit", type=int, default=None, help="Maximum papers to export.")
    scholar.add_argument(
        "--no-details",
        action="store_true",
        help="Only parse list metadata; skip per-paper detail pages and abstracts.",
    )
    scholar.add_argument(
        "--delay-seconds",
        type=float,
        default=1.0,
        help="Delay between Scholar detail requests.",
    )
    scholar.add_argument("--timeout-seconds", type=int, default=30, help="HTTP request timeout.")
    scholar.add_argument(
        "--include-non-articles",
        action="store_true",
        help="Include patents, conference abstracts, and unknown records in papers.local.jsonl.",
    )

    download = subparsers.add_parser(
        "download",
        help="Download paper sources (source preferred, fallback to PDF) and extract them",
    )
    download.add_argument(
        "arxiv_ids",
        nargs="+",
        help="Specific arXiv ID(s) to download.",
    )
    download.add_argument(
        "--date",
        default=None,
        help="Target arXiv submitted date, YYYY-MM-DD. If omitted, auto-resolves from cache/API.",
    )
    download.add_argument(
        "--delay-seconds",
        type=float,
        default=3.0,
        help="Delay between sequential paper downloads in seconds to prevent rate limiting.",
    )
    download.add_argument("--config", default="config/default.toml", help="Path to TOML config.")
    download.add_argument(
        "--output-dir", default=None, help="Root output directory for raw arXiv caches."
    )
    download.add_argument(
        "--dry-run", action="store_true", help="Print download plans without downloading."
    )

    return parser


def run_fetch(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    arxiv_config: dict[str, Any] = config["arxiv"]
    path_config: dict[str, Any] = config["paths"]

    target_date = _parse_date(args.date) if args.date else date.today()
    categories = args.category or list(arxiv_config["default_categories"])
    max_results = args.max_results or int(arxiv_config["max_results"])
    page_size = args.page_size or int(arxiv_config["page_size"])
    output_root = Path(args.output_dir or path_config["raw_arxiv_dir"])
    output_path = _output_path(output_root, target_date, categories)
    search_query = build_search_query(categories, target_date)

    if args.dry_run:
        preview_url = {
            "date": target_date.isoformat(),
            "categories": categories,
            "search_query": search_query,
            "output_path": str(output_path),
            "max_results": max_results,
            "page_size": page_size,
            "source": args.source,
        }
        print(json.dumps(preview_url, indent=2, ensure_ascii=False))
        return 0

    query, papers, source, fallback_error = _fetch_with_source(
        source=args.source,
        arxiv_config=arxiv_config,
        categories=categories,
        target_date=target_date,
        max_results=max_results,
        page_size=page_size,
    )

    payload = {
        "schema_version": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "date": target_date.isoformat(),
        "categories": categories,
        "source": source,
        "query": query,
        "count": len(papers),
        "papers": [paper.to_dict() for paper in papers],
    }
    if fallback_error:
        payload["fallback_error"] = fallback_error

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(papers)} papers to {output_path}")
    return 0


def _fetch_with_source(
    *,
    source: str,
    arxiv_config: dict[str, Any],
    categories: list[str],
    target_date: date,
    max_results: int,
    page_size: int,
) -> tuple[str, list[Paper], str, str | None]:
    if source == "html":
        query, papers = fetch_papers_from_html(
            categories=categories,
            target_date=target_date,
            max_results=max_results,
            timeout_seconds=int(arxiv_config["request_timeout_seconds"]),
        )
        return query, papers, "html", None

    try:
        query, papers = fetch_papers(
            base_url=str(arxiv_config["base_url"]),
            categories=categories,
            target_date=target_date,
            max_results=max_results,
            page_size=page_size,
            sort_by=str(arxiv_config["sort_by"]),
            sort_order=str(arxiv_config["sort_order"]),
            timeout_seconds=int(arxiv_config["request_timeout_seconds"]),
        )
        return query, papers, "api", None
    except (HTTPError, URLError, OSError, ParseError, ValueError) as exc:
        if source == "api":
            raise
        query, papers = fetch_papers_from_html(
            categories=categories,
            target_date=target_date,
            max_results=max_results,
            timeout_seconds=int(arxiv_config["request_timeout_seconds"]),
        )
        return query, papers, "html", f"arXiv API failed before HTML fallback: {exc}"


def run_profile(args: argparse.Namespace) -> int:
    if args.profile_command == "bootstrap-scholar":
        payload = bootstrap_scholar_profile(
            scholar_url=args.url,
            user_id=args.user_id,
            from_html=Path(args.from_html) if args.from_html else None,
            output_jsonl=Path(args.output_jsonl),
            raw_output=Path(args.raw_output),
            pagesize=args.pagesize,
            limit=args.limit,
            include_details=not args.no_details,
            delay_seconds=args.delay_seconds,
            timeout_seconds=args.timeout_seconds,
            include_non_articles=args.include_non_articles,
        )
        print(
            "Wrote "
            f"{payload['count']} papers to {args.output_jsonl}; "
            f"raw export to {args.raw_output}"
        )
        return 0

    raise SystemExit("No profile subcommand provided.")


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid --date {value!r}; expected YYYY-MM-DD.") from exc


def _output_path(output_root: Path, target_date: date, categories: list[str]) -> Path:
    category_token = "+".join(_safe_filename(category) for category in categories)
    return output_root / target_date.isoformat() / f"{category_token}.json"


def _safe_filename(value: str) -> str:
    safe = []
    for char in value:
        if char.isalnum() or char in {".", "-", "_"}:
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe)


def run_download(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    arxiv_config: dict[str, Any] = config["arxiv"]
    path_config: dict[str, Any] = config["paths"]

    output_root = Path(args.output_dir or path_config["raw_arxiv_dir"])
    timeout_seconds = int(arxiv_config["request_timeout_seconds"])

    success_count = 0
    failed_count = 0
    last_request_time = 0.0

    def wait_for_rate_limit() -> None:
        nonlocal last_request_time
        if args.delay_seconds > 0 and last_request_time > 0:
            elapsed = time.time() - last_request_time
            sleep_time = args.delay_seconds - elapsed
            if sleep_time > 0:
                print(f"Waiting {sleep_time:.1f} seconds to avoid rate limiting...")
                time.sleep(sleep_time)
        last_request_time = time.time()

    for arxiv_id in args.arxiv_ids:
        # 1. Determine submission date
        target_date = None
        if args.date:
            target_date = _parse_date(args.date)
        else:
            # Try to resolve date locally
            target_date = _find_paper_date_locally(output_root, arxiv_id)
            if not target_date:
                # If not found locally, query API to determine date
                print(
                    f"ArXiv ID {arxiv_id} not found in local cache. Querying API to resolve date..."
                )
                wait_for_rate_limit()
                target_date = _fetch_paper_date_from_api(arxiv_id, timeout_seconds)
                if not target_date:
                    target_date = date.today()
                    print(
                        f"Warning: Could not determine submission date for {arxiv_id}. "
                        f"Defaulting to today: {target_date}"
                    )

        # The output directory for this paper's source
        paper_dir = output_root / target_date.isoformat() / "sources" / arxiv_id

        if args.dry_run:
            print(f"[DRY-RUN] Would download source for {arxiv_id} to {paper_dir}")
            success_count += 1
            continue

        # 2. Check if already exists to avoid redundant calls
        if paper_dir.exists() and any(paper_dir.iterdir()):
            print(f"Paper {arxiv_id} already has files in {paper_dir}. Skipping.")
            success_count += 1
            continue

        # 3. Handle delay before download request
        wait_for_rate_limit()

        # 4. Download and extract
        _, success = download_paper_source_or_pdf(
            arxiv_id,
            paper_dir,
            timeout_seconds=timeout_seconds,
        )
        if success:
            success_count += 1
        else:
            failed_count += 1

    print(f"Download complete: {success_count} succeeded, {failed_count} failed.")
    return 0 if failed_count == 0 else 1


def _find_paper_date_locally(output_root: Path, arxiv_id: str) -> date | None:
    # pylint: disable=broad-exception-caught
    """
    Tries to find the paper in existing local date-batch metadata JSON files.
    """
    if not output_root.exists():
        return None
    for date_dir in output_root.iterdir():
        if not date_dir.is_dir():
            continue
        try:
            d = date.fromisoformat(date_dir.name)
        except ValueError:
            continue

        # Look for json files in this folder
        for json_file in date_dir.glob("*.json"):
            if json_file.name == "run_metadata.json":
                continue
            try:
                with json_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    for paper in data.get("papers", []):
                        if paper.get("arxiv_id") == arxiv_id:
                            return d
            except Exception:
                continue
    return None


def _fetch_paper_date_from_api(arxiv_id: str, timeout_seconds: int = 30) -> date | None:
    # pylint: disable=broad-exception-caught
    """
    Queries the arXiv API for the paper to retrieve its published date.
    """
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    try:
        xml_bytes = fetch_url(url, timeout_seconds=timeout_seconds)
        papers = parse_feed(xml_bytes)
        if papers:
            pub_str = papers[0].published
            if pub_str:
                # E.g. "2026-05-14T12:00:00Z" -> "2026-05-14"
                return date.fromisoformat(pub_str.split("T")[0])
    except Exception as exc:
        print(f"Failed to fetch paper metadata from arXiv API: {exc}")
    return None


if __name__ == "__main__":
    raise SystemExit(main())
