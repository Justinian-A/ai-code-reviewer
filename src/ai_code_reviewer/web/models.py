"""Web interface data models for AI Code Reviewer."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# Enums


class AnalysisStatus(str, Enum):
    """Status of a web analysis request."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Models


class WebAnalysis(BaseModel):
    """Analysis record for the web interface."""

    id: str = Field(..., description="Unique analysis ID")
    pr_url: str = Field(..., description="Pull request URL")
    pr_number: int
    repository: str
    title: str
    status: AnalysisStatus = AnalysisStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    cost_usd: float = 0.0
    risk_count: int = 0
    suggestion_count: int = 0


class WebConfiguration(BaseModel):
    """Web interface configuration."""

    github_token: str = ""
    ai_provider: str = "deepseek"
    ai_api_key: str = ""
    ai_model: str = "deepseek-v4-flash"
    ai_max_tokens: int = 4096


class CostRecord(BaseModel):
    """Cost tracking record for API usage."""

    id: str
    analysis_id: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
