"""Save webpage text without calling an LLM."""

import logging
import os
from datetime import date
from pathlib import Path
from typing import NotRequired, TypedDict

from app.github_writer import save_markdown_to_github
from app.markdown_writer import save_markdown
from app.scraper import fetch_webpage_content


RAW_TEXT_LIMIT = 8000
logger = logging.getLogger(__name__)


class RawSaveResult(TypedDict):
    success: bool
    title: str
    path: str
    html_url: NotRequired[str]
    error: str | None


def build_raw_markdown(title: str, url: str, text: str) -> str:
    """Create the non-LLM Markdown format from extracted webpage text."""

    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
    safe_url = url.replace("\\", "\\\\").replace('"', '\\"')
    return f"""\
---
title: "{safe_title}"
source: "{safe_url}"
created: "{date.today().isoformat()}"
tags:
  - raw
  - web-clip
type: raw-web-clip
---

# {title}

## Source

{url}

## Raw Extracted Content

{text[:RAW_TEXT_LIMIT].strip()}
"""


def _github_settings() -> dict[str, str] | None:
    values = {
        "token": os.getenv("GITHUB_TOKEN", "").strip(),
        "owner": os.getenv("GITHUB_OWNER", "").strip(),
        "repo": os.getenv("GITHUB_REPO", "").strip(),
        "branch": os.getenv("GITHUB_BRANCH", "").strip(),
        "notes_dir": os.getenv("GITHUB_NOTES_DIR", "").strip(),
    }
    return values if all(values.values()) else None


def save_raw_url(url: str, vault_path: Path) -> RawSaveResult:
    """Fetch and save one raw webpage using GitHub or the local vault."""

    webpage = fetch_webpage_content(url)
    if not webpage["success"]:
        return {
            "success": False,
            "title": "",
            "path": "",
            "error": "Could not extract readable article text.",
        }

    markdown = build_raw_markdown(
        webpage["title"],
        webpage["url"],
        webpage["text"],
    )

    try:
        github = _github_settings()
        if github:
            saved = save_markdown_to_github(
                webpage["title"],
                markdown,
                **github,
            )
            return {
                "success": True,
                "title": webpage["title"],
                "path": saved["path"],
                "html_url": saved["html_url"],
                "error": None,
            }

        path = save_markdown(
            webpage["title"],
            markdown,
            output_dir=vault_path / "Inbox",
        )
        return {
            "success": True,
            "title": webpage["title"],
            "path": str(path),
            "error": None,
        }
    except Exception:
        logger.exception("Failed to save raw webpage note")
        return {
            "success": False,
            "title": webpage["title"],
            "path": "",
            "error": "Storage write failed.",
        }
