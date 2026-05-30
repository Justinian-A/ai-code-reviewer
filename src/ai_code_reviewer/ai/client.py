"""AI client with unified interface for multiple LLM providers."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime
from typing import List

import litellm

from ai_code_reviewer.ai.prompts import (
    build_analyze_code_prompt,
    build_detect_issues_prompt,
    build_generate_summary_prompt,
)
from ai_code_reviewer.config import AIProvider
from ai_code_reviewer.models import (
    AnalysisResult,
    CostReport,
    FileChange,
    PullRequest,
    Risk,
    RiskCategory,
    RiskLevel,
)

logger = logging.getLogger(__name__)

# Provider to LiteLLM model prefix mapping
PROVIDER_MODEL_PREFIX: dict[str, str] = {
    AIProvider.DEEPSEEK: "deepseek/",
    AIProvider.CLAUDE: "anthropic/",
    AIProvider.OPENAI: "openai/",
}

# Default models per provider
DEFAULT_MODELS: dict[str, str] = {
    AIProvider.DEEPSEEK: "deepseek/deepseek-chat",
    AIProvider.CLAUDE: "anthropic/claude-sonnet-4-20250514",
    AIProvider.OPENAI: "openai/gpt-4o",
}

# Retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds
RETRY_BACKOFF_FACTOR = 2.0
RETRYABLE_EXCEPTIONS = (
    litellm.RateLimitError,
    litellm.Timeout,
    litellm.APIConnectionError,
    litellm.InternalServerError,
)


class AIClientError(Exception):
    """Base exception for AI client errors."""


class AIResponseParseError(AIClientError):
    """Raised when the AI response cannot be parsed."""


class AIClient:
    """Unified AI client supporting DeepSeek, Claude, and GPT-4o via LiteLLM.

    Args:
        provider: Provider name (deepseek/claude/openai).
        api_key: API key for the provider.
        model: Model identifier. If not prefixed, auto-prefixed by provider.
        max_tokens: Maximum tokens for responses.
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        max_tokens: int = 4096,
    ) -> None:
        self.provider = AIProvider(provider.lower())
        self.api_key = api_key
        self.model = self._resolve_model(model)
        self.max_tokens = max_tokens
        self._total_cost = CostReport()

    def _resolve_model(self, model: str) -> str:
        """Resolve model name to LiteLLM format.

        If the model already contains a provider prefix (e.g., 'deepseek/...'),
        use it as-is. Otherwise, prepend the provider prefix.

        Args:
            model: Raw model name.

        Returns:
            LiteLLM-compatible model string.
        """
        if "/" in model:
            return model
        prefix = PROVIDER_MODEL_PREFIX.get(self.provider, "")
        return f"{prefix}{model}"

    def switch_provider(self, provider: str) -> None:
        """Switch to a different AI provider.

        Args:
            provider: New provider name (deepseek/claude/openai).
        """
        self.provider = AIProvider(provider.lower())
        self.model = DEFAULT_MODELS[self.provider]
        logger.info("Switched to provider %s with model %s", self.provider, self.model)

    def _call_with_retry(self, messages: list[dict[str, str]]) -> litellm.ModelResponse:
        """Call the LLM with exponential backoff retry.

        Args:
            messages: Chat messages for the LLM.

        Returns:
            LiteLLM ModelResponse.

        Raises:
            AIClientError: If all retries are exhausted.
        """
        last_exception: Exception | None = None
        delay = INITIAL_RETRY_DELAY

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = litellm.completion(
                    model=self.model,
                    messages=messages,
                    api_key=self.api_key,
                    max_tokens=self.max_tokens,
                    timeout=60,
                )
                # Track usage
                if hasattr(response, "usage") and response.usage:
                    self._total_cost.input_tokens += response.usage.prompt_tokens or 0
                    self._total_cost.output_tokens += (
                        response.usage.completion_tokens or 0
                    )
                self._total_cost.model_name = self.model
                return response

            except RETRYABLE_EXCEPTIONS as exc:
                last_exception = exc
                logger.warning(
                    "Attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt,
                    MAX_RETRIES,
                    type(exc).__name__,
                    delay,
                )
                time.sleep(delay)
                delay *= RETRY_BACKOFF_FACTOR

            except litellm.AuthenticationError as exc:
                raise AIClientError(
                    f"Authentication failed for {self.provider}: {exc}"
                ) from exc

            except litellm.InvalidRequestError as exc:
                raise AIClientError(
                    f"Invalid request to {self.provider}: {exc}"
                ) from exc

            except Exception as exc:
                raise AIClientError(
                    f"Unexpected error calling {self.provider}: {exc}"
                ) from exc

        raise AIClientError(
            f"All {MAX_RETRIES} attempts failed for {self.provider}. "
            f"Last error: {last_exception}"
        )

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from a response that may contain markdown fences.

        Args:
            text: Raw response text.

        Returns:
            Parsed JSON dict.

        Raises:
            AIResponseParseError: If JSON cannot be extracted.
        """
        # Try to find JSON in code fences first
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            text = match.group(1).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIResponseParseError(
                f"Failed to parse JSON from response: {exc}"
            ) from exc

    def analyze_code(self, code: str, context: str) -> AnalysisResult:
        """Analyze code and return structured results.

        Args:
            code: Source code to analyze.
            context: Context about the code (file path, purpose, etc.).

        Returns:
            AnalysisResult with risks and summary.
        """
        messages = build_analyze_code_prompt(code, context)
        response = self._call_with_retry(messages)
        content = response.choices[0].message.content
        data = self._extract_json(content)

        risks = []
        for r in data.get("risks", []):
            try:
                risks.append(
                    Risk(
                        level=RiskLevel(r["level"].lower()),
                        category=RiskCategory(r["category"].lower()),
                        message=r["message"],
                        file_path=context,
                        suggestion=r.get("suggestion"),
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed risk entry: %s", exc)

        # Build a minimal AnalysisResult
        now = datetime.now(UTC)
        pr = PullRequest(
            number=0,
            title="Code Analysis",
            author="ai-client",
            repository="",
            head_branch="",
            created_at=now,
            updated_at=now,
        )
        return AnalysisResult(
            pr=pr,
            risks=risks,
            summary=data.get("summary"),
            cost=self._total_cost,
        )

    def generate_summary(self, changes: List[FileChange]) -> str:
        """Generate a human-readable summary of file changes.

        Args:
            changes: List of FileChange objects.

        Returns:
            Summary string.
        """
        desc_lines = []
        for c in changes:
            desc_lines.append(
                f"- {c.file_path} ({c.change_type.value}): "
                f"+{c.additions}/-{c.deletions}"
            )
        changes_desc = "\n".join(desc_lines)

        messages = build_generate_summary_prompt(changes_desc)
        response = self._call_with_retry(messages)
        content = response.choices[0].message.content
        data = self._extract_json(content)
        return data.get("summary", content)

    def detect_issues(self, code: str) -> List[Risk]:
        """Detect issues in code and return a list of risks.

        Args:
            code: Source code to scan.

        Returns:
            List of Risk objects.
        """
        messages = build_detect_issues_prompt(code)
        response = self._call_with_retry(messages)
        content = response.choices[0].message.content
        data = self._extract_json(content)

        risks = []
        for r in data.get("risks", []):
            try:
                risks.append(
                    Risk(
                        level=RiskLevel(r["level"].lower()),
                        category=RiskCategory(r["category"].lower()),
                        message=r["message"],
                        file_path="",
                        suggestion=r.get("suggestion"),
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning("Skipping malformed risk entry: %s", exc)

        return risks

    @property
    def cost_report(self) -> CostReport:
        """Return accumulated cost report."""
        return self._total_cost
