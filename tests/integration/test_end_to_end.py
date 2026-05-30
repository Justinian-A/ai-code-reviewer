"""End-to-end integration tests for AI Code Reviewer.

Tests the full pipeline from CLI input to output, mocking only external
services (GitHub API, AI API).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ai_code_reviewer.main import cli


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    """Provide a Click CliRunner."""
    return CliRunner()


@pytest.fixture()
def mock_config() -> MagicMock:
    """Provide a mock Config with sensible defaults."""
    config = MagicMock()
    config.github.token = "ghp_test_token_1234"
    config.ai.api_key = "sk-test-key"
    config.ai.provider.value = "deepseek"
    config.ai.model = "deepseek-chat"
    config.ai.max_tokens = 4096
    config.analysis.enable_ast = True
    config.analysis.enable_ai = True
    config.output.format.value = "terminal"
    return config


@pytest.fixture()
def sample_pr():
    """Return a mock PullRequest model."""
    from ai_code_reviewer.models import PullRequest

    return PullRequest(
        number=42,
        title="Add feature X",
        description="This PR adds feature X",
        author="test-user",
        repository="owner/repo",
        head_branch="feature-x",
        base_branch="main",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture()
def sample_files():
    """Return sample FileChange objects."""
    from ai_code_reviewer.models import ChangeType, FileChange

    return [
        FileChange(
            file_path="src/auth.py",
            change_type=ChangeType.FEATURE,
            additions=50,
            deletions=5,
            diff_content="+def authenticate(user, password):\n+    return True",
            language="python",
        ),
        FileChange(
            file_path="src/utils.js",
            change_type=ChangeType.FIX,
            additions=10,
            deletions=3,
            diff_content="+function fix() { return null; }",
            language="javascript",
        ),
    ]


@pytest.fixture()
def sample_result(sample_pr):
    """Return a minimal AnalysisResult."""
    from ai_code_reviewer.models import (
        AnalysisResult,
        CostReport,
        Risk,
        RiskCategory,
        RiskLevel,
        ReviewSuggestion,
    )

    return AnalysisResult(
        pr=sample_pr,
        risks=[
            Risk(
                level=RiskLevel.MEDIUM,
                category=RiskCategory.SECURITY,
                message="Potential SQL injection",
                file_path="app.py",
                line_number=10,
            )
        ],
        suggestions=[
            ReviewSuggestion(
                file_path="app.py",
                line_number=10,
                message="Use parameterized queries",
            )
        ],
        summary="Found 1 risk.",
        cost=CostReport(input_tokens=100, output_tokens=50, model_name="deepseek-chat"),
    )


# ---------------------------------------------------------------------------
# End-to-end: analyze command
# ---------------------------------------------------------------------------


class TestAnalyzeEndToEnd:
    """End-to-end tests for the analyze command."""

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_full_analyze_terminal(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_files,
        sample_result,
    ) -> None:
        """Full analyze flow with terminal output."""
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = sample_files
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        result = runner.invoke(
            cli,
            ["analyze", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 0
        mock_analyzer.analyze_pr.assert_called_once_with(sample_pr, sample_files)

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_full_analyze_json(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_files,
        sample_result,
    ) -> None:
        """Full analyze flow with JSON output."""
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = sample_files
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        result = runner.invoke(
            cli,
            ["analyze", "-f", "json", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 0
        # Parse JSON output
        json_start = result.output.index("{")
        json_text = result.output[json_start:]
        data = json.loads(json_text)
        assert data["pr"]["number"] == 42
        assert len(data["risks"]) == 1

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_full_analyze_markdown(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_files,
        sample_result,
    ) -> None:
        """Full analyze flow with markdown output."""
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = sample_files
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        result = runner.invoke(
            cli,
            ["analyze", "-f", "markdown", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 0
        assert "Code Review Report" in result.output

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_full_analyze_with_config_path(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_files,
        sample_result,
        tmp_path: Path,
    ) -> None:
        """Full analyze flow with custom config path."""
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = sample_files
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        config_file = tmp_path / "custom.yaml"
        config_file.write_text("github:\n  token: test\n")

        result = runner.invoke(
            cli,
            [
                "analyze",
                "--config", str(config_file),
                "https://github.com/owner/repo/pull/42",
            ],
        )
        assert result.exit_code == 0
        mock_load_config.assert_called_once_with(str(config_file))

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_full_analyze_zh_language(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_files,
        sample_result,
    ) -> None:
        """Full analyze flow with Chinese language."""
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = sample_files
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        result = runner.invoke(
            cli,
            [
                "analyze",
                "-f", "markdown",
                "-l", "zh",
                "https://github.com/owner/repo/pull/42",
            ],
        )
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# End-to-end: config commands
# ---------------------------------------------------------------------------


class TestConfigEndToEnd:
    """End-to-end tests for config commands."""

    def test_config_init_then_show(self, runner: CliRunner, tmp_path: Path) -> None:
        """Config init followed by show should work."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Init
            result = runner.invoke(cli, ["config", "init"])
            assert result.exit_code == 0
            assert Path("config/default.yaml").exists()

    def test_config_init_set_show(self, runner: CliRunner, tmp_path: Path) -> None:
        """Config init, set, then show should work."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # Init
            runner.invoke(cli, ["config", "init"])

            # Set value
            result = runner.invoke(cli, ["config", "set", "ai.provider", "claude"])
            assert result.exit_code == 0

            # Verify
            import yaml
            with open("config/default.yaml", "r") as f:
                data = yaml.safe_load(f)
            assert data["ai"]["provider"] == "claude"

    def test_config_set_multiple_values(self, runner: CliRunner, tmp_path: Path) -> None:
        """Setting multiple config values should work."""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["config", "init"])

            runner.invoke(cli, ["config", "set", "ai.provider", "openai"])
            runner.invoke(cli, ["config", "set", "ai.model", "gpt-4"])
            runner.invoke(cli, ["config", "set", "analysis.enable_ast", "false"])

            import yaml
            with open("config/default.yaml", "r") as f:
                data = yaml.safe_load(f)
            assert data["ai"]["provider"] == "openai"
            assert data["ai"]["model"] == "gpt-4"
            assert data["analysis"]["enable_ast"] is False


# ---------------------------------------------------------------------------
# Error handling integration
# ---------------------------------------------------------------------------


class TestErrorHandlingIntegration:
    """Integration tests for error handling across components."""

    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_github_not_found_error(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
    ) -> None:
        """GitHub 404 error should be handled gracefully."""
        from ai_code_reviewer.github.client import GitHubNotFoundError

        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.side_effect = GitHubNotFoundError("PR not found")
        mock_gh_cls.return_value = mock_gh

        result = runner.invoke(
            cli,
            ["analyze", "https://github.com/owner/repo/pull/999"],
        )
        assert result.exit_code == 1

    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_github_client_error(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
    ) -> None:
        """GitHub client error should be handled gracefully."""
        from ai_code_reviewer.github.client import GitHubClientError

        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.side_effect = GitHubClientError("API error")
        mock_gh_cls.return_value = mock_gh

        result = runner.invoke(
            cli,
            ["analyze", "https://github.com/owner/repo/pull/1"],
        )
        assert result.exit_code == 1

    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_github_client_init_error(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
    ) -> None:
        """GitHub client initialization error should be handled gracefully."""
        mock_load_config.return_value = mock_config
        mock_gh_cls.side_effect = ValueError("Invalid token")

        result = runner.invoke(
            cli,
            ["analyze", "https://github.com/owner/repo/pull/1"],
        )
        assert result.exit_code == 1

    def test_invalid_pr_url(
        self,
        runner: CliRunner,
    ) -> None:
        """Invalid PR URL should fail with non-zero exit."""
        result = runner.invoke(
            cli,
            ["analyze", "not-a-valid-url"],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Output format integration
# ---------------------------------------------------------------------------


class TestOutputFormatIntegration:
    """Integration tests for different output formats."""

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_json_output_structure(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_files,
        sample_result,
    ) -> None:
        """JSON output should have correct structure."""
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = sample_files
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        result = runner.invoke(
            cli,
            ["analyze", "-f", "json", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 0

        json_start = result.output.index("{")
        json_text = result.output[json_start:]
        data = json.loads(json_text)

        # Verify structure
        assert "pr" in data
        assert "risks" in data
        assert "suggestions" in data
        assert "summary" in data
        assert "cost" in data

        # Verify PR data
        assert data["pr"]["number"] == 42
        assert data["pr"]["title"] == "Add feature X"

        # Verify risks
        assert len(data["risks"]) == 1
        assert data["risks"][0]["level"] == "medium"

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_json_output_to_file(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_files,
        sample_result,
        tmp_path: Path,
    ) -> None:
        """JSON output to file should create valid JSON file."""
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = sample_files
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        output_file = str(tmp_path / "report.json")
        result = runner.invoke(
            cli,
            [
                "analyze",
                "-f", "json",
                "-o", output_file,
                "https://github.com/owner/repo/pull/42",
            ],
        )
        assert result.exit_code == 0
        assert Path(output_file).exists()

        with open(output_file, "r") as f:
            data = json.load(f)
        assert data["pr"]["number"] == 42

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_markdown_output_to_file(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_files,
        sample_result,
        tmp_path: Path,
    ) -> None:
        """Markdown output to file should create valid markdown file."""
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = sample_files
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        output_file = str(tmp_path / "report.md")
        result = runner.invoke(
            cli,
            [
                "analyze",
                "-f", "markdown",
                "-o", output_file,
                "https://github.com/owner/repo/pull/42",
            ],
        )
        assert result.exit_code == 0
        assert Path(output_file).exists()

        content = Path(output_file).read_text()
        assert "Code Review Report" in content
