"""Parse incoming chat text into commands or questions."""

from typing import TypedDict
from urllib.parse import urlparse


SAVE_COMMANDS = {"/record", "/紀錄"}
HELP_COMMANDS = {"/help", "/指令"}
STATUS_COMMANDS = {"/status"}
CHECK_COMMANDS = {"/check"}
RAW_COMMANDS = {"/raw"}
RECENT_COMMANDS = {"/最近"}
SEARCH_COMMANDS = {"/搜尋"}


class ParsedMessage(TypedDict, total=False):
    """Normalized representation of an incoming chat message."""

    type: str
    raw_text: str
    url: str
    question: str
    keyword: str
    error: str


def _is_web_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_command(text: str) -> ParsedMessage:
    """Classify text as a save-URL command, invalid command, or question."""

    raw_text = text
    normalized_text = text.strip()
    parts = normalized_text.split()
    command = parts[0].lower() if parts else ""

    if command in HELP_COMMANDS and len(parts) == 1:
        return {
            "type": "help",
            "raw_text": raw_text,
        }

    if command in STATUS_COMMANDS and len(parts) == 1:
        return {
            "type": "status",
            "raw_text": raw_text,
        }

    if command in RECENT_COMMANDS and len(parts) == 1:
        return {
            "type": "recent_notes",
            "raw_text": raw_text,
        }

    if command in SEARCH_COMMANDS:
        keyword = normalized_text[len(parts[0]) :].strip()
        if not keyword:
            return {
                "type": "invalid_command",
                "error": "Use /搜尋 followed by a keyword.",
                "raw_text": raw_text,
            }
        return {
            "type": "search_notes",
            "keyword": keyword,
            "raw_text": raw_text,
        }

    if command in CHECK_COMMANDS:
        if len(parts) != 2 or not _is_web_url(parts[1]):
            return {
                "type": "invalid_command",
                "error": "Use /check followed by one http(s) URL.",
                "raw_text": raw_text,
            }

        return {
            "type": "check_url",
            "url": parts[1],
            "raw_text": raw_text,
        }

    if command in RAW_COMMANDS:
        if len(parts) != 2 or not _is_web_url(parts[1]):
            return {
                "type": "invalid_command",
                "error": "Use /raw followed by one http(s) URL.",
                "raw_text": raw_text,
            }

        return {
            "type": "raw_url",
            "url": parts[1],
            "raw_text": raw_text,
        }

    if command in SAVE_COMMANDS:
        if len(parts) != 2 or not _is_web_url(parts[1]):
            return {
                "type": "invalid_command",
                "error": "Use /record or /紀錄 followed by one http(s) URL.",
                "raw_text": raw_text,
            }

        return {
            "type": "save_url",
            "url": parts[1],
            "raw_text": raw_text,
        }

    return {
        "type": "question",
        "question": normalized_text,
        "raw_text": raw_text,
    }
