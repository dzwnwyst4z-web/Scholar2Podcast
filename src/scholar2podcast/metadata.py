"""Extract and persist episode metadata from Scholar item pages."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup


class MetadataError(RuntimeError):
    """A friendly, expected failure while extracting or storing metadata."""


@dataclass(frozen=True)
class EpisodeMetadata:
    """Metadata needed by an episode and, later, its podcast feed entry."""

    title: str
    author: str | None
    description: str | None
    publication_date: str | None
    source_url: str


def _meta_values(soup: BeautifulSoup) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for meta in soup.find_all("meta"):
        name = str(meta.get("name") or meta.get("property") or "").lower()
        content = meta.get("content")
        if name and isinstance(content, str) and content.strip():
            values.setdefault(name, []).append(" ".join(content.split()))
    return values


def _first(values: dict[str, list[str]], *names: str) -> str | None:
    for name in names:
        candidates = values.get(name.lower())
        if candidates:
            return candidates[0]
    return None


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    for date_format in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return value if len(value) == 4 and value.isdigit() else None


def extract_metadata(page_html: str, source_url: str) -> EpisodeMetadata:
    """Extract metadata across common Digital Commons template variants."""

    soup = BeautifulSoup(page_html, "html.parser")
    values = _meta_values(soup)
    title = _first(
        values,
        "bepress_citation_title",
        "citation_title",
        "dc.title",
        "og:title",
    )
    if not title:
        heading = soup.find("h1")
        title = " ".join(heading.get_text(" ", strip=True).split()) if heading else ""
    if not title:
        raise MetadataError("No lecture title was found on the Scholar page.")

    return EpisodeMetadata(
        title=title,
        author=_first(
            values,
            "bepress_citation_author",
            "citation_author",
            "dc.creator",
            "author",
        ),
        description=_first(
            values,
            "description",
            "og:description",
            "citation_abstract",
            "dc.description",
        ),
        publication_date=_normalize_date(
            _first(
                values,
                "bepress_citation_online_date",
                "citation_online_date",
                "citation_publication_date",
                "bepress_citation_date",
                "dc.date",
            )
        ),
        source_url=source_url,
    )


def save_metadata(metadata: EpisodeMetadata, episode_path: Path) -> Path:
    """Atomically save a human-readable JSON sidecar beside an MP3 episode."""

    destination = episode_path.with_suffix(".json")
    temporary = destination.with_suffix(".json.part")
    payload = {"schema_version": 1, **asdict(metadata), "audio_file": episode_path.name}
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise MetadataError(f"Could not save episode metadata: {exc}") from exc
    return destination

