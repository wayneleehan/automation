from unittest.mock import Mock, patch

import requests

from app.scraper import fetch_webpage_content


def test_uses_trafilatura_extraction_first() -> None:
    extracted = {
        "title": "Example Article Title",
        "text": "Clean article text.",
    }

    with (
        patch("app.scraper.trafilatura.fetch_url", return_value="<html />"),
        patch(
            "app.scraper.trafilatura.bare_extraction",
            return_value=extracted,
        ) as bare_extraction,
        patch("app.scraper.requests.get") as requests_get,
    ):
        result = fetch_webpage_content("https://example.com/article")

    assert result == {
        "url": "https://example.com/article",
        "title": "Example Article Title",
        "text": "Clean article text.",
        "success": True,
        "error": None,
    }
    bare_extraction.assert_called_once()
    requests_get.assert_not_called()


def test_falls_back_to_requests_and_beautifulsoup() -> None:
    response = Mock()
    response.text = """
        <html>
          <head><title>Fallback Article</title></head>
          <body>
            <nav>Navigation</nav>
            <main>
              <h1>Fallback Article</h1>
              <p>Readable fallback content.</p>
              <script>ignored()</script>
            </main>
          </body>
        </html>
    """
    response.raise_for_status.return_value = None

    with (
        patch("app.scraper.trafilatura.fetch_url", return_value=None),
        patch("app.scraper.requests.get", return_value=response) as requests_get,
    ):
        result = fetch_webpage_content("https://example.com/fallback")

    assert result == {
        "url": "https://example.com/fallback",
        "title": "Fallback Article",
        "text": "Fallback Article Readable fallback content.",
        "success": True,
        "error": None,
    }
    requests_get.assert_called_once()


def test_uses_untitled_when_extraction_has_no_title() -> None:
    with (
        patch("app.scraper.trafilatura.fetch_url", return_value="<html />"),
        patch(
            "app.scraper.trafilatura.bare_extraction",
            return_value={"title": None, "text": "Article text."},
        ),
    ):
        result = fetch_webpage_content("https://example.com/no-title")

    assert result["success"] is True
    assert result["title"] == "Untitled"


def test_returns_structured_error_when_both_extractors_fail() -> None:
    with (
        patch(
            "app.scraper.trafilatura.fetch_url",
            side_effect=RuntimeError("download error"),
        ),
        patch(
            "app.scraper.requests.get",
            side_effect=requests.Timeout("request timed out"),
        ),
    ):
        result = fetch_webpage_content("https://example.com/unavailable")

    assert result["url"] == "https://example.com/unavailable"
    assert result["title"] == ""
    assert result["text"] == ""
    assert result["success"] is False
    assert result["error"] is not None
    assert "download error" in result["error"]
    assert "request timed out" in result["error"]
