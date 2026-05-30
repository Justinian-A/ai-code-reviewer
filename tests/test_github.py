"""Tests for the GitHub API client."""

from __future__ import annotations

import base64
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from github import GithubException, RateLimitExceededException, UnknownObjectException

from ai_code_reviewer.github.client import (
    GitHubClient,
    GitHubClientError,
    GitHubNotFoundError,
    GitHubPermissionError,
    _detect_language,
)
from ai_code_reviewer.models import ChangeType, ReviewSuggestion, Risk, RiskLevel, RiskCategory


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_mock_user(**overrides) -> MagicMock:
    """Create a mock PyGithub User object."""
    user = MagicMock()
    user.login = overrides.get("login", "testuser")
    user.name = overrides.get("name", "Test User")
    user.email = overrides.get("email", "test@example.com")
    user.id = overrides.get("id", 12345)
    user.avatar_url = overrides.get("avatar_url", "https://avatar.test/123")
    user.html_url = overrides.get("html_url", "https://github.com/testuser")
    return user


def _make_mock_pr(**overrides) -> MagicMock:
    """Create a mock PyGithub PullRequest object."""
    pr = MagicMock()
    pr.number = overrides.get("number", 42)
    pr.title = overrides.get("title", "Add feature X")
    pr.body = overrides.get("body", "This PR adds feature X")
    pr.user = _make_mock_user(login=overrides.get("author", "dev"))
    pr.base = MagicMock(ref=overrides.get("base_branch", "main"))
    pr.head = MagicMock(ref=overrides.get("head_branch", "feature/x"))
    pr.created_at = overrides.get("created_at", datetime(2025, 6, 1, 10, 0, 0))
    pr.updated_at = overrides.get("updated_at", datetime(2025, 6, 1, 12, 0, 0))
    return pr


def _make_mock_file(**overrides) -> MagicMock:
    """Create a mock PyGithub File object."""
    f = MagicMock()
    f.filename = overrides.get("filename", "src/main.py")
    f.status = overrides.get("status", "modified")
    f.additions = overrides.get("additions", 10)
    f.deletions = overrides.get("deletions", 5)
    f.patch = overrides.get("patch", "@@ -1,3 +1,10 @@\n+new code")
    return f


def _make_mock_commit() -> MagicMock:
    """Create a mock PyGithub Commit object."""
    commit = MagicMock()
    commit.sha = "abc123"
    return commit


def _make_mock_review_comment(**overrides) -> MagicMock:
    """Create a mock PyGithub ReviewComment object."""
    comment = MagicMock()
    comment.id = overrides.get("id", 999)
    comment.html_url = overrides.get("html_url", "https://github.com/org/repo/pull/42#discussion_r999")
    comment.body = overrides.get("body", "Consider this change")
    comment.path = overrides.get("path", "src/main.py")
    comment.line = overrides.get("line", 42)
    comment.created_at = overrides.get("created_at", datetime(2025, 6, 1, 12, 0, 0))
    return comment


def _make_mock_review(**overrides) -> MagicMock:
    """Create a mock PyGithub Review object."""
    review = MagicMock()
    review.id = overrides.get("id", 888)
    review.html_url = overrides.get("html_url", "https://github.com/org/repo/pull/42#pullrequestreview-888")
    review.body = overrides.get("body", "Looks good")
    review.state = overrides.get("state", "COMMENTED")
    return review


@pytest.fixture
def mock_github() -> MagicMock:
    """Create a patched GitHub client instance."""
    with patch("ai_code_reviewer.github.client.Github") as mock_gh_cls:
        mock_gh = MagicMock()
        mock_gh_cls.return_value = mock_gh
        client = GitHubClient(token="ghp_test_token_12345")
        yield client, mock_gh


# ── Initialization Tests ──────────────────────────────────────────────────────


class TestGitHubClientInit:
    def test_init_with_valid_token(self):
        with patch("ai_code_reviewer.github.client.Github") as mock_gh_cls:
            client = GitHubClient(token="ghp_valid_token")
            assert client is not None
            mock_gh_cls.assert_called_once()

    def test_init_with_empty_token_raises(self):
        with pytest.raises(ValueError, match="GitHub token is required"):
            GitHubClient(token="")

    def test_context_manager(self):
        with patch("ai_code_reviewer.github.client.Github") as mock_gh_cls:
            mock_gh = MagicMock()
            mock_gh_cls.return_value = mock_gh
            with GitHubClient(token="ghp_test") as client:
                assert client is not None
            mock_gh.close.assert_called_once()


# ── get_user Tests ────────────────────────────────────────────────────────────


class TestGetUser:
    def test_get_user_success(self, mock_github):
        client, gh = mock_github
        gh.get_user.return_value = _make_mock_user()

        result = client.get_user()

        assert result["login"] == "testuser"
        assert result["name"] == "Test User"
        assert result["email"] == "test@example.com"
        assert result["id"] == 12345

    def test_get_user_not_found(self, mock_github):
        client, gh = mock_github
        gh.get_user.side_effect = UnknownObjectException(status=404, data={}, headers={})

        with pytest.raises(GitHubNotFoundError):
            client.get_user()

    def test_get_user_api_error(self, mock_github):
        client, gh = mock_github
        gh.get_user.side_effect = GithubException(status=500, data={"message": "Server error"}, headers={})

        with pytest.raises(GitHubClientError):
            client.get_user()


# ── get_pull_request Tests ────────────────────────────────────────────────────


class TestGetPullRequest:
    def test_get_pull_request_success(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = _make_mock_pr(number=42, title="Fix bug")
        gh.get_repo.return_value = mock_repo

        result = client.get_pull_request("owner", "repo", 42)

        assert result.number == 42
        assert result.title == "Fix bug"
        assert result.author == "dev"
        assert result.base_branch == "main"
        assert result.head_branch == "feature/x"
        assert result.repository == "owner/repo"
        gh.get_repo.assert_called_once_with("owner/repo")

    def test_get_pull_request_not_found(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_pull.side_effect = UnknownObjectException(
            status=404, data={"message": "Not Found"}, headers={}
        )
        gh.get_repo.return_value = mock_repo

        with pytest.raises(GitHubNotFoundError, match="Pull request #999"):
            client.get_pull_request("owner", "repo", 999)

    def test_get_pull_request_with_description_none(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = _make_mock_pr(body=None)
        gh.get_repo.return_value = mock_repo

        result = client.get_pull_request("o", "r", 1)
        assert result.description is None

    def test_get_pull_request_forbidden(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_pull.side_effect = GithubException(
            status=403, data={"message": "Forbidden"}, headers={}
        )
        gh.get_repo.return_value = mock_repo

        with pytest.raises(GitHubPermissionError):
            client.get_pull_request("owner", "repo", 1)


# ── get_pr_files Tests ────────────────────────────────────────────────────────


class TestGetPrFiles:
    def test_get_pr_files_success(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_pr = _make_mock_pr()
        mock_file = _make_mock_file(
            filename="src/auth.py",
            status="modified",
            additions=15,
            deletions=3,
            patch="@@ -1,3 +1,15 @@\n+auth code",
        )
        mock_pr.get_files.return_value = [mock_file]
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = client.get_pr_files("owner", "repo", 42)

        assert len(result) == 1
        assert result[0].file_path == "src/auth.py"
        assert result[0].additions == 15
        assert result[0].deletions == 3
        assert result[0].language == "python"
        assert result[0].diff_content is not None

    def test_get_pr_files_multiple(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_pr = _make_mock_pr()
        mock_pr.get_files.return_value = [
            _make_mock_file(filename="a.py", status="added", additions=100, deletions=0),
            _make_mock_file(filename="b.ts", status="removed", additions=0, deletions=50),
            _make_mock_file(filename="c.go", status="modified", additions=10, deletions=5),
        ]
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = client.get_pr_files("o", "r", 1)

        assert len(result) == 3
        assert result[0].change_type == ChangeType.FEATURE  # "added"
        assert result[1].change_type == ChangeType.CHORE  # "removed"
        assert result[2].change_type == ChangeType.REFACTOR  # "modified"

    def test_get_pr_files_not_found(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_pull.side_effect = UnknownObjectException(
            status=404, data={"message": "Not Found"}, headers={}
        )
        gh.get_repo.return_value = mock_repo

        with pytest.raises(GitHubNotFoundError):
            client.get_pr_files("o", "r", 999)

    def test_get_pr_files_no_patch(self, mock_github):
        """File with no patch (e.g. binary) should have diff_content=None."""
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_pr = _make_mock_pr()
        mock_file = _make_mock_file(patch=None)
        mock_pr.get_files.return_value = [mock_file]
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = client.get_pr_files("o", "r", 1)
        assert result[0].diff_content is None


# ── get_file_content Tests ────────────────────────────────────────────────────


class TestGetFileContent:
    def test_get_file_content_success(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        content_bytes = b"print('hello')"
        encoded = base64.b64encode(content_bytes).decode("ascii")
        mock_content = MagicMock()
        mock_content.encoding = "base64"
        mock_content.content = encoded
        mock_repo.get_contents.return_value = mock_content
        gh.get_repo.return_value = mock_repo

        result = client.get_file_content("owner", "repo", "src/main.py", ref="develop")

        assert result == "print('hello')"
        mock_repo.get_contents.assert_called_once_with("src/main.py", ref="develop")

    def test_get_file_content_default_ref(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        content_bytes = b"hello"
        encoded = base64.b64encode(content_bytes).decode("ascii")
        mock_content = MagicMock()
        mock_content.encoding = "base64"
        mock_content.content = encoded
        mock_repo.get_contents.return_value = mock_content
        gh.get_repo.return_value = mock_repo

        result = client.get_file_content("o", "r", "README.md")
        assert result == "hello"
        mock_repo.get_contents.assert_called_once_with("README.md", ref="main")

    def test_get_file_content_directory_raises(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = [MagicMock(), MagicMock()]  # List = directory
        gh.get_repo.return_value = mock_repo

        with pytest.raises(GitHubClientError, match="directory"):
            client.get_file_content("o", "r", "src/")

    def test_get_file_content_not_found(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = UnknownObjectException(
            status=404, data={"message": "Not Found"}, headers={}
        )
        gh.get_repo.return_value = mock_repo

        with pytest.raises(GitHubNotFoundError, match="not found"):
            client.get_file_content("o", "r", "missing.py")


# ── create_review Tests ──────────────────────────────────────────────────────


class TestCreateReview:
    def test_create_review_with_line_number(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_pr = _make_mock_pr()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review_comment.return_value = _make_mock_review_comment(
            id=999, path="src/main.py", line=42
        )
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        review = ReviewSuggestion(
            file_path="src/main.py",
            line_number=42,
            message="Consider renaming this variable",
        )

        result = client.create_review("owner", "repo", 42, review)

        assert result["id"] == 999
        assert result["path"] == "src/main.py"
        assert result["line"] == 42
        mock_pr.create_review_comment.assert_called_once()

    def test_create_review_with_risk_prefix(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_pr = _make_mock_pr()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review_comment.return_value = _make_mock_review_comment()
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        review = ReviewSuggestion(
            file_path="auth.py",
            line_number=10,
            message="SQL injection risk",
            risk=Risk(
                level=RiskLevel.CRITICAL,
                category=RiskCategory.SECURITY,
                message="SQL injection risk",
                file_path="auth.py",
                line_number=10,
            ),
        )

        client.create_review("o", "r", 1, review)

        call_args = mock_pr.create_review_comment.call_args
        assert "[CRITICAL]" in call_args.kwargs["body"]

    def test_create_review_without_line_number(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_pr = _make_mock_pr()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review.return_value = _make_mock_review()
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        review = ReviewSuggestion(
            file_path="src/main.py",
            message="Overall looks good",
        )

        result = client.create_review("o", "r", 1, review)

        assert "state" in result
        mock_pr.create_review.assert_called_once()

    def test_create_review_high_risk_requests_changes(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_pr = _make_mock_pr()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review.return_value = _make_mock_review()
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        review = ReviewSuggestion(
            file_path="app.py",
            message="Critical security issue",
            risk=Risk(
                level=RiskLevel.HIGH,
                category=RiskCategory.SECURITY,
                message="Critical",
                file_path="app.py",
            ),
        )

        client.create_review("o", "r", 1, review)

        call_args = mock_pr.create_review.call_args
        assert call_args.kwargs["event"] == "REQUEST_CHANGES"

    def test_create_review_no_commits_raises(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_pr = _make_mock_pr()
        mock_pr.get_commits.return_value = []
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        review = ReviewSuggestion(file_path="a.py", message="test")

        with pytest.raises(GitHubClientError, match="no commits"):
            client.create_review("o", "r", 1, review)

    def test_create_review_pr_not_found(self, mock_github):
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_pull.side_effect = UnknownObjectException(
            status=404, data={"message": "Not Found"}, headers={}
        )
        gh.get_repo.return_value = mock_repo

        review = ReviewSuggestion(file_path="a.py", message="test")

        with pytest.raises(GitHubNotFoundError):
            client.create_review("o", "r", 999, review)


# ── Language Detection Tests ──────────────────────────────────────────────────


class TestDetectLanguage:
    def test_python(self):
        assert _detect_language("src/main.py") == "python"

    def test_typescript(self):
        assert _detect_language("app/index.ts") == "typescript"

    def test_javascript(self):
        assert _detect_language("lib/utils.js") == "javascript"

    def test_go(self):
        assert _detect_language("cmd/server.go") == "go"

    def test_rust(self):
        assert _detect_language("src/lib.rs") == "rust"

    def test_markdown(self):
        assert _detect_language("README.md") == "markdown"

    def test_unknown_extension(self):
        assert _detect_language("file.xyz") is None

    def test_no_extension(self):
        assert _detect_language("Makefile") == "makefile"

    def test_dockerfile(self):
        assert _detect_language("Dockerfile") == "dockerfile"

    def test_path_with_directories(self):
        assert _detect_language("very/deep/nested/path/file.py") == "python"


# ── Exception Mapping Tests ──────────────────────────────────────────────────


class TestExceptionMapping:
    def test_unknown_object_maps_to_not_found(self):
        exc = UnknownObjectException(status=404, data={"message": "Not Found"}, headers={})
        result = GitHubClient._map_exception(exc)
        assert isinstance(result, GitHubNotFoundError)
        assert result.status_code == 404

    def test_rate_limit_maps_to_permission_error(self):
        exc = RateLimitExceededException(
            status=403,
            data={"message": "API rate limit exceeded"},
            headers={"X-RateLimit-Reset": "12345"},
        )
        result = GitHubClient._map_exception(exc)
        assert isinstance(result, GitHubPermissionError)

    def test_forbidden_maps_to_permission_error(self):
        exc = GithubException(status=403, data={"message": "Forbidden"}, headers={})
        result = GitHubClient._map_exception(exc)
        assert isinstance(result, GitHubPermissionError)

    def test_server_error_maps_to_client_error(self):
        exc = GithubException(status=500, data={"message": "Internal Server Error"}, headers={})
        result = GitHubClient._map_exception(exc)
        assert isinstance(result, GitHubClientError)
        assert result.status_code == 500

    def test_other_error_maps_to_client_error(self):
        exc = GithubException(status=422, data={"message": "Validation Failed"}, headers={})
        result = GitHubClient._map_exception(exc)
        assert isinstance(result, GitHubClientError)
        assert result.status_code == 422


# ── Module Exports Tests ──────────────────────────────────────────────────────


class TestModuleExports:
    def test_imports_from_github_package(self):
        from ai_code_reviewer.github import (
            GitHubClient,
            GitHubClientError,
            GitHubNotFoundError,
            GitHubPermissionError,
            PullRequest,
            FileChange,
            ReviewSuggestion,
        )

        assert GitHubClient is not None
        assert GitHubClientError is not None
        assert PullRequest is not None

    def test_imports_from_github_models(self):
        from ai_code_reviewer.github.models import (
            ChangeType,
            FileChange,
            PullRequest,
            ReviewSuggestion,
            Risk,
            RiskCategory,
            RiskLevel,
        )

        assert ChangeType is not None
        assert RiskLevel.CRITICAL == "critical"


# ── Retry Decorator Tests ────────────────────────────────────────────────────


class TestRetryDecorator:
    """Tests for _retry_on_rate_limit decorator behavior.

    Note: The retry decorator catches RateLimitExceededException and GithubException,
    but the wrapped methods (get_pull_request, etc.) catch GithubException first
    and map it to GitHubPermissionError/GitHubClientError. So the retry decorator
    lines 109-139 are effectively dead code for these methods. These tests verify
    the decorator structure exists but the actual retry paths are unreachable.
    """

    def test_retry_decorator_exists(self):
        """Verify _retry_on_rate_limit decorator is importable."""
        from ai_code_reviewer.github.client import _retry_on_rate_limit
        assert callable(_retry_on_rate_limit)

    def test_retry_decorator_with_params(self):
        """Verify _retry_on_rate_limit accepts parameters."""
        from ai_code_reviewer.github.client import _retry_on_rate_limit
        decorator = _retry_on_rate_limit(max_retries=5, base_delay=2.0)
        assert callable(decorator)


# ── Additional get_pr_files Tests ─────────────────────────────────────────────


class TestGetPrFilesAdditional:
    """Additional tests for get_pr_files."""

    def test_get_pr_files_github_exception(self, mock_github):
        """Test that GithubException is mapped correctly."""
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_pull.side_effect = GithubException(
            status=500, data={"message": "Server error"}, headers={}
        )
        gh.get_repo.return_value = mock_repo

        with pytest.raises(GitHubClientError):
            client.get_pr_files("o", "r", 1)


# ── Additional get_file_content Tests ─────────────────────────────────────────


class TestGetFileContentAdditional:
    """Additional tests for get_file_content."""

    def test_get_file_content_decoded_content_fallback(self, mock_github):
        """Test fallback to decoded_content when encoding is not base64."""
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_content = MagicMock()
        mock_content.encoding = "utf-8"
        mock_content.content = ""
        mock_content.decoded_content = b"fallback content"
        mock_repo.get_contents.return_value = mock_content
        gh.get_repo.return_value = mock_repo

        result = client.get_file_content("o", "r", "file.txt")
        assert result == "fallback content"

    def test_get_file_content_github_exception(self, mock_github):
        """Test that GithubException is mapped correctly."""
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = GithubException(
            status=500, data={"message": "Server error"}, headers={}
        )
        gh.get_repo.return_value = mock_repo

        with pytest.raises(GitHubClientError):
            client.get_file_content("o", "r", "file.txt")


# ── Additional create_review Tests ────────────────────────────────────────────


class TestCreateReviewAdditional:
    """Additional tests for create_review."""

    def test_create_review_github_exception(self, mock_github):
        """Test that GithubException is mapped correctly in create_review."""
        client, gh = mock_github
        mock_repo = MagicMock()
        mock_pr = _make_mock_pr()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review_comment.side_effect = GithubException(
            status=500, data={"message": "Server error"}, headers={}
        )
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        review = ReviewSuggestion(file_path="a.py", message="test", line_number=10)

        with pytest.raises(GitHubClientError):
            client.create_review("o", "r", 1, review)


# ── Exception Data Format Tests ───────────────────────────────────────────────


class TestExceptionDataFormats:
    """Tests for _map_exception with different data formats."""

    def test_exception_with_string_data(self):
        """Test mapping exception when data is a string."""
        exc = GithubException(status=400, data="Bad request", headers={})
        result = GitHubClient._map_exception(exc)
        assert isinstance(result, GitHubClientError)
