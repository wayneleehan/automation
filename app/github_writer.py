"""Save Markdown notes with the GitHub Contents API."""

import base64
from datetime import date
from pathlib import PurePosixPath
from typing import TypedDict
from urllib.parse import quote

import certifi
import requests

from app.markdown_writer import slugify_title


GITHUB_API = "https://api.github.com"


class GitHubSaveResult(TypedDict):
    path: str
    html_url: str


def save_markdown_to_github(
    title: str,
    content: str,
    *,
    token: str,
    owner: str,
    repo: str,
    branch: str,
    notes_dir: str,
    note_date: date | None = None,
) -> GitHubSaveResult:
    """Create a uniquely named Markdown file in a GitHub repository."""

    filename_stem = (
        f"{(note_date or date.today()).isoformat()}-{slugify_title(title)}"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    counter = 1
    while True:
        suffix = "" if counter == 1 else f"-{counter}"
        path = str(
            PurePosixPath(notes_dir) / f"{filename_stem}{suffix}.md"
        )
        endpoint = (
            f"{GITHUB_API}/repos/{quote(owner)}/{quote(repo)}/contents/"
            f"{quote(path, safe='/')}"
        )
        existing = requests.get(
            endpoint,
            headers=headers,
            params={"ref": branch},
            timeout=15,
            verify=certifi.where(),
        )
        if existing.status_code == 404:
            break
        existing.raise_for_status()
        counter += 1

    response = requests.put(
        endpoint,
        headers=headers,
        json={
            "message": f"Add raw web clip: {title}",
            "content": base64.b64encode(content.encode("utf-8")).decode(),
            "branch": branch,
        },
        timeout=20,
        verify=certifi.where(),
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "path": payload["content"]["path"],
        "html_url": payload["content"]["html_url"],
    }
