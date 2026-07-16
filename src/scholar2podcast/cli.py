"""Command-line interface for Scholar2Podcast."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from scholar2podcast.converter import AudioConversionError, convert_to_mp3
from scholar2podcast.downloader import ScholarDownloadError, download_scholar_media
from scholar2podcast.feed import FeedError, generate_feed
from scholar2podcast.metadata import (
    MetadataError,
    find_episode_by_source_url,
    save_metadata,
)
from scholar2podcast.site import generate_index


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scholar2podcast",
        description="Download Scholar media and extract a podcast-quality MP3.",
    )
    parser.add_argument("url", help="Scholar item page URL")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("downloads"),
        help="download destination (default: ./downloads)",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="replace an existing destination file"
    )
    parser.add_argument(
        "--episodes-dir",
        type=Path,
        default=Path("episodes"),
        help="MP3 destination (default: ./episodes)",
    )
    parser.add_argument(
        "--feed-path",
        type=Path,
        default=Path("feed.xml"),
        help="RSS feed destination (default: ./feed.xml)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SCHOLAR2PODCAST_BASE_URL", "http://localhost:8000/"),
        help="public URL serving feed.xml and episodes/ (default: local test server)",
    )
    parser.add_argument(
        "--index-path",
        type=Path,
        default=Path("index.html"),
        help="landing-page destination (default: ./index.html)",
    )
    parser.add_argument(
        "--delete-video",
        action="store_true",
        help="delete the downloaded source video after successful publishing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        print("error: URL must be a complete http:// or https:// URL", file=sys.stderr)
        return 2

    try:
        existing = find_episode_by_source_url(args.episodes_dir, args.url)
        if existing and not args.overwrite:
            print(f"Episode already published: {existing}")
            return 0

        print(f"Fetching Scholar page: {args.url}")
        result = download_scholar_media(
            args.url, args.output_dir, overwrite=args.overwrite
        )
        print(f"Found media: {result.download_url}")
        print(f"Saved video: {result.path} ({result.bytes_downloaded / 1_048_576:.1f} MB)")
        print(f"Converting audio: {result.metadata.title}")
        episode = convert_to_mp3(
            result.path,
            result.metadata.title,
            args.episodes_dir,
            author=result.metadata.author,
            description=result.metadata.description,
            publication_date=result.metadata.publication_date,
            overwrite=args.overwrite,
        )
        metadata_path = save_metadata(result.metadata, episode.path)
        feed_path = generate_feed(args.episodes_dir, args.feed_path, args.base_url)
        index_path = generate_index(args.episodes_dir, args.index_path)
        if args.delete_video:
            result.path.unlink(missing_ok=True)
    except (ScholarDownloadError, AudioConversionError, MetadataError, FeedError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Saved episode: {episode.path} ({episode.bytes_written / 1_048_576:.1f} MB)")
    print(f"Saved metadata: {metadata_path}")
    print(f"Updated feed: {feed_path}")
    print(f"Updated landing page: {index_path}")
    if args.delete_video:
        print(f"Deleted source video: {result.path}")
    return 0
