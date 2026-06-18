"""Parse incoming chat text into commands or questions."""

from typing import TypedDict
from urllib.parse import urlparse


SAVE_COMMANDS = {"/record", "/紀錄"}


class ParsedMessage(TypedDict, total=False):
    """Normalized representation of an incoming chat message."""

    type: str
    raw_text: str
    url: str
    question: str
    error: str


def _is_web_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_command(text: str) -> ParsedMessage:
    """Classify text as a save-URL command, invalid command, or question."""

    raw_text = text
    normalized_text = text.strip()
    parts = normalized_text.split()

    if parts and parts[0].lower() in SAVE_COMMANDS:
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
