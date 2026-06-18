"""LINE Messaging API webhook processing."""

import logging
import os
from collections.abc import Callable
from pathlib import Path

import certifi
from linebot.v3 import WebhookParser
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from app.command_parser import parse_command
from app.note_storage import NoteItem
from app.raw_service import RawSaveResult
from app.save_service import LLM_FALLBACK_WARNING, QUOTA_WARNING, SaveResult
from app.scraper import ScrapeResult


logger = logging.getLogger(__name__)


HELP_MESSAGE = """\
目前支援的指令：

/紀錄 [網址]
儲存網址為 Obsidian Markdown。若 AI 摘要失敗，會儲存原始筆記。

/raw [網址]
不使用 AI，直接儲存網頁原始內容為 Markdown。

/check [網址]
檢查網頁是否可以被伺服器抓取。

/最近
列出最近儲存的筆記。

/搜尋 [關鍵字]
搜尋已儲存的 Markdown 筆記。

/status
檢查 LINE、GitHub、OpenAI 等服務設定狀態。"""


def _configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def build_status_message() -> str:
    """Return configuration presence without revealing secret values."""

    line_webhook_ok = _configured("LINE_CHANNEL_SECRET")
    line_token_ok = _configured("LINE_CHANNEL_ACCESS_TOKEN")
    github_ok = all(
        _configured(name)
        for name in (
            "GITHUB_TOKEN",
            "GITHUB_OWNER",
            "GITHUB_REPO",
            "GITHUB_BRANCH",
            "GITHUB_NOTES_DIR",
        )
    )
    openai_key_ok = _configured("OPENAI_API_KEY")
    openai_model_ok = _configured("OPENAI_MODEL")

    status = lambda configured: "OK" if configured else "Missing"
    return (
        "系統狀態：\n\n"
        f"LINE webhook：{status(line_webhook_ok)}\n"
        f"LINE access token：{status(line_token_ok)}\n"
        f"GitHub storage：{status(github_ok)}\n"
        f"OpenAI API key：{status(openai_key_ok)}\n"
        f"OpenAI model：{status(openai_model_ok)}\n"
        "OpenAI quota：未檢查或可能不可用\n\n"
        "注意：OpenAI API key 存在不代表 billing/quota 可用。"
    )


def _reply_text(
    reply_token: str,
    text: str,
    channel_access_token: str,
) -> None:
    configuration = Configuration(access_token=channel_access_token)
    configuration.ssl_ca_cert = certifi.where()
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )


def _save_reply(result: SaveResult) -> str:
    if result["success"]:
        if result.get("warning") == "insufficient_quota":
            return QUOTA_WARNING
        if result.get("warning") == "all_providers_failed":
            return LLM_FALLBACK_WARNING
        return (
            f"已儲存：{result['title']}\n"
            f"路徑：{result['path']}"
        )
    return f"儲存失敗：{result['message']}。請查看伺服器記錄。"


def _check_reply(result: ScrapeResult) -> str:
    if result["success"]:
        return (
            "網頁抓取成功：\n\n"
            f"Title: {result['title'] or 'Untitled'}\n"
            f"Text length: {len(result['text'])} characters\n"
            f"URL: {result['url']}"
        )
    return (
        "網頁抓取失敗：\n\n"
        f"URL: {result['url']}\n"
        "原因：Could not extract readable article text."
    )


def _raw_reply(result: RawSaveResult) -> str:
    if not result["success"]:
        return "儲存原始筆記失敗，請查看伺服器記錄。"
    destination = (
        f"GitHub: {result['html_url']}"
        if result.get("html_url")
        else f"Path: {result['path']}"
    )
    return (
        "已儲存原始筆記：\n\n"
        f"Title: {result['title']}\n"
        f"{destination}"
    )


def _recent_reply(notes: list[NoteItem]) -> str:
    if not notes:
        return "目前還沒有找到任何 Markdown 筆記。"
    lines = ["最近 5 篇筆記：", ""]
    lines.extend(
        f"{index}. {Path(note['path']).name}"
        for index, note in enumerate(notes, start=1)
    )
    return "\n".join(lines)


def _search_reply(keyword: str, notes: list[NoteItem]) -> str:
    if not notes:
        return f"找不到包含「{keyword}」的筆記。"

    lines = [f"找到 {len(notes)} 篇相關筆記：", ""]
    for index, note in enumerate(notes, start=1):
        lines.extend(
            [
                f"{index}. {note['title']}",
                f"檔案：{Path(note['path']).name}",
                f"片段：{note['snippet']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def process_line_webhook(
    body: str,
    signature: str,
    channel_secret: str,
    channel_access_token: str,
    save_handler: Callable[[str], SaveResult],
    question_handler: Callable[[str], str] | None = None,
    check_handler: Callable[[str], ScrapeResult] | None = None,
    raw_handler: Callable[[str], RawSaveResult] | None = None,
    recent_handler: Callable[[], list[NoteItem]] | None = None,
    search_handler: Callable[[str], list[NoteItem]] | None = None,
) -> int:
    """Verify and process LINE text events, returning the reply count."""

    events = WebhookParser(channel_secret).parse(body, signature)
    reply_count = 0

    for event in events:
        if not isinstance(event, MessageEvent) or not isinstance(
            event.message,
            TextMessageContent,
        ):
            continue

        try:
            parsed = parse_command(event.message.text)
            if parsed["type"] == "help":
                reply = HELP_MESSAGE
            elif parsed["type"] == "status":
                reply = build_status_message()
            elif parsed["type"] == "recent_notes":
                try:
                    if recent_handler is None:
                        raise RuntimeError(
                            "Recent notes handler is not configured"
                        )
                    reply = _recent_reply(recent_handler())
                except Exception:
                    logger.exception("LINE recent notes listing failed")
                    reply = "目前無法列出最近筆記，請稍後再試。"
            elif parsed["type"] == "search_notes":
                try:
                    if search_handler is None:
                        raise RuntimeError(
                            "Note search handler is not configured"
                        )
                    reply = _search_reply(
                        parsed["keyword"],
                        search_handler(parsed["keyword"]),
                    )
                except Exception:
                    logger.exception("LINE note search failed")
                    reply = "目前無法搜尋筆記，請稍後再試。"
            elif parsed["type"] == "check_url":
                try:
                    if check_handler is None:
                        raise RuntimeError("Check handler is not configured")
                    reply = _check_reply(check_handler(parsed["url"]))
                except Exception:
                    logger.exception("LINE webpage check failed")
                    reply = "網頁抓取失敗，請稍後再試。"
            elif parsed["type"] == "raw_url":
                try:
                    if raw_handler is None:
                        raise RuntimeError("Raw save handler is not configured")
                    reply = _raw_reply(raw_handler(parsed["url"]))
                except Exception:
                    logger.exception("LINE raw save workflow failed")
                    reply = "儲存原始筆記失敗，請稍後再試。"
            elif parsed["type"] == "save_url":
                try:
                    result = save_handler(parsed["url"])
                    reply = _save_reply(result)
                except Exception:
                    logger.exception("LINE save workflow failed")
                    reply = "儲存失敗，請稍後再試。"
            elif parsed["type"] == "invalid_command":
                reply = (
                    "指令格式不正確。請使用：\n"
                    "/紀錄 https://example.com/article"
                )
            else:
                try:
                    reply = (
                        question_handler(parsed["question"])
                        if question_handler
                        else HELP_MESSAGE
                    )
                except Exception:
                    logger.exception("LINE question workflow failed")
                    reply = "目前無法回答，請稍後再試。"

            try:
                _reply_text(event.reply_token, reply, channel_access_token)
                reply_count += 1
            except Exception:
                logger.exception("Failed to send LINE reply")
        except Exception:
            logger.exception("Unexpected LINE event processing failure")

    return reply_count
