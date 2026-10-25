from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .announcement_batch import (
    CatchupOutOfRange,
    build_catchup_url,
    build_listing_url,
    fetch_papers_from_announcement_batch,
)
from .arxiv_client import (
    download_paper_source_or_pdf,
    fetch_papers_by_ids,
    strip_version,
)
from .config import load_config
from .scholar_client import bootstrap_scholar_profile
from .submitted_slice import fetch_submitted_slice

SUBMITTED_SLICE_SOURCE = "api-submitted-slice"
ANNOUNCEMENT_SOURCES = {"list", "catchup"}


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

    fetch = subparsers.add_parser("fetch", help="Fetch one arXiv announcement batch into a cache")
    fetch.add_argument(
        "--date",
        default=None,
        help=(
            "Announcement date, YYYY-MM-DD. Defaults to today. The current batch is read from "
            "arxiv.org/list/<category>/new; a past one from arxiv.org/catchup/<category>/<date> "
            "(the past 90 days)."
        ),
    )
    fetch.add_argument(
        "--category",
        action="append",
        default=[],
        help="arXiv category, repeatable. Defaults to config.",
    )
    fetch.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Optional cap; the whole batch is kept by default and a cap is reported.",
    )
    fetch.add_argument("--config", default="config/default.toml", help="Path to TOML config.")
    fetch.add_argument(
        "--output-dir", default=None, help="Root output directory for raw arXiv caches."
    )
    fetch.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the candidate listing/catch-up URLs and output path without network access.",
    )
    fetch.add_argument(
        "--no-api",
        action="store_true",
        help=(
            "Never call the arXiv API. Skips the optional enrichment that fills real submission "
            "timestamps (the batch itself always comes from the arxiv.org listing page), and "
            "disables the submittedDate-slice fallback for dates beyond the catch-up window."
        ),
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
        help="Batch date (source folder), YYYY-MM-DD. If omitted, auto-resolves from cache/API.",
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
    max_results = args.max_results
    output_root = Path(args.output_dir or path_config["raw_arxiv_dir"])
    output_path = _output_path(output_root, target_date, categories)
    api_url = str(arxiv_config["base_url"])
    timeout_seconds = int(arxiv_config["request_timeout_seconds"])

    if args.dry_run:
        preview_url = {
            "date": target_date.isoformat(),
            "categories": categories,
            "listing_url": " | ".join(
                build_listing_url(category=category) for category in categories
            ),
            "catchup_url": " | ".join(
                build_catchup_url(category=category, target_date=target_date)
                for category in categories
            ),
            "output_path": str(output_path),
            "max_results": max_results,
            "api_enrichment": not args.no_api,
        }
        print(json.dumps(preview_url, indent=2, ensure_ascii=False))
        return 0

    try:
        query, papers, source = fetch_papers_from_announcement_batch(
            base_url=None if args.no_api else api_url,
            categories=categories,
            target_date=target_date,
            timeout_seconds=timeout_seconds,
        )
    except CatchupOutOfRange as exc:
        if output_path.exists():
            raise RuntimeError(
                f"{exc} A cache already exists at {output_path}, so it is left untouched. "
                "Delete that file explicitly if you really want to re-fetch this date."
            ) from exc
        if args.no_api:
            raise RuntimeError(
                f"{exc} The only remaining route is a submittedDate slice from the arXiv API, "
                "which --no-api disables; drop --no-api to use it."
            ) from exc
        print(
            f"Warning: {exc}\n"
            "Falling back to a submittedDate slice from the arXiv API. This is NOT the "
            "announcement batch: it misses papers announced that day but submitted earlier and "
            "includes some papers announced the next day. Record this in the report."
        )
        query, papers = fetch_submitted_slice(
            base_url=api_url,
            categories=categories,
            target_date=target_date,
            timeout_seconds=timeout_seconds,
        )
        source = SUBMITTED_SLICE_SOURCE

    if max_results is not None and len(papers) > max_results:
        print(
            f"Warning: fetched {len(papers)} papers; keeping the first {max_results} "
            "because --max-results was given."
        )
        query = f"{query} [truncated to {max_results} of {len(papers)} papers]"
        papers = papers[:max_results]

    payload = {
        "schema_version": 1,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "date": target_date.isoformat(),
        "categories": categories,
        "source": source,
        "date_convention": (
            "submitted_date_slice" if source == SUBMITTED_SLICE_SOURCE else "announcement_batch"
        ),
        "query": query,
        "count": len(papers),
        "papers": [paper.to_dict() for paper in papers],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(papers)} papers to {output_path}")
    return 0


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
        # 1. Determine the date folder: --date, else a local cache, else the API
        target_date = None
        if args.date:
            target_date = _parse_date(args.date)
        else:
            target_date = _find_paper_date_locally(output_root, arxiv_id)
            if not target_date:
                print(
                    f"ArXiv ID {arxiv_id} not found in any local date folder. "
                    "Querying the arXiv API for its submission date..."
                )
                wait_for_rate_limit()
                target_date = _fetch_paper_date_from_api(
                    arxiv_id,
                    base_url=str(arxiv_config["base_url"]),
                    timeout_seconds=timeout_seconds,
                )
                if target_date:
                    print(
                        f"Warning: filing {arxiv_id} under its v1 submission date {target_date}, "
                        "not an announcement date; arXiv publishes no announcement date for it. "
                        "Pass --date to choose the folder explicitly."
                    )
                else:
                    target_date = date.today()
                    print(
                        f"Warning: Could not determine a date for {arxiv_id}. "
                        f"Defaulting to today: {target_date}"
                    )

        # The output directory for this paper's source, always under the bare ID so
        # that every version of a paper shares one folder
        paper_dir = output_root / target_date.isoformat() / "sources" / strip_version(arxiv_id)

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
    """Find the date folder that already holds this paper, ignoring version suffixes.

    Every date folder is scanned. An announcement-batch cache that lists the paper
    beats any other cache (a legacy submitted-date cache or a slice), which beats
    a ``sources/<id>`` folder from an earlier download; within one rank the
    earliest date wins, so the result never depends on directory order.
    """
    if not output_root.exists():
        return None
    bare_id = strip_version(arxiv_id)
    candidates: list[tuple[int, date]] = []
    for date_dir in output_root.iterdir():
        try:
            folder_date = date.fromisoformat(date_dir.name)
        except ValueError:
            continue
        rank = _local_paper_rank(date_dir, bare_id=bare_id)
        if rank is not None:
            candidates.append((rank, folder_date))
    return min(candidates)[1] if candidates else None


def _local_paper_rank(date_dir: Path, *, bare_id: str) -> int | None:
    rank = None
    for json_file in date_dir.glob("*.json"):
        try:
            payload = json.loads(json_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        if any(
            strip_version(str(paper.get("arxiv_id", ""))) == bare_id
            for paper in payload.get("papers", [])
        ):
            if payload.get("source") in ANNOUNCEMENT_SOURCES:
                return 0
            rank = 1
    if rank is None and (date_dir / "sources" / bare_id).is_dir():
        rank = 2
    return rank


def _fetch_paper_date_from_api(
    arxiv_id: str, *, base_url: str, timeout_seconds: int = 30
) -> date | None:
    # pylint: disable=broad-exception-caught
    """Look the paper up in the arXiv API to recover its v1 submission date."""
    try:
        papers = fetch_papers_by_ids(
            base_url=base_url, ids=[arxiv_id], timeout_seconds=timeout_seconds
        )
        paper = papers.get(strip_version(arxiv_id))
        if paper is not None and paper.published:
            # E.g. "2026-05-14T12:00:00Z" -> "2026-05-14"
            return date.fromisoformat(paper.published.split("T")[0])
    except Exception as exc:
        print(f"Failed to fetch paper metadata from arXiv API: {exc}")
    return None


if __name__ == "__main__":
    raise SystemExit(main())
