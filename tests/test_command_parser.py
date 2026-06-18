import pytest

from app.command_parser import parse_command


@pytest.mark.parametrize("command", ["/record", "/RECORD", "/紀錄"])
def test_parses_save_url_commands(command: str) -> None:
    text = f"{command} https://example.com/article"

    assert parse_command(text) == {
        "type": "save_url",
        "url": "https://example.com/article",
        "raw_text": text,
    }


def test_parses_normal_text_as_question() -> None:
    text = "What did I save about AI agents?"

    assert parse_command(text) == {
        "type": "question",
        "question": text,
        "raw_text": text,
    }


def test_trims_question_for_processing_but_preserves_raw_text() -> None:
    text = "  What did I save?  "

    assert parse_command(text) == {
        "type": "question",
        "question": "What did I save?",
        "raw_text": text,
    }


@pytest.mark.parametrize(
    "text",
    [
        "/record",
        "/紀錄 not-a-url",
        "/record ftp://example.com/article",
        "/record https://example.com one-more-argument",
    ],
)
def test_rejects_malformed_save_commands(text: str) -> None:
    assert parse_command(text) == {
        "type": "invalid_command",
        "error": "Use /record or /紀錄 followed by one http(s) URL.",
        "raw_text": text,
    }
