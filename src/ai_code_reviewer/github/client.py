"""GitHub API client with rate limiting and retry logic.

Uses PyGithub for GitHub REST API access with exponential backoff retry.
"""

from __future__ import annotations

import base64
import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from github import Github, GithubException, RateLimitExceededException, UnknownObjectException
from github.Auth import Token
from github.GithubRetry import GithubRetry
from github.PullRequest import PullRequest as GhPullRequest
from github.Requester import Requester

from ai_code_reviewer.models import (
    ChangeType,
    FileChange,
    PullRequest,
    ReviewSuggestion,
)

logger = logging.getLogger(__name__)

# Type variable for decorated return type
T = TypeVar("T")

# Map GitHub file statuses to our ChangeType enum
_STATUS_TO_CHANGE_TYPE: dict[str, ChangeType] = {
    "added": ChangeType.FEATURE,
    "removed": ChangeType.CHORE,
    "modified": ChangeType.REFACTOR,
    "renamed": ChangeType.CHORE,
}

# Map file extensions to language names
_EXTENSION_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".md": "markdown",
    ".toml": "toml",
}


def _detect_language(file_path: str) -> str | None:
    """Detect programming language from file extension."""
    # Handle filenames like "Makefile", "Dockerfile" with no extension
    dot_index = file_path.rfind(".")
    if dot_index == -1:
        name = file_path.rsplit("/", 1)[-1].lower()
        _SPECIAL_NAMES: dict[str, str] = {
            "makefile": "makefile",
            "dockerfile": "dockerfile",
            "procfile": "procfile",
        }
        return _SPECIAL_NAMES.get(name)
    ext = file_path[dot_index:].lower()
    return _EXTENSION_TO_LANGUAGE.get(ext)


def _retry_on_rate_limit(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for exponential backoff retry on rate limit errors.

    PyGithub's GithubRetry handles most 403/5xx retries automatically.
    This decorator adds an extra safety net for edge cases.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except RateLimitExceededException as exc:
                    last_exception = exc
                    if attempt == max_retries:
                        raise GitHubClientError(
                            f"Rate limit exceeded after {max_retries} retries. "
                            f"Reset at: {exc.headers.get('X-RateLimit-Reset', 'unknown')}"
                        ) from exc
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "Rate limit hit (attempt %d/%d), retrying in %.1fs",
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)
                except GithubException as exc:
                    # Only retry on 403 (rate limit) or 5xx (server error)
                    if exc.status in (403, 500, 502, 503, 504) and attempt < max_retries:
                        last_exception = exc
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            "GitHub API error %d (attempt %d/%d), retrying in %.1fs",
                            exc.status,
                            attempt + 1,
                            max_retries,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        raise
            # Should not reach here, but safety net
            raise GitHubClientError("Max retries exceeded") from last_exception

        return wrapper  # type: ignore[return-value]

    return decorator


class GitHubClientError(Exception):
    """Base exception for GitHub client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GitHubNotFoundError(GitHubClientError):
    """Raised when a requested resource is not found (404)."""

    def __init__(self, message: str):
        super().__init__(message, status_code=404)


class GitHubPermissionError(GitHubClientError):
    """Raised when access is forbidden (403) after retries."""

    def __init__(self, message: str):
        super().__init__(message, status_code=403)


class GitHubClient:
    """GitHub API client with rate limiting and retry logic.

    Wraps PyGithub to provide typed methods that return Pydantic models.

    Args:
        token: GitHub Personal Access Token.
        max_retries: Maximum number of retries for rate-limited requests.
        base_delay: Base delay in seconds for exponential backoff.
    """

    def __init__(
        self,
        token: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        if not token:
            raise ValueError("GitHub token is required")

        self._max_retries = max_retries
        self._base_delay = base_delay

        # Configure PyGithub's built-in retry for 403/5xx
        retry = GithubRetry(total=3, backoff_factor=0.5)

        auth = Token(token)
        self._github: Github = Github(auth=auth, retry=retry)

    def close(self) -> None:
        """Close the underlying GitHub client and release resources."""
        self._github.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def get_user(self) -> dict[str, Any]:
        """Get the authenticated user's information.

        Returns:
            Dict with user details (login, name, email, etc.).

        Raises:
            GitHubClientError: If the request fails.
        """
        try:
            user = self._github.get_user()
            return {
                "login": user.login,
                "name": user.name,
                "email": user.email,
                "id": user.id,
                "avatar_url": user.avatar_url,
                "html_url": user.html_url,
            }
        except UnknownObjectException as exc:
            raise GitHubNotFoundError("Authenticated user not found") from exc
        except GithubException as exc:
            raise self._map_exception(exc) from exc

    @_retry_on_rate_limit()
    def get_pull_request(
        self, owner: str, repo: str, pr_number: int
    ) -> PullRequest:
        """Get pull request details.

        Args:
            owner: Repository owner (user or org).
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            PullRequest model with PR metadata.

        Raises:
            GitHubNotFoundError: If PR does not exist.
            GitHubClientError: If the request fails.
        """
        try:
            gh_repo = self._github.get_repo(f"{owner}/{repo}")
            pr = gh_repo.get_pull(pr_number)
            return self._map_pull_request(pr, f"{owner}/{repo}")
        except UnknownObjectException as exc:
            raise GitHubNotFoundError(
                f"Pull request #{pr_number} not found in {owner}/{repo}"
            ) from exc
        except GithubException as exc:
            raise self._map_exception(exc) from exc

    @_retry_on_rate_limit()
    def get_pr_files(
        self, owner: str, repo: str, pr_number: int
    ) -> list[FileChange]:
        """Get the list of files changed in a pull request.

        Args:
            owner: Repository owner (user or org).
            repo: Repository name.
            pr_number: Pull request number.

        Returns:
            List of FileChange models for each changed file.

        Raises:
            GitHubNotFoundError: If PR does not exist.
            GitHubClientError: If the request fails.
        """
        try:
            gh_repo = self._github.get_repo(f"{owner}/{repo}")
            pr = gh_repo.get_pull(pr_number)
            files = pr.get_files()
            return [self._map_file_change(f) for f in files]
        except UnknownObjectException as exc:
            raise GitHubNotFoundError(
                f"Pull request #{pr_number} not found in {owner}/{repo}"
            ) from exc
        except GithubException as exc:
            raise self._map_exception(exc) from exc

    @_retry_on_rate_limit()
    def get_file_content(
        self, owner: str, repo: str, path: str, ref: str = "main"
    ) -> str:
        """Get the content of a file at a specific ref.

        Args:
            owner: Repository owner (user or org).
            repo: Repository name.
            path: File path in the repository.
            ref: Git ref (branch, tag, or commit SHA). Defaults to "main".

        Returns:
            Decoded file content as string.

        Raises:
            GitHubNotFoundError: If file does not exist.
            GitHubClientError: If the request fails.
        """
        try:
            gh_repo = self._github.get_repo(f"{owner}/{repo}")
            content_file = gh_repo.get_contents(path, ref=ref)

            # get_contents may return a list for directories
            if isinstance(content_file, list):
                raise GitHubClientError(
                    f"Path '{path}' is a directory, not a file"
                )

            # Decode base64 content
            if content_file.encoding == "base64" and content_file.content:
                return base64.b64decode(content_file.content).decode("utf-8")
            # Fallback: content might already be decoded
            return content_file.decoded_content.decode("utf-8")
        except UnknownObjectException as exc:
            raise GitHubNotFoundError(
                f"File '{path}' not found in {owner}/{repo} at ref '{ref}'"
            ) from exc
        except GithubException as exc:
            raise self._map_exception(exc) from exc

    @_retry_on_rate_limit()
    def create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        review: ReviewSuggestion,
    ) -> dict[str, Any]:
        """Create a review comment on a pull request.

        Posts a review comment at the specified file and line with the
        given suggestion message.

        Args:
            owner: Repository owner (user or org).
            repo: Repository name.
            pr_number: Pull request number.
            review: ReviewSuggestion with file, line, and message.

        Returns:
            Dict with created review comment details.

        Raises:
            GitHubNotFoundError: If PR or file does not exist.
            GitHubClientError: If the request fails.
        """
        try:
            gh_repo = self._github.get_repo(f"{owner}/{repo}")
            pr = gh_repo.get_pull(pr_number)

            # Get the latest commit for the review comment
            commits = list(pr.get_commits())
            if not commits:
                raise GitHubClientError(
                    f"PR #{pr_number} has no commits to review"
                )
            latest_commit = commits[-1]

            # Build the review body
            body = review.message
            if review.risk:
                body = f"**[{review.risk.level.value.upper()}]** {body}"

            # Create review comment at specific file/line
            if review.line_number is not None:
                comment = pr.create_review_comment(
                    body=body,
                    commit=latest_commit,
                    path=review.file_path,
                    line=review.line_number,
                )
                return {
                    "id": comment.id,
                    "html_url": comment.html_url,
                    "body": comment.body,
                    "path": comment.path,
                    "line": comment.line,
                    "created_at": comment.created_at.isoformat(),
                }
            else:
                # If no line number, create a general review
                event = "COMMENT"
                if review.risk and review.risk.level.value in ("critical", "high"):
                    event = "REQUEST_CHANGES"

                gh_review = pr.create_review(
                    commit=latest_commit,
                    body=body,
                    event=event,
                )
                return {
                    "id": gh_review.id,
                    "html_url": gh_review.html_url,
                    "body": gh_review.body,
                    "state": gh_review.state,
                }
        except UnknownObjectException as exc:
            raise GitHubNotFoundError(
                f"Resource not found for PR #{pr_number} in {owner}/{repo}: {exc}"
            ) from exc
        except GithubException as exc:
            raise self._map_exception(exc) from exc

    @staticmethod
    def _map_pull_request(pr: object, repository: str) -> PullRequest:
        """Map a PyGithub PullRequest to our PullRequest model."""
        # Type narrowing for the PyGithub PullRequest object
        assert hasattr(pr, "number"), "Expected a PyGithub PullRequest"
        return PullRequest(
            number=pr.number,  # type: ignore[attr-defined]
            title=pr.title,  # type: ignore[attr-defined]
            description=pr.body or None,  # type: ignore[attr-defined]
            author=pr.user.login,  # type: ignore[attr-defined]
            repository=repository,
            base_branch=pr.base.ref,  # type: ignore[attr-defined]
            head_branch=pr.head.ref,  # type: ignore[attr-defined]
            created_at=pr.created_at,  # type: ignore[attr-defined]
            updated_at=pr.updated_at,  # type: ignore[attr-defined]
        )

    @staticmethod
    def _map_file_change(gh_file: object) -> FileChange:
        """Map a PyGithub File to our FileChange model."""
        assert hasattr(gh_file, "filename"), "Expected a PyGithub File"
        filename: str = gh_file.filename  # type: ignore[attr-defined]
        status: str = gh_file.status  # type: ignore[attr-defined]

        change_type = _STATUS_TO_CHANGE_TYPE.get(status, ChangeType.FEATURE)
        language = _detect_language(filename)

        return FileChange(
            file_path=filename,
            change_type=change_type,
            additions=gh_file.additions,  # type: ignore[attr-defined]
            deletions=gh_file.deletions,  # type: ignore[attr-defined]
            diff_content=gh_file.patch or None,  # type: ignore[attr-defined]
            language=language,
        )

    @staticmethod
    def _map_exception(exc: GithubException) -> GitHubClientError:
        """Map a PyGithub exception to our custom exceptions."""
        message = str(exc.data.get("message", str(exc))) if isinstance(exc.data, dict) else str(exc)

        if isinstance(exc, UnknownObjectException) or exc.status == 404:
            return GitHubNotFoundError(message)
        if isinstance(exc, RateLimitExceededException) or exc.status == 403:
            return GitHubPermissionError(f"Forbidden: {message}")
        if exc.status and exc.status >= 500:
            return GitHubClientError(f"GitHub server error: {message}", status_code=exc.status)
        return GitHubClientError(message, status_code=exc.status)
