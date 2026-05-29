"""GitHub PR review publisher.

Publishes analysis results as PR reviews with inline comments and summary.
"""

from __future__ import annotations

import logging
from typing import Any

from github import GithubException, UnknownObjectException
from github.GithubObject import NotSet

from ai_code_reviewer.github.client import GitHubClient, GitHubClientError, GitHubNotFoundError
from ai_code_reviewer.models import AnalysisResult, ReviewSuggestion, RiskLevel

logger = logging.getLogger(__name__)

# Risk level emoji mapping for visual distinction
_RISK_EMOJI: dict[str, str] = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "info": "ℹ️",
}

# Minimum risk level to trigger REQUEST_CHANGES event
_CHANGE_REQUEST_LEVELS = {RiskLevel.CRITICAL, RiskLevel.HIGH}


class ReviewPublisherError(GitHubClientError):
    """Raised when review publishing fails."""


class ReviewPublisher:
    """Publishes code review results as GitHub PR reviews.

    Supports:
    - Inline comments on specific files and lines
    - Summary review body with risk counts
    - Review event selection (COMMENT, REQUEST_CHANGES, APPROVE)

    Args:
        github_client: Authenticated GitHubClient instance.
    """

    def __init__(self, github_client: GitHubClient) -> None:
        self._client = github_client

    def publish_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        result: AnalysisResult,
    ) -> dict[str, Any]:
        """Publish a complete review on a pull request.

        Creates a single PR review with:
        - A summary body describing the analysis results
        - Inline comments for each actionable suggestion

        Args:
            owner: Repository owner (user or org).
            repo: Repository name.
            pr_number: Pull request number.
            result: The AnalysisResult to publish.

        Returns:
            Dict with review details (id, html_url, state).

        Raises:
            ReviewPublisherError: If publishing fails.
            GitHubNotFoundError: If the PR does not exist.
        """
        try:
            gh_repo = self._client._github.get_repo(f"{owner}/{repo}")
            pr = gh_repo.get_pull(pr_number)

            # Get the latest commit for the review
            commits = list(pr.get_commits())
            if not commits:
                raise ReviewPublisherError(
                    f"PR #{pr_number} has no commits to review"
                )
            latest_commit = commits[-1]

            # Build review body and inline comments
            body = self.create_review_body(result)
            inline_comments = self.create_inline_comments(result.suggestions)

            # Determine review event based on risk severity
            event = self._determine_review_event(result)

            # Create the review with inline comments
            gh_review = pr.create_review(
                commit=latest_commit,
                body=body,
                event=event,
                comments=inline_comments if inline_comments else NotSet,
            )

            return {
                "id": gh_review.id,
                "html_url": gh_review.html_url,
                "body": gh_review.body,
                "state": gh_review.state,
                "inline_comments_count": len(inline_comments),
            }

        except UnknownObjectException as exc:
            raise GitHubNotFoundError(
                f"PR #{pr_number} not found in {owner}/{repo}"
            ) from exc
        except GithubException as exc:
            raise ReviewPublisherError(
                f"Failed to publish review: {exc}"
            ) from exc

    def create_inline_comments(
        self, suggestions: list[ReviewSuggestion]
    ) -> list[dict[str, Any]]:
        """Create inline comment payloads from review suggestions.

        Converts ReviewSuggestion objects into the dict format required
        by GitHub's create_review API.

        Only includes suggestions that have a line_number set, as inline
        comments require a specific location.

        Args:
            suggestions: List of ReviewSuggestion objects.

        Returns:
            List of dicts with 'path', 'line', 'side', and 'body' keys.
        """
        comments: list[dict[str, Any]] = []

        for suggestion in suggestions:
            # Skip suggestions without a line number (can't be inline)
            if suggestion.line_number is None:
                continue

            # Build comment body with risk prefix if available
            body = suggestion.message
            if suggestion.risk:
                emoji = _RISK_EMOJI.get(suggestion.risk.level.value, "")
                prefix = f"{emoji} **[{suggestion.risk.level.value.upper()}]**"
                body = f"{prefix} {body}"

            # Add code snippet context if available
            if suggestion.code_snippet:
                body += f"\n\n```\n{suggestion.code_snippet}\n```"

            comments.append({
                "path": suggestion.file_path,
                "line": suggestion.line_number,
                "side": "RIGHT",
                "body": body,
            })

        return comments

    def create_review_body(self, result: AnalysisResult) -> str:
        """Create the review body summarizing analysis results.

        Formats a markdown review body with:
        - Summary section
        - Risk count breakdown
        - Suggestion count
        - Cost information if available

        Args:
            result: The AnalysisResult to summarize.

        Returns:
            Formatted markdown string for the review body.
        """
        # Count risks by severity
        risk_counts: dict[str, int] = {}
        for risk in result.risks:
            risk_counts[risk.level.value] = risk_counts.get(risk.level.value, 0) + 1

        critical_count = risk_counts.get("critical", 0)
        high_count = risk_counts.get("high", 0)
        medium_count = risk_counts.get("medium", 0)
        low_count = risk_counts.get("low", 0)
        info_count = risk_counts.get("info", 0)
        total_risks = len(result.risks)

        # Build summary section
        summary = result.summary or "No summary provided."

        # Build risk breakdown
        risk_lines: list[str] = []
        if critical_count:
            risk_lines.append(f"- 🔴 Critical: {critical_count}")
        if high_count:
            risk_lines.append(f"- 🟠 High: {high_count}")
        if medium_count:
            risk_lines.append(f"- 🟡 Medium: {medium_count}")
        if low_count:
            risk_lines.append(f"- 🔵 Low: {low_count}")
        if info_count:
            risk_lines.append(f"- ℹ️ Info: {info_count}")

        risk_section = "\n".join(risk_lines) if risk_lines else "No risks detected."

        # Build files summary
        files_count = len(result.files_changed)

        # Assemble the review body
        body_parts = [
            "## AI Code Review",
            "",
            "### Summary",
            summary,
            "",
            "### Risks Found",
            f"{total_risks} risk{'s' if total_risks != 1 else ''} detected "
            f"({critical_count} critical, {high_count} high)",
            "",
            risk_section,
            "",
            "### Suggestions",
            f"{len(result.suggestions)} suggestion{'s' if len(result.suggestions) != 1 else ''} provided",
            f"Files analyzed: {files_count}",
        ]

        # Add cost info if available
        if result.cost:
            body_parts.extend([
                "",
                "### Cost",
                f"- Model: {result.cost.model_name or 'unknown'}",
                f"- Tokens: {result.cost.input_tokens} in / {result.cost.output_tokens} out",
                f"- Cost: ${result.cost.total_cost_usd:.4f}",
            ])

        return "\n".join(body_parts)

    def preview_review(self, result: AnalysisResult) -> str:
        """Preview the review content without publishing.

        Generates the full review output including the summary body
        and all inline comments, formatted for human review.

        Args:
            result: The AnalysisResult to preview.

        Returns:
            Formatted string showing the complete review preview.
        """
        sections: list[str] = []

        # Review body
        sections.append("=" * 60)
        sections.append("REVIEW BODY PREVIEW")
        sections.append("=" * 60)
        sections.append("")
        sections.append(self.create_review_body(result))

        # Inline comments
        inline_comments = self.create_inline_comments(result.suggestions)

        if inline_comments:
            sections.append("")
            sections.append("=" * 60)
            sections.append(f"INLINE COMMENTS ({len(inline_comments)})")
            sections.append("=" * 60)

            for i, comment in enumerate(inline_comments, 1):
                sections.append("")
                sections.append(f"--- Comment {i} ---")
                sections.append(f"File: {comment['path']}")
                sections.append(f"Line: {comment['line']}")
                sections.append(f"Side: {comment['side']}")
                sections.append(f"Body:")
                sections.append(comment["body"])
        else:
            sections.append("")
            sections.append("=" * 60)
            sections.append("INLINE COMMENTS: None")
            sections.append("=" * 60)

        # Review event
        event = self._determine_review_event(result)
        sections.append("")
        sections.append("=" * 60)
        sections.append(f"REVIEW EVENT: {event}")
        sections.append("=" * 60)

        return "\n".join(sections)

    @staticmethod
    def _determine_review_event(result: AnalysisResult) -> str:
        """Determine the appropriate review event based on risk severity.

        Args:
            result: The AnalysisResult to evaluate.

        Returns:
            Review event string: 'REQUEST_CHANGES', 'COMMENT', or 'APPROVE'.
        """
        if not result.risks:
            return "APPROVE"

        # Check for critical or high risks
        has_blocking_risk = any(
            risk.level in _CHANGE_REQUEST_LEVELS for risk in result.risks
        )
        if has_blocking_risk:
            return "REQUEST_CHANGES"

        return "COMMENT"
