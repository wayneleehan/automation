"""Create structured Obsidian Markdown notes with the OpenAI API."""

import logging
import os
from datetime import date
from typing import NotRequired, TypedDict

from openai import OpenAI


DEFAULT_MODEL = "gpt-4.1-mini"
logger = logging.getLogger(__name__)


class SummaryResult(TypedDict):
    """Stable result shape for LLM summarization."""

    success: bool
    markdown: str
    error: str | None
    error_code: NotRequired[str | None]


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


def summarize_to_markdown(title: str, url: str, text: str) -> SummaryResult:
    """Summarize article text as a structured Obsidian Markdown note."""

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "success": False,
            "markdown": "",
            "error": "OPENAI_API_KEY is not configured.",
            "error_code": "missing_api_key",
        }

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            instructions=SYSTEM_INSTRUCTIONS,
            input=_build_prompt(title, url, text),
            max_output_tokens=2000,
        )
        markdown = _strip_markdown_fence(response.output_text)

        if not markdown:
            return {
                "success": False,
                "markdown": "",
                "error": "The OpenAI API returned an empty response.",
                "error_code": "empty_response",
            }

        return {
            "success": True,
            "markdown": markdown,
            "error": None,
            "error_code": None,
        }
    except Exception as exc:
        logger.exception("OpenAI summarization request failed")
        return {
            "success": False,
            "markdown": "",
            "error": "OpenAI summarization request failed.",
            "error_code": _openai_error_code(exc),
        }
