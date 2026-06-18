from datetime import date
from pathlib import Path

from app.markdown_writer import save_markdown, slugify_title


TEST_DATE = date(2026, 6, 18)


def test_slugifies_title_and_removes_unsafe_characters() -> None:
    assert slugify_title('AI Agents: "Useful" / Automation?') == (
        "ai-agents-useful-automation"
    )


def test_uses_fallback_for_title_without_filename_characters() -> None:
    assert slugify_title("第二大腦") == "untitled"


def test_saves_markdown_with_expected_filename_and_content(tmp_path: Path) -> None:
    content = "# AI Agents\n\nA useful note."

    saved_path = save_markdown(
        "AI Agents and Automation",
        content,
        output_dir=tmp_path / "vault" / "Inbox",
        note_date=TEST_DATE,
    )

    assert saved_path.name == "2026-06-18-ai-agents-and-automation.md"
    assert saved_path.read_text(encoding="utf-8") == content


def test_creates_missing_output_directory(tmp_path: Path) -> None:
    inbox = tmp_path / "nested" / "vault" / "Inbox"

    saved_path = save_markdown(
        "Example Article",
        "# Example",
        output_dir=inbox,
        note_date=TEST_DATE,
    )

    assert inbox.is_dir()
    assert saved_path.exists()


def test_appends_counter_when_filename_exists(tmp_path: Path) -> None:
    first_path = save_markdown(
        "Example Article",
        "first",
        output_dir=tmp_path,
        note_date=TEST_DATE,
    )
    second_path = save_markdown(
        "Example Article",
        "second",
        output_dir=tmp_path,
        note_date=TEST_DATE,
    )
    third_path = save_markdown(
        "Example Article",
        "third",
        output_dir=tmp_path,
        note_date=TEST_DATE,
    )

    assert first_path.name == "2026-06-18-example-article.md"
    assert second_path.name == "2026-06-18-example-article-2.md"
    assert third_path.name == "2026-06-18-example-article-3.md"
