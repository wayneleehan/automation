from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.raw_service import RAW_TEXT_LIMIT, build_raw_markdown, save_raw_url


def _webpage(text: str = "Readable raw content.") -> dict:
    return {
        "url": "https://example.com/article",
        "title": "Example Article",
        "text": text,
        "success": True,
        "error": None,
    }


def test_build_raw_markdown_uses_required_template_and_limit() -> None:
    markdown = build_raw_markdown(
        "Example Article",
        "https://example.com/article",
        "A" * (RAW_TEXT_LIMIT + 100),
    )

    assert 'title: "Example Article"' in markdown
    assert 'source: "https://example.com/article"' in markdown
    assert f'created: "{date.today().isoformat()}"' in markdown
    assert "  - raw" in markdown
    assert "  - web-clip" in markdown
    assert "type: raw-web-clip" in markdown
    assert "## Source" in markdown
    assert "## Raw Extracted Content" in markdown
    assert "A" * RAW_TEXT_LIMIT in markdown
    assert "A" * (RAW_TEXT_LIMIT + 1) not in markdown


def test_save_raw_url_uses_local_vault_without_github(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for name in (
        "GITHUB_TOKEN",
        "GITHUB_OWNER",
        "GITHUB_REPO",
        "GITHUB_BRANCH",
        "GITHUB_NOTES_DIR",
    ):
        monkeypatch.delenv(name, raising=False)

    with (
        patch("app.raw_service.fetch_webpage_content", return_value=_webpage()),
        patch("app.raw_service.save_markdown_to_github") as github_save,
    ):
        result = save_raw_url(
            "https://example.com/article",
            tmp_path,
        )

    assert result["success"] is True
    assert result["title"] == "Example Article"
    assert Path(result["path"]).exists()
    content = Path(result["path"]).read_text(encoding="utf-8")
    assert "Readable raw content." in content
    github_save.assert_not_called()


def test_save_raw_url_uses_github_when_fully_configured(
    tmp_path: Path,
    monkeypatch,
) -> None:
    values = {
        "GITHUB_TOKEN": "token",
        "GITHUB_OWNER": "owner",
        "GITHUB_REPO": "repo",
        "GITHUB_BRANCH": "main",
        "GITHUB_NOTES_DIR": "Inbox",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    with (
        patch("app.raw_service.fetch_webpage_content", return_value=_webpage()),
        patch(
            "app.raw_service.save_markdown_to_github",
            return_value={
                "path": "Inbox/2026-06-18-example-article.md",
                "html_url": "https://github.com/owner/repo/blob/main/note.md",
            },
        ) as github_save,
        patch("app.raw_service.save_markdown") as local_save,
    ):
        result = save_raw_url(
            "https://example.com/article",
            tmp_path,
        )

    assert result["success"] is True
    assert result["html_url"].startswith("https://github.com/")
    github_save.assert_called_once()
    local_save.assert_not_called()


def test_save_raw_url_returns_safe_scraper_failure(tmp_path: Path) -> None:
    failed = {
        "url": "https://example.com",
        "title": "",
        "text": "",
        "success": False,
        "error": "full internal error",
    }

    with patch("app.raw_service.fetch_webpage_content", return_value=failed):
        result = save_raw_url("https://example.com", tmp_path)

    assert result == {
        "success": False,
        "title": "",
        "path": "",
        "error": "Could not extract readable article text.",
    }
