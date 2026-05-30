"""History API endpoints for the AI Code Reviewer web interface."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ..database import delete_analysis, list_analyses

router = APIRouter(tags=["history"])


@router.get("/api/analyses")
async def list_analysis_history(
    limit: int = Query(default=50, ge=1, le=200, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
) -> dict[str, Any]:
    """List historical analysis records.

    Returns analyses ordered by creation time (newest first).

    Args:
        limit: Maximum number of results (1-200, default 50).
        offset: Number of results to skip for pagination.

    Returns:
        List of analysis summaries with total count.
    """
    analyses = list_analyses(limit=limit, offset=offset)

    items = [
        {
            "id": a.id,
            "pr_url": a.pr_url,
            "pr_number": a.pr_number,
            "repository": a.repository,
            "title": a.title,
            "status": a.status.value,
            "created_at": a.created_at.isoformat(),
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "cost_usd": a.cost_usd,
            "risk_count": a.risk_count,
            "suggestion_count": a.suggestion_count,
        }
        for a in analyses
    ]

    return {
        "items": items,
        "limit": limit,
        "offset": offset,
    }


@router.delete("/api/analyses/{analysis_id}")
async def delete_analysis_record(analysis_id: str) -> dict[str, str]:
    """Delete an analysis record and its associated cost records.

    Args:
        analysis_id: The analysis record ID to delete.

    Returns:
        Confirmation message.

    Raises:
        HTTPException: If analysis not found.
    """
    deleted = delete_analysis(analysis_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

    return {"message": f"Analysis {analysis_id} deleted", "id": analysis_id}
