"""Cost tracking and budget management for AI API usage."""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ai_code_reviewer.models import CostReport

logger = logging.getLogger(__name__)

# Model pricing per 1M tokens (in USD)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "deepseek-v4-flash": {"input": 0.14, "output": 0.28},
    "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
}


@dataclass
class UsageEntry:
    """Single API usage record."""

    input_tokens: int
    output_tokens: int
    model: str
    cost: float


@dataclass
class CostReportData:
    """Detailed cost report data."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    usage_entries: List[UsageEntry] = field(default_factory=list)
    budget_limit: float = 0.0
    budget_remaining: float = 0.0


class CostTracker:
    """Tracks API usage costs and manages budgets.

    Supports multiple AI models with different pricing.
    Provides cost estimation, budget checking, and warning mechanisms.
    """

    def __init__(self, budget_limit: float = 0.0) -> None:
        """Initialize the cost tracker.

        Args:
            budget_limit: Maximum budget in USD. 0 means no limit.
        """
        self._budget_limit: float = budget_limit
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._total_cost: float = 0.0
        self._usage_history: List[UsageEntry] = []
        self._budget_warned: bool = False

    @property
    def budget_limit(self) -> float:
        """Get the current budget limit."""
        return self._budget_limit

    @budget_limit.setter
    def budget_limit(self, value: float) -> None:
        """Set a new budget limit.

        Args:
            value: New budget limit in USD. Must be non-negative.
        """
        if value < 0:
            raise ValueError("Budget limit must be non-negative")
        self._budget_limit = value
        self._budget_warned = False

    def track_usage(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Track API usage and calculate cost.

        Args:
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens used.
            model: Model identifier (e.g., 'gpt-4o', 'claude-sonnet-4-5').

        Returns:
            Cost for this usage in USD.

        Raises:
            ValueError: If token counts are negative or model is unknown.
        """
        if input_tokens < 0:
            raise ValueError(f"input_tokens must be non-negative, got {input_tokens}")
        if output_tokens < 0:
            raise ValueError(f"output_tokens must be non-negative, got {output_tokens}")

        cost = self.estimate_cost(input_tokens, output_tokens, model)

        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_cost += cost

        entry = UsageEntry(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            cost=cost,
        )
        self._usage_history.append(entry)

        self._check_budget_warning()

        return cost

    def get_total_cost(self) -> float:
        """Get the total accumulated cost.

        Returns:
            Total cost in USD.
        """
        return self._total_cost

    def get_cost_report(self) -> CostReport:
        """Get a cost report as a Pydantic model.

        Returns:
            CostReport with current usage data.
        """
        last_model = self._usage_history[-1].model if self._usage_history else None
        return CostReport(
            input_tokens=self._total_input_tokens,
            output_tokens=self._total_output_tokens,
            total_cost_usd=self._total_cost,
            model_name=last_model,
        )

    def get_detailed_report(self) -> CostReportData:
        """Get a detailed cost report with usage history.

        Returns:
            CostReportData with full usage details.
        """
        budget_remaining = 0.0
        if self._budget_limit > 0:
            budget_remaining = max(0.0, self._budget_limit - self._total_cost)

        return CostReportData(
            total_input_tokens=self._total_input_tokens,
            total_output_tokens=self._total_output_tokens,
            total_cost_usd=self._total_cost,
            usage_entries=list(self._usage_history),
            budget_limit=self._budget_limit,
            budget_remaining=budget_remaining,
        )

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Estimate cost for given token counts without tracking.

        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            model: Model identifier.

        Returns:
            Estimated cost in USD.

        Raises:
            ValueError: If model is unknown or token counts are negative.
        """
        if input_tokens < 0:
            raise ValueError(f"input_tokens must be non-negative, got {input_tokens}")
        if output_tokens < 0:
            raise ValueError(f"output_tokens must be non-negative, got {output_tokens}")

        pricing = MODEL_PRICING.get(model)
        if pricing is None:
            raise ValueError(
                f"Unknown model: {model}. "
                f"Supported models: {', '.join(sorted(MODEL_PRICING.keys()))}"
            )

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def check_budget(self) -> bool:
        """Check if current spending is within budget.

        Returns:
            True if within budget (or no budget set), False if over budget.
        """
        if self._budget_limit <= 0:
            return True
        return self._total_cost <= self._budget_limit

    def get_budget_usage_percent(self) -> float:
        """Get budget usage as a percentage.

        Returns:
            Percentage of budget used (0-100+). Returns 0 if no budget set.
        """
        if self._budget_limit <= 0:
            return 0.0
        return (self._total_cost / self._budget_limit) * 100.0

    def reset(self) -> None:
        """Reset all tracking data.

        Clears usage history and totals. Budget limit is preserved.
        """
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost = 0.0
        self._usage_history.clear()
        self._budget_warned = False

    def _check_budget_warning(self) -> None:
        """Check and log budget warnings.

        Warns at 80% usage and when budget is exceeded.
        """
        if self._budget_limit <= 0:
            return

        usage_percent = self.get_budget_usage_percent()

        if usage_percent >= 100:
            logger.warning(
                "Budget exceeded! Current cost: $%.4f / Budget: $%.2f (%.1f%%)",
                self._total_cost,
                self._budget_limit,
                usage_percent,
            )
        elif usage_percent >= 80 and not self._budget_warned:
            logger.warning(
                "Budget warning: %.1f%% used. Current cost: $%.4f / Budget: $%.2f",
                usage_percent,
                self._total_cost,
                self._budget_limit,
            )
            self._budget_warned = True
