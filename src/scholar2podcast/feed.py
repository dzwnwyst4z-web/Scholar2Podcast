"""Generate a standards-compliant private podcast RSS feed."""

from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NS = "http://www.w3.org/2005/Atom"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("atom", ATOM_NS)
ET.register_namespace("content", CONTENT_NS)


class FeedError(RuntimeError):
    """A friendly, expected failure while generating the podcast feed."""


@dataclass(frozen=True)
class FeedEpisode:
    title: str
    author: str | None
    description: str
    published: datetime
    source_url: str
    audio_path: Path


def _publication_datetime(value: object, audio_path: Path) -> datetime:
    if isinstance(value, str):
        for date_format in ("%Y-%m-%d", "%Y"):
            try:
                return datetime.strptime(value, date_format).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return datetime.fromtimestamp(audio_path.stat().st_mtime, timezone.utc)


def load_episodes(episodes_dir: Path) -> list[FeedEpisode]:
    """Load valid JSON/MP3 episode pairs, newest first."""

    episodes: list[FeedEpisode] = []
    for sidecar in sorted(episodes_dir.glob("*.json")):
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            title = str(payload["title"]).strip()
            source_url = str(payload["source_url"]).strip()
            audio_path = episodes_dir / str(payload["audio_file"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise FeedError(f"Invalid episode metadata file {sidecar}: {exc}") from exc
        if not title or not source_url:
            raise FeedError(f"Episode metadata is missing a title or source URL: {sidecar}")
        if not audio_path.is_file():
            raise FeedError(f"Episode audio is missing: {audio_path}")
        episodes.append(
            FeedEpisode(
                title=title,
                author=str(payload["author"]).strip() if payload.get("author") else None,
                description=str(payload.get("description") or ""),
                published=_publication_datetime(payload.get("publication_date"), audio_path),
                source_url=source_url,
                audio_path=audio_path,
            )
        )
    episodes.sort(key=lambda episode: episode.published, reverse=True)
    return episodes


def _text(parent: ET.Element, tag: str, value: str) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = value
    return child


def generate_feed(
    episodes_dir: Path,
    feed_path: Path,
    base_url: str,
    *,
    generated_at: datetime | None = None,
) -> Path:
    """Generate ``feed.xml`` atomically from stored episode metadata."""

    parsed_url = urlparse(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise FeedError("Podcast base URL must be a complete http:// or https:// URL.")
    base_url = base_url.rstrip("/") + "/"
    episodes = load_episodes(episodes_dir)
    if not episodes:
        raise FeedError(f"No episodes with metadata were found in {episodes_dir}.")

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    _text(channel, "title", "Scholar2Podcast")
    _text(channel, "link", base_url)
    _text(channel, "description", "A private podcast of lectures from Scholar.")
    _text(channel, "language", "en-us")
    _text(channel, "lastBuildDate", format_datetime(now))
    ET.SubElement(
        channel,
        f"{{{ATOM_NS}}}link",
        {
            "href": urljoin(base_url, quote(feed_path.name)),
            "rel": "self",
            "type": "application/rss+xml",
        },
    )
    _text(channel, f"{{{ITUNES_NS}}}author", "Scholar2Podcast")
    _text(channel, f"{{{ITUNES_NS}}}explicit", "false")
    _text(channel, f"{{{ITUNES_NS}}}type", "episodic")
    ET.SubElement(channel, f"{{{ITUNES_NS}}}category", {"text": "Education"})

    for episode in episodes:
        item = ET.SubElement(channel, "item")
        _text(item, "title", episode.title)
        _text(item, "link", episode.source_url)
        description = episode.description or f"Lecture by {episode.author or 'Unknown author'}"
        _text(item, "description", description)
        _text(item, f"{{{CONTENT_NS}}}encoded", description)
        _text(item, "pubDate", format_datetime(episode.published))
        guid = _text(
            item,
            "guid",
            str(uuid.uuid5(uuid.NAMESPACE_URL, episode.source_url)),
        )
        guid.set("isPermaLink", "false")
        if episode.author:
            _text(item, f"{{{ITUNES_NS}}}author", episode.author)
        _text(item, f"{{{ITUNES_NS}}}explicit", "false")
        enclosure_url = urljoin(base_url, f"episodes/{quote(episode.audio_path.name)}")
        ET.SubElement(
            item,
            "enclosure",
            {
                "url": enclosure_url,
                "length": str(episode.audio_path.stat().st_size),
                "type": "audio/mpeg",
            },
        )

    ET.indent(rss, space="  ")
    tree = ET.ElementTree(rss)
    temporary = feed_path.with_suffix(feed_path.suffix + ".part")
    try:
        feed_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(temporary, encoding="utf-8", xml_declaration=True)
        temporary.replace(feed_path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise FeedError(f"Could not write podcast feed: {exc}") from exc
    return feed_path

