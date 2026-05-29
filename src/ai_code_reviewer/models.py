"""Core data models for AI Code Reviewer."""

from datetime import UTC, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# Enums


class RiskLevel(str, Enum):
    """Risk severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RiskCategory(str, Enum):
    """Risk classification categories."""

    SECURITY = "security"
    LOGIC = "logic"
    ARCHITECTURE = "architecture"


class ChangeType(str, Enum):
    """Types of code changes."""

    FEATURE = "feature"
    FIX = "fix"
    REFACTOR = "refactor"
    DOCS = "docs"
    TEST = "test"
    CHORE = "chore"


class OutputFormat(str, Enum):
    """Supported output formats."""

    TERMINAL = "terminal"
    MARKDOWN = "markdown"
    JSON = "json"


# Models


class Risk(BaseModel):
    """A risk identified during code review."""

    level: RiskLevel
    category: RiskCategory
    message: str
    file_path: str
    line_number: Optional[int] = None
    suggestion: Optional[str] = None


class PullRequest(BaseModel):
    """Pull request metadata."""

    number: int
    title: str
    description: Optional[str] = None
    author: str
    repository: str
    base_branch: str = "main"
    head_branch: str
    created_at: datetime
    updated_at: datetime


class FileChange(BaseModel):
    """Represents a single file change in a PR."""

    file_path: str
    change_type: ChangeType
    additions: int = Field(ge=0, default=0)
    deletions: int = Field(ge=0, default=0)
    diff_content: Optional[str] = None
    language: Optional[str] = None


class ReviewSuggestion(BaseModel):
    """A review suggestion for a specific location."""

    file_path: str
    line_number: Optional[int] = None
    message: str
    risk: Optional[Risk] = None
    code_snippet: Optional[str] = None


class CostReport(BaseModel):
    """API usage cost tracking."""

    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    total_cost_usd: float = Field(ge=0, default=0.0)
    model_name: Optional[str] = None


class AnalysisResult(BaseModel):
    """Complete analysis result for a PR."""

    pr: PullRequest
    files_changed: List[FileChange] = Field(default_factory=list)
    risks: List[Risk] = Field(default_factory=list)
    suggestions: List[ReviewSuggestion] = Field(default_factory=list)
    cost: Optional[CostReport] = None
    summary: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
