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


@pytest.mark.parametrize("command", ["/help", "/HELP", "/指令"])
def test_parses_help_commands(command: str) -> None:
    assert parse_command(command) == {
        "type": "help",
        "raw_text": command,
    }


@pytest.mark.parametrize("command", ["/status", "/STATUS"])
def test_parses_status_command(command: str) -> None:
    assert parse_command(command) == {
        "type": "status",
        "raw_text": command,
    }


def test_parses_recent_notes_command() -> None:
    assert parse_command("/最近") == {
        "type": "recent_notes",
        "raw_text": "/最近",
    }


def test_parses_search_notes_command() -> None:
    assert parse_command("/搜尋 Rust ownership") == {
        "type": "search_notes",
        "keyword": "Rust ownership",
        "raw_text": "/搜尋 Rust ownership",
    }


def test_rejects_search_without_keyword() -> None:
    assert parse_command("/搜尋") == {
        "type": "invalid_command",
        "error": "Use /搜尋 followed by a keyword.",
        "raw_text": "/搜尋",
    }


@pytest.mark.parametrize("command", ["/check", "/CHECK"])
def test_parses_check_url_command(command: str) -> None:
    text = f"{command} https://example.com/article"

    assert parse_command(text) == {
        "type": "check_url",
        "url": "https://example.com/article",
        "raw_text": text,
    }


@pytest.mark.parametrize("command", ["/raw", "/RAW"])
def test_parses_raw_url_command(command: str) -> None:
    text = f"{command} https://example.com/article"

    assert parse_command(text) == {
        "type": "raw_url",
        "url": "https://example.com/article",
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


@pytest.mark.parametrize(
    "text",
    [
        "/check",
        "/check not-a-url",
        "/check ftp://example.com",
        "/check https://example.com extra",
    ],
)
def test_rejects_malformed_check_commands(text: str) -> None:
    assert parse_command(text) == {
        "type": "invalid_command",
        "error": "Use /check followed by one http(s) URL.",
        "raw_text": text,
    }


@pytest.mark.parametrize(
    "text",
    [
        "/raw",
        "/raw not-a-url",
        "/raw ftp://example.com",
        "/raw https://example.com extra",
    ],
)
def test_rejects_malformed_raw_commands(text: str) -> None:
    assert parse_command(text) == {
        "type": "invalid_command",
        "error": "Use /raw followed by one http(s) URL.",
        "raw_text": text,
    }
