import os
from pathlib import Path
from unittest.mock import Mock, patch

from app.note_storage import list_recent_notes, search_stored_notes


GITHUB_ENV = {
    "GITHUB_TOKEN": "token",
    "GITHUB_OWNER": "owner",
    "GITHUB_REPO": "repo",
    "GITHUB_BRANCH": "main",
    "GITHUB_NOTES_DIR": "Inbox",
}


def test_lists_local_notes_by_modified_time(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for name in GITHUB_ENV:
        monkeypatch.delenv(name, raising=False)

    inbox = tmp_path / "Inbox"
    inbox.mkdir()
    old = inbox / "2026-06-17-old.md"
    new = inbox / "2026-06-18-new.md"
    old.write_text("old", encoding="utf-8")
    new.write_text("new", encoding="utf-8")
    os.utime(old, (100, 100))
    os.utime(new, (200, 200))

    notes = list_recent_notes(tmp_path)

    assert [Path(note["path"]).name for note in notes] == [
        "2026-06-18-new.md",
        "2026-06-17-old.md",
    ]


def test_lists_github_markdown_notes_by_filename(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for name, value in GITHUB_ENV.items():
        monkeypatch.setenv(name, value)

    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [
        {
            "type": "file",
            "name": "2026-06-17-old.md",
            "path": "Inbox/2026-06-17-old.md",
            "html_url": "https://github.com/old",
        },
        {
            "type": "file",
            "name": "ignore.txt",
            "path": "Inbox/ignore.txt",
            "html_url": "https://github.com/ignore",
        },
        {
            "type": "file",
            "name": "2026-06-18-new.md",
            "path": "Inbox/2026-06-18-new.md",
            "html_url": "https://github.com/new",
        },
    ]

    with patch("app.note_storage.requests.get", return_value=response):
        notes = list_recent_notes(tmp_path)

    assert [note["path"] for note in notes] == [
        "Inbox/2026-06-18-new.md",
        "Inbox/2026-06-17-old.md",
    ]


def test_returns_empty_when_no_local_notes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for name in GITHUB_ENV:
        monkeypatch.delenv(name, raising=False)

    assert list_recent_notes(tmp_path) == []


def test_searches_local_notes_case_insensitively(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for name in GITHUB_ENV:
        monkeypatch.delenv(name, raising=False)
    inbox = tmp_path / "Inbox"
    inbox.mkdir()
    (inbox / "rust.md").write_text(
        '---\ntitle: "Rust Ownership"\n---\n'
        "# Rust Ownership\n\nOwnership is Rust's unique feature.",
        encoding="utf-8",
    )
    (inbox / "python.md").write_text(
        "# Python\n\nPython content.",
        encoding="utf-8",
    )

    notes = search_stored_notes("RUST", tmp_path)

    assert len(notes) == 1
    assert notes[0]["title"] == "Rust Ownership"
    assert "Rust" in notes[0]["snippet"]
    assert len(notes[0]["snippet"]) < 250


def test_searches_github_note_contents(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import base64

    for name, value in GITHUB_ENV.items():
        monkeypatch.setenv(name, value)

    listing = Mock()
    listing.raise_for_status.return_value = None
    listing.json.return_value = [
        {
            "type": "file",
            "name": "2026-06-18-rust.md",
            "path": "Inbox/2026-06-18-rust.md",
            "html_url": "https://github.com/rust",
        }
    ]
    content = Mock()
    content.raise_for_status.return_value = None
    content.json.return_value = {
        "content": base64.b64encode(
            b'# Rust Ownership\n\nownership is important'
        ).decode()
    }

    with patch(
        "app.note_storage.requests.get",
        side_effect=[listing, content],
    ):
        notes = search_stored_notes("Ownership", tmp_path)

    assert len(notes) == 1
    assert notes[0]["title"] == "Rust Ownership"
    assert notes[0]["html_url"] == "https://github.com/rust"


def test_search_returns_empty_for_no_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for name in GITHUB_ENV:
        monkeypatch.delenv(name, raising=False)
    inbox = tmp_path / "Inbox"
    inbox.mkdir()
    (inbox / "note.md").write_text("ordinary content", encoding="utf-8")

    assert search_stored_notes("unlikelykeyword123", tmp_path) == []
