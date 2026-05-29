"""Tests for terminal report formatter."""

from __future__ import annotations

from datetime import datetime

import pytest
from rich.console import Console

from ai_code_reviewer.models import (
    CostReport,
    PullRequest,
    ReviewSuggestion,
    Risk,
    RiskCategory,
    RiskLevel,
)
from ai_code_reviewer.report.terminal import (
    RISK_COLORS,
    RISK_LABELS,
    TerminalReporter,
)


# Fixtures


@pytest.fixture
def console() -> Console:
    """Create a Rich Console that captures output to a string buffer."""
    return Console(record=True, width=120, force_terminal=True)


@pytest.fixture
def reporter(console: Console) -> TerminalReporter:
    """Create a TerminalReporter with the capturing console."""
    return TerminalReporter(console=console)


@pytest.fixture
def sample_pr() -> PullRequest:
    """Create a sample pull request."""
    return PullRequest(
        number=42,
        title="Fix authentication vulnerability",
        description="Patches SQL injection in login endpoint",
        author="alice",
        repository="acme/backend",
        head_branch="fix/auth-sqli",
        base_branch="main",
        created_at=datetime(2025, 6, 1, 10, 0, 0),
        updated_at=datetime(2025, 6, 1, 12, 0, 0),
    )


@pytest.fixture
def sample_risks() -> list[Risk]:
    """Create a list of sample risks at various levels."""
    return [
        Risk(
            level=RiskLevel.CRITICAL,
            category=RiskCategory.SECURITY,
            message="SQL injection in login query",
            file_path="app/auth.py",
            line_number=42,
            suggestion="Use parameterized queries",
        ),
        Risk(
            level=RiskLevel.HIGH,
            category=RiskCategory.SECURITY,
            message="Hardcoded API secret",
            file_path="config/secrets.py",
            line_number=7,
            suggestion="Move to environment variables",
        ),
        Risk(
            level=RiskLevel.MEDIUM,
            category=RiskCategory.LOGIC,
            message="Unvalidated user input",
            file_path="app/handlers.py",
            line_number=15,
        ),
        Risk(
            level=RiskLevel.LOW,
            category=RiskCategory.ARCHITECTURE,
            message="Consider using dependency injection",
            file_path="app/main.py",
        ),
        Risk(
            level=RiskLevel.INFO,
            category=RiskCategory.LOGIC,
            message="Unused import detected",
            file_path="app/utils.py",
            line_number=3,
        ),
    ]


@pytest.fixture
def sample_suggestions(sample_risks: list[Risk]) -> list[ReviewSuggestion]:
    """Create a list of sample review suggestions."""
    return [
        ReviewSuggestion(
            file_path="app/auth.py",
            line_number=42,
            message="Replace raw SQL with ORM query builder",
            risk=sample_risks[0],
            code_snippet='cursor.execute(f"SELECT * FROM users WHERE name={name}")',
        ),
        ReviewSuggestion(
            file_path="config/secrets.py",
            line_number=7,
            message="Use os.environ.get() for secret values",
            risk=sample_risks[1],
        ),
        ReviewSuggestion(
            file_path="app/handlers.py",
            message="Add input validation middleware",
        ),
    ]


@pytest.fixture
def sample_cost() -> CostReport:
    """Create a sample cost report."""
    return CostReport(
        input_tokens=1500,
        output_tokens=800,
        total_cost_usd=0.0460,
        model_name="gpt-4o",
    )


# Helper


def get_output(console: Console) -> str:
    """Extract the plain text output from a recording console."""
    return console.export_text()


# ──────────────────────────────────────────────
# RISK_COLORS / RISK_LABELS constants
# ──────────────────────────────────────────────


class TestRiskConstants:
    """Verify color/label mappings for all risk levels."""

    def test_all_levels_have_colors(self):
        for level in RiskLevel:
            assert level in RISK_COLORS, f"Missing color for {level}"

    def test_all_levels_have_labels(self):
        for level in RiskLevel:
            assert level in RISK_LABELS, f"Missing label for {level}"

    def test_critical_is_bold_red(self):
        assert RISK_COLORS[RiskLevel.CRITICAL] == "bold red"

    def test_high_is_red(self):
        assert RISK_COLORS[RiskLevel.HIGH] == "red"

    def test_medium_is_yellow(self):
        assert RISK_COLORS[RiskLevel.MEDIUM] == "yellow"

    def test_low_is_blue(self):
        assert RISK_COLORS[RiskLevel.LOW] == "blue"

    def test_info_is_green(self):
        assert RISK_COLORS[RiskLevel.INFO] == "green"


# ──────────────────────────────────────────────
# Constructor
# ──────────────────────────────────────────────


class TestTerminalReporterInit:
    """Test reporter initialization."""

    def test_default_console(self):
        reporter = TerminalReporter()
        assert reporter.console is not None

    def test_custom_console(self, console: Console):
        reporter = TerminalReporter(console=console)
        assert reporter.console is console


# ──────────────────────────────────────────────
# print_summary
# ──────────────────────────────────────────────


class TestPrintSummary:
    """Test PR summary output."""

    def test_contains_pr_number(self, reporter, console, sample_pr):
        reporter.print_summary(sample_pr, "Analysis complete")
        output = get_output(console)
        assert "42" in output

    def test_contains_title(self, reporter, console, sample_pr):
        reporter.print_summary(sample_pr, "Analysis complete")
        output = get_output(console)
        assert "Fix authentication vulnerability" in output

    def test_contains_author(self, reporter, console, sample_pr):
        reporter.print_summary(sample_pr, "Analysis complete")
        output = get_output(console)
        assert "alice" in output

    def test_contains_repository(self, reporter, console, sample_pr):
        reporter.print_summary(sample_pr, "Analysis complete")
        output = get_output(console)
        assert "acme/backend" in output

    def test_contains_branch_info(self, reporter, console, sample_pr):
        reporter.print_summary(sample_pr, "Analysis complete")
        output = get_output(console)
        assert "fix/auth-sqli" in output
        assert "main" in output

    def test_contains_summary_text(self, reporter, console, sample_pr):
        reporter.print_summary(sample_pr, "Found 3 risks")
        output = get_output(console)
        assert "Found 3 risks" in output

    def test_contains_description(self, reporter, console, sample_pr):
        reporter.print_summary(sample_pr, "OK")
        output = get_output(console)
        assert "Patches SQL injection" in output

    def test_pr_without_description(self, reporter, console):
        pr = PullRequest(
            number=1,
            title="No desc PR",
            author="bob",
            repository="org/repo",
            head_branch="feature",
            created_at=datetime(2025, 1, 1),
            updated_at=datetime(2025, 1, 1),
        )
        reporter.print_summary(pr, "Done")
        output = get_output(console)
        assert "No desc PR" in output


# ──────────────────────────────────────────────
# print_risks
# ──────────────────────────────────────────────


class TestPrintRisks:
    """Test risk table output."""

    def test_empty_risks_shows_message(self, reporter, console):
        reporter.print_risks([])
        output = get_output(console)
        assert "No risks" in output

    def test_contains_risk_message(self, reporter, console, sample_risks):
        reporter.print_risks(sample_risks)
        output = get_output(console)
        assert "SQL injection" in output
        assert "Hardcoded API secret" in output

    def test_contains_file_path(self, reporter, console, sample_risks):
        reporter.print_risks(sample_risks)
        output = get_output(console)
        assert "app/auth.py" in output
        assert "config/secrets.py" in output

    def test_contains_line_numbers(self, reporter, console, sample_risks):
        reporter.print_risks(sample_risks)
        output = get_output(console)
        assert "42" in output
        assert "7" in output

    def test_contains_level_labels(self, reporter, console, sample_risks):
        reporter.print_risks(sample_risks)
        output = get_output(console)
        assert "CRITICAL" in output
        assert "HIGH" in output
        assert "MEDIUM" in output
        assert "LOW" in output
        assert "INFO" in output

    def test_contains_category(self, reporter, console, sample_risks):
        reporter.print_risks(sample_risks)
        output = get_output(console)
        assert "security" in output
        assert "logic" in output
        assert "architecture" in output

    def test_risk_without_line_number(self, reporter, console):
        risk = Risk(
            level=RiskLevel.LOW,
            category=RiskCategory.LOGIC,
            message="Consider refactoring",
            file_path="app.py",
        )
        reporter.print_risks([risk])
        output = get_output(console)
        assert "Consider refactoring" in output

    def test_single_risk(self, reporter, console):
        risk = Risk(
            level=RiskLevel.HIGH,
            category=RiskCategory.SECURITY,
            message="XSS vulnerability",
            file_path="templates/index.html",
            line_number=10,
        )
        reporter.print_risks([risk])
        output = get_output(console)
        assert "XSS vulnerability" in output
        assert "HIGH" in output

    def test_suggestions_printed_for_risks(self, reporter, console, sample_risks):
        reporter.print_risks(sample_risks)
        output = get_output(console)
        # Risks with .suggestion should have their suggestions printed
        assert "parameterized queries" in output
        assert "environment variables" in output


# ──────────────────────────────────────────────
# print_suggestions
# ──────────────────────────────────────────────


class TestPrintSuggestions:
    """Test suggestions list output."""

    def test_empty_suggestions_shows_message(self, reporter, console):
        reporter.print_suggestions([])
        output = get_output(console)
        assert "No suggestions" in output

    def test_contains_file_path(self, reporter, console, sample_suggestions):
        reporter.print_suggestions(sample_suggestions)
        output = get_output(console)
        assert "app/auth.py" in output

    def test_contains_line_number(self, reporter, console, sample_suggestions):
        reporter.print_suggestions(sample_suggestions)
        output = get_output(console)
        assert "42" in output

    def test_contains_message(self, reporter, console, sample_suggestions):
        reporter.print_suggestions(sample_suggestions)
        output = get_output(console)
        assert "Replace raw SQL" in output
        assert "os.environ.get()" in output

    def test_contains_code_snippet(self, reporter, console, sample_suggestions):
        reporter.print_suggestions(sample_suggestions)
        output = get_output(console)
        assert "cursor.execute" in output

    def test_contains_risk_level(self, reporter, console, sample_suggestions):
        reporter.print_suggestions(sample_suggestions)
        output = get_output(console)
        assert "CRITICAL" in output
        assert "HIGH" in output

    def test_suggestion_without_risk(self, reporter, console):
        suggestion = ReviewSuggestion(
            file_path="app.py",
            message="Add type hints",
        )
        reporter.print_suggestions([suggestion])
        output = get_output(console)
        assert "Add type hints" in output

    def test_suggestion_without_code_snippet(self, reporter, console):
        suggestion = ReviewSuggestion(
            file_path="app.py",
            line_number=10,
            message="Refactor this function",
        )
        reporter.print_suggestions([suggestion])
        output = get_output(console)
        assert "Refactor this function" in output

    def test_numbered_suggestions(self, reporter, console, sample_suggestions):
        reporter.print_suggestions(sample_suggestions)
        output = get_output(console)
        # Should contain numbered items
        assert "1." in output
        assert "2." in output
        assert "3." in output


# ──────────────────────────────────────────────
# print_cost_report
# ──────────────────────────────────────────────


class TestPrintCostReport:
    """Test cost report table output."""

    def test_contains_input_tokens(self, reporter, console, sample_cost):
        reporter.print_cost_report(sample_cost)
        output = get_output(console)
        assert "1,500" in output

    def test_contains_output_tokens(self, reporter, console, sample_cost):
        reporter.print_cost_report(sample_cost)
        output = get_output(console)
        assert "800" in output

    def test_contains_total_tokens(self, reporter, console, sample_cost):
        reporter.print_cost_report(sample_cost)
        output = get_output(console)
        assert "2,300" in output

    def test_contains_model_name(self, reporter, console, sample_cost):
        reporter.print_cost_report(sample_cost)
        output = get_output(console)
        assert "gpt-4o" in output

    def test_contains_cost_dollars(self, reporter, console, sample_cost):
        reporter.print_cost_report(sample_cost)
        output = get_output(console)
        assert "$0.0460" in output

    def test_cost_without_model(self, reporter, console):
        cost = CostReport(
            input_tokens=100,
            output_tokens=50,
            total_cost_usd=0.0075,
        )
        reporter.print_cost_report(cost)
        output = get_output(console)
        assert "100" in output
        assert "50" in output

    def test_zero_cost(self, reporter, console):
        cost = CostReport()
        reporter.print_cost_report(cost)
        output = get_output(console)
        assert "$0.0000" in output


# ──────────────────────────────────────────────
# print_error / print_success
# ──────────────────────────────────────────────


class TestPrintMessages:
    """Test error and success message output."""

    def test_error_contains_message(self, reporter, console):
        reporter.print_error("Connection failed")
        output = get_output(console)
        assert "Connection failed" in output

    def test_error_contains_label(self, reporter, console):
        reporter.print_error("Something broke")
        output = get_output(console)
        assert "Error" in output

    def test_success_contains_message(self, reporter, console):
        reporter.print_success("All tests passed")
        output = get_output(console)
        assert "All tests passed" in output

    def test_success_contains_checkmark(self, reporter, console):
        reporter.print_success("Done")
        output = get_output(console)
        # Rich check mark character
        assert "✓" in output


# ──────────────────────────────────────────────
# create_progress_bar
# ──────────────────────────────────────────────


class TestProgressBar:
    """Test progress bar creation."""

    def test_returns_progress_instance(self, reporter):
        from rich.progress import Progress

        progress = reporter.create_progress_bar("Analyzing files")
        assert isinstance(progress, Progress)

    def test_progress_can_be_used_context_manager(self, reporter):
        progress = reporter.create_progress_bar("Working")
        with progress:
            task = progress.add_task("Working", total=10)
            progress.update(task, advance=5)
            assert progress.tasks[0].completed == 5

    def test_progress_tracks_completion(self, reporter):
        progress = reporter.create_progress_bar("Processing")
        with progress:
            task = progress.add_task("Processing", total=100)
            progress.update(task, completed=100)
            assert progress.tasks[0].finished
