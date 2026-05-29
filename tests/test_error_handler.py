"""Tests for the unified error handler."""

from __future__ import annotations

import socket
import time
from unittest.mock import MagicMock, patch

import pytest

from ai_code_reviewer.ai.client import AIClientError, AIResponseParseError
from ai_code_reviewer.github.client import (
    GitHubClientError,
    GitHubNotFoundError,
    GitHubPermissionError,
)
from ai_code_reviewer.utils.error_handler import ErrorHandler


@pytest.fixture
def handler() -> ErrorHandler:
    """Create an ErrorHandler instance for testing."""
    return ErrorHandler(max_retries=2, base_delay=0.01, max_delay=0.1)


class TestHandleGithubError:
    """Tests for handle_github_error method."""

    def test_not_found_error(self, handler: ErrorHandler) -> None:
        """Test handling of GitHub not found errors."""
        error = GitHubNotFoundError("Repository not found")
        result = handler.handle_github_error(error)
        assert "Resource not found" in result
        assert "Repository not found" in result

    def test_permission_error(self, handler: ErrorHandler) -> None:
        """Test handling of GitHub permission errors."""
        error = GitHubPermissionError("Forbidden")
        result = handler.handle_github_error(error)
        assert "Access denied" in result
        assert "token permissions" in result

    def test_rate_limit_error(self, handler: ErrorHandler) -> None:
        """Test handling of GitHub rate limit errors."""
        error = GitHubClientError("Rate limit exceeded", status_code=403)
        result = handler.handle_github_error(error)
        assert "rate limit" in result.lower()

    def test_server_error(self, handler: ErrorHandler) -> None:
        """Test handling of GitHub server errors."""
        error = GitHubClientError("Internal server error", status_code=500)
        result = handler.handle_github_error(error)
        assert "experiencing issues" in result

    def test_generic_github_error(self, handler: ErrorHandler) -> None:
        """Test handling of generic GitHub errors."""
        error = GitHubClientError("Something went wrong")
        result = handler.handle_github_error(error)
        assert "GitHub error" in result


class TestHandleAiError:
    """Tests for handle_ai_error method."""

    def test_parse_error(self, handler: ErrorHandler) -> None:
        """Test handling of AI response parse errors."""
        error = AIResponseParseError("Invalid JSON")
        result = handler.handle_ai_error(error)
        assert "parse" in result.lower()

    def test_authentication_error(self, handler: ErrorHandler) -> None:
        """Test handling of AI authentication errors."""
        error = AIClientError("Authentication failed for openai")
        result = handler.handle_ai_error(error)
        assert "authentication" in result.lower()
        assert "API key" in result

    def test_rate_limit_error(self, handler: ErrorHandler) -> None:
        """Test handling of AI rate limit errors."""
        error = AIClientError("Rate limit exceeded")
        result = handler.handle_ai_error(error)
        assert "rate limit" in result.lower()

    def test_timeout_error(self, handler: ErrorHandler) -> None:
        """Test handling of AI timeout errors."""
        error = AIClientError("Request timeout occurred")
        result = handler.handle_ai_error(error)
        assert "timed out" in result.lower()

    def test_generic_ai_error(self, handler: ErrorHandler) -> None:
        """Test handling of generic AI errors."""
        error = AIClientError("Unknown error")
        result = handler.handle_ai_error(error)
        assert "AI error" in result


class TestHandleApiError:
    """Tests for handle_api_error method."""

    def test_github_error(self, handler: ErrorHandler) -> None:
        """Test that GitHub errors are routed correctly."""
        error = GitHubNotFoundError("PR not found")
        result = handler.handle_api_error(error)
        assert "Resource not found" in result

    def test_ai_error(self, handler: ErrorHandler) -> None:
        """Test that AI errors are routed correctly."""
        error = AIClientError("API error")
        result = handler.handle_api_error(error)
        assert "AI error" in result

    def test_timeout_error(self, handler: ErrorHandler) -> None:
        """Test handling of timeout errors."""
        error = TimeoutError("Connection timed out")
        result = handler.handle_api_error(error)
        assert "timed out" in result

    def test_connection_error(self, handler: ErrorHandler) -> None:
        """Test handling of connection errors."""
        error = ConnectionError("Connection refused")
        result = handler.handle_api_error(error)
        assert "connect" in result.lower()

    def test_permission_error(self, handler: ErrorHandler) -> None:
        """Test handling of permission errors."""
        error = PermissionError("Access denied")
        result = handler.handle_api_error(error)
        assert "Permission denied" in result

    def test_generic_error(self, handler: ErrorHandler) -> None:
        """Test handling of generic errors."""
        error = ValueError("Invalid value")
        result = handler.handle_api_error(error)
        assert "unexpected error" in result.lower()


class TestRetryWithBackoff:
    """Tests for retry_with_backoff method."""

    def test_successful_call(self, handler: ErrorHandler) -> None:
        """Test that successful calls return immediately."""
        mock_func = MagicMock(return_value="success")
        result = handler.retry_with_backoff(mock_func)
        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_on_timeout(self, handler: ErrorHandler) -> None:
        """Test retry on timeout errors."""
        mock_func = MagicMock(side_effect=[TimeoutError, "success"])
        result = handler.retry_with_backoff(mock_func)
        assert result == "success"
        assert mock_func.call_count == 2

    def test_retry_on_connection_error(self, handler: ErrorHandler) -> None:
        """Test retry on connection errors."""
        mock_func = MagicMock(side_effect=[ConnectionError, "success"])
        result = handler.retry_with_backoff(mock_func)
        assert result == "success"
        assert mock_func.call_count == 2

    def test_max_retries_exceeded(self, handler: ErrorHandler) -> None:
        """Test that exception is raised after max retries."""
        mock_func = MagicMock(side_effect=TimeoutError("timeout"))
        with pytest.raises(TimeoutError):
            handler.retry_with_backoff(mock_func)
        assert mock_func.call_count == 3  # 1 initial + 2 retries

    def test_non_retryable_exception(self, handler: ErrorHandler) -> None:
        """Test that non-retryable exceptions are raised immediately."""
        mock_func = MagicMock(side_effect=ValueError("invalid"))
        with pytest.raises(ValueError):
            handler.retry_with_backoff(mock_func)
        assert mock_func.call_count == 1

    def test_custom_retryable_exceptions(self, handler: ErrorHandler) -> None:
        """Test custom retryable exceptions."""
        mock_func = MagicMock(side_effect=[ValueError, "success"])
        result = handler.retry_with_backoff(
            mock_func, retryable_exceptions=(ValueError,)
        )
        assert result == "success"
        assert mock_func.call_count == 2

    def test_custom_max_retries(self, handler: ErrorHandler) -> None:
        """Test custom max retries parameter."""
        mock_func = MagicMock(side_effect=TimeoutError("timeout"))
        with pytest.raises(TimeoutError):
            handler.retry_with_backoff(mock_func, max_retries=1)
        assert mock_func.call_count == 2  # 1 initial + 1 retry

    @patch("ai_code_reviewer.utils.error_handler.time.sleep")
    def test_exponential_backoff_delay(self, mock_sleep: MagicMock, handler: ErrorHandler) -> None:
        """Test that delays increase exponentially."""
        mock_func = MagicMock(side_effect=[TimeoutError, TimeoutError, "success"])
        result = handler.retry_with_backoff(mock_func)
        assert result == "success"
        # Verify sleep was called with increasing delays
        assert mock_sleep.call_count == 2
        first_delay = mock_sleep.call_args_list[0][0][0]
        second_delay = mock_sleep.call_args_list[1][0][0]
        assert second_delay > first_delay


class TestFormatErrorMessage:
    """Tests for format_error_message method."""

    def test_github_error(self, handler: ErrorHandler) -> None:
        """Test formatting GitHub errors."""
        error = GitHubNotFoundError("Repo not found")
        result = handler.format_error_message(error)
        assert "Resource not found" in result

    def test_ai_error(self, handler: ErrorHandler) -> None:
        """Test formatting AI errors."""
        error = AIClientError("API error")
        result = handler.format_error_message(error)
        assert "AI error" in result

    def test_timeout_error(self, handler: ErrorHandler) -> None:
        """Test formatting timeout errors."""
        error = TimeoutError("timed out")
        result = handler.format_error_message(error)
        assert "timed out" in result

    def test_connection_error(self, handler: ErrorHandler) -> None:
        """Test formatting connection errors."""
        error = ConnectionError("refused")
        result = handler.format_error_message(error)
        assert "Connection" in result

    def test_permission_error(self, handler: ErrorHandler) -> None:
        """Test formatting permission errors."""
        error = PermissionError("denied")
        result = handler.format_error_message(error)
        assert "Permission denied" in result

    def test_socket_timeout(self, handler: ErrorHandler) -> None:
        """Test formatting socket timeout errors."""
        error = socket.timeout("timed out")
        result = handler.format_error_message(error)
        assert "timed out" in result

    def test_os_error(self, handler: ErrorHandler) -> None:
        """Test formatting OS errors."""
        error = OSError("disk full")
        result = handler.format_error_message(error)
        assert "System error" in result

    def test_generic_error(self, handler: ErrorHandler) -> None:
        """Test formatting generic errors."""
        error = RuntimeError("something broke")
        result = handler.format_error_message(error)
        assert "An error occurred" in result


class TestGetDegradedResponse:
    """Tests for get_degraded_response method."""

    def test_returns_dict(self, handler: ErrorHandler) -> None:
        """Test that degraded response is a dict."""
        error = GitHubClientError("API error")
        result = handler.get_degraded_response(error)
        assert isinstance(result, dict)

    def test_contains_required_fields(self, handler: ErrorHandler) -> None:
        """Test that degraded response contains required fields."""
        error = AIClientError("AI failed")
        result = handler.get_degraded_response(error, context="code review")
        assert result["success"] is False
        assert result["degraded"] is True
        assert "error" in result
        assert "AI error" in result["error"]
        assert result["context"] == "code review"
        assert result["risks"] == []
        assert "incomplete" in result["summary"].lower()

    def test_with_context(self, handler: ErrorHandler) -> None:
        """Test degraded response with context."""
        error = TimeoutError("timeout")
        result = handler.get_degraded_response(error, context="PR analysis")
        assert result["context"] == "PR analysis"

    def test_without_context(self, handler: ErrorHandler) -> None:
        """Test degraded response without context."""
        error = ConnectionError("offline")
        result = handler.get_degraded_response(error)
        assert result["context"] == ""


class TestHandleGithubErrorFallback:
    """Tests for handle_github_error fallback path."""

    def test_generic_exception_in_handle_github_error(self, handler: ErrorHandler) -> None:
        """Non-GitHubClientError passed to handle_github_error returns fallback message."""
        error = RuntimeError("not a github error")
        result = handler.handle_github_error(error)
        assert "GitHub error" in result
        assert "not a github error" in result


class TestHandleAiErrorFallback:
    """Tests for handle_ai_error fallback path."""

    def test_generic_exception_in_handle_ai_error(self, handler: ErrorHandler) -> None:
        """Non-AIClientError passed to handle_ai_error returns fallback message."""
        error = RuntimeError("not an ai error")
        result = handler.handle_ai_error(error)
        assert "AI error" in result
        assert "not an ai error" in result
