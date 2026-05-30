"""Tests for Markdown report generator."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_code_reviewer.models import (
    AnalysisResult,
    CostReport,
    FileChange,
    ChangeType,
    PullRequest,
    Risk,
    RiskCategory,
    RiskLevel,
    ReviewSuggestion,
)
from ai_code_reviewer.report.markdown import MarkdownReporter


@pytest.fixture
def reporter_en() -> MarkdownReporter:
    """English Markdown reporter."""
    return MarkdownReporter(language="en")


@pytest.fixture
def reporter_zh() -> MarkdownReporter:
    """Chinese Markdown reporter."""
    return MarkdownReporter(language="zh")


@pytest.fixture
def sample_pr() -> PullRequest:
    """Sample pull request."""
    return PullRequest(
        number=42,
        title="Fix authentication vulnerability",
        description="Fix SQL injection in login endpoint",
        author="developer",
        repository="org/repo",
        base_branch="main",
        head_branch="fix/auth",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        updated_at=datetime(2025, 1, 2, tzinfo=UTC),
    )


@pytest.fixture
def sample_risks() -> list[Risk]:
    """Sample risks."""
    return [
        Risk(
            level=RiskLevel.CRITICAL,
            category=RiskCategory.SECURITY,
            message="SQL injection vulnerability",
            file_path="src/auth.py",
            line_number=42,
            suggestion="Use parameterized queries",
        ),
        Risk(
            level=RiskLevel.HIGH,
            category=RiskCategory.LOGIC,
            message="Null pointer dereference",
            file_path="src/utils.py",
            line_number=15,
        ),
        Risk(
            level=RiskLevel.MEDIUM,
            category=RiskCategory.ARCHITECTURE,
            message="Tight coupling detected",
            file_path="src/service.py",
        ),
    ]


@pytest.fixture
def sample_suggestions() -> list[ReviewSuggestion]:
    """Sample review suggestions."""
    return [
        ReviewSuggestion(
            file_path="src/auth.py",
            line_number=42,
            message="Use parameterized queries instead of string concatenation",
        ),
        ReviewSuggestion(
            file_path="src/utils.py",
            line_number=15,
            message="Add null check before accessing object",
        ),
    ]


@pytest.fixture
def sample_cost() -> CostReport:
    """Sample cost report."""
    return CostReport(
        input_tokens=1500,
        output_tokens=500,
        total_cost_usd=0.0250,
        model_name="gpt-4",
    )


@pytest.fixture
def sample_result(
    sample_pr: PullRequest,
    sample_risks: list[Risk],
    sample_suggestions: list[ReviewSuggestion],
    sample_cost: CostReport,
) -> AnalysisResult:
    """Sample analysis result."""
    return AnalysisResult(
        pr=sample_pr,
        files_changed=[
            FileChange(
                file_path="src/auth.py",
                change_type=ChangeType.FIX,
                additions=10,
                deletions=5,
            ),
        ],
        risks=sample_risks,
        suggestions=sample_suggestions,
        cost=sample_cost,
        summary="Critical security issue found in authentication module.",
    )


class TestMarkdownReporterInit:
    """Test reporter initialization."""

    def test_default_language_is_english(self) -> None:
        reporter = MarkdownReporter()
        assert reporter.language == "en"

    def test_english_language(self) -> None:
        reporter = MarkdownReporter(language="en")
        assert reporter.language == "en"

    def test_chinese_language(self) -> None:
        reporter = MarkdownReporter(language="zh")
        assert reporter.language == "zh"

    def test_unsupported_language_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            MarkdownReporter(language="fr")


class TestGenerateSummarySection:
    """Test summary section generation."""

    def test_english_summary_contains_pr_info(
        self, reporter_en: MarkdownReporter, sample_pr: PullRequest
    ) -> None:
        result = reporter_en.generate_summary_section(sample_pr, "Test summary")
        assert "# Code Review Report" not in result  # Title not in section
        assert "## Summary" in result
        assert "#42" in result
        assert "Fix authentication vulnerability" in result
        assert "developer" in result
        assert "org/repo" in result
        assert "Test summary" in result

    def test_chinese_summary_contains_pr_info(
        self, reporter_zh: MarkdownReporter, sample_pr: PullRequest
    ) -> None:
        result = reporter_zh.generate_summary_section(sample_pr, "测试摘要")
        assert "## 摘要" in result
        assert "#42" in result
        assert "测试摘要" in result

    def test_summary_without_text(
        self, reporter_en: MarkdownReporter, sample_pr: PullRequest
    ) -> None:
        result = reporter_en.generate_summary_section(sample_pr, "")
        assert "## Summary" in result
        assert "#42" in result

    def test_summary_with_changes(
        self, reporter_en: MarkdownReporter, sample_pr: PullRequest
    ) -> None:
        result = reporter_en.generate_summary_section_with_changes(
            sample_pr, "Summary", 100, 50, 3
        )
        assert "100 additions" in result
        assert "50 deletions" in result
        assert "3 files" in result

    def test_chinese_summary_with_changes(
        self, reporter_zh: MarkdownReporter, sample_pr: PullRequest
    ) -> None:
        result = reporter_zh.generate_summary_section_with_changes(
            sample_pr, "摘要", 100, 50, 3
        )
        assert "100 新增" in result
        assert "50 删除" in result
        assert "3 个文件" in result


class TestGenerateRisksSection:
    """Test risks section generation."""

    def test_english_risks_table(
        self, reporter_en: MarkdownReporter, sample_risks: list[Risk]
    ) -> None:
        result = reporter_en.generate_risks_section(sample_risks)
        assert "## Risks Found" in result
        assert "| Level | Category |" in result
        assert "| CRITICAL | security |" in result
        assert "src/auth.py" in result
        assert "42" in result
        assert "SQL injection vulnerability" in result
        assert "| HIGH | logic |" in result
        assert "| MEDIUM | architecture |" in result

    def test_chinese_risks_table(
        self, reporter_zh: MarkdownReporter, sample_risks: list[Risk]
    ) -> None:
        result = reporter_zh.generate_risks_section(sample_risks)
        assert "## 发现的风险" in result
        assert "| 级别 | 分类 |" in result

    def test_empty_risks(
        self, reporter_en: MarkdownReporter
    ) -> None:
        result = reporter_en.generate_risks_section([])
        assert "## Risks Found" in result
        assert "No risks identified." in result

    def test_risk_without_line_number(
        self, reporter_en: MarkdownReporter
    ) -> None:
        risks = [
            Risk(
                level=RiskLevel.LOW,
                category=RiskCategory.LOGIC,
                message="Minor issue",
                file_path="src/main.py",
            )
        ]
        result = reporter_en.generate_risks_section(risks)
        assert "N/A" in result

    def test_chinese_no_risks(
        self, reporter_zh: MarkdownReporter
    ) -> None:
        result = reporter_zh.generate_risks_section([])
        assert "未发现风险。" in result


class TestGenerateSuggestionsSection:
    """Test suggestions section generation."""

    def test_english_suggestions(
        self, reporter_en: MarkdownReporter, sample_suggestions: list[ReviewSuggestion]
    ) -> None:
        result = reporter_en.generate_suggestions_section(sample_suggestions)
        assert "## Suggestions" in result
        assert "1. **src/auth.py:42**" in result
        assert "Use parameterized queries" in result
        assert "2. **src/utils.py:15**" in result

    def test_chinese_suggestions(
        self, reporter_zh: MarkdownReporter, sample_suggestions: list[ReviewSuggestion]
    ) -> None:
        result = reporter_zh.generate_suggestions_section(sample_suggestions)
        assert "## 建议" in result

    def test_empty_suggestions(
        self, reporter_en: MarkdownReporter
    ) -> None:
        result = reporter_en.generate_suggestions_section([])
        assert "## Suggestions" in result
        assert "No suggestions." in result

    def test_suggestion_without_line_number(
        self, reporter_en: MarkdownReporter
    ) -> None:
        suggestions = [
            ReviewSuggestion(
                file_path="src/main.py",
                message="General improvement",
            )
        ]
        result = reporter_en.generate_suggestions_section(suggestions)
        assert "**src/main.py**" in result
        assert ":" not in result.split("**src/main.py**")[1].split("**")[0]


class TestGenerateCostSection:
    """Test cost section generation."""

    def test_english_cost(
        self, reporter_en: MarkdownReporter, sample_cost: CostReport
    ) -> None:
        result = reporter_en.generate_cost_section(sample_cost)
        assert "## Cost Report" in result
        assert "Input Tokens**: 1,500" in result
        assert "Output Tokens**: 500" in result
        assert "Total Cost**: $0.0250" in result

    def test_chinese_cost(
        self, reporter_zh: MarkdownReporter, sample_cost: CostReport
    ) -> None:
        result = reporter_zh.generate_cost_section(sample_cost)
        assert "## 成本报告" in result
        assert "输入Token**: 1,500" in result
        assert "输出Token**: 500" in result
        assert "总成本**: $0.0250" in result

    def test_zero_cost(self, reporter_en: MarkdownReporter) -> None:
        cost = CostReport(input_tokens=0, output_tokens=0, total_cost_usd=0.0)
        result = reporter_en.generate_cost_section(cost)
        assert "$0.0000" in result


class TestGenerateReport:
    """Test full report generation."""

    def test_full_report_structure(
        self, reporter_en: MarkdownReporter, sample_result: AnalysisResult
    ) -> None:
        result = reporter_en.generate_report(sample_result)
        assert result.startswith("# Code Review Report")
        assert "## Summary" in result
        assert "## Risks Found" in result
        assert "## Suggestions" in result
        assert "## Cost Report" in result

    def test_chinese_full_report(
        self, reporter_zh: MarkdownReporter, sample_result: AnalysisResult
    ) -> None:
        result = reporter_zh.generate_report(sample_result)
        assert result.startswith("# 代码审查报告")
        assert "## 摘要" in result
        assert "## 发现的风险" in result
        assert "## 建议" in result
        assert "## 成本报告" in result

    def test_report_without_cost(self, reporter_en: MarkdownReporter, sample_pr: PullRequest) -> None:
        result_data = AnalysisResult(
            pr=sample_pr,
            risks=[],
            suggestions=[],
            cost=None,
            summary="No issues found.",
        )
        report = reporter_en.generate_report(result_data)
        assert "## Cost Report" not in report

    def test_report_with_no_risks_or_suggestions(
        self, reporter_en: MarkdownReporter, sample_pr: PullRequest
    ) -> None:
        result_data = AnalysisResult(
            pr=sample_pr,
            risks=[],
            suggestions=[],
            summary="Clean code.",
        )
        report = reporter_en.generate_report(result_data)
        assert "No risks identified." in report
        assert "No suggestions." in report


class TestSaveReport:
    """Test report file saving."""

    def test_save_report_creates_file(
        self, reporter_en: MarkdownReporter, sample_result: AnalysisResult, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "report.md"
        reporter_en.save_report(sample_result, str(output_file))
        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "# Code Review Report" in content

    def test_save_report_creates_parent_directories(
        self, reporter_en: MarkdownReporter, sample_result: AnalysisResult, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "nested" / "dir" / "report.md"
        reporter_en.save_report(sample_result, str(output_file))
        assert output_file.exists()

    def test_save_report_utf8_encoding(
        self, reporter_zh: MarkdownReporter, sample_result: AnalysisResult, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "report.md"
        reporter_zh.save_report(sample_result, str(output_file))
        content = output_file.read_text(encoding="utf-8")
        assert "代码审查报告" in content
