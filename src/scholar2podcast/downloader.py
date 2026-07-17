"""Discover and download media from Scholar/Digital Commons item pages."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scholar2podcast.metadata import (
    EpisodeMetadata,
    MetadataError,
    extract_metadata,
)

USER_AGENT = "Scholar2Podcast/0.1 (personal-use media downloader)"
CHUNK_SIZE = 1024 * 256


class ScholarDownloadError(RuntimeError):
    """A friendly, expected failure while discovering or downloading media."""


@dataclass(frozen=True)
class DownloadResult:
    """Information about a completed download."""

    source_url: str
    download_url: str
    metadata: EpisodeMetadata
    path: Path
    bytes_downloaded: int


def discover_download_url(page_html: str, page_url: str) -> str:
    """Return the most likely direct media URL found in a Scholar page.

    Digital Commons templates differ between collections. We rank all links
    instead of depending on one fragile CSS selector, while strongly preferring
    the conventional ``viewcontent.cgi`` endpoint and visible download links.
    """

    soup = BeautifulSoup(page_html, "html.parser")
    ranked: list[tuple[int, str]] = []

    for meta in soup.find_all("meta"):
        key = str(meta.get("name") or meta.get("property") or "").lower()
        content = meta.get("content")
        if not content or not isinstance(content, str):
            continue
        if key in {"citation_pdf_url", "citation_fulltext_html_url"}:
            ranked.append((70, urljoin(page_url, content)))

    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        absolute_url = urljoin(page_url, href)
        searchable = " ".join(
            (
                anchor.get_text(" ", strip=True),
                str(anchor.get("title") or ""),
                str(anchor.get("class") or ""),
                str(anchor.get("id") or ""),
            )
        ).lower()
        score = 0
        if "viewcontent.cgi" in absolute_url.lower():
            score += 100
        if "/type/native/" in absolute_url.lower():
            score += 200
        if "type=additional" in absolute_url.lower() or "/type/additional/" in absolute_url.lower():
            score -= 200
        if "download" in searchable:
            score += 60
        if "/download" in urlparse(absolute_url).path.lower():
            score += 40
        if re.search(r"\.(?:mp4|mov|m4v|webm|avi)(?:$|[?#])", absolute_url, re.I):
            score += 80
        if score:
            ranked.append((score, absolute_url))

    if not ranked:
        raise ScholarDownloadError(
            "No downloadable media link was found on the Scholar page."
        )
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


def discover_title(page_html: str) -> str | None:
    """Extract the lecture title needed for the MP3 filename and ID3 tag."""

    try:
        return extract_metadata(page_html, "").title
    except MetadataError:
        return None


def _filename_from_response(response: requests.Response, fallback_stem: str) -> str:
    """Create a safe filename using HTTP headers, URL, and content type."""

    disposition = response.headers.get("Content-Disposition", "")
    encoded = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.I)
    plain = re.search(r'filename="?([^";]+)', disposition, re.I)
    candidate = unquote(encoded.group(1)) if encoded else plain.group(1) if plain else ""

    if not candidate:
        url_name = Path(unquote(urlparse(response.url).path)).name
        if url_name and "." in url_name and not url_name.lower().endswith(".cgi"):
            candidate = url_name

    extension_by_type = {
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
        "audio/mpeg": ".mp3",
    }
    if not candidate:
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        candidate = fallback_stem + extension_by_type.get(content_type, ".mp4")

    # Discard directories and characters that are awkward or unsafe on macOS.
    candidate = Path(candidate).name
    candidate = re.sub(r"[^\w.()\[\] -]+", "_", candidate, flags=re.UNICODE).strip(". ")
    return candidate or f"{fallback_stem}.mp4"


def _page_stem(page_url: str) -> str:
    parts = [part for part in urlparse(page_url).path.split("/") if part]
    raw = "-".join(parts[-2:]) if parts else "scholar-download"
    return re.sub(r"[^\w.-]+", "-", raw).strip("-.") or "scholar-download"


def _print_progress(downloaded: int, total: int | None) -> None:
    if total:
        percent = min(downloaded / total * 100, 100)
        message = f"\rDownloading: {percent:6.1f}% ({downloaded / 1_048_576:.1f} MB)"
    else:
        message = f"\rDownloading: {downloaded / 1_048_576:.1f} MB"
    print(message, end="", file=sys.stderr, flush=True)


def _write_chunks(
    chunks: Iterable[bytes], destination: BinaryIO, total: int | None
) -> int:
    downloaded = 0
    for chunk in chunks:
        if not chunk:
            continue
        destination.write(chunk)
        downloaded += len(chunk)
        _print_progress(downloaded, total)
    print(file=sys.stderr)
    return downloaded


def download_scholar_media(
    page_url: str,
    output_dir: Path,
    *,
    overwrite: bool = False,
    timeout: float = 30,
    session: requests.Session | None = None,
) -> DownloadResult:
    """Discover and stream a Scholar item's media file to ``output_dir``."""

    http = session or requests.Session()
    http.headers.setdefault("User-Agent", USER_AGENT)
    try:
        page_response = http.get(page_url, timeout=timeout)
        page_response.raise_for_status()
        direct_url = discover_download_url(page_response.text, page_response.url)
        metadata = extract_metadata(page_response.text, page_response.url)

        media_response = http.get(direct_url, stream=True, timeout=timeout)
        media_response.raise_for_status()
    except requests.RequestException as exc:
        raise ScholarDownloadError(f"Network request failed: {exc}") from exc

    content_type = media_response.headers.get("Content-Type", "").split(";", 1)[0].lower()
    if content_type and not (
        content_type.startswith("video/") or content_type.startswith("audio/")
    ):
        media_response.close()
        raise ScholarDownloadError(
            f"Discovered download is not audio or video (Content-Type: {content_type})."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    filename = _filename_from_response(media_response, _page_stem(page_url))
    destination = output_dir / filename
    if destination.exists() and not overwrite:
        media_response.close()
        raise ScholarDownloadError(
            f"Destination already exists: {destination}. Use --overwrite to replace it."
        )

    total_header = media_response.headers.get("Content-Length")
    total = int(total_header) if total_header and total_header.isdigit() else None
    temporary = destination.with_suffix(destination.suffix + ".part")
    try:
        with temporary.open("wb") as output:
            count = _write_chunks(media_response.iter_content(CHUNK_SIZE), output, total)
        temporary.replace(destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ScholarDownloadError(f"Could not save download: {exc}") from exc
    finally:
        media_response.close()

    return DownloadResult(
        page_url,
        direct_url,
        metadata,
        destination,
        count,
    )
