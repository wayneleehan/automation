from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_save_url_runs_full_workflow(tmp_path: Path) -> None:
    webpage = {
        "url": "https://example.com/article",
        "title": "Example Article",
        "text": "Readable article text.",
        "success": True,
        "error": None,
    }
    summary = {
        "success": True,
        "markdown": "# Example Article\n\nA concise summary.",
        "error": None,
    }

    with (
        patch(
            "app.save_service.fetch_webpage_content",
            return_value=webpage,
        ) as scrape,
        patch(
            "app.save_service.summarize_to_markdown",
            return_value=summary,
        ) as summarize,
        patch("app.main.settings", SimpleNamespace(vault_path=tmp_path)),
    ):
        response = client.post(
            "/api/save-url",
            json={"url": "https://example.com/article"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Saved to Obsidian vault"
    assert body["title"] == "Example Article"
    assert Path(body["path"]).name.endswith("-example-article.md")
    assert Path(body["path"]).read_text(encoding="utf-8") == summary["markdown"]
    scrape.assert_called_once_with("https://example.com/article")
    summarize.assert_called_once_with(
        "Example Article",
        "https://example.com/article",
        "Readable article text.",
    )


def test_save_url_rejects_invalid_url() -> None:
    response = client.post("/api/save-url", json={"url": "not-a-url"})

    assert response.status_code == 422


def test_save_url_reports_scraper_failure() -> None:
    webpage = {
        "url": "https://example.com/",
        "title": "",
        "text": "",
        "success": False,
        "error": "network unavailable",
    }

    with patch(
        "app.save_service.fetch_webpage_content",
        return_value=webpage,
    ):
        response = client.post(
            "/api/save-url",
            json={"url": "https://example.com"},
        )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Could not fetch webpage: network unavailable"
    }


def test_save_url_reports_summarizer_failure() -> None:
    webpage = {
        "url": "https://example.com/",
        "title": "Example Domain",
        "text": "Example text.",
        "success": True,
        "error": None,
    }
    summary = {
        "success": False,
        "markdown": "",
        "error": "OPENAI_API_KEY is not configured.",
    }

    with (
        patch("app.save_service.fetch_webpage_content", return_value=webpage),
        patch(
            "app.save_service.summarize_to_markdown",
            return_value=summary,
        ),
    ):
        response = client.post(
            "/api/save-url",
            json={"url": "https://example.com"},
        )

    assert response.status_code == 502
    assert response.json() == {
        "detail": (
            "Could not summarize webpage: "
            "OPENAI_API_KEY is not configured."
        )
    }
