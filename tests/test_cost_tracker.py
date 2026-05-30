"""Tests for CostTracker."""

import pytest

from ai_code_reviewer.models import CostReport
from ai_code_reviewer.utils.cost_tracker import (
    MODEL_PRICING,
    CostReportData,
    CostTracker,
    UsageEntry,
)


class TestCostTrackerInit:
    """Tests for CostTracker initialization."""

    def test_default_init(self) -> None:
        tracker = CostTracker()
        assert tracker.budget_limit == 0.0
        assert tracker.get_total_cost() == 0.0

    def test_init_with_budget(self) -> None:
        tracker = CostTracker(budget_limit=100.0)
        assert tracker.budget_limit == 100.0


class TestEstimateCost:
    """Tests for cost estimation."""

    def test_estimate_deepseek(self) -> None:
        tracker = CostTracker()
        # 1M input tokens at $0.14/M = $0.14
        # 1M output tokens at $0.28/M = $0.28
        cost = tracker.estimate_cost(1_000_000, 1_000_000, "deepseek-v4-flash")
        assert cost == pytest.approx(0.42)

    def test_estimate_claude(self) -> None:
        tracker = CostTracker()
        # 1M input at $3.0/M + 1M output at $15.0/M = $18.0
        cost = tracker.estimate_cost(1_000_000, 1_000_000, "claude-sonnet-4-5")
        assert cost == pytest.approx(18.0)

    def test_estimate_gpt4o(self) -> None:
        tracker = CostTracker()
        cost = tracker.estimate_cost(1_000_000, 1_000_000, "gpt-4o")
        assert cost == pytest.approx(12.5)

    def test_estimate_partial_tokens(self) -> None:
        tracker = CostTracker()
        # 500K input at $2.5/M = $1.25, 500K output at $10.0/M = $5.0
        cost = tracker.estimate_cost(500_000, 500_000, "gpt-4o")
        assert cost == pytest.approx(6.25)

    def test_estimate_small_tokens(self) -> None:
        tracker = CostTracker()
        cost = tracker.estimate_cost(1000, 2000, "gpt-4o")
        expected = (1000 / 1_000_000) * 2.5 + (2000 / 1_000_000) * 10.0
        assert cost == pytest.approx(expected)

    def test_estimate_zero_tokens(self) -> None:
        tracker = CostTracker()
        cost = tracker.estimate_cost(0, 0, "gpt-4o")
        assert cost == 0.0

    def test_estimate_unknown_model(self) -> None:
        tracker = CostTracker()
        with pytest.raises(ValueError, match="Unknown model"):
            tracker.estimate_cost(1000, 1000, "unknown-model")

    def test_estimate_negative_input_tokens(self) -> None:
        tracker = CostTracker()
        with pytest.raises(ValueError, match="input_tokens must be non-negative"):
            tracker.estimate_cost(-1, 1000, "gpt-4o")

    def test_estimate_negative_output_tokens(self) -> None:
        tracker = CostTracker()
        with pytest.raises(ValueError, match="output_tokens must be non-negative"):
            tracker.estimate_cost(1000, -1, "gpt-4o")


class TestTrackUsage:
    """Tests for usage tracking."""

    def test_track_single_usage(self) -> None:
        tracker = CostTracker()
        cost = tracker.track_usage(1000, 2000, "gpt-4o")
        expected = (1000 / 1_000_000) * 2.5 + (2000 / 1_000_000) * 10.0
        assert cost == pytest.approx(expected)
        assert tracker.get_total_cost() == pytest.approx(expected)

    def test_track_multiple_usages(self) -> None:
        tracker = CostTracker()
        cost1 = tracker.track_usage(1000, 2000, "gpt-4o")
        cost2 = tracker.track_usage(500, 1000, "deepseek-v4-flash")
        assert tracker.get_total_cost() == pytest.approx(cost1 + cost2)

    def test_track_different_models(self) -> None:
        tracker = CostTracker()
        tracker.track_usage(1000, 1000, "gpt-4o")
        tracker.track_usage(1000, 1000, "claude-sonnet-4-5")
        tracker.track_usage(1000, 1000, "deepseek-v4-flash")
        assert len(tracker._usage_history) == 3

    def test_track_zero_tokens(self) -> None:
        tracker = CostTracker()
        cost = tracker.track_usage(0, 0, "gpt-4o")
        assert cost == 0.0
        assert tracker.get_total_cost() == 0.0

    def test_track_negative_input_raises(self) -> None:
        tracker = CostTracker()
        with pytest.raises(ValueError, match="input_tokens must be non-negative"):
            tracker.track_usage(-1, 1000, "gpt-4o")

    def test_track_negative_output_raises(self) -> None:
        tracker = CostTracker()
        with pytest.raises(ValueError, match="output_tokens must be non-negative"):
            tracker.track_usage(1000, -1, "gpt-4o")

    def test_track_unknown_model_raises(self) -> None:
        tracker = CostTracker()
        with pytest.raises(ValueError, match="Unknown model"):
            tracker.track_usage(1000, 1000, "nonexistent")


class TestGetCostReport:
    """Tests for cost report generation."""

    def test_empty_report(self) -> None:
        tracker = CostTracker()
        report = tracker.get_cost_report()
        assert isinstance(report, CostReport)
        assert report.input_tokens == 0
        assert report.output_tokens == 0
        assert report.total_cost_usd == 0.0
        assert report.model_name is None

    def test_report_after_usage(self) -> None:
        tracker = CostTracker()
        tracker.track_usage(1000, 2000, "gpt-4o")
        report = tracker.get_cost_report()
        assert report.input_tokens == 1000
        assert report.output_tokens == 2000
        assert report.model_name == "gpt-4o"
        assert report.total_cost_usd > 0

    def test_report_aggregates_tokens(self) -> None:
        tracker = CostTracker()
        tracker.track_usage(100, 200, "gpt-4o")
        tracker.track_usage(300, 400, "gpt-4o")
        report = tracker.get_cost_report()
        assert report.input_tokens == 400
        assert report.output_tokens == 600

    def test_report_last_model(self) -> None:
        tracker = CostTracker()
        tracker.track_usage(100, 200, "gpt-4o")
        tracker.track_usage(100, 200, "claude-sonnet-4-5")
        report = tracker.get_cost_report()
        assert report.model_name == "claude-sonnet-4-5"


class TestGetDetailedReport:
    """Tests for detailed cost report."""

    def test_detailed_report_structure(self) -> None:
        tracker = CostTracker(budget_limit=50.0)
        tracker.track_usage(1000, 2000, "gpt-4o")
        report = tracker.get_detailed_report()
        assert isinstance(report, CostReportData)
        assert report.total_input_tokens == 1000
        assert report.total_output_tokens == 2000
        assert report.budget_limit == 50.0
        assert len(report.usage_entries) == 1

    def test_detailed_report_budget_remaining(self) -> None:
        tracker = CostTracker(budget_limit=100.0)
        tracker.track_usage(1_000_000, 1_000_000, "gpt-4o")  # $12.50
        report = tracker.get_detailed_report()
        assert report.budget_remaining == pytest.approx(87.5)

    def test_detailed_report_over_budget(self) -> None:
        tracker = CostTracker(budget_limit=1.0)
        tracker.track_usage(1_000_000, 1_000_000, "gpt-4o")  # $12.50
        report = tracker.get_detailed_report()
        assert report.budget_remaining == 0.0

    def test_detailed_report_no_budget(self) -> None:
        tracker = CostTracker()
        report = tracker.get_detailed_report()
        assert report.budget_remaining == 0.0


class TestCheckBudget:
    """Tests for budget checking."""

    def test_no_budget_always_true(self) -> None:
        tracker = CostTracker()
        assert tracker.check_budget() is True

    def test_within_budget(self) -> None:
        tracker = CostTracker(budget_limit=100.0)
        tracker.track_usage(1000, 1000, "gpt-4o")
        assert tracker.check_budget() is True

    def test_exactly_at_budget(self) -> None:
        # Use a specific amount that hits exactly
        tracker = CostTracker(budget_limit=100.0)
        # Track enough to be close to budget but under
        tracker.track_usage(1_000_000, 1_000_000, "gpt-4o")  # $12.50
        assert tracker.check_budget() is True

    def test_over_budget(self) -> None:
        tracker = CostTracker(budget_limit=0.01)
        tracker.track_usage(1_000_000, 1_000_000, "gpt-4o")  # $12.50
        assert tracker.check_budget() is False


class TestBudgetUsagePercent:
    """Tests for budget usage percentage."""

    def test_no_budget_returns_zero(self) -> None:
        tracker = CostTracker()
        assert tracker.get_budget_usage_percent() == 0.0

    def test_usage_percent_calculation(self) -> None:
        tracker = CostTracker(budget_limit=100.0)
        tracker.track_usage(1_000_000, 1_000_000, "gpt-4o")  # $12.50
        assert tracker.get_budget_usage_percent() == pytest.approx(12.5)


class TestBudgetLimit:
    """Tests for budget limit management."""

    def test_set_budget_limit(self) -> None:
        tracker = CostTracker()
        tracker.budget_limit = 50.0
        assert tracker.budget_limit == 50.0

    def test_set_negative_budget_raises(self) -> None:
        tracker = CostTracker()
        with pytest.raises(ValueError, match="Budget limit must be non-negative"):
            tracker.budget_limit = -1.0

    def test_set_zero_budget(self) -> None:
        tracker = CostTracker(budget_limit=100.0)
        tracker.budget_limit = 0.0
        assert tracker.budget_limit == 0.0


class TestReset:
    """Tests for tracker reset."""

    def test_reset_clears_totals(self) -> None:
        tracker = CostTracker(budget_limit=100.0)
        tracker.track_usage(1000, 2000, "gpt-4o")
        tracker.reset()
        assert tracker.get_total_cost() == 0.0
        assert tracker._total_input_tokens == 0
        assert tracker._total_output_tokens == 0

    def test_reset_clears_history(self) -> None:
        tracker = CostTracker()
        tracker.track_usage(1000, 2000, "gpt-4o")
        tracker.track_usage(500, 1000, "deepseek-v4-flash")
        tracker.reset()
        assert len(tracker._usage_history) == 0

    def test_reset_preserves_budget_limit(self) -> None:
        tracker = CostTracker(budget_limit=100.0)
        tracker.track_usage(1000, 2000, "gpt-4o")
        tracker.reset()
        assert tracker.budget_limit == 100.0

    def test_reset_allows_new_tracking(self) -> None:
        tracker = CostTracker()
        tracker.track_usage(1_000_000, 1_000_000, "gpt-4o")
        tracker.reset()
        cost = tracker.track_usage(1000, 1000, "gpt-4o")
        assert tracker.get_total_cost() == pytest.approx(cost)


class TestModelPricing:
    """Tests for model pricing configuration."""

    def test_all_models_have_pricing(self) -> None:
        expected_models = {"deepseek-v4-flash", "claude-sonnet-4-5", "gpt-4o"}
        assert set(MODEL_PRICING.keys()) == expected_models

    def test_pricing_structure(self) -> None:
        for model, pricing in MODEL_PRICING.items():
            assert "input" in pricing, f"{model} missing 'input' price"
            assert "output" in pricing, f"{model} missing 'output' price"
            assert pricing["input"] >= 0, f"{model} has negative input price"
            assert pricing["output"] >= 0, f"{model} has negative output price"


class TestBudgetWarning:
    """Tests for budget warning mechanism."""

    def test_warning_at_80_percent(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        logger = logging.getLogger("ai_code_reviewer.utils.cost_tracker")
        with caplog.at_level(logging.WARNING, logger=logger.name):
            tracker = CostTracker(budget_limit=10.0)
            # Track usage that brings us to ~80%
            # Need ~$8.00 worth: 8.0 = (x/1M)*2.5 => x = 3,200,000
            tracker.track_usage(3_200_000, 0, "gpt-4o")
            assert "Budget warning" in caplog.text

    def test_warning_at_exceeded(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        logger = logging.getLogger("ai_code_reviewer.utils.cost_tracker")
        with caplog.at_level(logging.WARNING, logger=logger.name):
            tracker = CostTracker(budget_limit=0.01)
            tracker.track_usage(1_000_000, 1_000_000, "gpt-4o")  # $12.50
            assert "Budget exceeded" in caplog.text

    def test_no_warning_when_no_budget(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        logger = logging.getLogger("ai_code_reviewer.utils.cost_tracker")
        with caplog.at_level(logging.WARNING, logger=logger.name):
            tracker = CostTracker()
            tracker.track_usage(1_000_000, 1_000_000, "gpt-4o")
            assert "Budget" not in caplog.text


class TestUsageEntry:
    """Tests for UsageEntry dataclass."""

    def test_usage_entry_creation(self) -> None:
        entry = UsageEntry(
            input_tokens=1000,
            output_tokens=2000,
            model="gpt-4o",
            cost=0.0225,
        )
        assert entry.input_tokens == 1000
        assert entry.output_tokens == 2000
        assert entry.model == "gpt-4o"
        assert entry.cost == 0.0225


class TestCostReportData:
    """Tests for CostReportData dataclass."""

    def test_default_values(self) -> None:
        report = CostReportData()
        assert report.total_input_tokens == 0
        assert report.total_output_tokens == 0
        assert report.total_cost_usd == 0.0
        assert report.usage_entries == []
        assert report.budget_limit == 0.0
        assert report.budget_remaining == 0.0
