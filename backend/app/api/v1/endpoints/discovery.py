from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from app.db.base import get_db
from app.models.user import User
from app.schemas.discovery import (
    DiscoveryRequest,
    DiscoveryJobResponse,
    DiscoveryStatusResponse,
    DiscoveryResultsResponse,
    DiscoveryFilters,
    DiscoveryStep,
    DiscoveryProgress,
    DiscoveryMode,
    BUSINESS_TYPE_OPTIONS,
)
from app.core.dependencies import get_current_user
from app.core.discovery_orchestrator import discovery_orchestrator, DiscoveryMode as OrchestratorMode
from app.core.geocoding_service import geocoding_service

router = APIRouter()


@router.get("/business-types")
async def get_business_type_options():
    """
    Get available business type options for discovery.
    
    Returns a list of business types grouped by tier (premium, high, standard).
    Use these IDs in the `business_type_ids` field when starting discovery.
    """
    return {
        "tiers": [
            {
                "id": "premium",
                "label": "Premium (High Success Rate)",
                "icon": "trophy",
                "description": "Apartments, condos, mobile homes - actual properties with parking",
                "types": BUSINESS_TYPE_OPTIONS["premium"],
            },
            {
                "id": "high",
                "label": "High Priority",
                "icon": "star",
                "description": "Commercial properties with large parking areas",
                "types": BUSINESS_TYPE_OPTIONS["high"],
            },
            {
                "id": "standard",
                "label": "Standard",
                "icon": "map-pin",
                "description": "Other businesses that may have parking lots",
                "types": BUSINESS_TYPE_OPTIONS["standard"],
            },
        ]
    }


@router.post("", response_model=DiscoveryJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_discovery(
    request: DiscoveryRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start parking lot discovery process.
    
    This is an async operation. Returns a job_id that can be used to check status.
    
    Two discovery modes available:
    
    **business_first** (recommended, default):
    1. Find businesses by type (HOAs, apartments, shopping centers)
    2. Find parking lots for each business
    3. Fetch satellite imagery and evaluate condition
    4. Return prioritized leads with contact info
    
    **parking_first** (legacy):
    1. Find all parking lots in area
    2. Fetch satellite imagery and evaluate condition
    3. Find nearby businesses
    4. Associate parking lots with businesses
    """
    # Validate request
    if request.area_type == "county" and not request.state:
        raise HTTPException(
            status_code=400,
            detail="State is required for county search"
        )
    
    if request.area_type == "polygon" and not request.polygon:
        raise HTTPException(
            status_code=400,
            detail="Polygon is required when area_type is 'polygon'"
        )
    
    # Get or create polygon
    if request.area_type == "polygon":
        area_polygon = request.polygon.model_dump()
    else:
        area_polygon = await geocoding_service.get_area_polygon(
            request.area_type.value,
            request.value,
            request.state
        )
        
        if not area_polygon:
            raise HTTPException(
                status_code=400,
                detail=f"Could not geocode {request.area_type.value}: {request.value}"
            )
    
    # Create job
    job_id = uuid4()
    filters = request.filters or DiscoveryFilters()
    
    # Override max_lots if max_results is provided in request
    if request.max_results:
        filters.max_lots = request.max_results
        filters.max_businesses = request.max_results
    
    # Initialize job status BEFORE starting background task (so status endpoint works immediately)
    discovery_orchestrator.initialize_job(job_id, current_user.id)
    
    # Convert schema mode to orchestrator mode
    orchestrator_mode = OrchestratorMode.BUSINESS_FIRST
    if request.mode == DiscoveryMode.PARKING_FIRST:
        orchestrator_mode = OrchestratorMode.PARKING_FIRST
    
    # Convert tiers to strings if provided
    tier_strings = None
    if request.tiers:
        tier_strings = [t.value for t in request.tiers]
    
    # Start discovery in background
    background_tasks.add_task(
        discovery_orchestrator.start_discovery,
        job_id,
        current_user.id,
        area_polygon,
        filters,
        db,
        orchestrator_mode,
        tier_strings,
        request.business_type_ids,
    )
    
    mode_desc = "business-first" if orchestrator_mode == OrchestratorMode.BUSINESS_FIRST else "parking-first"
    
    # Add tier info to message if specified
    if tier_strings:
        mode_desc += f" [{', '.join(tier_strings)}]"
    
    return DiscoveryJobResponse(
        job_id=job_id,
        status=DiscoveryStep.QUEUED,
        message=f"Discovery started ({mode_desc}). Use GET /discover/{{job_id}} to check status.",
        estimated_completion=datetime.utcnow() + timedelta(minutes=5),
    )


@router.get("/{job_id}", response_model=DiscoveryStatusResponse)
async def get_discovery_status(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Get status of a discovery job.
    
    Returns current step, progress metrics, and any errors.
    """
    job = discovery_orchestrator.get_job_status(job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Discovery job not found"
        )
    
    # Verify ownership
    if job.get("user_id") != str(current_user.id):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this job"
        )
    
    return DiscoveryStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        started_at=job["started_at"],
        completed_at=job.get("completed_at"),
        error=job.get("error"),
    )


@router.get("/{job_id}/results", response_model=DiscoveryResultsResponse)
async def get_discovery_results(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Get results summary of a completed discovery job.
    """
    job = discovery_orchestrator.get_job_status(job_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Discovery job not found"
        )
    
    if job.get("user_id") != str(current_user.id):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to view this job"
        )
    
    if job["status"] != DiscoveryStep.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Current status: {job['status'].value}"
        )
    
    progress = job["progress"]
    
    return DiscoveryResultsResponse(
        job_id=job_id,
        status=job["status"],
        results={
            "parking_lots_found": progress.parking_lots_found,
            "parking_lots_evaluated": progress.parking_lots_evaluated,
            "businesses_loaded": progress.businesses_loaded,
            "associations_made": progress.associations_made,
            "high_value_leads": progress.high_value_leads,
        },
        message=f"Found {progress.parking_lots_found} parking lots. {progress.high_value_leads} high-value leads identified.",
    )

