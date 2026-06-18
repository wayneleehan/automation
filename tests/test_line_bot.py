import base64
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.line_bot import HELP_MESSAGE, build_status_message, process_line_webhook
from app.main import app


CHANNEL_SECRET = "test-channel-secret"
CHANNEL_ACCESS_TOKEN = "test-access-token"
client = TestClient(app)


def _webhook_body(text: str = "/紀錄 https://example.com/article") -> str:
    return json.dumps(
        {
            "destination": "U1234567890",
            "events": [
                {
                    "type": "message",
                    "mode": "active",
                    "timestamp": 1710000000000,
                    "source": {"type": "user", "userId": "U123"},
                    "webhookEventId": "01HVTESTEVENT",
                    "deliveryContext": {"isRedelivery": False},
                    "replyToken": "test-reply-token",
                    "message": {
                        "id": "123456789",
                        "type": "text",
                        "quoteToken": "test-quote-token",
                        "text": text,
                    },
                }
            ],
        },
        separators=(",", ":"),
    )


def _signature(body: str, secret: str = CHANNEL_SECRET) -> str:
    digest = hmac.new(
        secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode()


def test_save_command_replies_with_saved_note() -> None:
    body = _webhook_body()
    save_handler = Mock(
        return_value={
            "success": True,
            "message": "Saved to Obsidian vault",
            "path": "vault/Inbox/2026-06-18-example-article.md",
            "title": "Example Article",
            "error": None,
        }
    )

    with patch("app.line_bot._reply_text") as reply:
        count = process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            save_handler,
        )

    assert count == 1
    save_handler.assert_called_once_with("https://example.com/article")
    reply.assert_called_once_with(
        "test-reply-token",
        (
            "已儲存：Example Article\n"
            "路徑：vault/Inbox/2026-06-18-example-article.md"
        ),
        CHANNEL_ACCESS_TOKEN,
    )


def test_save_command_replies_with_github_url() -> None:
    body = _webhook_body()
    save_handler = Mock(
        return_value={
            "success": True,
            "message": "Saved to Obsidian vault",
            "path": "Inbox/example.md",
            "html_url": "https://github.com/owner/repo/blob/main/Inbox/example.md",
            "title": "Example Article",
            "error": None,
        }
    )

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            save_handler,
        )

    reply.assert_called_once_with(
        "test-reply-token",
        (
            "已儲存：Example Article\n"
            "GitHub：https://github.com/owner/repo/blob/main/Inbox/example.md"
        ),
        CHANNEL_ACCESS_TOKEN,
    )


def test_quota_fallback_uses_sanitized_line_reply() -> None:
    body = _webhook_body()
    save_handler = Mock(
        return_value={
            "success": True,
            "message": "internal message should not be used",
            "path": "vault/Inbox/fallback.md",
            "title": "Example Article",
            "error": None,
            "warning": "insufficient_quota",
        }
    )

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            save_handler,
        )

    reply.assert_called_once_with(
        "test-reply-token",
        (
            "已儲存原始筆記，但 AI 摘要失敗："
            "OpenAI API quota/billing 尚未可用。"
        ),
        CHANNEL_ACCESS_TOKEN,
    )


def test_normal_message_replies_with_help() -> None:
    body = _webhook_body("你可以做什麼？")

    with patch("app.line_bot._reply_text") as reply:
        count = process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            Mock(),
        )

    assert count == 1
    reply.assert_called_once_with(
        "test-reply-token",
        HELP_MESSAGE,
        CHANNEL_ACCESS_TOKEN,
    )


@pytest.mark.parametrize("command", ["/help", "/指令"])
def test_help_command_does_not_call_save_or_question_handlers(
    command: str,
) -> None:
    body = _webhook_body(command)
    save_handler = Mock()
    question_handler = Mock()

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            save_handler,
            question_handler,
        )

    save_handler.assert_not_called()
    question_handler.assert_not_called()
    reply.assert_called_once_with(
        "test-reply-token",
        HELP_MESSAGE,
        CHANNEL_ACCESS_TOKEN,
    )


def test_status_message_reports_presence_without_secret_values(
    monkeypatch,
) -> None:
    configured = {
        "LINE_CHANNEL_ACCESS_TOKEN": "line-token-secret",
        "LINE_CHANNEL_SECRET": "line-channel-secret",
        "GITHUB_TOKEN": "github-token-secret",
        "GITHUB_OWNER": "owner",
        "GITHUB_REPO": "repo",
        "GITHUB_BRANCH": "main",
        "GITHUB_NOTES_DIR": "Inbox",
        "OPENAI_API_KEY": "openai-key-secret",
        "OPENAI_MODEL": "gpt-test",
    }
    for name, value in configured.items():
        monkeypatch.setenv(name, value)

    message = build_status_message()

    assert "LINE webhook：OK" in message
    assert "LINE access token：OK" in message
    assert "GitHub storage：OK" in message
    assert "OpenAI API key：OK" in message
    assert "OpenAI model：OK" in message
    assert "OpenAI quota：未檢查或可能不可用" in message
    for value in configured.values():
        assert value not in message


def test_status_command_does_not_call_save_or_question_handlers(
    monkeypatch,
) -> None:
    body = _webhook_body("/status")
    save_handler = Mock()
    question_handler = Mock()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            save_handler,
            question_handler,
        )

    save_handler.assert_not_called()
    question_handler.assert_not_called()
    status_reply = reply.call_args.args[1]
    assert "GitHub storage：Missing" in status_reply
    assert "OpenAI quota：未檢查或可能不可用" in status_reply


def test_check_command_reports_success_without_save_or_llm() -> None:
    body = _webhook_body("/check https://example.com/article")
    save_handler = Mock()
    question_handler = Mock()
    check_handler = Mock(
        return_value={
            "url": "https://example.com/article",
            "title": "Example Article",
            "text": "Readable text.",
            "success": True,
            "error": None,
        }
    )

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            save_handler,
            question_handler,
            check_handler,
        )

    save_handler.assert_not_called()
    question_handler.assert_not_called()
    check_handler.assert_called_once_with("https://example.com/article")
    reply.assert_called_once_with(
        "test-reply-token",
        (
            "網頁抓取成功：\n\n"
            "Title: Example Article\n"
            "Text length: 14 characters\n"
            "URL: https://example.com/article"
        ),
        CHANNEL_ACCESS_TOKEN,
    )


def test_check_command_returns_short_safe_failure() -> None:
    body = _webhook_body("/check https://example.com")
    check_handler = Mock(
        return_value={
            "url": "https://example.com",
            "title": "",
            "text": "",
            "success": False,
            "error": "full internal scraper failure and stack details",
        }
    )

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            Mock(),
            None,
            check_handler,
        )

    message = reply.call_args.args[1]
    assert "網頁抓取失敗" in message
    assert "https://example.com" in message
    assert "Could not extract readable article text." in message
    assert "stack details" not in message


def test_raw_command_saves_without_save_or_question_handlers() -> None:
    body = _webhook_body("/raw https://example.com/article")
    save_handler = Mock()
    question_handler = Mock()
    check_handler = Mock()
    raw_handler = Mock(
        return_value={
            "success": True,
            "title": "Example Article",
            "path": "vault/Inbox/2026-06-18-example-article.md",
            "error": None,
        }
    )

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            save_handler,
            question_handler,
            check_handler,
            raw_handler,
        )

    save_handler.assert_not_called()
    question_handler.assert_not_called()
    check_handler.assert_not_called()
    raw_handler.assert_called_once_with("https://example.com/article")
    reply.assert_called_once_with(
        "test-reply-token",
        (
            "已儲存原始筆記：\n\n"
            "Title: Example Article\n"
            "Path: vault/Inbox/2026-06-18-example-article.md"
        ),
        CHANNEL_ACCESS_TOKEN,
    )


def test_raw_command_prefers_github_url_in_reply() -> None:
    body = _webhook_body("/raw https://example.com/article")
    raw_handler = Mock(
        return_value={
            "success": True,
            "title": "Example Article",
            "path": "Inbox/example.md",
            "html_url": "https://github.com/owner/repo/blob/main/Inbox/example.md",
            "error": None,
        }
    )

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            Mock(),
            None,
            None,
            raw_handler,
        )

    message = reply.call_args.args[1]
    assert "GitHub: https://github.com/" in message
    assert "Path:" not in message


def test_recent_command_lists_up_to_five_notes() -> None:
    body = _webhook_body("/最近")
    recent_handler = Mock(
        return_value=[
            {
                "title": "new",
                "path": "Inbox/2026-06-18-new.md",
                "html_url": "",
                "snippet": "",
            },
            {
                "title": "old",
                "path": "Inbox/2026-06-17-old.md",
                "html_url": "",
                "snippet": "",
            },
        ]
    )

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            Mock(),
            None,
            None,
            None,
            recent_handler,
        )

    recent_handler.assert_called_once_with()
    reply.assert_called_once_with(
        "test-reply-token",
        (
            "最近 5 篇筆記：\n\n"
            "1. 2026-06-18-new.md\n"
            "2. 2026-06-17-old.md"
        ),
        CHANNEL_ACCESS_TOKEN,
    )


def test_recent_command_handles_empty_storage() -> None:
    body = _webhook_body("/最近")

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            Mock(),
            None,
            None,
            None,
            Mock(return_value=[]),
        )

    assert reply.call_args.args[1] == "目前還沒有找到任何 Markdown 筆記。"


def test_search_command_returns_matching_notes_without_llm() -> None:
    body = _webhook_body("/搜尋 Rust")
    question_handler = Mock()
    search_handler = Mock(
        return_value=[
            {
                "title": "Rust Ownership",
                "path": "Inbox/2026-06-18-rust-ownership.md",
                "html_url": "",
                "snippet": "...ownership is Rust's unique feature...",
            }
        ]
    )

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            Mock(),
            question_handler,
            None,
            None,
            None,
            search_handler,
        )

    question_handler.assert_not_called()
    search_handler.assert_called_once_with("Rust")
    message = reply.call_args.args[1]
    assert "找到 1 篇相關筆記" in message
    assert "Rust Ownership" in message
    assert "2026-06-18-rust-ownership.md" in message
    assert "ownership is Rust's unique feature" in message


def test_search_command_returns_no_match_message() -> None:
    body = _webhook_body("/搜尋 unlikelykeyword123")

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            Mock(),
            None,
            None,
            None,
            None,
            Mock(return_value=[]),
        )

    assert reply.call_args.args[1] == (
        "找不到包含「unlikelykeyword123」的筆記。"
    )


def test_normal_message_uses_question_handler() -> None:
    body = _webhook_body("AI Agent 的重點是什麼？")
    question_handler = Mock(return_value="根據筆記，AI Agent 能使用工具。")

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            Mock(),
            question_handler,
        )

    question_handler.assert_called_once_with("AI Agent 的重點是什麼？")
    reply.assert_called_once_with(
        "test-reply-token",
        "根據筆記，AI Agent 能使用工具。",
        CHANNEL_ACCESS_TOKEN,
    )


def test_invalid_command_replies_with_usage() -> None:
    body = _webhook_body("/紀錄")

    with patch("app.line_bot._reply_text") as reply:
        process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            Mock(),
        )

    assert "/紀錄 https://example.com/article" in reply.call_args.args[1]


def test_webhook_route_acknowledges_missing_credentials() -> None:
    body = _webhook_body()
    settings = SimpleNamespace(
        line_channel_secret="",
        line_channel_access_token="",
    )

    with patch("app.main.settings", settings):
        response = client.post(
            "/line/webhook",
            content=body,
            headers={"X-Line-Signature": _signature(body)},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_webhook_route_rejects_invalid_signature() -> None:
    body = _webhook_body()
    settings = SimpleNamespace(
        line_channel_secret=CHANNEL_SECRET,
        line_channel_access_token=CHANNEL_ACCESS_TOKEN,
        vault_path="vault",
    )

    with patch("app.main.settings", settings):
        response = client.post(
            "/line/webhook",
            content=body,
            headers={"X-Line-Signature": "invalid"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid LINE webhook signature."
    }


def test_webhook_route_processes_valid_request() -> None:
    body = _webhook_body()
    settings = SimpleNamespace(
        line_channel_secret=CHANNEL_SECRET,
        line_channel_access_token=CHANNEL_ACCESS_TOKEN,
        vault_path="vault",
    )

    with (
        patch("app.main.settings", settings),
        patch("app.main.process_line_webhook", return_value=1) as process,
    ):
        response = client.post(
            "/line/webhook",
            content=body,
            headers={"X-Line-Signature": _signature(body)},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    process.assert_called_once()


def test_webhook_verify_with_empty_events_returns_ok() -> None:
    body = json.dumps({"events": []}, separators=(",", ":"))

    response = client.post(
        "/line/webhook",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_nonempty_webhook_without_signature_is_rejected() -> None:
    body = _webhook_body()
    settings = SimpleNamespace(
        line_channel_secret=CHANNEL_SECRET,
        line_channel_access_token=CHANNEL_ACCESS_TOKEN,
        vault_path="vault",
    )

    with patch("app.main.settings", settings):
        response = client.post(
            "/line/webhook",
            content=body,
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid LINE webhook signature."
    }


def test_webhook_route_acknowledges_processing_errors() -> None:
    body = _webhook_body()
    settings = SimpleNamespace(
        line_channel_secret=CHANNEL_SECRET,
        line_channel_access_token=CHANNEL_ACCESS_TOKEN,
        vault_path="vault",
    )

    with (
        patch("app.main.settings", settings),
        patch(
            "app.main.process_line_webhook",
            side_effect=RuntimeError("internal provider details"),
        ),
    ):
        response = client.post(
            "/line/webhook",
            content=body,
            headers={"X-Line-Signature": _signature(body)},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_save_handler_exception_replies_with_short_failure() -> None:
    body = _webhook_body()
    save_handler = Mock(side_effect=RuntimeError("full storage error"))

    with patch("app.line_bot._reply_text") as reply:
        count = process_line_webhook(
            body,
            _signature(body),
            CHANNEL_SECRET,
            CHANNEL_ACCESS_TOKEN,
            save_handler,
        )

    assert count == 1
    reply.assert_called_once_with(
        "test-reply-token",
        "儲存失敗，請稍後再試。",
        CHANNEL_ACCESS_TOKEN,
    )
