"""Tests for the CLI entry point (main.py)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ai_code_reviewer.github.client import GitHubClientError, GitHubNotFoundError
from ai_code_reviewer.main import _mask, cli, parse_pr_url


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
    from datetime import UTC, datetime

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
def sample_result(sample_pr):
    """Return a minimal AnalysisResult."""
    from datetime import UTC, datetime

    from ai_code_reviewer.models import (
        AnalysisResult,
        CostReport,
        Risk,
        RiskCategory,
        RiskLevel,
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
        summary="Found 1 risk.",
        cost=CostReport(input_tokens=100, output_tokens=50, model_name="deepseek-chat"),
    )


# ---------------------------------------------------------------------------
# Tests: parse_pr_url
# ---------------------------------------------------------------------------


class TestParsePRUrl:
    """Tests for the parse_pr_url helper."""

    def test_valid_url(self) -> None:
        owner, repo, number = parse_pr_url(
            "https://github.com/octocat/hello-world/pull/42"
        )
        assert owner == "octocat"
        assert repo == "hello-world"
        assert number == 42

    def test_valid_url_with_trailing_slash(self) -> None:
        owner, repo, number = parse_pr_url(
            "https://github.com/my-org/my-repo/pull/123"
        )
        assert owner == "my-org"
        assert repo == "my-repo"
        assert number == 123

    def test_valid_url_http(self) -> None:
        owner, repo, number = parse_pr_url(
            "http://github.com/owner/repo/pull/1"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert number == 1

    def test_invalid_url_no_pull(self) -> None:
        with pytest.raises(Exception):
            parse_pr_url("https://github.com/owner/repo/issues/42")

    def test_invalid_url_wrong_domain(self) -> None:
        with pytest.raises(Exception):
            parse_pr_url("https://gitlab.com/owner/repo/pull/42")

    def test_invalid_url_malformed(self) -> None:
        with pytest.raises(Exception):
            parse_pr_url("not-a-url")

    def test_empty_url(self) -> None:
        with pytest.raises(Exception):
            parse_pr_url("")


# ---------------------------------------------------------------------------
# Tests: CLI root
# ---------------------------------------------------------------------------


class TestCLIRoot:
    """Tests for the CLI root group."""

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "AI Code Reviewer" in result.output

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


# ---------------------------------------------------------------------------
# Tests: analyze command
# ---------------------------------------------------------------------------


class TestAnalyzeCommand:
    """Tests for the analyze command."""

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "PR_URL" in result.output
        assert "--output-format" in result.output
        assert "--publish" in result.output
        assert "--preview" in result.output
        assert "--language" in result.output

    @patch("ai_code_reviewer.main.load_config")
    def test_missing_github_token(
        self, mock_load_config: MagicMock, runner: CliRunner, mock_config: MagicMock
    ) -> None:
        mock_config.github.token = ""
        mock_load_config.return_value = mock_config

        result = runner.invoke(
            cli, ["analyze", "https://github.com/owner/repo/pull/1"]
        )
        assert result.exit_code == 1
        # stderr/stdout mixed in output without mix_stderr
        assert "Missing" in result.output or "GitHub token" in result.output

    @patch("ai_code_reviewer.main.load_config")
    def test_missing_ai_key(
        self, mock_load_config: MagicMock, runner: CliRunner, mock_config: MagicMock
    ) -> None:
        mock_config.ai.api_key = ""
        mock_load_config.return_value = mock_config

        result = runner.invoke(
            cli, ["analyze", "https://github.com/owner/repo/pull/1"]
        )
        assert result.exit_code == 1

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_terminal_output(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_result,
    ) -> None:
        mock_load_config.return_value = mock_config

        # Mock GitHub client
        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = []
        mock_gh_cls.return_value = mock_gh

        # Mock analyzer
        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        result = runner.invoke(
            cli,
            ["analyze", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 0

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_json_output(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_result,
    ) -> None:
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = []
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        result = runner.invoke(
            cli,
            ["analyze", "-f", "json", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 0
        # Should be valid JSON (output may contain stderr lines mixed in)
        json_start = result.output.index("{")
        json_text = result.output[json_start:]
        data = json.loads(json_text)
        assert "pr" in data

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_markdown_output(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_result,
    ) -> None:
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = []
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
    def test_analyze_output_to_file(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_result,
        tmp_path: Path,
    ) -> None:
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = []
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

    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_github_not_found(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
    ) -> None:
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.side_effect = GitHubNotFoundError("PR not found")
        mock_gh_cls.return_value = mock_gh

        result = runner.invoke(
            cli,
            ["analyze", "https://github.com/owner/repo/pull/999"],
        )
        assert result.exit_code == 1

    def test_analyze_invalid_url(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["analyze", "not-a-valid-url"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Tests: config commands
# ---------------------------------------------------------------------------


class TestConfigCommands:
    """Tests for the config subcommands."""

    def test_config_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["config", "--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "show" in result.output
        assert "set" in result.output

    @patch("ai_code_reviewer.main.load_config")
    def test_config_show(
        self, mock_load_config: MagicMock, runner: CliRunner, mock_config: MagicMock
    ) -> None:
        mock_load_config.return_value = mock_config

        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "github" in data
        assert "ai" in data
        assert "analysis" in data
        assert "output" in data
        # Tokens should be masked
        assert "test_token_1234" not in result.output

    def test_config_init_creates_file(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["config", "init"])
            assert result.exit_code == 0
            assert Path("config/default.yaml").exists()

    def test_config_set_value(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            # First init
            runner.invoke(cli, ["config", "init"])
            # Then set a value
            result = runner.invoke(cli, ["config", "set", "ai.provider", "claude"])
            assert result.exit_code == 0
            assert "ai.provider" in result.output

            # Verify value was written
            import yaml

            with open("config/default.yaml", "r") as f:
                data = yaml.safe_load(f)
            assert data["ai"]["provider"] == "claude"

    def test_config_set_invalid_key(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["config", "set", "invalidkey", "value"])
            assert result.exit_code == 1

    def test_config_set_boolean_value(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["config", "init"])
            result = runner.invoke(cli, ["config", "set", "analysis.enable_ast", "false"])
            assert result.exit_code == 0

            import yaml
            with open("config/default.yaml", "r") as f:
                data = yaml.safe_load(f)
            assert data["analysis"]["enable_ast"] is False

    def test_config_set_integer_value(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["config", "init"])
            result = runner.invoke(cli, ["config", "set", "ai.max_tokens", "8192"])
            assert result.exit_code == 0

            import yaml
            with open("config/default.yaml", "r") as f:
                data = yaml.safe_load(f)
            assert data["ai"]["max_tokens"] == 8192

    def test_config_init_overwrite_decline(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["config", "init"])
            # Decline overwrite
            result = runner.invoke(cli, ["config", "init"], input="n\n")
            assert result.exit_code == 0
            assert "Aborted" in result.output

    def test_config_init_overwrite_accept(self, runner: CliRunner, tmp_path: Path) -> None:
        with runner.isolated_filesystem(temp_dir=tmp_path):
            runner.invoke(cli, ["config", "init"])
            # Accept overwrite
            result = runner.invoke(cli, ["config", "init"], input="y\n")
            assert result.exit_code == 0
            assert "Configuration written" in result.output


# ---------------------------------------------------------------------------
# Tests: _mask helper
# ---------------------------------------------------------------------------


class TestMaskHelper:
    """Tests for the _mask secret masking helper."""

    def test_mask_empty_string(self) -> None:
        assert _mask("") == "(not set)"

    def test_mask_short_string(self) -> None:
        assert _mask("abc") == "****"

    def test_mask_exactly_four_chars(self) -> None:
        assert _mask("abcd") == "****"

    def test_mask_long_string(self) -> None:
        result = _mask("ghp_test_token_1234")
        assert result.endswith("1234")
        assert result.startswith("*")
        assert len(result) == len("ghp_test_token_1234")

    def test_mask_five_chars(self) -> None:
        result = _mask("abcde")
        assert result == "*bcde"


# ---------------------------------------------------------------------------
# Tests: analyze publish/preview
# ---------------------------------------------------------------------------


class TestAnalyzePublishPreview:
    """Tests for the analyze command with --publish and --preview flags."""

    @patch("ai_code_reviewer.main.ReviewPublisher")
    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_preview(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        mock_publisher_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_result,
    ) -> None:
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = []
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        mock_publisher = MagicMock()
        mock_publisher.preview_review.return_value = "Preview text"
        mock_publisher_cls.return_value = mock_publisher

        result = runner.invoke(
            cli,
            ["analyze", "--preview", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 0
        assert "Preview text" in result.output

    @patch("ai_code_reviewer.main.ReviewPublisher")
    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_publish(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        mock_publisher_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_result,
    ) -> None:
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = []
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        mock_publisher = MagicMock()
        mock_publisher.publish_review.return_value = {"html_url": "https://github.com/reviews/1"}
        mock_publisher_cls.return_value = mock_publisher

        result = runner.invoke(
            cli,
            ["analyze", "--publish", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 0

    @patch("ai_code_reviewer.main.ReviewPublisher")
    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_publish_review_error(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        mock_publisher_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_result,
    ) -> None:
        from ai_code_reviewer.github.review_publisher import ReviewPublisherError

        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = []
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        mock_publisher = MagicMock()
        mock_publisher.publish_review.side_effect = ReviewPublisherError("Publish failed")
        mock_publisher_cls.return_value = mock_publisher

        result = runner.invoke(
            cli,
            ["analyze", "--publish", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 1

    @patch("ai_code_reviewer.main.ReviewPublisher")
    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_publish_github_error(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        mock_publisher_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_result,
    ) -> None:
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = []
        mock_gh_cls.return_value = mock_gh

        mock_analyzer = MagicMock()
        mock_analyzer.analyze_pr.return_value = sample_result
        mock_analyzer_cls.return_value = mock_analyzer

        mock_publisher = MagicMock()
        mock_publisher.publish_review.side_effect = GitHubClientError("GitHub error")
        mock_publisher_cls.return_value = mock_publisher

        result = runner.invoke(
            cli,
            ["analyze", "--publish", "https://github.com/owner/repo/pull/42"],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Tests: analyze GitHubClientError
# ---------------------------------------------------------------------------


class TestAnalyzeGitHubClientError:
    """Tests for generic GitHubClientError in analyze command."""

    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_github_client_error(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
    ) -> None:
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
    def test_analyze_github_client_init_value_error(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
    ) -> None:
        mock_load_config.return_value = mock_config
        mock_gh_cls.side_effect = ValueError("Invalid token")

        result = runner.invoke(
            cli,
            ["analyze", "https://github.com/owner/repo/pull/1"],
        )
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Tests: output result formats
# ---------------------------------------------------------------------------


class TestOutputResult:
    """Tests for different output formats."""

    @patch("ai_code_reviewer.main.HybridAnalyzer")
    @patch("ai_code_reviewer.main.GitHubClient")
    @patch("ai_code_reviewer.main.load_config")
    def test_analyze_json_output_to_file(
        self,
        mock_load_config: MagicMock,
        mock_gh_cls: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: MagicMock,
        sample_pr,
        sample_result,
        tmp_path: Path,
    ) -> None:
        mock_load_config.return_value = mock_config

        mock_gh = MagicMock()
        mock_gh.get_pull_request.return_value = sample_pr
        mock_gh.get_pr_files.return_value = []
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
        assert "pr" in data
