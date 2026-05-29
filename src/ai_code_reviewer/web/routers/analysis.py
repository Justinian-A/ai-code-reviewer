"""Analysis API endpoints for the AI Code Reviewer web interface."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..database import create_analysis, get_analysis, save_configuration, update_analysis
from ..models import AnalysisStatus, WebAnalysis, WebConfiguration

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analysis"])

# PR URL pattern
_PR_URL_PATTERN = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)"
)


class AnalyzeRequest(BaseModel):
    """Request model for starting a PR analysis."""

    pr_url: str = Field(
        ...,
        description="GitHub pull request URL (https://github.com/owner/repo/pull/123)",
    )


class AnalyzeResponse(BaseModel):
    """Response model for analysis creation."""

    analysis_id: str
    status: str
    message: str


def _parse_pr_url(url: str) -> tuple[str, str, int]:
    """Extract owner, repo, and PR number from a GitHub pull request URL.

    Args:
        url: GitHub PR URL.

    Returns:
        Tuple of (owner, repo, pr_number).

    Raises:
        ValueError: If the URL format is invalid.
    """
    match = _PR_URL_PATTERN.match(url.strip())
    if not match:
        raise ValueError(
            f"Invalid PR URL: {url}. "
            "Expected format: https://github.com/owner/repo/pull/123"
        )
    return match.group("owner"), match.group("repo"), int(match.group("number"))


async def _run_analysis_background(analysis_id: str, pr_url: str) -> None:
    """Execute analysis in background.

    Args:
        analysis_id: The analysis record ID.
        pr_url: GitHub PR URL to analyze.
    """
    try:
        # Update status to running
        analysis = get_analysis(analysis_id)
        if not analysis:
            logger.error("Analysis %s not found", analysis_id)
            return

        analysis.status = AnalysisStatus.RUNNING
        update_analysis(analysis)

        # Parse PR URL
        owner, repo, pr_number = _parse_pr_url(pr_url)

        # Load config and create analyzer
        from ai_code_reviewer.analyzer.hybrid_analyzer import HybridAnalyzer
        from ai_code_reviewer.config import load_config
        from ai_code_reviewer.github.client import GitHubClient

        config = load_config()
        analyzer = HybridAnalyzer(config)

        # Fetch PR data from GitHub
        gh_client = GitHubClient(token=config.github.token)
        pr = gh_client.get_pull_request(owner, repo, pr_number)
        files = gh_client.get_pr_files(owner, repo, pr_number)

        # Run analysis
        result = analyzer.analyze_pr(pr, files)

        # Update with results
        analysis.status = AnalysisStatus.COMPLETED
        analysis.completed_at = datetime.now(UTC)
        analysis.result = result.model_dump()
        analysis.risk_count = len(result.risks)
        analysis.suggestion_count = len(result.suggestions)
        analysis.cost_usd = result.cost.total_cost_usd if result.cost else 0.0
        update_analysis(analysis)

        logger.info("Analysis %s completed successfully", analysis_id)

    except Exception as e:
        logger.exception("Analysis %s failed: %s", analysis_id, e)
        analysis = get_analysis(analysis_id)
        if analysis:
            analysis.status = AnalysisStatus.FAILED
            analysis.error = str(e)
            analysis.completed_at = datetime.now(UTC)
            update_analysis(analysis)


@router.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_pr(request: AnalyzeRequest, background_tasks: BackgroundTasks) -> AnalyzeResponse:
    """Start a PR analysis as a background task.

    Creates an analysis record and schedules background execution.

    Args:
        request: The analysis request containing the PR URL.
        background_tasks: FastAPI background task runner.

    Returns:
        Analysis ID and initial status.
    """
    # Validate PR URL format
    try:
        owner, repo, pr_number = _parse_pr_url(request.pr_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create analysis record
    analysis_id = uuid.uuid4().hex[:12]
    analysis = WebAnalysis(
        id=analysis_id,
        pr_url=request.pr_url,
        pr_number=pr_number,
        repository=f"{owner}/{repo}",
        title=f"PR #{pr_number}",
        status=AnalysisStatus.PENDING,
    )
    create_analysis(analysis)

    # Schedule background task
    background_tasks.add_task(_run_analysis_background, analysis_id, request.pr_url)

    return AnalyzeResponse(
        analysis_id=analysis_id,
        status=AnalysisStatus.PENDING.value,
        message=f"Analysis started for {owner}/{repo}#{pr_number}",
    )


@router.get("/api/analyses/{analysis_id}")
async def get_analysis_result(analysis_id: str) -> dict[str, Any]:
    """Get the result of a specific analysis.

    Args:
        analysis_id: The analysis record ID.

    Returns:
        Analysis record with full details.

    Raises:
        HTTPException: If analysis not found.
    """
    analysis = get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

    return {
        "id": analysis.id,
        "pr_url": analysis.pr_url,
        "pr_number": analysis.pr_number,
        "repository": analysis.repository,
        "title": analysis.title,
        "status": analysis.status.value,
        "created_at": analysis.created_at.isoformat(),
        "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
        "result": analysis.result,
        "error": analysis.error,
        "cost_usd": analysis.cost_usd,
        "risk_count": analysis.risk_count,
        "suggestion_count": analysis.suggestion_count,
    }
