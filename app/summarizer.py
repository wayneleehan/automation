"""Create structured Obsidian Markdown notes with the OpenAI API."""

import logging
import os
from datetime import date
from typing import NotRequired, TypedDict

import requests
from openai import OpenAI


DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
logger = logging.getLogger(__name__)


class SummaryResult(TypedDict):
    """Stable result shape for LLM summarization."""

    success: bool
    markdown: str
    error: str | None
    error_code: NotRequired[str | None]
    provider: NotRequired[str | None]


SYSTEM_INSTRUCTIONS = """\
你是一位嚴謹的知識整理助手。請將文章轉換為適合 Obsidian 的 Markdown 筆記。

規則：
1. 預設使用繁體中文。
2. 保留文章標題與來源 URL。
3. 產生 3 到 7 個實用、簡短的 tags。
4. 筆記必須精簡、有結構，並使用指定章節。
5. 不得加入文章沒有支持的事實。
6. 如果文章太短、內容不清楚或資訊不足，必須在筆記中明確說明。
7. 只輸出 Markdown，不要使用 Markdown 程式碼圍欄，也不要加入前言。
"""


def _build_prompt(title: str, url: str, text: str) -> str:
    return f"""\
請依照以下格式建立筆記：

---
title: "{title}"
source: "{url}"
created: "{date.today().isoformat()}"
tags:
  - tag-1
  - tag-2
  - tag-3
type: web-clip
---

# {title}

## Summary

## Key Points

## Why It Matters

## My Notes

## Related Concepts

文章內容如下：

<article>
{text}
</article>
"""


def _strip_markdown_fence(markdown: str) -> str:
    cleaned = markdown.strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            return "\n".join(lines[1:-1]).strip()
    return cleaned


def _openai_error_code(exc: Exception) -> str | None:
    """Extract a stable OpenAI error code without exposing error details."""

    code = getattr(exc, "code", None)
    if isinstance(code, str):
        return code

    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            return error["code"]

    if "insufficient_quota" in str(exc):
        return "insufficient_quota"
    return None


def _summarize_with_openai(
    api_key: str,
    title: str,
    url: str,
    text: str,
) -> str:
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        instructions=SYSTEM_INSTRUCTIONS,
        input=_build_prompt(title, url, text),
        max_output_tokens=2000,
    )
    return _strip_markdown_fence(response.output_text)


def _summarize_with_gemini(
    api_key: str,
    title: str,
    url: str,
    text: str,
) -> str:
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    response = requests.post(
        GEMINI_API_URL.format(model=model),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "system_instruction": {
                "parts": [{"text": SYSTEM_INSTRUCTIONS}],
            },
            "contents": [
                {
                    "parts": [
                        {"text": _build_prompt(title, url, text)},
                    ]
                }
            ],
            "generationConfig": {"maxOutputTokens": 2000},
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    parts = payload["candidates"][0]["content"]["parts"]
    output = "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict)
    )
    return _strip_markdown_fence(output)


def summarize_to_markdown(title: str, url: str, text: str) -> SummaryResult:
    """Summarize with OpenAI first, then Gemini as a fallback."""

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not openai_key and not gemini_key:
        return {
            "success": False,
            "markdown": "",
            "error": "No LLM API key is configured.",
            "error_code": "missing_api_keys",
            "provider": None,
        }

    openai_error_code: str | None = None
    if openai_key:
        try:
            markdown = _summarize_with_openai(
                openai_key,
                title,
                url,
                text,
            )
            if not markdown:
                raise ValueError("OpenAI returned an empty response")
            return {
                "success": True,
                "markdown": markdown,
                "error": None,
                "error_code": None,
                "provider": "openai",
            }
        except Exception as exc:
            openai_error_code = _openai_error_code(exc)
            logger.exception(
                "OpenAI summarization failed; trying Gemini fallback"
            )

    if gemini_key:
        try:
            markdown = _summarize_with_gemini(
                gemini_key,
                title,
                url,
                text,
            )
            if not markdown:
                raise ValueError("Gemini returned an empty response")
            return {
                "success": True,
                "markdown": markdown,
                "error": None,
                "error_code": None,
                "provider": "gemini",
            }
        except Exception:
            logger.exception("Gemini fallback summarization failed")

    error_code = (
        "insufficient_quota"
        if openai_error_code == "insufficient_quota"
        else "all_providers_failed"
    )
    return {
        "success": False,
        "markdown": "",
        "error": "All configured LLM providers failed.",
        "error_code": error_code,
        "provider": None,
    }
