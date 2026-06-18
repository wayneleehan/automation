from unittest.mock import Mock, patch

from app.summarizer import summarize_to_markdown


def test_returns_clear_error_when_api_key_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    result = summarize_to_markdown(
        "Example Article",
        "https://example.com/article",
        "Article text.",
    )

    assert result == {
        "success": False,
        "markdown": "",
        "error": "No LLM API key is configured.",
        "error_code": "missing_api_keys",
        "provider": None,
    }


def test_generates_structured_markdown_with_responses_api(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    response = Mock()
    response.output_text = "---\ntitle: Example\n---\n\n# Example"
    client = Mock()
    client.responses.create.return_value = response

    with patch("app.summarizer.OpenAI", return_value=client) as openai:
        result = summarize_to_markdown(
            "Example Article",
            "https://example.com/article",
            "Supported article text.",
        )

    assert result == {
        "success": True,
        "markdown": "---\ntitle: Example\n---\n\n# Example",
        "error": None,
        "error_code": None,
        "provider": "openai",
    }
    openai.assert_called_once_with(api_key="test-key")

    request = client.responses.create.call_args.kwargs
    assert request["model"] == "test-model"
    assert request["max_output_tokens"] == 2000
    assert "繁體中文" in request["instructions"]
    assert "3 到 7" in request["instructions"]
    assert "不得加入文章沒有支持的事實" in request["instructions"]
    assert "資訊不足" in request["instructions"]
    assert "https://example.com/article" in request["input"]
    assert "Supported article text." in request["input"]
    assert "## Related Concepts" in request["input"]


def test_removes_markdown_code_fence(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = Mock()
    response.output_text = "```markdown\n# Example\n\nSummary\n```"
    client = Mock()
    client.responses.create.return_value = response

    with patch("app.summarizer.OpenAI", return_value=client):
        result = summarize_to_markdown(
            "Example",
            "https://example.com",
            "Short text.",
        )

    assert result["success"] is True
    assert result["markdown"] == "# Example\n\nSummary"


def test_returns_error_when_api_call_fails(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = Mock()
    client.responses.create.side_effect = RuntimeError("service unavailable")

    with patch("app.summarizer.OpenAI", return_value=client):
        result = summarize_to_markdown(
            "Example",
            "https://example.com",
            "Article text.",
        )

    assert result["success"] is False
    assert result["markdown"] == ""
    assert result["error"] == "All configured LLM providers failed."
    assert result["error_code"] == "all_providers_failed"
    assert result["provider"] is None


def test_identifies_insufficient_quota_without_exposing_details(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = Mock()
    client.responses.create.side_effect = RuntimeError(
        "429 insufficient_quota secret provider details"
    )

    with patch("app.summarizer.OpenAI", return_value=client):
        result = summarize_to_markdown(
            "Example",
            "https://example.com",
            "Article text.",
        )

    assert result == {
        "success": False,
        "markdown": "",
        "error": "All configured LLM providers failed.",
        "error_code": "insufficient_quota",
        "provider": None,
    }


def test_uses_gemini_when_openai_quota_is_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")
    openai_client = Mock()
    openai_client.responses.create.side_effect = RuntimeError(
        "429 insufficient_quota"
    )
    gemini_response = Mock()
    gemini_response.raise_for_status.return_value = None
    gemini_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "# Gemini Summary\n\nFallback worked."}
                    ]
                }
            }
        ]
    }

    with (
        patch("app.summarizer.OpenAI", return_value=openai_client),
        patch(
            "app.summarizer.requests.post",
            return_value=gemini_response,
        ) as post,
    ):
        result = summarize_to_markdown(
            "Example",
            "https://example.com",
            "Article text.",
        )

    assert result == {
        "success": True,
        "markdown": "# Gemini Summary\n\nFallback worked.",
        "error": None,
        "error_code": None,
        "provider": "gemini",
    }
    request = post.call_args
    assert request.args[0].endswith(
        "/gemini-test-model:generateContent"
    )
    assert request.kwargs["headers"]["x-goog-api-key"] == "gemini-key"
    assert request.kwargs["timeout"] == 30
    system_text = request.kwargs["json"]["system_instruction"]["parts"][0][
        "text"
    ]
    assert "繁體中文" in system_text


def test_uses_gemini_when_openai_key_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    gemini_response = Mock()
    gemini_response.raise_for_status.return_value = None
    gemini_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "# Gemini-only summary"}]
                }
            }
        ]
    }

    with patch(
        "app.summarizer.requests.post",
        return_value=gemini_response,
    ):
        result = summarize_to_markdown(
            "Example",
            "https://example.com",
            "Article text.",
        )

    assert result["success"] is True
    assert result["provider"] == "gemini"
