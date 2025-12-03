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
)
from app.core.dependencies import get_current_user
from app.core.discovery_orchestrator import discovery_orchestrator
from app.core.geocoding_service import geocoding_service

router = APIRouter()


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
    
    The discovery process:
    1. Converts area (ZIP/county/polygon) to GeoJSON polygon
    2. Queries INRIX, HERE, and OSM for parking lots
    3. Normalizes and deduplicates results
    4. Fetches satellite imagery for each lot
    5. Evaluates condition using computer vision
    6. Loads business data from Infobel/SafeGraph
    7. Associates parking lots with businesses
    8. Filters for high-value leads
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
    
    # Initialize job status BEFORE starting background task (so status endpoint works immediately)
    discovery_orchestrator.initialize_job(job_id, current_user.id)
    
    # Start discovery in background
    background_tasks.add_task(
        discovery_orchestrator.start_discovery,
        job_id,
        current_user.id,
        area_polygon,
        filters,
        db
    )
    
    return DiscoveryJobResponse(
        job_id=job_id,
        status=DiscoveryStep.QUEUED,
        message="Discovery started. Use GET /discover/{job_id} to check status.",
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

