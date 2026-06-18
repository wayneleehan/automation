"""Application service for saving a webpage into the Markdown vault."""

from pathlib import Path
from typing import TypedDict

from app.markdown_writer import save_markdown
from app.scraper import fetch_webpage_content
from app.summarizer import summarize_to_markdown


class SaveResult(TypedDict):
    success: bool
    message: str
    path: str
    title: str
    error: str | None


def save_url_to_vault(url: str, vault_path: Path) -> SaveResult:
    """Fetch, summarize, and save one URL without transport-specific logic."""

    webpage = fetch_webpage_content(url)
    if not webpage["success"]:
        return {
            "success": False,
            "message": "Could not fetch webpage",
            "path": "",
            "title": "",
            "error": webpage["error"],
        }

    summary = summarize_to_markdown(
        webpage["title"],
        webpage["url"],
        webpage["text"],
    )
    if not summary["success"]:
        return {
            "success": False,
            "message": "Could not summarize webpage",
            "path": "",
            "title": webpage["title"],
            "error": summary["error"],
        }

    try:
        saved_path = save_markdown(
            webpage["title"],
            summary["markdown"],
            output_dir=vault_path / "Inbox",
        )
    except OSError as exc:
        return {
            "success": False,
            "message": "Could not save Markdown note",
            "path": "",
            "title": webpage["title"],
            "error": str(exc),
        }

    return {
        "success": True,
        "message": "Saved to Obsidian vault",
        "path": str(saved_path),
        "title": webpage["title"],
        "error": None,
    }
