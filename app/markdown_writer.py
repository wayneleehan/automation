"""Write Markdown notes to an Obsidian-compatible vault folder."""

import re
import unicodedata
from datetime import date
from pathlib import Path


DEFAULT_INBOX = Path("vault/Inbox")


def slugify_title(title: str) -> str:
    """Convert a title into a safe, portable filename slug."""

    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title.lower()).strip("-")
    return slug or "untitled"


def save_markdown(
    title: str,
    content: str,
    output_dir: str | Path = DEFAULT_INBOX,
    note_date: date | None = None,
) -> Path:
    """Save Markdown content and return the resulting file path."""

    inbox = Path(output_dir)
    inbox.mkdir(parents=True, exist_ok=True)

    date_prefix = (note_date or date.today()).isoformat()
    filename_stem = f"{date_prefix}-{slugify_title(title)}"
    path = inbox / f"{filename_stem}.md"

    counter = 2
    while path.exists():
        path = inbox / f"{filename_stem}-{counter}.md"
        counter += 1

    path.write_text(content, encoding="utf-8")
    return path
