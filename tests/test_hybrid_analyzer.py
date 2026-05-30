"""Tests for the HybridAnalyzer class."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from ai_code_reviewer.analyzer.hybrid_analyzer import HybridAnalyzer
from ai_code_reviewer.config import Config
from ai_code_reviewer.models import (
    AnalysisResult,
    ChangeType,
    CostReport,
    FileChange,
    PullRequest,
    Risk,
    RiskCategory,
    RiskLevel,
    ReviewSuggestion,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(enable_ai: bool = False, api_key: str = "") -> Config:
    """Create a Config with controlled settings."""
    return Config(
        analysis={"enable_ast": True, "enable_ai": enable_ai},
        ai={"provider": "openai", "api_key": api_key, "model": "gpt-4"},
    )


def _make_pr() -> PullRequest:
    """Create a sample PullRequest."""
    now = datetime.now(UTC)
    return PullRequest(
        number=42,
        title="Fix security vulnerability",
        description="Patches eval usage",
        author="dev@example.com",
        repository="org/repo",
        head_branch="fix/eval",
        created_at=now,
        updated_at=now,
    )


def _make_file_change(
    file_path: str = "app.py",
    diff_content: str | None = "x = 1\n",
    language: str | None = None,
) -> FileChange:
    """Create a sample FileChange."""
    return FileChange(
        file_path=file_path,
        change_type=ChangeType.FIX,
        diff_content=diff_content,
        language=language,
    )


def _make_risk(
    message: str = "test risk",
    level: RiskLevel = RiskLevel.MEDIUM,
    category: RiskCategory = RiskCategory.LOGIC,
    file_path: str = "app.py",
    line_number: int | None = 1,
) -> Risk:
    """Create a sample Risk."""
    return Risk(
        level=level,
        category=category,
        message=message,
        file_path=file_path,
        line_number=line_number,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_with_ast_only(self):
        config = _make_config(enable_ai=False)
        analyzer = HybridAnalyzer(config)
        assert analyzer.ast_parser is not None
        assert analyzer.python_analyzer is not None
        assert analyzer.js_ts_analyzer is not None
        assert analyzer.risk_detector is not None
        assert analyzer.summary_generator is not None
        assert analyzer.review_generator is not None
        assert analyzer.ai_client is None

    def test_creates_with_ai_enabled(self):
        config = _make_config(enable_ai=True, api_key="test-key")
        analyzer = HybridAnalyzer(config)
        assert analyzer.ai_client is not None

    def test_ai_disabled_when_no_api_key(self):
        config = _make_config(enable_ai=True, api_key="")
        analyzer = HybridAnalyzer(config)
        assert analyzer.ai_client is None

    def test_stores_config(self):
        config = _make_config()
        analyzer = HybridAnalyzer(config)
        assert analyzer.config is config


# ---------------------------------------------------------------------------
# merge_results
# ---------------------------------------------------------------------------


class TestMergeResults:
    def test_empty_lists(self):
        config = _make_config()
        analyzer = HybridAnalyzer(config)
        result = analyzer.merge_results([], [])
        assert result == []

    def test_only_ast_risks(self):
        config = _make_config()
        analyzer = HybridAnalyzer(config)
        ast_risks = [_make_risk(message="ast issue")]
        result = analyzer.merge_results(ast_risks, [])
        assert len(result) == 1
        assert result[0].message == "ast issue"

    def test_only_ai_risks(self):
        config = _make_config()
        analyzer = HybridAnalyzer(config)
        ai_risks = [_make_risk(message="ai issue")]
        result = analyzer.merge_results([], ai_risks)
        assert len(result) == 1
        assert result[0].message == "ai issue"

    def test_merges_both_sources(self):
        config = _make_config()
        analyzer = HybridAnalyzer(config)
        ast_risks = [_make_risk(message="ast issue")]
        ai_risks = [_make_risk(message="ai issue")]
        result = analyzer.merge_results(ast_risks, ai_risks)
        assert len(result) == 2

    def test_deduplicates_across_sources(self):
        config = _make_config()
        analyzer = HybridAnalyzer(config)
        # Same risk from both AST and AI
        ast_risks = [_make_risk(message="eval usage", file_path="a.py", line_number=5)]
        ai_risks = [_make_risk(message="eval usage", file_path="a.py", line_number=5)]
        result = analyzer.merge_results(ast_risks, ai_risks)
        assert len(result) == 1

    def test_sorts_by_priority(self):
        config = _make_config()
        analyzer = HybridAnalyzer(config)
        ast_risks = [_make_risk(level=RiskLevel.LOW)]
        ai_risks = [_make_risk(level=RiskLevel.CRITICAL, message="critical")]
        result = analyzer.merge_results(ast_risks, ai_risks)
        assert result[0].level == RiskLevel.CRITICAL
        assert result[1].level == RiskLevel.LOW


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_basic_report(self):
        config = _make_config()
        analyzer = HybridAnalyzer(config)
        pr = _make_pr()
        risks = [_make_risk()]
        suggestions = [
            ReviewSuggestion(
                file_path="app.py",
                message="fix this",
                risk=risks[0],
            )
        ]

        result = analyzer.generate_report(pr, risks, suggestions, summary="test summary")

        assert isinstance(result, AnalysisResult)
        assert result.pr is pr
        assert result.risks == risks
        assert result.suggestions == suggestions
        assert result.summary == "test summary"

    def test_report_without_summary(self):
        config = _make_config()
        analyzer = HybridAnalyzer(config)
        pr = _make_pr()

        result = analyzer.generate_report(pr, [], [])

        assert result.summary is None

    def test_report_includes_cost_when_ai_enabled(self):
        config = _make_config(enable_ai=True, api_key="test-key")
        analyzer = HybridAnalyzer(config)
        pr = _make_pr()
        # Simulate some cost accumulation
        analyzer._ai_client._total_cost = CostReport(
            input_tokens=100, output_tokens=50, total_cost_usd=0.01
        )

        result = analyzer.generate_report(pr, [], [])

        assert result.cost is not None
        assert result.cost.input_tokens == 100

    def test_report_no_cost_when_ai_disabled(self):
        config = _make_config(enable_ai=False)
        analyzer = HybridAnalyzer(config)
        pr = _make_pr()

        result = analyzer.generate_report(pr, [], [])

        assert result.cost is None


# ---------------------------------------------------------------------------
# analyze_file
# ---------------------------------------------------------------------------


class TestAnalyzeFile:
    def test_ast_only_analysis(self):
        config = _make_config(enable_ai=False)
        analyzer = HybridAnalyzer(config)
        # Use real code that triggers AST detection
        file = _make_file_change(
            file_path="danger.py",
            diff_content='password = "secret123"\n',
        )

        result = analyzer.analyze_file(file)

        assert len(result) >= 1
        assert any("Hardcoded secret" in r.message for r in result)

    def test_returns_empty_for_no_content(self):
        config = _make_config(enable_ai=False)
        analyzer = HybridAnalyzer(config)
        file = _make_file_change(diff_content=None)

        result = analyzer.analyze_file(file)

        assert result == []

    @patch("ai_code_reviewer.analyzer.hybrid_analyzer.AIClient")
    def test_ai_analysis_called_when_enabled(self, mock_ai_cls):
        config = _make_config(enable_ai=True, api_key="test-key")
        mock_client = MagicMock()
        mock_client.detect_issues.return_value = [
            _make_risk(message="ai found issue")
        ]
        mock_client.cost_report = CostReport()
        mock_ai_cls.return_value = mock_client

        analyzer = HybridAnalyzer(config)
        analyzer._ai_client = mock_client

        file = _make_file_change(diff_content="some code\n")
        result = analyzer.analyze_file(file)

        mock_client.detect_issues.assert_called_once_with("some code\n")

    @patch("ai_code_reviewer.analyzer.hybrid_analyzer.AIClient")
    def test_ai_failure_does_not_crash(self, mock_ai_cls):
        config = _make_config(enable_ai=True, api_key="test-key")
        mock_client = MagicMock()
        mock_client.detect_issues.side_effect = Exception("API error")
        mock_client.cost_report = CostReport()
        mock_ai_cls.return_value = mock_client

        analyzer = HybridAnalyzer(config)
        analyzer._ai_client = mock_client

        file = _make_file_change(diff_content="some code\n")
        # Should not raise
        result = analyzer.analyze_file(file)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# analyze_pr
# ---------------------------------------------------------------------------


class TestAnalyzePR:
    def test_full_flow_ast_only(self):
        config = _make_config(enable_ai=False)
        analyzer = HybridAnalyzer(config)
        pr = _make_pr()
        files = [
            _make_file_change(
                file_path="app.py",
                diff_content='password = "secret"\n',
            ),
        ]

        result = analyzer.analyze_pr(pr, files)

        assert isinstance(result, AnalysisResult)
        assert result.pr is pr
        assert len(result.risks) >= 1
        assert result.summary is not None
        assert len(result.suggestions) >= 1

    def test_empty_files(self):
        config = _make_config(enable_ai=False)
        analyzer = HybridAnalyzer(config)
        pr = _make_pr()

        result = analyzer.analyze_pr(pr, [])

        assert isinstance(result, AnalysisResult)
        assert result.risks == []

    def test_multiple_files(self):
        config = _make_config(enable_ai=False)
        analyzer = HybridAnalyzer(config)
        pr = _make_pr()
        files = [
            _make_file_change(
                file_path="app.py",
                diff_content='password = "secret"\n',
            ),
            _make_file_change(
                file_path="ui.js",
                diff_content="el.innerHTML = userInput;\n",
            ),
        ]

        result = analyzer.analyze_pr(pr, files)

        assert isinstance(result, AnalysisResult)
        py_risks = [r for r in result.risks if r.file_path == "app.py"]
        js_risks = [r for r in result.risks if r.file_path == "ui.js"]
        assert len(py_risks) >= 1
        assert len(js_risks) >= 1

    @patch("ai_code_reviewer.analyzer.hybrid_analyzer.AIClient")
    def test_ai_integration(self, mock_ai_cls):
        config = _make_config(enable_ai=True, api_key="test-key")
        mock_client = MagicMock()
        mock_client.detect_issues.return_value = [
            _make_risk(message="ai issue", file_path="app.py")
        ]
        mock_client.cost_report = CostReport(
            input_tokens=200, output_tokens=100, total_cost_usd=0.05
        )
        mock_ai_cls.return_value = mock_client

        analyzer = HybridAnalyzer(config)
        analyzer._ai_client = mock_client

        pr = _make_pr()
        files = [_make_file_change(file_path="app.py", diff_content="code\n")]

        result = analyzer.analyze_pr(pr, files)

        assert isinstance(result, AnalysisResult)
        mock_client.detect_issues.assert_called_once()
        assert result.cost is not None

    @patch("ai_code_reviewer.analyzer.hybrid_analyzer.AIClient")
    def test_ai_failure_graceful_degradation(self, mock_ai_cls):
        config = _make_config(enable_ai=True, api_key="test-key")
        mock_client = MagicMock()
        mock_client.detect_issues.side_effect = Exception("API down")
        mock_client.cost_report = CostReport()
        mock_ai_cls.return_value = mock_client

        analyzer = HybridAnalyzer(config)
        analyzer._ai_client = mock_client

        pr = _make_pr()
        files = [
            _make_file_change(
                file_path="app.py",
                diff_content='password = "secret"\n',
            ),
        ]

        # Should not raise - AI failure is caught
        result = analyzer.analyze_pr(pr, files)
        assert isinstance(result, AnalysisResult)
        # AST risks should still be present
        assert len(result.risks) >= 1

    def test_ast_disabled(self):
        config = _make_config(enable_ai=False)
        config.analysis.enable_ast = False
        analyzer = HybridAnalyzer(config)
        pr = _make_pr()
        files = [
            _make_file_change(
                file_path="app.py",
                diff_content='password = "secret"\n',
            ),
        ]

        result = analyzer.analyze_pr(pr, files)

        # No AST analysis, no AI => no risks
        assert result.risks == []

    def test_suggestions_sorted_by_severity(self):
        config = _make_config(enable_ai=False)
        analyzer = HybridAnalyzer(config)
        pr = _make_pr()
        files = [
            _make_file_change(
                file_path="app.py",
                diff_content='password = "secret"\nresult = eval(x)\n',
            ),
        ]

        result = analyzer.analyze_pr(pr, files)

        # Suggestions should be sorted: critical before lower levels
        if len(result.suggestions) >= 2 and result.suggestions[0].risk:
            for i in range(len(result.suggestions) - 1):
                curr = result.suggestions[i]
                nxt = result.suggestions[i + 1]
                if curr.risk and nxt.risk:
                    level_order = {
                        RiskLevel.CRITICAL: 0,
                        RiskLevel.HIGH: 1,
                        RiskLevel.MEDIUM: 2,
                        RiskLevel.LOW: 3,
                        RiskLevel.INFO: 4,
                    }
                    assert level_order[curr.risk.level] <= level_order[nxt.risk.level]
