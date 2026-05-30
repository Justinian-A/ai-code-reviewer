"""Tests for the ReviewGenerator."""

import pytest

from ai_code_reviewer.analyzer.review_generator import ReviewGenerator
from ai_code_reviewer.models import Risk, RiskCategory, RiskLevel, ReviewSuggestion


@pytest.fixture
def generator() -> ReviewGenerator:
    """Create a ReviewGenerator instance."""
    return ReviewGenerator()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_risk(
    level: RiskLevel = RiskLevel.MEDIUM,
    category: RiskCategory = RiskCategory.LOGIC,
    message: str = "test risk",
    file_path: str = "src/main.py",
    line_number: int | None = 10,
    suggestion: str | None = None,
) -> Risk:
    return Risk(
        level=level,
        category=category,
        message=message,
        file_path=file_path,
        line_number=line_number,
        suggestion=suggestion,
    )


# ---------------------------------------------------------------------------
# format_suggestion
# ---------------------------------------------------------------------------


class TestFormatSuggestion:
    def test_basic_formatting(self, generator: ReviewGenerator):
        risk = _make_risk(level=RiskLevel.HIGH, category=RiskCategory.SECURITY, message="SQL injection detected")
        suggestion = generator.format_suggestion(risk)

        assert isinstance(suggestion, ReviewSuggestion)
        assert suggestion.file_path == "src/main.py"
        assert suggestion.line_number == 10
        assert suggestion.risk is risk
        assert "SQL injection detected" in suggestion.message
        assert "SECURITY HIGH" in suggestion.message

    def test_critical_security_message(self, generator: ReviewGenerator):
        risk = _make_risk(level=RiskLevel.CRITICAL, category=RiskCategory.SECURITY, message="Hardcoded credentials")
        suggestion = generator.format_suggestion(risk)

        assert "SECURITY CRITICAL" in suggestion.message
        assert "MUST be fixed before merging" in suggestion.message

    def test_low_logic_message(self, generator: ReviewGenerator):
        risk = _make_risk(level=RiskLevel.LOW, category=RiskCategory.LOGIC, message="Unused variable")
        suggestion = generator.format_suggestion(risk)

        assert "LOGIC LOW" in suggestion.message
        assert "Minor logic concern" in suggestion.message

    def test_info_architecture_message(self, generator: ReviewGenerator):
        risk = _make_risk(level=RiskLevel.INFO, category=RiskCategory.ARCHITECTURE, message="Consider DRY")
        suggestion = generator.format_suggestion(risk)

        assert "ARCHITECTURE INFO" in suggestion.message
        assert "future consideration" in suggestion.message

    def test_includes_suggestion_fix(self, generator: ReviewGenerator):
        risk = _make_risk(
            level=RiskLevel.HIGH,
            category=RiskCategory.SECURITY,
            message="SQL injection",
            suggestion="Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
        )
        suggestion = generator.format_suggestion(risk)

        assert "Suggested fix:" in suggestion.message
        assert "parameterized queries" in suggestion.message

    def test_no_suggestion_fix_when_none(self, generator: ReviewGenerator):
        risk = _make_risk(suggestion=None)
        suggestion = generator.format_suggestion(risk)

        assert "Suggested fix:" not in suggestion.message

    def test_code_snippet_is_none(self, generator: ReviewGenerator):
        risk = _make_risk()
        suggestion = generator.format_suggestion(risk)

        assert suggestion.code_snippet is None

    def test_no_line_number(self, generator: ReviewGenerator):
        risk = _make_risk(line_number=None)
        suggestion = generator.format_suggestion(risk)

        assert suggestion.line_number is None


# ---------------------------------------------------------------------------
# generate_suggestions
# ---------------------------------------------------------------------------


class TestGenerateSuggestions:
    def test_empty_risks(self, generator: ReviewGenerator):
        suggestions = generator.generate_suggestions([])
        assert suggestions == []

    def test_single_risk(self, generator: ReviewGenerator):
        risks = [_make_risk(level=RiskLevel.MEDIUM)]
        suggestions = generator.generate_suggestions(risks)

        assert len(suggestions) == 1
        assert suggestions[0].risk is risks[0]

    def test_sorted_by_severity(self, generator: ReviewGenerator):
        risks = [
            _make_risk(level=RiskLevel.LOW, message="low"),
            _make_risk(level=RiskLevel.CRITICAL, message="critical"),
            _make_risk(level=RiskLevel.MEDIUM, message="medium"),
            _make_risk(level=RiskLevel.HIGH, message="high"),
            _make_risk(level=RiskLevel.INFO, message="info"),
        ]
        suggestions = generator.generate_suggestions(risks)

        assert len(suggestions) == 5
        # Should be sorted: CRITICAL, HIGH, MEDIUM, LOW, INFO
        assert suggestions[0].risk.level == RiskLevel.CRITICAL
        assert suggestions[1].risk.level == RiskLevel.HIGH
        assert suggestions[2].risk.level == RiskLevel.MEDIUM
        assert suggestions[3].risk.level == RiskLevel.LOW
        assert suggestions[4].risk.level == RiskLevel.INFO

    def test_preserves_risk_reference(self, generator: ReviewGenerator):
        risk = _make_risk(message="original message")
        suggestions = generator.generate_suggestions([risk])

        assert suggestions[0].risk is risk
        assert suggestions[0].file_path == risk.file_path
        assert suggestions[0].line_number == risk.line_number

    def test_multiple_same_level(self, generator: ReviewGenerator):
        risks = [
            _make_risk(level=RiskLevel.HIGH, message="first"),
            _make_risk(level=RiskLevel.HIGH, message="second"),
        ]
        suggestions = generator.generate_suggestions(risks)

        assert len(suggestions) == 2
        assert all(s.risk.level == RiskLevel.HIGH for s in suggestions)


# ---------------------------------------------------------------------------
# group_by_priority
# ---------------------------------------------------------------------------


class TestGroupByPriority:
    def test_empty_risks(self, generator: ReviewGenerator):
        groups = generator.group_by_priority([])
        assert groups == {}

    def test_single_level(self, generator: ReviewGenerator):
        risks = [_make_risk(level=RiskLevel.HIGH) for _ in range(3)]
        groups = generator.group_by_priority(risks)

        assert len(groups) == 1
        assert RiskLevel.HIGH in groups
        assert len(groups[RiskLevel.HIGH]) == 3

    def test_multiple_levels(self, generator: ReviewGenerator):
        risks = [
            _make_risk(level=RiskLevel.CRITICAL, message="c1"),
            _make_risk(level=RiskLevel.HIGH, message="h1"),
            _make_risk(level=RiskLevel.HIGH, message="h2"),
            _make_risk(level=RiskLevel.LOW, message="l1"),
        ]
        groups = generator.group_by_priority(risks)

        assert len(groups) == 3
        assert len(groups[RiskLevel.CRITICAL]) == 1
        assert len(groups[RiskLevel.HIGH]) == 2
        assert len(groups[RiskLevel.LOW]) == 1
        assert RiskLevel.MEDIUM not in groups
        assert RiskLevel.INFO not in groups

    def test_all_levels_present(self, generator: ReviewGenerator):
        risks = [_make_risk(level=level) for level in RiskLevel]
        groups = generator.group_by_priority(risks)

        assert len(groups) == 5
        for level in RiskLevel:
            assert level in groups
            assert len(groups[level]) == 1


# ---------------------------------------------------------------------------
# generate_summary
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    def test_empty_suggestions(self, generator: ReviewGenerator):
        summary = generator.generate_summary([])
        assert "No issues found" in summary
        assert "looks good" in summary

    def test_single_critical(self, generator: ReviewGenerator):
        risks = [_make_risk(level=RiskLevel.CRITICAL, message="critical bug")]
        suggestions = generator.generate_suggestions(risks)
        summary = generator.generate_summary(suggestions)

        assert "1 suggestion(s)" in summary
        assert "Critical" in summary
        assert "BLOCKER" in summary
        assert "must be resolved" in summary

    def test_multiple_levels(self, generator: ReviewGenerator):
        risks = [
            _make_risk(level=RiskLevel.CRITICAL, message="c"),
            _make_risk(level=RiskLevel.HIGH, message="h1"),
            _make_risk(level=RiskLevel.HIGH, message="h2"),
            _make_risk(level=RiskLevel.MEDIUM, message="m"),
            _make_risk(level=RiskLevel.LOW, message="l"),
            _make_risk(level=RiskLevel.INFO, message="i"),
        ]
        suggestions = generator.generate_suggestions(risks)
        summary = generator.generate_summary(suggestions)

        assert "6 suggestion(s)" in summary
        assert "Critical (must fix): 1" in summary
        assert "High (must fix): 2" in summary
        assert "Medium: 1" in summary
        assert "Low: 1" in summary
        assert "Info: 1" in summary
        assert "BLOCKER" in summary
        assert "3 issue(s) must be resolved" in summary

    def test_only_advisory(self, generator: ReviewGenerator):
        risks = [
            _make_risk(level=RiskLevel.MEDIUM, message="m"),
            _make_risk(level=RiskLevel.LOW, message="l"),
            _make_risk(level=RiskLevel.INFO, message="i"),
        ]
        suggestions = generator.generate_suggestions(risks)
        summary = generator.generate_summary(suggestions)

        assert "BLOCKER" not in summary
        assert "advisory" in summary
        assert "3 suggestion(s)" in summary

    def test_no_critical_but_has_high(self, generator: ReviewGenerator):
        risks = [_make_risk(level=RiskLevel.HIGH, message="high")]
        suggestions = generator.generate_suggestions(risks)
        summary = generator.generate_summary(suggestions)

        assert "BLOCKER" in summary
        assert "1 issue(s) must be resolved" in summary

    def test_only_info(self, generator: ReviewGenerator):
        risks = [_make_risk(level=RiskLevel.INFO, message="info")]
        suggestions = generator.generate_suggestions(risks)
        summary = generator.generate_summary(suggestions)

        assert "BLOCKER" not in summary
        assert "advisory" in summary


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_full_workflow(self, generator: ReviewGenerator):
        """Test the complete workflow: risks -> suggestions -> grouped -> summary."""
        risks = [
            _make_risk(
                level=RiskLevel.CRITICAL,
                category=RiskCategory.SECURITY,
                message="SQL injection vulnerability",
                file_path="src/auth.py",
                line_number=42,
                suggestion="Use parameterized queries",
            ),
            _make_risk(
                level=RiskLevel.HIGH,
                category=RiskCategory.LOGIC,
                message="Unhandled exception",
                file_path="src/api.py",
                line_number=15,
                suggestion="Add try/except block",
            ),
            _make_risk(
                level=RiskLevel.MEDIUM,
                category=RiskCategory.ARCHITECTURE,
                message="God class detected",
                file_path="src/models.py",
                line_number=1,
                suggestion="Split into smaller classes",
            ),
        ]

        # Generate suggestions
        suggestions = generator.generate_suggestions(risks)
        assert len(suggestions) == 3

        # Verify sorting
        assert suggestions[0].risk.level == RiskLevel.CRITICAL
        assert suggestions[1].risk.level == RiskLevel.HIGH
        assert suggestions[2].risk.level == RiskLevel.MEDIUM

        # Verify messages contain actionable content
        assert "SECURITY CRITICAL" in suggestions[0].message
        assert "SQL injection" in suggestions[0].message
        assert "Suggested fix:" in suggestions[0].message

        # Group by priority
        groups = generator.group_by_priority(risks)
        assert len(groups) == 3
        assert len(groups[RiskLevel.CRITICAL]) == 1

        # Generate summary
        summary = generator.generate_summary(suggestions)
        assert "3 suggestion(s)" in summary
        assert "BLOCKER" in summary

    def test_suggestion_message_format_per_level(self, generator: ReviewGenerator):
        """Verify each risk level produces the correct message prefix."""
        for level in RiskLevel:
            for category in RiskCategory:
                risk = _make_risk(level=level, category=category, message="test issue")
                suggestion = generator.format_suggestion(risk)

                # Verify level and category are in the message
                assert level.value.upper() in suggestion.message
                assert category.value.upper() in suggestion.message
