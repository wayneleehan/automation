from pathlib import Path
from unittest.mock import Mock, patch

from app.rag import answer_from_notes, search_notes


def test_search_notes_ranks_matching_markdown_notes(tmp_path: Path) -> None:
    inbox = tmp_path / "Inbox"
    inbox.mkdir()
    (inbox / "agents.md").write_text(
        '---\ntitle: "AI Agents"\n---\n'
        "# AI Agents\n\nAI Agent 可以使用工具完成自動化任務。",
        encoding="utf-8",
    )
    (inbox / "cooking.md").write_text(
        "# Cooking\n\nA recipe for soup.",
        encoding="utf-8",
    )

    results = search_notes("AI Agent 的重點是什麼？", tmp_path)

    assert len(results) == 1
    assert results[0]["title"] == "AI Agents"
    assert results[0]["path"].endswith("agents.md")
    assert "自動化任務" in results[0]["snippet"]
    assert results[0]["score"] > 0


def test_search_notes_obeys_max_results_and_score_order(tmp_path: Path) -> None:
    (tmp_path / "one.md").write_text(
        "# Automation\n\nautomation automation automation",
        encoding="utf-8",
    )
    (tmp_path / "two.md").write_text(
        "# Notes\n\nautomation",
        encoding="utf-8",
    )

    results = search_notes("automation", tmp_path, max_results=1)

    assert len(results) == 1
    assert results[0]["path"].endswith("one.md")


def test_search_notes_returns_empty_for_missing_vault(tmp_path: Path) -> None:
    assert search_notes("AI agents", tmp_path / "missing") == []


def test_answer_from_notes_uses_only_supplied_context(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    response = Mock(output_text="AI Agent 可使用工具完成任務。\n\n參考：AI Agents")
    client = Mock()
    client.responses.create.return_value = response
    notes = [
        {
            "title": "AI Agents",
            "path": "vault/Inbox/agents.md",
            "snippet": "AI Agent 可以使用工具完成自動化任務。",
            "score": 5,
        }
    ]

    with patch("app.rag.OpenAI", return_value=client):
        result = answer_from_notes("AI Agent 的重點？", notes)

    assert result["success"] is True
    assert result["sources"] == ["vault/Inbox/agents.md"]
    request = client.responses.create.call_args.kwargs
    assert "只能根據" in request["instructions"]
    assert "不得使用外部知識" in request["instructions"]
    assert notes[0]["snippet"] in request["input"]


def test_answer_from_notes_handles_no_matches() -> None:
    result = answer_from_notes("unknown", [])

    assert result["success"] is False
    assert result["answer"] == "找不到與這個問題相關的筆記。"


def test_answer_from_notes_handles_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    notes = [
        {
            "title": "Example",
            "path": "vault/Inbox/example.md",
            "snippet": "Relevant text.",
            "score": 1,
        }
    ]

    result = answer_from_notes("Question", notes)

    assert result["success"] is False
    assert "OPENAI_API_KEY" in result["answer"]
