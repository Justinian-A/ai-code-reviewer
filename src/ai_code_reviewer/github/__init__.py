"""GitHub integration module.

Provides a typed GitHub API client with rate limiting and retry logic.
"""

from ai_code_reviewer.github.client import (
    GitHubClient,
    GitHubClientError,
    GitHubNotFoundError,
    GitHubPermissionError,
)
from ai_code_reviewer.github.models import (
    ChangeType,
    FileChange,
    PullRequest,
    ReviewSuggestion,
    Risk,
    RiskCategory,
    RiskLevel,
)
from ai_code_reviewer.github.review_publisher import ReviewPublisher, ReviewPublisherError

__all__ = [
    # Client
    "GitHubClient",
    "GitHubClientError",
    "GitHubNotFoundError",
    "GitHubPermissionError",
    # Publisher
    "ReviewPublisher",
    "ReviewPublisherError",
    # Models (re-exported from core)
    "ChangeType",
    "FileChange",
    "PullRequest",
    "ReviewSuggestion",
    "Risk",
    "RiskCategory",
    "RiskLevel",
]
