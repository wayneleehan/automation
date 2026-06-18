"""Application service for saving a webpage into the Markdown vault."""

import logging
from datetime import date
from pathlib import Path
from typing import NotRequired, TypedDict

from app.markdown_writer import save_markdown
from app.scraper import fetch_webpage_content
from app.summarizer import summarize_to_markdown


logger = logging.getLogger(__name__)


class SaveResult(TypedDict):
    success: bool
    message: str
    path: str
    title: str
    error: str | None
    warning: NotRequired[str | None]


QUOTA_WARNING = (
    "已儲存原始筆記，但 AI 摘要失敗："
    "OpenAI API quota/billing 尚未可用。"
)


def _fallback_markdown(title: str, url: str, text: str) -> str:
    """Build a minimal note when quota prevents AI summarization."""

    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_url = url.replace("\\", "\\\\").replace('"', '\\"')
    excerpt = text[:1500].strip()
    return f"""\
---
title: "{safe_title}"
source: "{safe_url}"
created: "{date.today().isoformat()}"
type: web-clip
---

# {title}

## LLM Summary Failed

The webpage was saved, but AI summarization failed because the OpenAI API quota or billing is not available.

## Extracted Text

{excerpt}
"""


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
        if summary.get("error_code") == "insufficient_quota":
            markdown = _fallback_markdown(
                webpage["title"],
                webpage["url"],
                webpage["text"],
            )
            warning = "insufficient_quota"
        else:
            return {
                "success": False,
                "message": "Could not summarize webpage",
                "path": "",
                "title": webpage["title"],
                "error": summary["error"],
                "warning": None,
            }
    else:
        markdown = summary["markdown"]
        warning = None

    try:
        saved_path = save_markdown(
            webpage["title"],
            markdown,
            output_dir=vault_path / "Inbox",
        )
    except OSError as exc:
        logger.exception(
            "Failed to save Markdown note to configured vault/storage"
        )
        return {
            "success": False,
            "message": "Could not save Markdown note",
            "path": "",
            "title": webpage["title"],
            "error": str(exc),
            "warning": warning,
        }

    return {
        "success": True,
        "message": QUOTA_WARNING if warning else "Saved to Obsidian vault",
        "path": str(saved_path),
        "title": webpage["title"],
        "error": None,
        "warning": warning,
    }
