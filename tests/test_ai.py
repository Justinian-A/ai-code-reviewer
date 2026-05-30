"""Tests for AI client module."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ai_code_reviewer.ai.client import (
    AIClient,
    AIClientError,
    AIResponseParseError,
    DEFAULT_MODELS,
)
from ai_code_reviewer.config import AIProvider
from ai_code_reviewer.models import ChangeType, FileChange, RiskLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(content: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    """Create a mock LiteLLM ModelResponse."""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
        model="test-model",
    )


def _risks_json():
    """Sample risks JSON payload."""
    return json.dumps({
        "risks": [
            {
                "level": "high",
                "category": "security",
                "message": "Hardcoded secret detected",
                "suggestion": "Use environment variables",
            },
            {
                "level": "medium",
                "category": "logic",
                "message": "Potential null pointer",
                "suggestion": "Add null check",
            },
        ],
        "summary": "Found 2 issues in the code.",
    })


def _summary_json():
    """Sample summary JSON payload."""
    return json.dumps({"summary": "Added auth module with JWT support."})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create an AIClient with test credentials."""
    return AIClient(
        provider="openai",
        api_key="test-key",
        model="gpt-4o",
    )


@pytest.fixture
def deepseek_client():
    """Create a DeepSeek AIClient."""
    return AIClient(
        provider="deepseek",
        api_key="ds-key",
        model="deepseek-chat",
    )


@pytest.fixture
def claude_client():
    """Create a Claude AIClient."""
    return AIClient(
        provider="claude",
        api_key="claude-key",
        model="claude-sonnet-4-20250514",
    )


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


class TestAIClientInit:
    """Test AIClient initialization."""

    def test_init_sets_provider(self, client):
        assert client.provider == AIProvider.OPENAI

    def test_init_sets_api_key(self, client):
        assert client.api_key == "test-key"

    def test_init_auto_prefixes_model(self):
        c = AIClient(provider="deepseek", api_key="k", model="deepseek-chat")
        assert c.model == "deepseek/deepseek-chat"

    def test_init_preserves_prefixed_model(self):
        c = AIClient(provider="openai", api_key="k", model="openai/gpt-4o")
        assert c.model == "openai/gpt-4o"

    def test_init_sets_max_tokens(self, client):
        assert client.max_tokens == 4096

    def test_init_default_cost_report(self, client):
        report = client.cost_report
        assert report.input_tokens == 0
        assert report.output_tokens == 0
        assert report.total_cost_usd == 0.0

    def test_invalid_provider_raises(self):
        with pytest.raises((ValueError, Exception)):
            AIClient(provider="invalid", api_key="k", model="m")


# ---------------------------------------------------------------------------
# Model resolution tests
# ---------------------------------------------------------------------------


class TestModelResolution:
    """Test model name resolution."""

    def test_deepseek_prefix(self, deepseek_client):
        assert deepseek_client.model == "deepseek/deepseek-chat"

    def test_claude_prefix(self, claude_client):
        assert claude_client.model == "anthropic/claude-sonnet-4-20250514"

    def test_openai_prefix(self, client):
        assert client.model == "openai/gpt-4o"

    def test_already_prefixed_model(self):
        c = AIClient(provider="openai", api_key="k", model="deepseek/deepseek-chat")
        assert c.model == "deepseek/deepseek-chat"


# ---------------------------------------------------------------------------
# switch_provider tests
# ---------------------------------------------------------------------------


class TestSwitchProvider:
    """Test provider switching."""

    def test_switch_to_deepseek(self, client):
        client.switch_provider("deepseek")
        assert client.provider == AIProvider.DEEPSEEK
        assert client.model == DEFAULT_MODELS[AIProvider.DEEPSEEK]

    def test_switch_to_claude(self, client):
        client.switch_provider("claude")
        assert client.provider == AIProvider.CLAUDE
        assert client.model == DEFAULT_MODELS[AIProvider.CLAUDE]

    def test_switch_to_openai(self, deepseek_client):
        deepseek_client.switch_provider("openai")
        assert deepseek_client.provider == AIProvider.OPENAI
        assert deepseek_client.model == DEFAULT_MODELS[AIProvider.OPENAI]

    def test_switch_invalid_provider_raises(self, client):
        with pytest.raises(ValueError):
            client.switch_provider("nonexistent")


# ---------------------------------------------------------------------------
# analyze_code tests
# ---------------------------------------------------------------------------


class TestAnalyzeCode:
    """Test code analysis."""

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_returns_analysis_result(self, mock_completion, client):
        mock_completion.return_value = _make_response(_risks_json())

        result = client.analyze_code("print('hello')", "test.py")

        assert result.summary == "Found 2 issues in the code."
        assert len(result.risks) == 2
        assert result.risks[0].level == RiskLevel.HIGH
        assert result.risks[0].category.value == "security"

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_passes_correct_messages(self, mock_completion, client):
        mock_completion.return_value = _make_response(_risks_json())

        client.analyze_code("x = 1", "main.py")

        call_args = mock_completion.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        assert any(m["role"] == "system" for m in messages)
        assert any("x = 1" in m["content"] for m in messages)

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_passes_api_key(self, mock_completion, client):
        mock_completion.return_value = _make_response(_risks_json())

        client.analyze_code("x = 1", "main.py")

        call_args = mock_completion.call_args
        assert (call_args.kwargs.get("api_key") or call_args[1].get("api_key")) == "test-key"

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_tracks_cost(self, mock_completion, client):
        mock_completion.return_value = _make_response(_risks_json(), 200, 100)

        client.analyze_code("x = 1", "main.py")

        report = client.cost_report
        assert report.input_tokens == 200
        assert report.output_tokens == 100
        assert report.model_name == "openai/gpt-4o"

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_handles_response_without_fences(self, mock_completion, client):
        raw = _risks_json()
        mock_completion.return_value = _make_response(raw)

        result = client.analyze_code("x = 1", "main.py")
        assert len(result.risks) == 2

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_handles_malformed_risk_gracefully(self, mock_completion, client):
        data = json.dumps({
            "risks": [
                {"level": "high", "category": "security", "message": "ok"},
                {"bad": "entry"},
            ],
            "summary": "partial",
        })
        mock_completion.return_value = _make_response(data)

        result = client.analyze_code("x = 1", "main.py")
        assert len(result.risks) == 1


# ---------------------------------------------------------------------------
# detect_issues tests
# ---------------------------------------------------------------------------


class TestDetectIssues:
    """Test issue detection."""

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_returns_risk_list(self, mock_completion, client):
        mock_completion.return_value = _make_response(_risks_json())

        risks = client.detect_issues("eval(input())")

        assert len(risks) == 2
        assert risks[0].level == RiskLevel.HIGH
        assert risks[1].level == RiskLevel.MEDIUM

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_empty_risks(self, mock_completion, client):
        mock_completion.return_value = _make_response(json.dumps({"risks": []}))

        risks = client.detect_issues("x = 1")
        assert risks == []

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_tracks_cost(self, mock_completion, client):
        mock_completion.return_value = _make_response(_risks_json(), 150, 80)

        client.detect_issues("x = 1")

        assert client.cost_report.input_tokens == 150
        assert client.cost_report.output_tokens == 80


# ---------------------------------------------------------------------------
# generate_summary tests
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    """Test summary generation."""

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_returns_summary_string(self, mock_completion, client):
        mock_completion.return_value = _make_response(_summary_json())

        changes = [
            FileChange(
                file_path="auth.py",
                change_type=ChangeType.FEATURE,
                additions=50,
                deletions=5,
            )
        ]
        summary = client.generate_summary(changes)

        assert summary == "Added auth module with JWT support."

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_includes_change_details_in_prompt(self, mock_completion, client):
        mock_completion.return_value = _make_response(_summary_json())

        changes = [
            FileChange(
                file_path="main.py",
                change_type=ChangeType.FIX,
                additions=10,
                deletions=3,
            ),
            FileChange(
                file_path="utils.py",
                change_type=ChangeType.REFACTOR,
                additions=20,
                deletions=15,
            ),
        ]
        client.generate_summary(changes)

        call_args = mock_completion.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        assert "main.py" in user_msg
        assert "utils.py" in user_msg


# ---------------------------------------------------------------------------
# Retry tests
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """Test exponential backoff retry."""

    @patch("ai_code_reviewer.ai.client.time.sleep")
    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_retries_on_rate_limit(self, mock_completion, mock_sleep, client):
        import litellm

        mock_completion.side_effect = [
            litellm.RateLimitError("rate limited", model="m", llm_provider="p"),
            _make_response(_risks_json()),
        ]

        result = client.detect_issues("x = 1")
        assert len(result) == 2
        assert mock_completion.call_count == 2
        mock_sleep.assert_called_once()

    @patch("ai_code_reviewer.ai.client.time.sleep")
    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_retries_on_timeout(self, mock_completion, mock_sleep, client):
        import litellm

        mock_completion.side_effect = [
            litellm.Timeout("timeout", model="m", llm_provider="p"),
            _make_response(_risks_json()),
        ]

        result = client.detect_issues("x = 1")
        assert len(result) == 2

    @patch("ai_code_reviewer.ai.client.time.sleep")
    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_raises_after_max_retries(self, mock_completion, mock_sleep, client):
        import litellm

        mock_completion.side_effect = litellm.RateLimitError(
            "rate limited", model="m", llm_provider="p"
        )

        with pytest.raises(AIClientError, match="All 3 attempts failed"):
            client.detect_issues("x = 1")

        assert mock_completion.call_count == 3

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_no_retry_on_auth_error(self, mock_completion, client):
        import litellm

        mock_completion.side_effect = litellm.AuthenticationError(
            "bad key", model="m", llm_provider="p"
        )

        with pytest.raises(AIClientError, match="Authentication failed"):
            client.detect_issues("x = 1")

        assert mock_completion.call_count == 1

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_no_retry_on_invalid_request(self, mock_completion, client):
        import litellm

        mock_completion.side_effect = litellm.InvalidRequestError(
            "bad request", model="m", llm_provider="p"
        )

        with pytest.raises(AIClientError, match="Invalid request"):
            client.detect_issues("x = 1")

        assert mock_completion.call_count == 1


# ---------------------------------------------------------------------------
# JSON extraction tests
# ---------------------------------------------------------------------------


class TestExtractJson:
    """Test JSON extraction from responses."""

    def test_plain_json(self):
        data = AIClient._extract_json('{"key": "value"}')
        assert data == {"key": "value"}

    def test_json_in_code_fence(self):
        text = '```json\n{"key": "value"}\n```'
        data = AIClient._extract_json(text)
        assert data == {"key": "value"}

    def test_json_in_plain_fence(self):
        text = '```\n{"key": "value"}\n```'
        data = AIClient._extract_json(text)
        assert data == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        data = AIClient._extract_json(text)
        assert data == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(AIResponseParseError, match="Failed to parse JSON"):
            AIClient._extract_json("not json at all")

    def test_empty_fence_raises(self):
        with pytest.raises(AIResponseParseError):
            AIClient._extract_json("```json\n```")


# ---------------------------------------------------------------------------
# Cost accumulation tests
# ---------------------------------------------------------------------------


class TestCostAccumulation:
    """Test that costs accumulate across calls."""

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_costs_accumulate(self, mock_completion, client):
        mock_completion.return_value = _make_response(_risks_json(), 100, 50)

        client.detect_issues("x = 1")
        client.detect_issues("y = 2")

        report = client.cost_report
        assert report.input_tokens == 200
        assert report.output_tokens == 100

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_cost_report_tracks_model(self, mock_completion, client):
        mock_completion.return_value = _make_response(_risks_json())
        client.detect_issues("x = 1")

        assert client.cost_report.model_name == "openai/gpt-4o"


# ---------------------------------------------------------------------------
# Generic exception and malformed risk tests
# ---------------------------------------------------------------------------


class TestGenericException:
    """Test that generic exceptions are wrapped in AIClientError."""

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_generic_exception_wrapped(self, mock_completion, client):
        """Generic Exception during completion should become AIClientError."""
        mock_completion.side_effect = RuntimeError("unexpected error")

        with pytest.raises(AIClientError, match="Unexpected error"):
            client.detect_issues("x = 1")


class TestMalformedRiskParsing:
    """Test that malformed risk entries are skipped gracefully."""

    @patch("ai_code_reviewer.ai.client.litellm.completion")
    def test_malformed_risk_skipped(self, mock_completion, client):
        """Malformed risk entries should be skipped without crashing."""
        malformed_json = json.dumps({
            "risks": [
                {
                    "level": "high",
                    "category": "security",
                    "message": "Valid risk",
                    "suggestion": "Fix it",
                },
                {
                    # Missing required 'level' field
                    "category": "security",
                    "message": "Malformed risk",
                },
                {
                    "level": "invalid_level",  # Invalid enum value
                    "category": "security",
                    "message": "Bad level",
                },
            ]
        })
        mock_completion.return_value = _make_response(malformed_json)

        result = client.detect_issues("x = 1")
        # detect_issues returns a list of Risk objects directly
        assert len(result) == 1
        assert result[0].message == "Valid risk"
