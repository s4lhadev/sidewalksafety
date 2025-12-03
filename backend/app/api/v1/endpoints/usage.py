from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.db.base import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.core.usage_tracking_service import usage_tracking_service

router = APIRouter()


@router.get("/summary", response_model=Dict[str, Any])
async def get_usage_summary(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to look back"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get usage summary for the current user.
    
    Returns:
        - Total requests
        - Total estimated cost
        - Breakdown by action type (discovery, cv_evaluation, api_call)
        - Breakdown by resource (inrix, here, google_maps, roboflow, etc.)
    """
    return usage_tracking_service.get_user_usage_summary(db, current_user.id, days)


@router.get("/daily", response_model=list)
async def get_daily_usage(
    days: int = Query(default=7, ge=1, le=30, description="Number of days to look back"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get daily usage breakdown for the current user.
    
    Returns list of daily usage with:
        - date
        - request_count
        - total_cost_usd
        - bytes_processed
    """
    return usage_tracking_service.get_daily_usage(db, current_user.id, days)

