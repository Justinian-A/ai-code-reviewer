"""Tests for AI Code Reviewer data models."""

import json
from datetime import datetime

import pytest

from ai_code_reviewer.models import (
    AnalysisResult,
    ChangeType,
    CostReport,
    FileChange,
    OutputFormat,
    PullRequest,
    Risk,
    RiskCategory,
    RiskLevel,
    ReviewSuggestion,
)


# Enum tests


class TestEnums:
    def test_risk_level_values(self):
        assert RiskLevel.CRITICAL == "critical"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.LOW == "low"
        assert RiskLevel.INFO == "info"

    def test_risk_category_values(self):
        assert RiskCategory.SECURITY == "security"
        assert RiskCategory.LOGIC == "logic"
        assert RiskCategory.ARCHITECTURE == "architecture"

    def test_change_type_values(self):
        assert ChangeType.FEATURE == "feature"
        assert ChangeType.FIX == "fix"
        assert ChangeType.REFACTOR == "refactor"
        assert ChangeType.DOCS == "docs"
        assert ChangeType.TEST == "test"
        assert ChangeType.CHORE == "chore"

    def test_output_format_values(self):
        assert OutputFormat.TERMINAL == "terminal"
        assert OutputFormat.MARKDOWN == "markdown"
        assert OutputFormat.JSON == "json"


# Model creation tests


class TestRisk:
    def test_create_risk(self):
        risk = Risk(
            level=RiskLevel.HIGH,
            category=RiskCategory.SECURITY,
            message="SQL injection vulnerability",
            file_path="app/db.py",
            line_number=42,
            suggestion="Use parameterized queries",
        )
        assert risk.level == RiskLevel.HIGH
        assert risk.category == RiskCategory.SECURITY
        assert risk.line_number == 42

    def test_risk_with_defaults(self):
        risk = Risk(
            level=RiskLevel.INFO,
            category=RiskCategory.LOGIC,
            message="Consider edge case",
            file_path="utils.py",
        )
        assert risk.line_number is None
        assert risk.suggestion is None


class TestPullRequest:
    def test_create_pr(self):
        pr = PullRequest(
            number=123,
            title="Add auth module",
            author="dev",
            repository="org/repo",
            head_branch="feature/auth",
            created_at=datetime(2025, 1, 1),
            updated_at=datetime(2025, 1, 2),
        )
        assert pr.number == 123
        assert pr.base_branch == "main"
        assert pr.description is None


class TestFileChange:
    def test_create_file_change(self):
        fc = FileChange(
            file_path="src/main.py",
            change_type=ChangeType.FEATURE,
            additions=10,
            deletions=5,
        )
        assert fc.additions == 10
        assert fc.language is None

    def test_file_change_validation(self):
        with pytest.raises(Exception):
            FileChange(
                file_path="test.py",
                change_type=ChangeType.FIX,
                additions=-1,
            )


class TestCostReport:
    def test_create_cost_report(self):
        cost = CostReport(
            input_tokens=1000,
            output_tokens=500,
            total_cost_usd=0.05,
            model_name="gpt-4",
        )
        assert cost.total_cost_usd == 0.05

    def test_cost_defaults(self):
        cost = CostReport()
        assert cost.input_tokens == 0
        assert cost.total_cost_usd == 0.0


class TestAnalysisResult:
    def _make_result(self) -> AnalysisResult:
        pr = PullRequest(
            number=1,
            title="Test PR",
            author="dev",
            repository="org/repo",
            head_branch="feature",
            created_at=datetime(2025, 1, 1),
            updated_at=datetime(2025, 1, 1),
        )
        return AnalysisResult(pr=pr)

    def test_create_analysis_result(self):
        result = self._make_result()
        assert result.pr.number == 1
        assert result.files_changed == []
        assert result.risks == []
        assert result.suggestions == []

    def test_analysis_with_data(self):
        result = self._make_result()
        result.risks.append(
            Risk(
                level=RiskLevel.LOW,
                category=RiskCategory.LOGIC,
                message="Minor issue",
                file_path="app.py",
            )
        )
        assert len(result.risks) == 1


# Serialization tests


class TestSerialization:
    def _make_full_result(self) -> AnalysisResult:
        pr = PullRequest(
            number=42,
            title="Fix bug",
            description="Fixes the login bug",
            author="alice",
            repository="org/app",
            base_branch="main",
            head_branch="fix/login",
            created_at=datetime(2025, 6, 1, 10, 0, 0),
            updated_at=datetime(2025, 6, 1, 12, 0, 0),
        )
        risk = Risk(
            level=RiskLevel.MEDIUM,
            category=RiskCategory.SECURITY,
            message="Weak hashing",
            file_path="auth.py",
            line_number=15,
            suggestion="Use bcrypt",
        )
        fc = FileChange(
            file_path="auth.py",
            change_type=ChangeType.FIX,
            additions=3,
            deletions=1,
            language="python",
        )
        suggestion = ReviewSuggestion(
            file_path="auth.py",
            line_number=15,
            message="Consider using bcrypt",
            risk=risk,
        )
        cost = CostReport(
            input_tokens=2000,
            output_tokens=800,
            total_cost_usd=0.12,
            model_name="gpt-4o",
        )
        return AnalysisResult(
            pr=pr,
            files_changed=[fc],
            risks=[risk],
            suggestions=[suggestion],
            cost=cost,
            summary="Found 1 medium risk",
        )

    def test_model_dump_json_roundtrip(self):
        original = self._make_full_result()
        json_str = original.model_dump_json()
        restored = AnalysisResult.model_validate_json(json_str)
        assert restored.pr.number == original.pr.number
        assert len(restored.risks) == 1
        assert restored.risks[0].level == RiskLevel.MEDIUM
        assert restored.cost.total_cost_usd == 0.12

    def test_model_dump_dict(self):
        result = self._make_full_result()
        data = result.model_dump()
        assert isinstance(data, dict)
        assert data["pr"]["number"] == 42
        assert data["risks"][0]["level"] == "medium"

    def test_json_structure(self):
        result = self._make_full_result()
        json_str = result.model_dump_json()
        data = json.loads(json_str)
        assert "pr" in data
        assert "risks" in data
        assert "suggestions" in data
        assert "cost" in data
        assert "analyzed_at" in data

    def test_enum_serialization(self):
        risk = Risk(
            level=RiskLevel.CRITICAL,
            category=RiskCategory.SECURITY,
            message="Critical vuln",
            file_path="app.py",
        )
        data = risk.model_dump()
        assert data["level"] == "critical"
        assert data["category"] == "security"

    def test_datetime_serialization(self):
        pr = PullRequest(
            number=1,
            title="Test",
            author="dev",
            repository="org/repo",
            head_branch="feature",
            created_at=datetime(2025, 1, 15, 10, 30, 0),
            updated_at=datetime(2025, 1, 15, 11, 0, 0),
        )
        json_str = pr.model_dump_json()
        restored = PullRequest.model_validate_json(json_str)
        assert restored.created_at == datetime(2025, 1, 15, 10, 30, 0)
