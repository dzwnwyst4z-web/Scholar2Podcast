"""Unit tests for link discovery and response filename handling."""

from __future__ import annotations

import unittest

import requests

from scholar2podcast.downloader import (
    ScholarDownloadError,
    _filename_from_response,
    discover_download_url,
    discover_title,
)


class DiscoverDownloadUrlTests(unittest.TestCase):
    def test_prefers_digital_commons_viewcontent_link(self) -> None:
        html = """
        <a href="/bible_film_christ_figures/">Browse collection</a>
        <a class="btn download-button"
           href="/cgi/viewcontent.cgi?article=1007&amp;context=bible_film_christ_figures">
          Download
        </a>
        """
        found = discover_download_url(
            html, "https://scholar.csl.edu/bible_film_christ_figures/8/"
        )
        self.assertEqual(
            found,
            "https://scholar.csl.edu/cgi/viewcontent.cgi?article=1007&context=bible_film_christ_figures",
        )

    def test_resolves_relative_direct_media_link(self) -> None:
        html = '<a href="files/lecture.mp4">Watch video</a>'
        found = discover_download_url(html, "https://example.edu/items/8/")
        self.assertEqual(found, "https://example.edu/items/8/files/lecture.mp4")

    def test_raises_friendly_error_when_no_link_exists(self) -> None:
        with self.assertRaisesRegex(ScholarDownloadError, "No downloadable"):
            discover_download_url("<p>No media here</p>", "https://example.edu/item/1/")


class FilenameTests(unittest.TestCase):
    def _response(self, url: str, **headers: str) -> requests.Response:
        response = requests.Response()
        response.url = url
        response.headers.update(headers)
        return response

    def test_uses_content_disposition_filename(self) -> None:
        response = self._response(
            "https://example.edu/cgi/viewcontent.cgi?article=1",
            **{"Content-Disposition": 'attachment; filename="Lecture One.mp4"'},
        )
        self.assertEqual(_filename_from_response(response, "fallback"), "Lecture One.mp4")

    def test_uses_content_type_for_cgi_url(self) -> None:
        response = self._response(
            "https://example.edu/cgi/viewcontent.cgi?article=1",
            **{"Content-Type": "video/quicktime; charset=binary"},
        )
        self.assertEqual(_filename_from_response(response, "collection-8"), "collection-8.mov")


class TitleTests(unittest.TestCase):
    def test_prefers_citation_title(self) -> None:
        html = """
        <meta name="citation_title" content="Lecture One">
        <h1>Less authoritative heading</h1>
        """
        self.assertEqual(discover_title(html), "Lecture One")

    def test_falls_back_to_heading(self) -> None:
        self.assertEqual(discover_title("<h1>  Lecture   Two </h1>"), "Lecture Two")


if __name__ == "__main__":
    unittest.main()
