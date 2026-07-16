"""Tests for the generated GitHub Pages landing page."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scholar2podcast.site import generate_index


class GenerateIndexTests(unittest.TestCase):
    def test_generates_episode_player_and_escapes_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            audio = root / "Lecture One.mp3"
            audio.write_bytes(b"mp3")
            (root / "Lecture One.json").write_text(
                json.dumps(
                    {
                        "title": "Lecture <One>",
                        "author": "Scholar & Author",
                        "description": "Useful & safe.",
                        "publication_date": "2018-11-21",
                        "source_url": "https://example.edu/items/1/",
                        "audio_file": audio.name,
                    }
                ),
                encoding="utf-8",
            )
            index = generate_index(root, root / "index.html")
            document = index.read_text(encoding="utf-8")
        self.assertIn("Lecture &lt;One&gt;", document)
        self.assertIn("Scholar &amp; Author", document)
        self.assertIn("episodes/Lecture%20One.mp3", document)
        self.assertIn("<audio controls", document)


if __name__ == "__main__":
    unittest.main()

