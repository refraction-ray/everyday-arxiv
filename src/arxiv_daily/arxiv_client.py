from __future__ import annotations

import gzip
import io
import re
import tarfile
import zipfile
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from xml.etree import ElementTree

import requests

from .models import Paper

ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"
NS = {"atom": ATOM_NS, "arxiv": ARXIV_NS}
MIN_HTML_TIMEOUT_SECONDS = 60
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)
BROWSER_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def strip_version(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id)


def fetch_papers_by_ids(
    *, base_url: str, ids: Iterable[str], timeout_seconds: int
) -> dict[str, Paper]:
    clean_ids = [strip_version(item) for item in ids if item]
    if not clean_ids:
        return {}

    params = {"id_list": ",".join(clean_ids), "max_results": str(len(clean_ids))}
    xml_bytes = fetch_url(f"{base_url}?{urlencode(params)}", timeout_seconds=timeout_seconds)
    return {strip_version(paper.arxiv_id): paper for paper in parse_feed(xml_bytes)}


def fetch_html_page(url: str, *, timeout_seconds: int) -> str:
    return fetch_url(url, timeout_seconds=max(timeout_seconds, MIN_HTML_TIMEOUT_SECONDS)).decode(
        "utf-8", errors="replace"
    )


def fetch_url(url: str, *, timeout_seconds: int) -> bytes:
    """GET ``url``; an HTTP status error keeps its code as ``urllib.error.HTTPError``."""
    headers = {"User-Agent": BROWSER_USER_AGENT, **BROWSER_REQUEST_HEADERS}
    try:
        response = requests.get(url, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        return response.content
    except requests.HTTPError as exc:
        raise HTTPError(url, exc.response.status_code, str(exc), None, None) from exc
    except requests.RequestException as exc:
        raise URLError(str(exc)) from exc


def parse_feed(xml_bytes: bytes) -> list[Paper]:
    root = ElementTree.fromstring(xml_bytes)
    papers: list[Paper] = []

    for entry in root.findall("atom:entry", NS):
        abs_url = _required_text(entry, "atom:id")
        arxiv_id = abs_url.rstrip("/").split("/")[-1]
        title = clean_text(_required_text(entry, "atom:title"))
        summary = clean_text(_required_text(entry, "atom:summary"))
        authors = [
            clean_text(name.text or "")
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
    text = clean_text(found.text)
    return text or None


def clean_text(value: str) -> str:
    return " ".join(value.split())


def extract_source_data(data: bytes, arxiv_id: str, output_dir: Path) -> None:
    # pylint: disable=too-many-branches,broad-exception-caught
    """
    Extracts raw source package data to output_dir, transparently handling
    various compression and container formats (.tar.gz, .zip, single .gz, PDF).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Gzip compression (starts with \x1f\x8b)
    if data.startswith(b"\x1f\x8b"):
        try:
            # First attempt: parse as gzipped tarball (.tar.gz / .tgz)
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
                # Safe path extraction: prevent directory traversal attacks
                for member in tar.getmembers():
                    member_path = Path(member.name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise ValueError(f"Dangerous path in tarball member: {member.name}")
                tar.extractall(path=output_dir)
                return
        except (tarfile.ReadError, ValueError, tarfile.CompressionError):
            # Fallback: treat as a single gzipped file (e.g. single .tex file)
            try:
                decompressed = gzip.decompress(data)
                # Inspect magic bytes of the decompressed content
                if decompressed.startswith(b"%PDF"):
                    ext = "pdf"
                elif decompressed.startswith(b"%!"):
                    ext = "ps"
                else:
                    ext = "tex"
                dest_file = output_dir / f"{arxiv_id}.{ext}"
                dest_file.write_bytes(decompressed)
                return
            except Exception:
                pass

    # 2. Zip compression (starts with PK\x03\x04)
    elif data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                # Safe path extraction
                for name in zf.namelist():
                    member_path = Path(name)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise ValueError(f"Dangerous path in zip member: {name}")
                zf.extractall(path=output_dir)
                return
        except Exception:
            pass

    # 3. PDF file (starts with %PDF)
    elif data.startswith(b"%PDF"):
        dest_file = output_dir / f"{arxiv_id}.pdf"
        dest_file.write_bytes(data)
        return

    # 4. Fallback: try decoding as text (raw LaTeX) or save as raw binary
    try:
        data.decode("utf-8")
        dest_file = output_dir / f"{arxiv_id}.tex"
        dest_file.write_bytes(data)
    except UnicodeDecodeError:
        dest_file = output_dir / f"{arxiv_id}.tar.gz"
        dest_file.write_bytes(data)


def download_paper_source_or_pdf(
    arxiv_id: str,
    output_dir: Path,
    pdf_url: str | None = None,
    timeout_seconds: int = 30,
) -> tuple[str, bool]:
    # pylint: disable=broad-exception-caught
    """
    Downloads paper source (preferred) or PDF fallback, and extracts it to output_dir.
    Returns:
        tuple (download_type, success)
        download_type: "source", "pdf", or "failed"
    """
    source_url = f"https://arxiv.org/src/{arxiv_id}"

    # Try downloading the source package first
    try:
        print(f"Downloading source from {source_url}...")
        data = fetch_url(source_url, timeout_seconds=timeout_seconds)
        extract_source_data(data, arxiv_id, output_dir)
        print(f"Successfully downloaded and extracted source for {arxiv_id} to {output_dir}")
        return "source", True
    except Exception as exc:
        print(f"Failed to download source for {arxiv_id}: {exc}")

    # Fallback to downloading the PDF
    if not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    try:
        print(f"Falling back to downloading PDF from {pdf_url}...")
        data = fetch_url(pdf_url, timeout_seconds=timeout_seconds)
        output_dir.mkdir(parents=True, exist_ok=True)
        dest_file = output_dir / f"{arxiv_id}.pdf"
        dest_file.write_bytes(data)
        print(f"Successfully downloaded fallback PDF for {arxiv_id} to {dest_file}")
        return "pdf", True
    except Exception as exc:
        print(f"Failed to download fallback PDF for {arxiv_id}: {exc}")
        return "failed", False
