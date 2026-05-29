"""Integration tests for the analyzer pipeline.

Tests the interaction between different analyzer components:
RiskDetector, SummaryGenerator, ReviewGenerator, HybridAnalyzer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from ai_code_reviewer.analyzer.hybrid_analyzer import HybridAnalyzer
from ai_code_reviewer.analyzer.risk_detector import RiskDetector
from ai_code_reviewer.analyzer.summary_generator import SummaryGenerator
from ai_code_reviewer.analyzer.review_generator import ReviewGenerator
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
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_pr() -> PullRequest:
    """Create a sample pull request."""
    return PullRequest(
        number=42,
        title="Add authentication module",
        description="Implements JWT-based auth",
        author="testuser",
        repository="org/repo",
        base_branch="main",
        head_branch="feature/auth",
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        updated_at=datetime(2025, 1, 2, tzinfo=UTC),
    )


@pytest.fixture()
def sample_files() -> list[FileChange]:
    """Create sample file changes."""
    return [
        FileChange(
            file_path="src/auth/login.py",
            change_type=ChangeType.FEATURE,
            additions=50,
            deletions=5,
            diff_content="+def authenticate(user, password):\n+    return True",
            language="python",
        ),
        FileChange(
            file_path="src/utils/helper.js",
            change_type=ChangeType.FIX,
            additions=10,
            deletions=3,
            diff_content="+function fix() { return null; }",
            language="javascript",
        ),
    ]


@pytest.fixture()
def risk_detector() -> RiskDetector:
    """Create a RiskDetector instance."""
    return RiskDetector()


@pytest.fixture()
def summary_generator() -> SummaryGenerator:
    """Create a SummaryGenerator instance."""
    return SummaryGenerator()


@pytest.fixture()
def review_generator() -> ReviewGenerator:
    """Create a ReviewGenerator instance."""
    return ReviewGenerator()


# ---------------------------------------------------------------------------
# RiskDetector integration
# ---------------------------------------------------------------------------


class TestRiskDetectorIntegration:
    """Integration tests for RiskDetector."""

    def test_detect_python_risks(self, risk_detector: RiskDetector) -> None:
        """RiskDetector should detect Python risks."""
        fc = FileChange(
            file_path="auth.py",
            change_type=ChangeType.FEATURE,
            additions=20,
            deletions=0,
            diff_content='password = "hardcoded_secret"\nresult = eval(user_input)',
            language="python",
        )
        risks = risk_detector.detect_risks([fc])
        assert len(risks) > 0
        assert any(r.category == RiskCategory.SECURITY for r in risks)

    def test_detect_js_risks(self, risk_detector: RiskDetector) -> None:
        """RiskDetector should detect JavaScript risks."""
        fc = FileChange(
            file_path="app.js",
            change_type=ChangeType.FEATURE,
            additions=10,
            deletions=0,
            diff_content="el.innerHTML = data;\n",
            language="javascript",
        )
        risks = risk_detector.detect_risks([fc])
        assert len(risks) > 0

    def test_detect_multiple_files(self, risk_detector: RiskDetector) -> None:
        """RiskDetector should handle multiple files."""
        files = [
            FileChange(
                file_path="a.py",
                change_type=ChangeType.FEATURE,
                additions=10,
                deletions=0,
                diff_content='password = "secret"',
                language="python",
            ),
            FileChange(
                file_path="b.js",
                change_type=ChangeType.FIX,
                additions=5,
                deletions=0,
                diff_content="var x = 1;\n",
                language="javascript",
            ),
        ]
        risks = risk_detector.detect_risks(files)
        assert len(risks) > 0

    def test_unsupported_language_skipped(self, risk_detector: RiskDetector) -> None:
        """Unsupported languages should be skipped."""
        fc = FileChange(
            file_path="main.go",
            change_type=ChangeType.FEATURE,
            additions=10,
            deletions=0,
            diff_content="package main\n",
            language="go",
        )
        risks = risk_detector.detect_risks([fc])
        assert risks == []


# ---------------------------------------------------------------------------
# SummaryGenerator integration
# ---------------------------------------------------------------------------


class TestSummaryGeneratorIntegration:
    """Integration tests for SummaryGenerator."""

    def test_generate_summary_en(
        self, sample_pr: PullRequest, sample_files: list[FileChange]
    ) -> None:
        """SummaryGenerator should generate English summary."""
        gen = SummaryGenerator(language="en")
        summary = gen.generate_summary(sample_pr, sample_files)
        assert summary is not None
        assert len(summary) > 0

    def test_generate_summary_zh(
        self, sample_pr: PullRequest, sample_files: list[FileChange]
    ) -> None:
        """SummaryGenerator should generate Chinese summary."""
        gen = SummaryGenerator(language="zh")
        summary = gen.generate_summary(sample_pr, sample_files)
        assert summary is not None
        assert len(summary) > 0

    def test_extract_key_changes(
        self, summary_generator: SummaryGenerator, sample_files: list[FileChange]
    ) -> None:
        """SummaryGenerator should extract key changes."""
        changes = summary_generator.extract_key_changes(sample_files)
        assert len(changes) > 0
        assert all(isinstance(c, str) for c in changes)


# ---------------------------------------------------------------------------
# ReviewGenerator integration
# ---------------------------------------------------------------------------


class TestReviewGeneratorIntegration:
    """Integration tests for ReviewGenerator."""

    def test_generate_suggestions(
        self, review_generator: ReviewGenerator
    ) -> None:
        """ReviewGenerator should generate suggestions from risks."""
        risks = [
            Risk(
                level=RiskLevel.HIGH,
                category=RiskCategory.SECURITY,
                message="SQL injection risk",
                file_path="auth.py",
                line_number=10,
                suggestion="Use parameterized queries",
            ),
        ]
        suggestions = review_generator.generate_suggestions(risks)
        assert len(suggestions) > 0

    def test_generate_suggestions_empty_risks(
        self, review_generator: ReviewGenerator
    ) -> None:
        """ReviewGenerator should handle empty risks."""
        suggestions = review_generator.generate_suggestions([])
        assert suggestions == []


# ---------------------------------------------------------------------------
# HybridAnalyzer integration
# ---------------------------------------------------------------------------


class TestHybridAnalyzerIntegration:
    """Integration tests for HybridAnalyzer."""

    @patch("ai_code_reviewer.analyzer.hybrid_analyzer.AIClient")
    def test_analyze_pr(
        self,
        mock_ai_cls: MagicMock,
        sample_pr: PullRequest,
        sample_files: list[FileChange],
    ) -> None:
        """HybridAnalyzer should analyze a PR end-to-end."""
        config = MagicMock()
        config.analysis.enable_ast = True
        config.analysis.enable_ai = False
        config.ai.provider.value = "deepseek"
        config.ai.api_key = "test-key"
        config.ai.model = "deepseek-chat"
        config.ai.max_tokens = 4096

        analyzer = HybridAnalyzer(config)
        result = analyzer.analyze_pr(sample_pr, sample_files)

        assert isinstance(result, AnalysisResult)
        assert result.pr == sample_pr
        assert isinstance(result.risks, list)
        assert isinstance(result.summary, str)

    @patch("ai_code_reviewer.analyzer.hybrid_analyzer.AIClient")
    def test_analyze_pr_empty_files(
        self,
        mock_ai_cls: MagicMock,
        sample_pr: PullRequest,
    ) -> None:
        """HybridAnalyzer should handle empty file list."""
        config = MagicMock()
        config.analysis.enable_ast = True
        config.analysis.enable_ai = False

        analyzer = HybridAnalyzer(config)
        result = analyzer.analyze_pr(sample_pr, [])

        assert isinstance(result, AnalysisResult)
        assert result.risks == []


# ---------------------------------------------------------------------------
# Cross-component integration
# ---------------------------------------------------------------------------


class TestCrossComponentIntegration:
    """Tests that verify components work together correctly."""

    def test_risk_to_suggestion_flow(
        self,
        risk_detector: RiskDetector,
        review_generator: ReviewGenerator,
    ) -> None:
        """Risks from detector should flow into suggestion generator."""
        fc = FileChange(
            file_path="auth.py",
            change_type=ChangeType.FEATURE,
            additions=20,
            deletions=0,
            diff_content='password = "hardcoded_secret"\nresult = eval(user_input)',
            language="python",
        )
        risks = risk_detector.detect_risks([fc])
        assert len(risks) > 0

        suggestions = review_generator.generate_suggestions(risks)
        # Should generate suggestions for risks that have suggestions
        risks_with_suggestions = [r for r in risks if r.suggestion]
        assert len(suggestions) <= len(risks_with_suggestions)

    def test_full_pipeline_flow(
        self,
        risk_detector: RiskDetector,
        review_generator: ReviewGenerator,
        sample_pr: PullRequest,
    ) -> None:
        """Full pipeline: detect risks -> generate summary -> generate suggestions."""
        files = [
            FileChange(
                file_path="auth.py",
                change_type=ChangeType.FEATURE,
                additions=20,
                deletions=0,
                diff_content='password = "hardcoded_secret"\nresult = eval(user_input)',
                language="python",
            ),
        ]

        # Step 1: Detect risks
        risks = risk_detector.detect_risks(files)
        assert len(risks) > 0

        # Step 2: Generate summary
        summary_gen = SummaryGenerator(language="en")
        summary = summary_gen.generate_summary(sample_pr, files)
        assert summary is not None

        # Step 3: Generate suggestions
        suggestions = review_generator.generate_suggestions(risks)
        assert isinstance(suggestions, list)

    def test_multiple_languages_pipeline(
        self,
        risk_detector: RiskDetector,
    ) -> None:
        """Pipeline should handle multiple languages in a single PR."""
        files = [
            FileChange(
                file_path="backend.py",
                change_type=ChangeType.FEATURE,
                additions=20,
                deletions=0,
                diff_content='password = "secret"\nresult = eval(input())',
                language="python",
            ),
            FileChange(
                file_path="frontend.js",
                change_type=ChangeType.FIX,
                additions=10,
                deletions=0,
                diff_content="el.innerHTML = data;\nvar x = 1;\n",
                language="javascript",
            ),
            FileChange(
                file_path="README.md",
                change_type=ChangeType.DOCS,
                additions=5,
                deletions=0,
                diff_content="# Updated README",
                language="markdown",
            ),
        ]

        risks = risk_detector.detect_risks(files)
        # Should have risks from both Python and JavaScript files
        python_risks = [r for r in risks if r.file_path == "backend.py"]
        js_risks = [r for r in risks if r.file_path == "frontend.js"]
        assert len(python_risks) > 0
        assert len(js_risks) > 0
