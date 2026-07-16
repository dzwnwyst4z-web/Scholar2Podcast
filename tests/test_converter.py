"""Unit tests for ffmpeg audio conversion orchestration."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scholar2podcast.converter import AudioConversionError, convert_to_mp3, safe_episode_stem


class SafeEpisodeStemTests(unittest.TestCase):
    def test_preserves_readable_title(self) -> None:
        self.assertEqual(
            safe_episode_stem('Session 4: Christ / "Figure" Films'),
            "Session 4 - Christ - Figure - Films",
        )


class ConvertToMp3Tests(unittest.TestCase):
    def test_builds_podcast_quality_ffmpeg_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            video = root / "lecture.mp4"
            video.write_bytes(b"video")

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                Path(command[-1]).write_bytes(b"mp3")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("scholar2podcast.converter.subprocess.run", side_effect=fake_run) as run:
                result = convert_to_mp3(
                    video,
                    "Lecture One",
                    root / "episodes",
                    author="Scholar, Ada",
                    description="A useful lecture.",
                    publication_date="2018-11-21",
                    ffmpeg_path="ffmpeg",
                )

            command = run.call_args.args[0]
            self.assertIn("128k", command)
            self.assertIn("44100", command)
            self.assertIn("title=Lecture One", command)
            self.assertIn("artist=Scholar, Ada", command)
            self.assertIn("comment=A useful lecture.", command)
            self.assertIn("date=2018-11-21", command)
            self.assertEqual(result.path.name, "Lecture One.mp3")
            self.assertEqual(result.path.read_bytes(), b"mp3")

    def test_refuses_to_overwrite_episode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            video = root / "lecture.mp4"
            video.write_bytes(b"video")
            episodes = root / "episodes"
            episodes.mkdir()
            (episodes / "Lecture One.mp3").write_bytes(b"existing")
            with self.assertRaisesRegex(AudioConversionError, "already exists"):
                convert_to_mp3(video, "Lecture One", episodes, ffmpeg_path="ffmpeg")


if __name__ == "__main__":
    unittest.main()
