"""Convert downloaded lecture videos into podcast-compatible MP3 files."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class AudioConversionError(RuntimeError):
    """A friendly, expected failure during audio conversion."""


@dataclass(frozen=True)
class ConversionResult:
    """Information about a completed MP3 conversion."""

    source_path: Path
    path: Path
    title: str
    bytes_written: int


def safe_episode_stem(title: str) -> str:
    """Return a readable macOS-safe filename stem without losing the title."""

    stem = re.sub(r'[/:*?"<>|]+', " - ", title)
    stem = " ".join(stem.split()).strip(". ")
    stem = re.sub(r"(?:\s*-\s*){2,}", " - ", stem)
    return stem[:180].rstrip(". ") or "Untitled episode"


def convert_to_mp3(
    video_path: Path,
    title: str,
    episodes_dir: Path,
    *,
    author: str | None = None,
    description: str | None = None,
    publication_date: str | None = None,
    overwrite: bool = False,
    ffmpeg_path: str | None = None,
) -> ConversionResult:
    """Extract podcast-quality MP3 audio and embed the lecture title.

    A constant 128 kbps bitrate and 44.1 kHz sample rate give predictable file
    sizes and work across Overcast, Apple Podcasts, and Pocket Casts.
    """

    ffmpeg = ffmpeg_path or shutil.which("ffmpeg")
    if not ffmpeg:
        raise AudioConversionError(
            "ffmpeg was not found. Install it with: brew install ffmpeg"
        )
    if not video_path.is_file():
        raise AudioConversionError(f"Downloaded video does not exist: {video_path}")

    try:
        episodes_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AudioConversionError(f"Could not create episodes directory: {exc}") from exc

    destination = episodes_dir / f"{safe_episode_stem(title)}.mp3"
    if destination.exists() and not overwrite:
        raise AudioConversionError(
            f"Episode already exists: {destination}. Use --overwrite to replace it."
        )

    temporary = destination.with_suffix(".mp3.part")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-map",
        "0:a:0",
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-id3v2_version",
        "3",
        "-metadata",
        f"title={title}",
    ]
    if author:
        command.extend(("-metadata", f"artist={author}"))
    if description:
        command.extend(("-metadata", f"comment={description}"))
    if publication_date:
        command.extend(("-metadata", f"date={publication_date}"))
    command.extend(("-f", "mp3", str(temporary)))
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "unknown ffmpeg error"
            raise AudioConversionError(f"ffmpeg could not extract the audio: {detail}")
        temporary.replace(destination)
    except OSError as exc:
        raise AudioConversionError(f"Could not run ffmpeg or save the MP3: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)

    return ConversionResult(video_path, destination, title, destination.stat().st_size)
