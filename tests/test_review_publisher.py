"""Tests for the ReviewPublisher class."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from github import GithubException, UnknownObjectException

from ai_code_reviewer.github.client import GitHubClient
from ai_code_reviewer.github.review_publisher import ReviewPublisher, ReviewPublisherError
from ai_code_reviewer.models import (
    AnalysisResult,
    CostReport,
    FileChange,
    ChangeType,
    PullRequest,
    ReviewSuggestion,
    Risk,
    RiskCategory,
    RiskLevel,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_pull_request(**overrides) -> PullRequest:
    """Create a PullRequest model instance."""
    return PullRequest(
        number=overrides.get("number", 42),
        title=overrides.get("title", "Add feature X"),
        description=overrides.get("description", "This PR adds feature X"),
        author=overrides.get("author", "dev"),
        repository=overrides.get("repository", "owner/repo"),
        base_branch=overrides.get("base_branch", "main"),
        head_branch=overrides.get("head_branch", "feature/x"),
        created_at=overrides.get("created_at", datetime(2025, 6, 1, 10, 0, 0)),
        updated_at=overrides.get("updated_at", datetime(2025, 6, 1, 12, 0, 0)),
    )


def _make_risk(**overrides) -> Risk:
    """Create a Risk model instance."""
    return Risk(
        level=overrides.get("level", RiskLevel.MEDIUM),
        category=overrides.get("category", RiskCategory.SECURITY),
        message=overrides.get("message", "Potential issue"),
        file_path=overrides.get("file_path", "src/main.py"),
        line_number=overrides.get("line_number", 42),
        suggestion=overrides.get("suggestion", "Consider refactoring"),
    )


def _make_suggestion(**overrides) -> ReviewSuggestion:
    """Create a ReviewSuggestion model instance."""
    return ReviewSuggestion(
        file_path=overrides.get("file_path", "src/main.py"),
        line_number=overrides.get("line_number", 42),
        message=overrides.get("message", "Consider renaming this variable"),
        risk=overrides.get("risk"),
        code_snippet=overrides.get("code_snippet"),
    )


def _make_analysis_result(**overrides) -> AnalysisResult:
    """Create an AnalysisResult model instance."""
    return AnalysisResult(
        pr=overrides.get("pr", _make_pull_request()),
        files_changed=overrides.get("files_changed", [
            FileChange(file_path="src/main.py", change_type=ChangeType.FEATURE, additions=10, deletions=5),
        ]),
        risks=overrides.get("risks", []),
        suggestions=overrides.get("suggestions", []),
        cost=overrides.get("cost"),
        summary=overrides.get("summary", "Overall looks good with minor suggestions."),
    )


def _make_mock_commit() -> MagicMock:
    """Create a mock PyGithub Commit object."""
    commit = MagicMock()
    commit.sha = "abc123"
    return commit


def _make_mock_review(**overrides) -> MagicMock:
    """Create a mock PyGithub Review object."""
    review = MagicMock()
    review.id = overrides.get("id", 888)
    review.html_url = overrides.get("html_url", "https://github.com/org/repo/pull/42#pullrequestreview-888")
    review.body = overrides.get("body", "Looks good")
    review.state = overrides.get("state", "COMMENTED")
    return review


@pytest.fixture
def mock_publisher() -> tuple[ReviewPublisher, MagicMock]:
    """Create a ReviewPublisher with mocked GitHubClient."""
    with patch("ai_code_reviewer.github.client.Github") as mock_gh_cls:
        mock_gh = MagicMock()
        mock_gh_cls.return_value = mock_gh
        client = GitHubClient(token="ghp_test_token_12345")
        publisher = ReviewPublisher(client)
        return publisher, mock_gh


# ── create_inline_comments Tests ─────────────────────────────────────────────


class TestCreateInlineComments:
    def test_creates_comments_with_line_numbers(self, mock_publisher):
        publisher, _ = mock_publisher
        suggestions = [
            _make_suggestion(file_path="src/auth.py", line_number=10, message="SQL injection risk"),
            _make_suggestion(file_path="src/main.py", line_number=25, message="Unused variable"),
        ]

        comments = publisher.create_inline_comments(suggestions)

        assert len(comments) == 2
        assert comments[0]["path"] == "src/auth.py"
        assert comments[0]["line"] == 10
        assert comments[0]["side"] == "RIGHT"
        assert "SQL injection risk" in comments[0]["body"]
        assert comments[1]["path"] == "src/main.py"
        assert comments[1]["line"] == 25

    def test_skips_suggestions_without_line_number(self, mock_publisher):
        publisher, _ = mock_publisher
        suggestions = [
            _make_suggestion(file_path="src/auth.py", line_number=None, message="General comment"),
            _make_suggestion(file_path="src/main.py", line_number=42, message="Specific issue"),
        ]

        comments = publisher.create_inline_comments(suggestions)

        assert len(comments) == 1
        assert comments[0]["line"] == 42

    def test_adds_risk_prefix_with_emoji(self, mock_publisher):
        publisher, _ = mock_publisher
        risk = _make_risk(level=RiskLevel.CRITICAL, message="SQL injection")
        suggestion = _make_suggestion(risk=risk, message="Use parameterized queries")

        comments = publisher.create_inline_comments([suggestion])

        assert len(comments) == 1
        assert "🔴" in comments[0]["body"]
        assert "[CRITICAL]" in comments[0]["body"]
        assert "Use parameterized queries" in comments[0]["body"]

    def test_adds_high_risk_prefix(self, mock_publisher):
        publisher, _ = mock_publisher
        risk = _make_risk(level=RiskLevel.HIGH)
        suggestion = _make_suggestion(risk=risk, message="Buffer overflow possible")

        comments = publisher.create_inline_comments([suggestion])

        assert "🟠" in comments[0]["body"]
        assert "[HIGH]" in comments[0]["body"]

    def test_adds_medium_risk_prefix(self, mock_publisher):
        publisher, _ = mock_publisher
        risk = _make_risk(level=RiskLevel.MEDIUM)
        suggestion = _make_suggestion(risk=risk, message="Consider refactoring")

        comments = publisher.create_inline_comments([suggestion])

        assert "🟡" in comments[0]["body"]
        assert "[MEDIUM]" in comments[0]["body"]

    def test_adds_code_snippet(self, mock_publisher):
        publisher, _ = mock_publisher
        suggestion = _make_suggestion(
            message="Use a context manager",
            code_snippet="f = open('file.txt')",
        )

        comments = publisher.create_inline_comments([suggestion])

        assert "```" in comments[0]["body"]
        assert "f = open('file.txt')" in comments[0]["body"]

    def test_no_risk_prefix_without_risk(self, mock_publisher):
        publisher, _ = mock_publisher
        suggestion = _make_suggestion(message="Simple suggestion", risk=None)

        comments = publisher.create_inline_comments([suggestion])

        assert comments[0]["body"] == "Simple suggestion"
        assert "[" not in comments[0]["body"]

    def test_empty_suggestions_list(self, mock_publisher):
        publisher, _ = mock_publisher

        comments = publisher.create_inline_comments([])

        assert comments == []


# ── create_review_body Tests ─────────────────────────────────────────────────


class TestCreateReviewBody:
    def test_basic_structure(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(
            summary="No major issues found.",
            risks=[],
            suggestions=[],
        )

        body = publisher.create_review_body(result)

        assert "## AI Code Review" in body
        assert "### Summary" in body
        assert "No major issues found." in body
        assert "### Risks Found" in body
        assert "0 risks detected" in body
        assert "### Suggestions" in body
        assert "0 suggestions provided" in body

    def test_counts_risks_by_severity(self, mock_publisher):
        publisher, _ = mock_publisher
        risks = [
            _make_risk(level=RiskLevel.CRITICAL),
            _make_risk(level=RiskLevel.CRITICAL),
            _make_risk(level=RiskLevel.HIGH),
            _make_risk(level=RiskLevel.MEDIUM),
            _make_risk(level=RiskLevel.LOW),
            _make_risk(level=RiskLevel.INFO),
        ]
        result = _make_analysis_result(risks=risks)

        body = publisher.create_review_body(result)

        assert "6 risks detected (2 critical, 1 high)" in body
        assert "🔴 Critical: 2" in body
        assert "🟠 High: 1" in body
        assert "🟡 Medium: 1" in body
        assert "🔵 Low: 1" in body
        assert "ℹ️ Info: 1" in body

    def test_includes_suggestion_count(self, mock_publisher):
        publisher, _ = mock_publisher
        suggestions = [
            _make_suggestion(message="Fix 1"),
            _make_suggestion(message="Fix 2"),
            _make_suggestion(message="Fix 3"),
        ]
        result = _make_analysis_result(suggestions=suggestions)

        body = publisher.create_review_body(result)

        assert "3 suggestions provided" in body

    def test_includes_files_count(self, mock_publisher):
        publisher, _ = mock_publisher
        files = [
            FileChange(file_path="a.py", change_type=ChangeType.FEATURE),
            FileChange(file_path="b.py", change_type=ChangeType.FIX),
        ]
        result = _make_analysis_result(files_changed=files)

        body = publisher.create_review_body(result)

        assert "Files analyzed: 2" in body

    def test_includes_cost_when_available(self, mock_publisher):
        publisher, _ = mock_publisher
        cost = CostReport(
            input_tokens=1000,
            output_tokens=500,
            total_cost_usd=0.0234,
            model_name="gpt-4",
        )
        result = _make_analysis_result(cost=cost)

        body = publisher.create_review_body(result)

        assert "### Cost" in body
        assert "Model: gpt-4" in body
        assert "Tokens: 1000 in / 500 out" in body
        assert "$0.0234" in body

    def test_no_cost_section_without_cost(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(cost=None)

        body = publisher.create_review_body(result)

        assert "### Cost" not in body

    def test_default_summary_when_none(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(summary=None)

        body = publisher.create_review_body(result)

        assert "No summary provided." in body

    def test_singular_forms(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(
            risks=[_make_risk(level=RiskLevel.LOW)],
            suggestions=[_make_suggestion()],
        )

        body = publisher.create_review_body(result)

        assert "1 risk detected" in body
        assert "1 suggestion provided" in body


# ── preview_review Tests ─────────────────────────────────────────────────────


class TestPreviewReview:
    def test_includes_review_body(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(summary="Test summary")

        preview = publisher.preview_review(result)

        assert "REVIEW BODY PREVIEW" in preview
        assert "## AI Code Review" in preview
        assert "Test summary" in preview

    def test_includes_inline_comments_section(self, mock_publisher):
        publisher, _ = mock_publisher
        suggestions = [
            _make_suggestion(file_path="src/auth.py", line_number=10, message="Fix this"),
            _make_suggestion(file_path="src/main.py", line_number=25, message="Fix that"),
        ]
        result = _make_analysis_result(suggestions=suggestions)

        preview = publisher.preview_review(result)

        assert "INLINE COMMENTS (2)" in preview
        assert "src/auth.py" in preview
        assert "src/main.py" in preview

    def test_shows_no_inline_comments_when_empty(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(suggestions=[])

        preview = publisher.preview_review(result)

        assert "INLINE COMMENTS: None" in preview

    def test_includes_review_event(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(risks=[])

        preview = publisher.preview_review(result)

        assert "REVIEW EVENT: APPROVE" in preview

    def test_preview_with_critical_risk(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(
            risks=[_make_risk(level=RiskLevel.CRITICAL)],
            summary="Critical issues found",
        )

        preview = publisher.preview_review(result)

        assert "REVIEW EVENT: REQUEST_CHANGES" in preview


# ── _determine_review_event Tests ────────────────────────────────────────────


class TestDetermineReviewEvent:
    def test_approve_when_no_risks(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(risks=[])

        event = publisher._determine_review_event(result)

        assert event == "APPROVE"

    def test_request_changes_for_critical_risk(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(
            risks=[_make_risk(level=RiskLevel.CRITICAL)]
        )

        event = publisher._determine_review_event(result)

        assert event == "REQUEST_CHANGES"

    def test_request_changes_for_high_risk(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(
            risks=[_make_risk(level=RiskLevel.HIGH)]
        )

        event = publisher._determine_review_event(result)

        assert event == "REQUEST_CHANGES"

    def test_comment_for_medium_risk(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(
            risks=[_make_risk(level=RiskLevel.MEDIUM)]
        )

        event = publisher._determine_review_event(result)

        assert event == "COMMENT"

    def test_comment_for_low_risk(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(
            risks=[_make_risk(level=RiskLevel.LOW)]
        )

        event = publisher._determine_review_event(result)

        assert event == "COMMENT"

    def test_request_changes_when_mixed_risks(self, mock_publisher):
        publisher, _ = mock_publisher
        result = _make_analysis_result(
            risks=[
                _make_risk(level=RiskLevel.LOW),
                _make_risk(level=RiskLevel.CRITICAL),
                _make_risk(level=RiskLevel.MEDIUM),
            ]
        )

        event = publisher._determine_review_event(result)

        assert event == "REQUEST_CHANGES"


# ── publish_review Tests ─────────────────────────────────────────────────────


class TestPublishReview:
    def test_publish_review_success(self, mock_publisher):
        publisher, gh = mock_publisher
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review.return_value = _make_mock_review(id=888, state="COMMENTED")
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = _make_analysis_result(
            summary="Test review",
            risks=[_make_risk(level=RiskLevel.LOW)],
            suggestions=[
                _make_suggestion(file_path="src/main.py", line_number=10, message="Fix this"),
            ],
        )

        review = publisher.publish_review("owner", "repo", 42, result)

        assert review["id"] == 888
        assert review["state"] == "COMMENTED"
        assert review["inline_comments_count"] == 1
        mock_pr.create_review.assert_called_once()

    def test_publish_review_with_no_suggestions(self, mock_publisher):
        publisher, gh = mock_publisher
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review.return_value = _make_mock_review()
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = _make_analysis_result(suggestions=[])

        review = publisher.publish_review("owner", "repo", 42, result)

        assert review["inline_comments_count"] == 0
        mock_pr.create_review.assert_called_once()

    def test_publish_review_with_critical_risk_requests_changes(self, mock_publisher):
        publisher, gh = mock_publisher
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review.return_value = _make_mock_review(state="CHANGES_REQUESTED")
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = _make_analysis_result(
            risks=[_make_risk(level=RiskLevel.CRITICAL)],
        )

        review = publisher.publish_review("owner", "repo", 42, result)

        call_args = mock_pr.create_review.call_args
        assert call_args.kwargs["event"] == "REQUEST_CHANGES"
        assert review["state"] == "CHANGES_REQUESTED"

    def test_publish_review_approves_when_no_risks(self, mock_publisher):
        publisher, gh = mock_publisher
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review.return_value = _make_mock_review(state="APPROVED")
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = _make_analysis_result(risks=[])

        publisher.publish_review("owner", "repo", 42, result)

        call_args = mock_pr.create_review.call_args
        assert call_args.kwargs["event"] == "APPROVE"

    def test_publish_review_no_commits_raises(self, mock_publisher):
        publisher, gh = mock_publisher
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.get_commits.return_value = []
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = _make_analysis_result()

        with pytest.raises(ReviewPublisherError, match="no commits"):
            publisher.publish_review("owner", "repo", 42, result)

    def test_publish_review_pr_not_found(self, mock_publisher):
        publisher, gh = mock_publisher
        mock_repo = MagicMock()
        mock_repo.get_pull.side_effect = UnknownObjectException(
            status=404, data={"message": "Not Found"}, headers={}
        )
        gh.get_repo.return_value = mock_repo

        result = _make_analysis_result()

        with pytest.raises(Exception, match="not found"):
            publisher.publish_review("owner", "repo", 999, result)

    def test_publish_review_api_error(self, mock_publisher):
        publisher, gh = mock_publisher
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review.side_effect = GithubException(
            status=422, data={"message": "Validation Failed"}, headers={}
        )
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = _make_analysis_result()

        with pytest.raises(ReviewPublisherError, match="Failed to publish"):
            publisher.publish_review("owner", "repo", 42, result)

    def test_publish_review_passes_inline_comments(self, mock_publisher):
        publisher, gh = mock_publisher
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review.return_value = _make_mock_review()
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        suggestions = [
            _make_suggestion(file_path="a.py", line_number=10, message="Fix A"),
            _make_suggestion(file_path="b.py", line_number=20, message="Fix B"),
            _make_suggestion(file_path="c.py", line_number=None, message="General"),
        ]
        result = _make_analysis_result(suggestions=suggestions)

        publisher.publish_review("owner", "repo", 42, result)

        call_args = mock_pr.create_review.call_args
        comments = call_args.kwargs["comments"]
        # Only 2 have line numbers
        assert len(comments) == 2
        assert comments[0]["path"] == "a.py"
        assert comments[1]["path"] == "b.py"

    def test_publish_review_includes_body(self, mock_publisher):
        publisher, gh = mock_publisher
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_pr.get_commits.return_value = [_make_mock_commit()]
        mock_pr.create_review.return_value = _make_mock_review()
        mock_repo.get_pull.return_value = mock_pr
        gh.get_repo.return_value = mock_repo

        result = _make_analysis_result(summary="Custom summary")

        publisher.publish_review("owner", "repo", 42, result)

        call_args = mock_pr.create_review.call_args
        body = call_args.kwargs["body"]
        assert "## AI Code Review" in body
        assert "Custom summary" in body


# ── Module Exports Tests ─────────────────────────────────────────────────────


class TestModuleExports:
    def test_import_from_github_package(self):
        from ai_code_reviewer.github import ReviewPublisher, ReviewPublisherError

        assert ReviewPublisher is not None
        assert ReviewPublisherError is not None

    def test_publisher_error_is_github_client_error(self):
        from ai_code_reviewer.github.client import GitHubClientError

        assert issubclass(ReviewPublisherError, GitHubClientError)
