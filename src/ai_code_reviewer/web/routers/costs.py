"""Cost tracking API endpoints for the AI Code Reviewer web interface."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query

from ..database import get_cost_records_since, get_cost_summary, get_daily_costs

router = APIRouter(tags=["costs"])


@router.get("/api/costs")
async def get_costs(days: int = Query(default=30, ge=1, le=365, description="Number of days")) -> dict[str, Any]:
    """Get cost statistics for the specified time period.

    Returns daily cost breakdown and aggregated totals.

    Args:
        days: Number of days to look back (1-365, default 30).

    Returns:
        Cost statistics with daily breakdown.
    """
    daily_costs = get_daily_costs(days)
    total_cost = sum(d["total_cost_usd"] for d in daily_costs)
    total_analyses = sum(d["analysis_count"] for d in daily_costs)

    return {
        "days": days,
        "total_cost_usd": round(total_cost, 4),
        "total_analyses": total_analyses,
        "avg_cost_per_analysis": round(total_cost / total_analyses, 4) if total_analyses > 0 else 0.0,
        "daily": daily_costs,
    }


@router.get("/api/costs/summary")
async def get_cost_summary_endpoint() -> dict[str, Any]:
    """Get overall cost summary across all analyses.

    Returns aggregated cost metrics for all completed analyses.

    Returns:
        Cost summary with totals and averages.
    """
    summary = get_cost_summary()
    return summary
