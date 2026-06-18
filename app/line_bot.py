"""LINE Messaging API webhook processing."""

import logging
from collections.abc import Callable

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
from app.save_service import QUOTA_WARNING, SaveResult


logger = logging.getLogger(__name__)


HELP_MESSAGE = (
    "目前我支援：\n"
    "/紀錄 [網址]：把網頁整理成 Markdown 並存進 Obsidian Vault。"
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
        return (
            f"已儲存：{result['title']}\n"
            f"路徑：{result['path']}"
        )
    return f"儲存失敗：{result['message']}。請查看伺服器記錄。"


def process_line_webhook(
    body: str,
    signature: str,
    channel_secret: str,
    channel_access_token: str,
    save_handler: Callable[[str], SaveResult],
    question_handler: Callable[[str], str] | None = None,
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
            if parsed["type"] == "save_url":
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
