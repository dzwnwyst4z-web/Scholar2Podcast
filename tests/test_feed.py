"""Tests for podcast RSS generation."""

from __future__ import annotations

import json
import tempfile
import unittest
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from scholar2podcast.feed import ATOM_NS, ITUNES_NS, FeedError, generate_feed


class GenerateFeedTests(unittest.TestCase):
    def _episode(self, directory: Path) -> tuple[Path, dict[str, object]]:
        audio = directory / "Lecture One.mp3"
        audio.write_bytes(b"podcast audio")
        metadata: dict[str, object] = {
            "schema_version": 1,
            "title": "Lecture One",
            "author": "Scholar, Ada",
            "description": "A useful lecture.",
            "publication_date": "2018-11-21",
            "source_url": "https://example.edu/items/1/",
            "audio_file": audio.name,
        }
        (directory / "Lecture One.json").write_text(json.dumps(metadata), encoding="utf-8")
        return audio, metadata

    def test_generates_podcast_rss(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            audio, metadata = self._episode(root)
            audio_size = audio.stat().st_size
            feed = generate_feed(
                root,
                root / "feed.xml",
                "https://podcast.example/private/",
                generated_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
            )
            document = ET.parse(feed)

        rss = document.getroot()
        item = rss.find("./channel/item")
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.findtext("title"), "Lecture One")
        self.assertEqual(item.findtext("pubDate"), "Wed, 21 Nov 2018 00:00:00 +0000")
        self.assertEqual(
            item.findtext("guid"),
            str(uuid.uuid5(uuid.NAMESPACE_URL, str(metadata["source_url"]))),
        )
        self.assertEqual(item.find("guid").get("isPermaLink"), "false")  # type: ignore[union-attr]
        enclosure = item.find("enclosure")
        self.assertEqual(enclosure.get("type"), "audio/mpeg")  # type: ignore[union-attr]
        self.assertEqual(enclosure.get("length"), str(audio_size))  # type: ignore[union-attr]
        self.assertIn("Lecture%20One.mp3", enclosure.get("url", ""))  # type: ignore[union-attr]
        self.assertEqual(item.findtext(f"{{{ITUNES_NS}}}author"), "Scholar, Ada")
        atom_link = rss.find(f"./channel/{{{ATOM_NS}}}link")
        self.assertEqual(atom_link.get("rel"), "self")  # type: ignore[union-attr]

    def test_rejects_invalid_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            self._episode(root)
            with self.assertRaisesRegex(FeedError, "base URL"):
                generate_feed(root, root / "feed.xml", "not-a-url")

    def test_requires_an_episode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            with self.assertRaisesRegex(FeedError, "No episodes"):
                generate_feed(root, root / "feed.xml", "https://example.com/")


if __name__ == "__main__":
    unittest.main()
