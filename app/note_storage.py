"""Read note metadata from GitHub storage or a local vault."""

import base64
import logging
import os
import re
from pathlib import Path
from typing import TypedDict
from urllib.parse import quote

import certifi
import requests


GITHUB_API = "https://api.github.com"
logger = logging.getLogger(__name__)


class NoteItem(TypedDict):
    title: str
    path: str
    html_url: str
    snippet: str


def _github_settings() -> dict[str, str] | None:
    values = {
        "token": os.getenv("GITHUB_TOKEN", "").strip(),
        "owner": os.getenv("GITHUB_OWNER", "").strip(),
        "repo": os.getenv("GITHUB_REPO", "").strip(),
        "branch": os.getenv("GITHUB_BRANCH", "").strip(),
        "notes_dir": os.getenv("GITHUB_NOTES_DIR", "").strip(),
    }
    return values if all(values.values()) else None


def _list_github_notes(settings: dict[str, str], limit: int) -> list[NoteItem]:
    endpoint = (
        f"{GITHUB_API}/repos/{quote(settings['owner'])}/"
        f"{quote(settings['repo'])}/contents/"
        f"{quote(settings['notes_dir'], safe='/')}"
    )
    response = requests.get(
        endpoint,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {settings['token']}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        params={"ref": settings["branch"]},
        timeout=15,
        verify=certifi.where(),
    )
    response.raise_for_status()
    entries = response.json()
    notes = [
        entry
        for entry in entries
        if entry.get("type") == "file"
        and entry.get("name", "").lower().endswith(".md")
    ]
    notes.sort(key=lambda entry: entry["name"], reverse=True)
    return [
        {
            "title": entry["name"].removesuffix(".md"),
            "path": entry["path"],
            "html_url": entry.get("html_url", ""),
            "snippet": "",
        }
        for entry in notes[:limit]
    ]


def _list_local_notes(vault_path: Path, limit: int) -> list[NoteItem]:
    inbox = vault_path / "Inbox"
    if not inbox.exists():
        return []

    paths = sorted(
        inbox.glob("*.md"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return [
        {
            "title": path.stem,
            "path": str(path),
            "html_url": "",
            "snippet": "",
        }
        for path in paths[:limit]
    ]


def list_recent_notes(
    vault_path: str | Path,
    limit: int = 5,
) -> list[NoteItem]:
    """List recent Markdown notes from configured GitHub or local storage."""

    if limit <= 0:
        return []

    github = _github_settings()
    if github:
        try:
            return _list_github_notes(github, limit)
        except Exception:
            logger.exception("Failed to list recent notes from GitHub")
            return []

    try:
        return _list_local_notes(Path(vault_path), limit)
    except Exception:
        logger.exception("Failed to list recent notes from local vault")
        return []


def _extract_title(content: str, fallback: str) -> str:
    frontmatter = re.search(
        r'^title:\s*["\']?(.+?)["\']?\s*$',
        content,
        re.MULTILINE,
    )
    if frontmatter:
        return frontmatter.group(1).strip()
    heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return heading.group(1).strip() if heading else fallback


def _keyword_snippet(content: str, keyword: str, radius: int = 100) -> str:
    match = re.search(re.escape(keyword), content, re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - radius)
    end = min(len(content), match.end() + radius)
    snippet = " ".join(content[start:end].split())
    if start:
        snippet = f"...{snippet}"
    if end < len(content):
        snippet = f"{snippet}..."
    return snippet


def _search_local_notes(
    vault_path: Path,
    keyword: str,
    limit: int,
) -> list[NoteItem]:
    inbox = vault_path / "Inbox"
    if not inbox.exists():
        return []

    matches: list[NoteItem] = []
    for path in inbox.glob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            logger.exception("Failed to read local Markdown note: %s", path)
            continue
        snippet = _keyword_snippet(content, keyword)
        if not snippet:
            continue
        matches.append(
            {
                "title": _extract_title(content, path.stem),
                "path": str(path),
                "html_url": "",
                "snippet": snippet,
            }
        )

    matches.sort(key=lambda note: note["path"], reverse=True)
    return matches[:limit]


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _search_github_notes(
    settings: dict[str, str],
    keyword: str,
    limit: int,
) -> list[NoteItem]:
    recent = _list_github_notes(settings, 100)
    matches: list[NoteItem] = []

    for note in recent:
        endpoint = (
            f"{GITHUB_API}/repos/{quote(settings['owner'])}/"
            f"{quote(settings['repo'])}/contents/"
            f"{quote(note['path'], safe='/')}"
        )
        response = requests.get(
            endpoint,
            headers=_github_headers(settings["token"]),
            params={"ref": settings["branch"]},
            timeout=15,
            verify=certifi.where(),
        )
        response.raise_for_status()
        payload = response.json()
        content = base64.b64decode(payload["content"]).decode("utf-8")
        snippet = _keyword_snippet(content, keyword)
        if not snippet:
            continue
        matches.append(
            {
                "title": _extract_title(content, note["title"]),
                "path": note["path"],
                "html_url": note["html_url"],
                "snippet": snippet,
            }
        )
        if len(matches) >= limit:
            break
    return matches


def search_stored_notes(
    keyword: str,
    vault_path: str | Path,
    limit: int = 5,
) -> list[NoteItem]:
    """Search stored Markdown notes without using an LLM."""

    keyword = keyword.strip()
    if not keyword or limit <= 0:
        return []

    github = _github_settings()
    try:
        if github:
            return _search_github_notes(github, keyword, limit)
        return _search_local_notes(Path(vault_path), keyword, limit)
    except Exception:
        logger.exception("Failed to search stored Markdown notes")
        return []
