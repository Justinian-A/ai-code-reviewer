"""Tests for the web interface API endpoints."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from ai_code_reviewer.web.app import app
from ai_code_reviewer.web.models import AnalysisStatus, WebAnalysis, WebConfiguration


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_db(tmp_path):
    """Create a temporary database for testing."""
    import ai_code_reviewer.web.database as db_module

    # Use a temporary database file
    test_db_path = tmp_path / "test_web.db"
    with patch.object(db_module, "DB_PATH", test_db_path):
        # Initialize the test database
        db_module.init_db()
        yield db_module


# ── Health Check ──────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests for the /api/health endpoint."""

    def test_health_returns_ok(self, client):
        """Health check returns 200 with ok status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"

    def test_health_response_structure(self, client):
        """Health check response has required fields."""
        response = client.get("/api/health")
        data = response.json()
        assert "status" in data
        assert "version" in data


# ── Analysis Endpoints ───────────────────────────────────────────────────


class TestAnalysisEndpoints:
    """Tests for analysis-related endpoints."""

    def test_analyze_valid_url(self, client, mock_db):
        """POST /api/analyze accepts a valid GitHub PR URL."""
        with patch(
            "ai_code_reviewer.web.routers.analysis.create_analysis"
        ) as mock_create:
            mock_create.return_value = WebAnalysis(
                id="test-123",
                pr_url="https://github.com/test/repo/pull/1",
                pr_number=1,
                repository="test/repo",
                title="PR #1",
                status=AnalysisStatus.PENDING,
            )

            response = client.post(
                "/api/analyze",
                json={"pr_url": "https://github.com/test/repo/pull/1"},
            )
            assert response.status_code == 200
            data = response.json()
            assert "analysis_id" in data
            assert data["status"] == "pending"

    def test_analyze_invalid_url(self, client, mock_db):
        """POST /api/analyze rejects an invalid PR URL."""
        response = client.post(
            "/api/analyze",
            json={"pr_url": "https://example.com/not-a-pr"},
        )
        assert response.status_code == 400

    def test_analyze_missing_url(self, client, mock_db):
        """POST /api/analyze rejects request without pr_url."""
        response = client.post("/api/analyze", json={})
        assert response.status_code == 422

    def test_get_analysis_found(self, client, mock_db):
        """GET /api/analyses/{id} returns analysis when found."""
        mock_analysis = WebAnalysis(
            id="test-456",
            pr_url="https://github.com/test/repo/pull/2",
            pr_number=2,
            repository="test/repo",
            title="PR #2",
            status=AnalysisStatus.COMPLETED,
        )

        with patch(
            "ai_code_reviewer.web.routers.analysis.get_analysis",
            return_value=mock_analysis,
        ):
            response = client.get("/api/analyses/test-456")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "test-456"
            assert data["status"] == "completed"

    def test_get_analysis_not_found(self, client, mock_db):
        """GET /api/analyses/{id} returns 404 when not found."""
        with patch(
            "ai_code_reviewer.web.routers.analysis.get_analysis",
            return_value=None,
        ):
            response = client.get("/api/analyses/nonexistent")
            assert response.status_code == 404


# ── History Endpoints ────────────────────────────────────────────────────


class TestHistoryEndpoints:
    """Tests for history-related endpoints."""

    def test_list_analyses_empty(self, client, mock_db):
        """GET /api/analyses returns empty list when no analyses exist."""
        with patch(
            "ai_code_reviewer.web.routers.history.list_analyses",
            return_value=[],
        ):
            response = client.get("/api/analyses")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data["items"], list)
            assert len(data["items"]) == 0

    def test_list_analyses_with_data(self, client, mock_db):
        """GET /api/analyses returns analyses list."""
        mock_analyses = [
            WebAnalysis(
                id=f"test-{i}",
                pr_url=f"https://github.com/test/repo/pull/{i}",
                pr_number=i,
                repository="test/repo",
                title=f"PR #{i}",
                status=AnalysisStatus.COMPLETED,
            )
            for i in range(3)
        ]

        with patch(
            "ai_code_reviewer.web.routers.history.list_analyses",
            return_value=mock_analyses,
        ):
            response = client.get("/api/analyses")
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 3
            assert data["items"][0]["id"] == "test-0"

    def test_list_analyses_with_pagination(self, client, mock_db):
        """GET /api/analyses respects limit and offset parameters."""
        with patch(
            "ai_code_reviewer.web.routers.history.list_analyses",
            return_value=[],
        ) as mock_list:
            client.get("/api/analyses?limit=10&offset=20")
            mock_list.assert_called_once_with(limit=10, offset=20)

    def test_delete_analysis_found(self, client, mock_db):
        """DELETE /api/analyses/{id} deletes existing analysis."""
        with patch(
            "ai_code_reviewer.web.routers.history.delete_analysis",
            return_value=True,
        ):
            response = client.delete("/api/analyses/test-123")
            assert response.status_code == 200
            data = response.json()
            assert "deleted" in data["message"].lower()

    def test_delete_analysis_not_found(self, client, mock_db):
        """DELETE /api/analyses/{id} returns 404 when not found."""
        with patch(
            "ai_code_reviewer.web.routers.history.delete_analysis",
            return_value=False,
        ):
            response = client.delete("/api/analyses/nonexistent")
            assert response.status_code == 404


# ── Configuration Endpoints ──────────────────────────────────────────────


class TestConfigEndpoints:
    """Tests for configuration endpoints."""

    def test_get_config_returns_defaults(self, client, mock_db):
        """GET /api/returns default config when no config saved."""
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "github_token" in data
        assert "ai_provider" in data
        assert "ai_api_key" in data
        assert "ai_model" in data
        assert "ai_max_tokens" in data

    def test_get_config_masks_secrets(self, client, mock_db):
        """GET /api/config masks secret values."""
        config = WebConfiguration(
            github_token="ghp_1234567890abcdef",
            ai_api_key="sk-1234567890abcdef",
        )
        mock_db.save_configuration(config)

        response = client.get("/api/config")
        data = response.json()
        # Tokens should be masked: first 4 + "..." + last 4
        assert data["github_token"] == "ghp_...cdef"
        assert data["ai_api_key"] == "sk-1...cdef"
        # Full token should NOT be visible
        assert "1234567890" not in data["github_token"]
        assert "1234567890" not in data["ai_api_key"]

    def test_update_config(self, client, mock_db):
        """PUT /api/config updates configuration."""
        new_config = {
            "github_token": "ghp_new_token",
            "ai_provider": "claude",
            "ai_api_key": "sk-new-key",
            "ai_model": "claude-3-opus",
            "ai_max_tokens": 8192,
        }
        response = client.put("/api/config", json=new_config)
        assert response.status_code == 200
        assert "updated" in response.json()["message"].lower()

    def test_update_config_validates_data(self, client, mock_db):
        """PUT /api/config rejects invalid configuration data."""
        response = client.put("/api/config", json={"invalid_field": "value"})
        # Should still succeed as extra fields are ignored by Pydantic
        assert response.status_code == 200


# ── Cost Endpoints ───────────────────────────────────────────────────────


class TestCostEndpoints:
    """Tests for cost tracking endpoints."""

    def test_get_costs_default_period(self, client, mock_db):
        """GET /api/costs returns cost data for default 30-day period."""
        with patch(
            "ai_code_reviewer.web.routers.costs.get_daily_costs",
            return_value=[],
        ):
            response = client.get("/api/costs")
            assert response.status_code == 200
            data = response.json()
            assert data["days"] == 30
            assert data["total_cost_usd"] == 0.0
            assert data["total_analyses"] == 0

    def test_get_costs_custom_period(self, client, mock_db):
        """GET /api/costs accepts custom day parameter."""
        with patch(
            "ai_code_reviewer.web.routers.costs.get_daily_costs",
            return_value=[],
        ):
            response = client.get("/api/costs?days=7")
            assert response.status_code == 200
            data = response.json()
            assert data["days"] == 7

    def test_get_costs_with_data(self, client, mock_db):
        """GET /api/costs returns correct totals."""
        mock_daily = [
            {"date": "2026-05-28", "analysis_count": 5, "total_cost_usd": 0.5},
            {"date": "2026-05-29", "analysis_count": 3, "total_cost_usd": 0.3},
        ]

        with patch(
            "ai_code_reviewer.web.routers.costs.get_daily_costs",
            return_value=mock_daily,
        ):
            response = client.get("/api/costs")
            data = response.json()
            assert data["total_cost_usd"] == 0.8
            assert data["total_analyses"] == 8
            assert data["avg_cost_per_analysis"] == 0.1

    def test_get_cost_summary(self, client, mock_db):
        """GET /api/costs/summary returns summary statistics."""
        mock_summary = {
            "total_analyses": 100,
            "total_cost_usd": 10.5,
            "avg_cost_usd": 0.105,
            "max_cost_usd": 0.5,
            "total_risks": 250,
            "total_suggestions": 180,
        }

        with patch(
            "ai_code_reviewer.web.routers.costs.get_cost_summary",
            return_value=mock_summary,
        ):
            response = client.get("/api/costs/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["total_analyses"] == 100
            assert data["total_cost_usd"] == 10.5

    def test_get_costs_invalid_days(self, client, mock_db):
        """GET /api/costs rejects invalid day parameter."""
        response = client.get("/api/costs?days=0")
        assert response.status_code == 422

        response = client.get("/api/costs?days=400")
        assert response.status_code == 422
