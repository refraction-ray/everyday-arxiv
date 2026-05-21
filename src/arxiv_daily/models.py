from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    title: str
    authors: list[str]
    summary: str
    categories: list[str]
    primary_category: str | None
    published: str
    updated: str
    abs_url: str
    pdf_url: str | None
    doi: str | None = None
    journal_ref: str | None = None
    comment: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
