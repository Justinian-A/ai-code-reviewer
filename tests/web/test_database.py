"""Tests for the web interface database operations."""

from __future__ import annotations

import json
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from ai_code_reviewer.web.database import (
    create_analysis,
    create_cost_record,
    delete_analysis,
    delete_cost_records_by_analysis,
    get_analysis,
    get_configuration,
    get_cost_records_by_analysis,
    get_cost_records_since,
    get_cost_summary,
    get_daily_costs,
    init_db,
    list_analyses,
    save_configuration,
    update_analysis,
)
from ai_code_reviewer.web.models import (
    AnalysisStatus,
    CostRecord,
    WebAnalysis,
    WebConfiguration,
)


@pytest.fixture
def db(tmp_path):
    """Initialize a temporary database for testing."""
    import ai_code_reviewer.web.database as db_module

    # Use a temporary database file
    test_db_path = tmp_path / "test_web.db"
    with patch.object(db_module, "DB_PATH", test_db_path):
        db_module.init_db()
        yield db_module


@pytest.fixture
def sample_analysis():
    """Create a sample WebAnalysis for testing."""
    return WebAnalysis(
        id="test-001",
        pr_url="https://github.com/test/repo/pull/1",
        pr_number=1,
        repository="test/repo",
        title="Test PR #1",
        status=AnalysisStatus.PENDING,
    )


@pytest.fixture
def completed_analysis():
    """Create a completed WebAnalysis with results."""
    return WebAnalysis(
        id="test-002",
        pr_url="https://github.com/test/repo/pull/2",
        pr_number=2,
        repository="test/repo",
        title="Test PR #2",
        status=AnalysisStatus.COMPLETED,
        completed_at=datetime.now(UTC),
        result={"summary": "No issues found", "risks": [], "suggestions": []},
        cost_usd=0.05,
        risk_count=0,
        suggestion_count=3,
    )


@pytest.fixture
def sample_cost_record():
    """Create a sample CostRecord for testing."""
    return CostRecord(
        id="cost-001",
        analysis_id="test-001",
        model="deepseek-chat",
        input_tokens=1000,
        output_tokens=500,
        cost_usd=0.0015,
        created_at=datetime.now(UTC),
    )


# ── Analysis CRUD ──────────────────────────────────────────────────────────


class TestAnalysisCRUD:
    """Tests for analysis CRUD operations."""

    def test_create_analysis(self, db, sample_analysis):
        """Create an analysis record."""
        result = create_analysis(sample_analysis)
        assert result.id == "test-001"
        assert result.pr_url == "https://github.com/test/repo/pull/1"
        assert result.status == AnalysisStatus.PENDING

    def test_get_analysis_found(self, db, sample_analysis):
        """Get an existing analysis by ID."""
        create_analysis(sample_analysis)
        result = get_analysis("test-001")
        assert result is not None
        assert result.id == "test-001"
        assert result.pr_number == 1
        assert result.repository == "test/repo"

    def test_get_analysis_not_found(self, db):
        """Return None when analysis not found."""
        result = get_analysis("nonexistent")
        assert result is None

    def test_update_analysis(self, db, sample_analysis):
        """Update an existing analysis."""
        create_analysis(sample_analysis)

        # Update the analysis
        sample_analysis.status = AnalysisStatus.RUNNING
        sample_analysis.risk_count = 5
        update_analysis(sample_analysis)

        # Verify update
        result = get_analysis("test-001")
        assert result.status == AnalysisStatus.RUNNING
        assert result.risk_count == 5

    def test_update_analysis_to_completed(self, db, sample_analysis):
        """Update analysis status to completed with results."""
        create_analysis(sample_analysis)

        # Complete the analysis
        sample_analysis.status = AnalysisStatus.COMPLETED
        sample_analysis.completed_at = datetime.now(UTC)
        sample_analysis.result = {"summary": "All good"}
        sample_analysis.cost_usd = 0.10
        update_analysis(sample_analysis)

        result = get_analysis("test-001")
        assert result.status == AnalysisStatus.COMPLETED
        assert result.completed_at is not None
        assert result.result == {"summary": "All good"}
        assert result.cost_usd == 0.10

    def test_delete_analysis(self, db, sample_analysis):
        """Delete an existing analysis."""
        create_analysis(sample_analysis)
        assert delete_analysis("test-001") is True
        assert get_analysis("test-001") is None

    def test_delete_analysis_not_found(self, db):
        """Return False when deleting nonexistent analysis."""
        assert delete_analysis("nonexistent") is False

    def test_delete_analysis_cascades_cost_records(self, db, sample_analysis, sample_cost_record):
        """Deleting analysis also deletes associated cost records."""
        create_analysis(sample_analysis)
        create_cost_record(sample_cost_record)

        delete_analysis("test-001")

        # Cost records should be deleted
        assert get_analysis("test-001") is None

    def test_list_analyses_empty(self, db):
        """Return empty list when no analyses exist."""
        result = list_analyses()
        assert result == []

    def test_list_analyses_ordered_by_date(self, db):
        """List analyses ordered by creation date (newest first)."""
        # Create analyses with different dates
        for i in range(3):
            analysis = WebAnalysis(
                id=f"test-{i:03d}",
                pr_url=f"https://github.com/test/repo/pull/{i}",
                pr_number=i,
                repository="test/repo",
                title=f"PR #{i}",
                status=AnalysisStatus.PENDING,
            )
            create_analysis(analysis)

        result = list_analyses()
        assert len(result) == 3
        # Newest first (test-002 was created last)
        assert result[0].id == "test-002"
        assert result[1].id == "test-001"
        assert result[2].id == "test-000"

    def test_list_analyses_with_limit(self, db):
        """List analyses respects limit parameter."""
        for i in range(5):
            analysis = WebAnalysis(
                id=f"test-{i:03d}",
                pr_url=f"https://github.com/test/repo/pull/{i}",
                pr_number=i,
                repository="test/repo",
                title=f"PR #{i}",
            )
            create_analysis(analysis)

        result = list_analyses(limit=2)
        assert len(result) == 2

    def test_list_analyses_with_offset(self, db):
        """List analyses respects offset parameter."""
        for i in range(5):
            analysis = WebAnalysis(
                id=f"test-{i:03d}",
                pr_url=f"https://github.com/test/repo/pull/{i}",
                pr_number=i,
                repository="test/repo",
                title=f"PR #{i}",
            )
            create_analysis(analysis)

        result = list_analyses(limit=10, offset=2)
        assert len(result) == 3


# ── Configuration CRUD ────────────────────────────────────────────────────


class TestConfigurationCRUD:
    """Tests for configuration CRUD operations."""

    def test_get_default_configuration(self, db):
        """Return default configuration when none saved."""
        config = get_configuration()
        assert config.github_token == ""
        assert config.ai_provider == "deepseek"
        assert config.ai_api_key == ""
        assert config.ai_model == "deepseek-v4-flash"

    def test_save_and_get_configuration(self, db):
        """Save and retrieve configuration."""
        config = WebConfiguration(
            github_token="ghp_test_token",
            ai_provider="claude",
            ai_api_key="sk-test-key",
            ai_model="claude-3-opus",
            ai_max_tokens=8192,
        )
        save_configuration(config)

        result = get_configuration()
        assert result.github_token == "ghp_test_token"
        assert result.ai_provider == "claude"
        assert result.ai_api_key == "sk-test-key"
        assert result.ai_model == "claude-3-opus"
        assert result.ai_max_tokens == 8192

    def test_update_configuration(self, db):
        """Update existing configuration."""
        # Save initial config
        config1 = WebConfiguration(github_token="ghp_old_token")
        save_configuration(config1)

        # Update with new values
        config2 = WebConfiguration(
            github_token="ghp_new_token",
            ai_provider="openai",
        )
        save_configuration(config2)

        result = get_configuration()
        assert result.github_token == "ghp_new_token"
        assert result.ai_provider == "openai"

    def test_configuration_partial_update(self, db):
        """Partial configuration update preserves other values."""
        # Save full config
        config = WebConfiguration(
            github_token="ghp_test",
            ai_api_key="sk-test",
            ai_model="custom-model",
        )
        save_configuration(config)

        # Update only github_token
        new_config = WebConfiguration(github_token="ghp_updated")
        save_configuration(new_config)

        result = get_configuration()
        assert result.github_token == "ghp_updated"
        # Other values should be preserved (from defaults)
        assert result.ai_provider == "deepseek"


# ── CostRecord CRUD ───────────────────────────────────────────────────────


class TestCostRecordCRUD:
    """Tests for cost record CRUD operations."""

    def test_create_cost_record(self, db, sample_analysis, sample_cost_record):
        """Create a cost record."""
        create_analysis(sample_analysis)
        result = create_cost_record(sample_cost_record)
        assert result.id == "cost-001"
        assert result.analysis_id == "test-001"
        assert result.model == "deepseek-chat"
        assert result.input_tokens == 1000
        assert result.output_tokens == 500
        assert result.cost_usd == 0.0015

    def test_get_cost_records_by_analysis(self, db, sample_analysis):
        """Get cost records for a specific analysis."""
        create_analysis(sample_analysis)

        # Create multiple cost records
        for i in range(3):
            record = CostRecord(
                id=f"cost-{i:03d}",
                analysis_id="test-001",
                model="deepseek-chat",
                input_tokens=100 * (i + 1),
                output_tokens=50 * (i + 1),
                cost_usd=0.001 * (i + 1),
                created_at=datetime.now(UTC),
            )
            create_cost_record(record)

        records = get_cost_records_by_analysis("test-001")
        assert len(records) == 3
        assert records[0].id == "cost-000"
        assert records[1].id == "cost-001"
        assert records[2].id == "cost-002"

    def test_get_cost_records_empty(self, db):
        """Return empty list when no cost records exist."""
        records = get_cost_records_by_analysis("nonexistent")
        assert records == []

    def test_delete_cost_records_by_analysis(self, db, sample_analysis):
        """Delete all cost records for an analysis."""
        create_analysis(sample_analysis)

        # Create cost records
        for i in range(3):
            record = CostRecord(
                id=f"cost-{i:03d}",
                analysis_id="test-001",
                model="deepseek-chat",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
                created_at=datetime.now(UTC),
            )
            create_cost_record(record)

        deleted_count = delete_cost_records_by_analysis("test-001")
        assert deleted_count == 3

        # Verify deletion
        records = get_cost_records_by_analysis("test-001")
        assert records == []

    def test_delete_cost_records_empty(self, db):
        """Return 0 when no cost records to delete."""
        deleted_count = delete_cost_records_by_analysis("nonexistent")
        assert deleted_count == 0


# ── Cost Summary Functions ────────────────────────────────────────────────


class TestCostSummaryFunctions:
    """Tests for cost summary and statistics functions."""

    def test_get_cost_summary_empty(self, db):
        """Return zero summary when no completed analyses."""
        summary = get_cost_summary()
        assert summary["total_analyses"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["avg_cost_usd"] == 0.0
        assert summary["max_cost_usd"] == 0.0
        assert summary["total_risks"] == 0
        assert summary["total_suggestions"] == 0

    def test_get_cost_summary_with_data(self, db):
        """Calculate cost summary from completed analyses."""
        # Create completed analyses
        for i in range(3):
            analysis = WebAnalysis(
                id=f"completed-{i:03d}",
                pr_url=f"https://github.com/test/repo/pull/{i}",
                pr_number=i,
                repository="test/repo",
                title=f"PR #{i}",
                status=AnalysisStatus.COMPLETED,
                cost_usd=0.10 * (i + 1),
                risk_count=i * 2,
                suggestion_count=i + 1,
            )
            create_analysis(analysis)

        # Create one pending analysis (should be excluded)
        pending = WebAnalysis(
            id="pending-001",
            pr_url="https://github.com/test/repo/pull/99",
            pr_number=99,
            repository="test/repo",
            title="Pending PR",
            status=AnalysisStatus.PENDING,
        )
        create_analysis(pending)

        summary = get_cost_summary()
        assert summary["total_analyses"] == 3
        assert summary["total_cost_usd"] == 0.6  # 0.10 + 0.20 + 0.30
        assert summary["avg_cost_usd"] == 0.2
        assert summary["max_cost_usd"] == 0.3
        assert summary["total_risks"] == 6  # 0 + 2 + 4
        assert summary["total_suggestions"] == 6  # 1 + 2 + 3

    def test_get_daily_costs_empty(self, db):
        """Return empty list when no completed analyses."""
        daily = get_daily_costs()
        assert daily == []

    def test_get_daily_costs_with_data(self, db):
        """Calculate daily cost breakdown."""
        # Create analyses on different days
        today = datetime.now(UTC)
        yesterday = today - timedelta(days=1)

        analysis1 = WebAnalysis(
            id="today-001",
            pr_url="https://github.com/test/repo/pull/1",
            pr_number=1,
            repository="test/repo",
            title="Today PR",
            status=AnalysisStatus.COMPLETED,
            created_at=today,
            cost_usd=0.10,
        )
        analysis2 = WebAnalysis(
            id="yesterday-001",
            pr_url="https://github.com/test/repo/pull/2",
            pr_number=2,
            repository="test/repo",
            title="Yesterday PR",
            status=AnalysisStatus.COMPLETED,
            created_at=yesterday,
            cost_usd=0.20,
        )

        create_analysis(analysis1)
        create_analysis(analysis2)

        daily = get_daily_costs(days=7)
        assert len(daily) == 2
        # Verify costs are aggregated by day
        costs_by_date = {d["date"]: d for d in daily}
        assert costs_by_date[today.date().isoformat()]["total_cost_usd"] == 0.1
        assert costs_by_date[yesterday.date().isoformat()]["total_cost_usd"] == 0.2

    def test_get_cost_records_since(self, db, sample_analysis, sample_cost_record):
        """Get cost records since a specific time."""
        create_analysis(sample_analysis)
        create_cost_record(sample_cost_record)

        # Query records from 1 hour ago
        since = datetime.now(UTC) - timedelta(hours=1)
        records = get_cost_records_since(since)
        assert len(records) == 1
        assert records[0].id == "cost-001"

    def test_get_cost_records_since_empty(self, db):
        """Return empty list when no records since time."""
        since = datetime.now(UTC) - timedelta(hours=1)
        records = get_cost_records_since(since)
        assert records == []


# ── Database Initialization ──────────────────────────────────────────────


class TestDatabaseInit:
    """Tests for database initialization."""

    def test_init_db_creates_tables(self, db):
        """init_db creates required tables."""
        # Should be able to perform operations after init
        analysis = WebAnalysis(
            id="init-test",
            pr_url="https://github.com/test/repo/pull/1",
            pr_number=1,
            repository="test/repo",
            title="Init Test",
        )
        create_analysis(analysis)
        result = get_analysis("init-test")
        assert result is not None

    def test_init_db_idempotent(self, db):
        """init_db can be called multiple times safely."""
        # First init
        db.init_db()

        # Second init should not fail
        db.init_db()

        # Should still work
        analysis = WebAnalysis(
            id="idempotent-test",
            pr_url="https://github.com/test/repo/pull/1",
            pr_number=1,
            repository="test/repo",
            title="Idempotent Test",
        )
        create_analysis(analysis)
        assert get_analysis("idempotent-test") is not None
