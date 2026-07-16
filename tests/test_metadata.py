"""Tests for Scholar metadata extraction and JSON persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scholar2podcast.metadata import (
    EpisodeMetadata,
    MetadataError,
    extract_metadata,
    save_metadata,
)


class ExtractMetadataTests(unittest.TestCase):
    def test_extracts_digital_commons_metadata(self) -> None:
        html = """
        <meta name="bepress_citation_title" content="Lecture One">
        <meta name="bepress_citation_author" content="Scholar, Ada">
        <meta name="description" content="A useful lecture.">
        <meta name="bepress_citation_date" content="2018">
        <meta name="bepress_citation_online_date" content="2018/11/21">
        """
        metadata = extract_metadata(html, "https://example.edu/item/1/")
        self.assertEqual(metadata.title, "Lecture One")
        self.assertEqual(metadata.author, "Scholar, Ada")
        self.assertEqual(metadata.description, "A useful lecture.")
        self.assertEqual(metadata.publication_date, "2018-11-21")
        self.assertEqual(metadata.source_url, "https://example.edu/item/1/")

    def test_allows_missing_optional_fields(self) -> None:
        metadata = extract_metadata("<h1>Lecture Two</h1>", "https://example.edu/2/")
        self.assertIsNone(metadata.author)
        self.assertIsNone(metadata.description)
        self.assertIsNone(metadata.publication_date)

    def test_requires_a_title(self) -> None:
        with self.assertRaisesRegex(MetadataError, "No lecture title"):
            extract_metadata("<p>No metadata</p>", "https://example.edu/3/")


class SaveMetadataTests(unittest.TestCase):
    def test_writes_json_sidecar(self) -> None:
        metadata = EpisodeMetadata(
            title="Lecture One",
            author="Scholar, Ada",
            description="A useful lecture.",
            publication_date="2018-11-21",
            source_url="https://example.edu/1/",
        )
        with tempfile.TemporaryDirectory() as temporary_dir:
            episode = Path(temporary_dir) / "Lecture One.mp3"
            episode.write_bytes(b"mp3")
            path = save_metadata(metadata, episode)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["audio_file"], "Lecture One.mp3")
        self.assertEqual(payload["publication_date"], "2018-11-21")


if __name__ == "__main__":
    unittest.main()

