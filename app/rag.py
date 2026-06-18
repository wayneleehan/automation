"""Simple keyword retrieval and grounded Q&A over Markdown notes."""

import os
import re
from pathlib import Path
from typing import TypedDict

from openai import OpenAI

from app.summarizer import DEFAULT_MODEL


MAX_SNIPPET_LENGTH = 700
STOP_WORDS = {
    "what",
    "about",
    "the",
    "and",
    "我之",
    "之前",
    "前存",
    "存過",
    "過的",
    "的是",
    "是什",
    "什麼",
}


class NoteMatch(TypedDict):
    title: str
    path: str
    snippet: str
    score: int


class AnswerResult(TypedDict):
    success: bool
    answer: str
    sources: list[str]
    error: str | None


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[a-zA-Z0-9]+|[\u3400-\u9fff]+", query.lower()):
        if re.fullmatch(r"[\u3400-\u9fff]+", token) and len(token) > 2:
            terms.extend(token[index : index + 2] for index in range(len(token) - 1))
        else:
            terms.append(token)
    return list(dict.fromkeys(term for term in terms if term not in STOP_WORDS))


def _note_title(content: str, path: Path) -> str:
    frontmatter = re.search(
        r'^title:\s*["\']?(.+?)["\']?\s*$',
        content,
        re.MULTILINE,
    )
    if frontmatter:
        return frontmatter.group(1).strip()

    heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return heading.group(1).strip() if heading else path.stem


def _relevant_snippet(content: str, terms: list[str]) -> str:
    lower_content = content.lower()
    positions = [
        lower_content.find(term)
        for term in terms
        if lower_content.find(term) >= 0
    ]
    start = max(0, min(positions, default=0) - 150)
    snippet = content[start : start + MAX_SNIPPET_LENGTH].strip()
    if start:
        snippet = f"…{snippet}"
    if start + MAX_SNIPPET_LENGTH < len(content):
        snippet = f"{snippet}…"
    return snippet


def search_notes(
    query: str,
    vault_path: str | Path,
    max_results: int = 5,
) -> list[NoteMatch]:
    """Rank Markdown notes with a small, deterministic keyword search."""

    terms = _query_terms(query)
    root = Path(vault_path)
    if not terms or not root.exists() or max_results <= 0:
        return []

    matches: list[NoteMatch] = []
    for path in root.rglob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue

        title = _note_title(content, path)
        lower_title = title.lower()
        lower_content = content.lower()
        score = sum(
            (3 if term in lower_title else 0) + lower_content.count(term)
            for term in terms
        )
        if score == 0:
            continue

        matches.append(
            {
                "title": title,
                "path": str(path),
                "snippet": _relevant_snippet(content, terms),
                "score": score,
            }
        )

    matches.sort(key=lambda note: (-note["score"], note["path"]))
    return matches[:max_results]


def answer_from_notes(
    question: str,
    notes: list[NoteMatch],
) -> AnswerResult:
    """Answer a question using only the supplied note snippets."""

    if not notes:
        return {
            "success": False,
            "answer": "找不到與這個問題相關的筆記。",
            "sources": [],
            "error": "No relevant notes found.",
        }

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {
            "success": False,
            "answer": "已找到相關筆記，但 OPENAI_API_KEY 尚未設定，無法整理答案。",
            "sources": [note["path"] for note in notes],
            "error": "OPENAI_API_KEY is not configured.",
        }

    context = "\n\n".join(
        (
            f"<note title={note['title']!r} path={note['path']!r}>\n"
            f"{note['snippet']}\n"
            "</note>"
        )
        for note in notes
    )

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            instructions=(
                "請使用繁體中文回答。只能根據提供的 Obsidian 筆記片段作答，"
                "不得使用外部知識或自行補充事實。若片段不足以回答，請明確說明。"
                "回答保持精簡，最後列出參考筆記標題。"
            ),
            input=f"問題：{question}\n\n筆記片段：\n{context}",
            max_output_tokens=1000,
        )
        answer = response.output_text.strip()
        if not answer:
            raise ValueError("The OpenAI API returned an empty response.")
    except Exception as exc:
        return {
            "success": False,
            "answer": "找到相關筆記，但目前無法產生答案，請稍後再試。",
            "sources": [note["path"] for note in notes],
            "error": f"OpenAI note Q&A failed: {exc}",
        }

    return {
        "success": True,
        "answer": answer,
        "sources": [note["path"] for note in notes],
        "error": None,
    }


def answer_question_from_vault(
    question: str,
    vault_path: str | Path,
) -> AnswerResult:
    """Search the vault and answer one question from the best note matches."""

    return answer_from_notes(question, search_notes(question, vault_path))
