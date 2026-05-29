"""Unified error handling with retry logic and user-friendly messages.

Provides centralized error handling for GitHub, AI, and general API errors
with exponential backoff retry and graceful degradation.
"""

from __future__ import annotations

import logging
import socket
import time
from typing import Any, Callable, TypeVar

from ai_code_reviewer.ai.client import AIClientError, AIResponseParseError
from ai_code_reviewer.github.client import (
    GitHubClientError,
    GitHubNotFoundError,
    GitHubPermissionError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 60.0


class ErrorHandler:
    """Unified error handler with retry logic and user-friendly messages.

    Provides methods to handle different error types from GitHub, AI,
    and general API calls with exponential backoff retry.
    """

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: float = DEFAULT_BASE_DELAY,
        max_delay: float = DEFAULT_MAX_DELAY,
    ) -> None:
        """Initialize ErrorHandler.

        Args:
            max_retries: Maximum number of retry attempts.
            base_delay: Base delay in seconds for exponential backoff.
            max_delay: Maximum delay in seconds between retries.
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def handle_api_error(self, error: Exception) -> str:
        """Handle general API errors and return user-friendly message.

        Args:
            error: The exception to handle.

        Returns:
            User-friendly error message string.
        """
        if isinstance(error, GitHubClientError):
            return self.handle_github_error(error)
        if isinstance(error, AIClientError):
            return self.handle_ai_error(error)
        if isinstance(error, TimeoutError):
            return "The request timed out. Please try again later."
        if isinstance(error, ConnectionError):
            return "Unable to connect to the server. Please check your internet connection."
        if isinstance(error, PermissionError):
            return "Permission denied. Please check your access rights."
        return f"An unexpected error occurred: {error}"

    def handle_github_error(self, error: Exception) -> str:
        """Handle GitHub-specific errors and return user-friendly message.

        Args:
            error: The exception to handle.

        Returns:
            User-friendly error message string.
        """
        if isinstance(error, GitHubNotFoundError):
            return f"Resource not found: {error}"
        if isinstance(error, GitHubPermissionError):
            return "Access denied. Please check your GitHub token permissions."
        if isinstance(error, GitHubClientError):
            if error.status_code == 403:
                return "GitHub API rate limit exceeded. Please wait and try again."
            if error.status_code and error.status_code >= 500:
                return "GitHub is experiencing issues. Please try again later."
            return f"GitHub error: {error}"
        return f"GitHub error: {error}"

    def handle_ai_error(self, error: Exception) -> str:
        """Handle AI-specific errors and return user-friendly message.

        Args:
            error: The exception to handle.

        Returns:
            User-friendly error message string.
        """
        if isinstance(error, AIResponseParseError):
            return "Failed to parse AI response. The model may have returned invalid data."
        if isinstance(error, AIClientError):
            error_str = str(error).lower()
            if "authentication" in error_str:
                return "AI API authentication failed. Please check your API key."
            if "rate limit" in error_str:
                return "AI API rate limit exceeded. Please wait and try again."
            if "timeout" in error_str:
                return "AI request timed out. Please try again."
            return f"AI error: {error}"
        return f"AI error: {error}"

    def retry_with_backoff(
        self,
        func: Callable[..., T],
        max_retries: int | None = None,
        base_delay: float | None = None,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ) -> T:
        """Execute a function with exponential backoff retry.

        Args:
            func: The function to execute.
            max_retries: Maximum retry attempts (overrides instance default).
            base_delay: Base delay in seconds (overrides instance default).
            retryable_exceptions: Tuple of exception types to retry on.
                Defaults to (TimeoutError, ConnectionError, OSError).

        Returns:
            The result of the function call.

        Raises:
            The last exception if all retries are exhausted.
        """
        retries = max_retries if max_retries is not None else self.max_retries
        delay = base_delay if base_delay is not None else self.base_delay
        if retryable_exceptions is None:
            retryable_exceptions = (TimeoutError, ConnectionError, OSError)

        last_exception: Exception | None = None

        for attempt in range(retries + 1):
            try:
                return func()
            except retryable_exceptions as exc:
                last_exception = exc
                if attempt == retries:
                    logger.error(
                        "All %d retry attempts exhausted. Last error: %s",
                        retries,
                        exc,
                    )
                    raise
                current_delay = min(delay * (2 ** attempt), self.max_delay)
                logger.warning(
                    "Attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt + 1,
                    retries,
                    type(exc).__name__,
                    current_delay,
                )
                time.sleep(current_delay)
            except Exception as exc:
                logger.error("Non-retryable error: %s", exc)
                raise

        raise RuntimeError("Unexpected retry loop exit") from last_exception

    def format_error_message(self, error: Exception) -> str:
        """Format an error into a user-friendly message.

        Args:
            error: The exception to format.

        Returns:
            Formatted user-friendly error message.
        """
        # Try specific handlers first
        if isinstance(error, GitHubClientError):
            return self.handle_github_error(error)
        if isinstance(error, AIClientError):
            return self.handle_ai_error(error)

        # Handle common system errors
        if isinstance(error, TimeoutError):
            return "The operation timed out. Please try again."
        if isinstance(error, ConnectionError):
            return "Connection failed. Please check your network."
        if isinstance(error, PermissionError):
            return "Permission denied. Please check your access rights."
        if isinstance(error, socket.timeout):
            return "The connection timed out. Please try again."
        if isinstance(error, OSError):
            return f"System error: {error}"

        # Generic fallback
        return f"An error occurred: {error}"

    def get_degraded_response(self, error: Exception, context: str = "") -> dict[str, Any]:
        """Provide a graceful degradation response when an operation fails.

        Args:
            error: The exception that caused the failure.
            context: Additional context about what failed.

        Returns:
            Dict with degraded response data.
        """
        error_message = self.format_error_message(error)

        return {
            "success": False,
            "error": error_message,
            "context": context,
            "degraded": True,
            "risks": [],
            "summary": f"Analysis incomplete due to error: {error_message}",
        }
