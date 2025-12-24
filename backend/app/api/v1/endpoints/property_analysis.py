"""
Property Analysis API endpoints.

Provides endpoints for:
- Starting property analysis
- Getting analysis status/results
- Listing analyses
- Serving CV images
"""
import logging
import os
from uuid import UUID, uuid4
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape

from app.core.dependencies import get_db, get_current_user
from app.core.property_analysis_service import property_analysis_service
from app.core.config import settings
from app.models.user import User
from app.models.property_analysis import PropertyAnalysis
from app.models.asphalt_area import AsphaltArea
from app.schemas.property_analysis import (
    PropertyAnalysisRequest,
    PropertyAnalysisResponse,
    PropertyAnalysisJobResponse,
    PropertyAnalysisListResponse,
    PropertyAnalysisImages,
    AsphaltAreaResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/property-analysis", tags=["property-analysis"])


@router.post("", response_model=PropertyAnalysisJobResponse)
async def start_property_analysis(
    request: PropertyAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start a property analysis for a business location.
    
    This initiates the two-stage CV pipeline:
    1. Fetch wide satellite image
    2. Segment buildings and paved surfaces
    3. Associate asphalt with business
    4. Evaluate condition
    5. Generate annotated images
    
    Returns a job ID for polling status.
    """
    job_id = str(uuid4())
    analysis_id = uuid4()
    
    logger.info(f"Starting property analysis job {job_id} for user {current_user.id}")
    logger.info(f"   Location: ({request.latitude}, {request.longitude})")
    
    # Create initial analysis record
    property_analysis = PropertyAnalysis(
        id=analysis_id,
        user_id=current_user.id,
        status="pending",
        segmentation_model_id=settings.ROBOFLOW_SEGMENTATION_MODEL
    )
    
    # We'll update the location in the background task
    # For now, just save the pending record
    
    # Run analysis in background
    background_tasks.add_task(
        run_analysis_task,
        analysis_id=analysis_id,
        latitude=request.latitude,
        longitude=request.longitude,
        user_id=str(current_user.id),
        business_id=str(request.business_id) if request.business_id else None,
        parking_lot_id=str(request.parking_lot_id) if request.parking_lot_id else None,
        job_id=job_id
    )
    
    return PropertyAnalysisJobResponse(
        job_id=job_id,
        analysis_id=analysis_id,
        status="processing",
        message="Property analysis started. Poll the analysis endpoint for results."
    )


async def run_analysis_task(
    analysis_id: UUID,
    latitude: float,
    longitude: float,
    user_id: str,
    business_id: Optional[str],
    parking_lot_id: Optional[str],
    job_id: str
):
    """Background task to run property analysis."""
    from app.db.base import SessionLocal
    
    logger.info(f"Running analysis task {job_id}")
    
    db = SessionLocal()
    try:
        result = await property_analysis_service.analyze_property(
            business_location=(latitude, longitude),
            user_id=user_id,
            db=db,
            business_id=business_id,
            parking_lot_id=parking_lot_id,
            job_id=job_id
        )
        
        if result.success:
            logger.info(f"Analysis {analysis_id} completed successfully")
        else:
            logger.error(f"Analysis {analysis_id} failed: {result.error}")
            
    except Exception as e:
        logger.error(f"Analysis task failed: {e}", exc_info=True)
        
        # Update status to failed
        analysis = db.query(PropertyAnalysis).filter(
            PropertyAnalysis.id == analysis_id
        ).first()
        
        if analysis:
            analysis.status = "failed"
            analysis.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.get("/{analysis_id}", response_model=PropertyAnalysisResponse)
async def get_property_analysis(
    analysis_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get property analysis results.
    
    Returns the complete analysis including:
    - Status (pending, processing, completed, failed)
    - Aggregated metrics (total area, condition score)
    - Image URLs (segmentation, property boundary, condition)
    - List of asphalt areas with individual metrics
    """
    analysis = db.query(PropertyAnalysis).filter(
        PropertyAnalysis.id == analysis_id,
        PropertyAnalysis.user_id == current_user.id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get asphalt areas
    areas = db.query(AsphaltArea).filter(
        AsphaltArea.property_analysis_id == analysis_id
    ).all()
    
    # Extract location from geography
    lat, lng = None, None
    if analysis.business_location:
        point = to_shape(analysis.business_location)
        lat, lng = point.y, point.x
    
    return PropertyAnalysisResponse(
        id=analysis.id,
        status=analysis.status,
        latitude=lat,
        longitude=lng,
        total_asphalt_area_m2=analysis.total_asphalt_area_m2,
        weighted_condition_score=analysis.weighted_condition_score,
        total_crack_count=int(analysis.total_crack_count) if analysis.total_crack_count else None,
        total_pothole_count=int(analysis.total_pothole_count) if analysis.total_pothole_count else None,
        images=PropertyAnalysisImages(
            wide_satellite=analysis.wide_image_base64,
            segmentation=analysis.segmentation_image_base64,
            property_boundary=analysis.property_boundary_image_base64,
            condition_analysis=analysis.condition_analysis_image_base64,
        ),
        asphalt_areas=[
            AsphaltAreaResponse(
                id=area.id,
                area_type=area.area_type,
                area_m2=area.area_m2,
                is_associated=area.is_associated,
                association_reason=area.association_reason,
                distance_to_building_m=area.distance_to_building_m,
                condition_score=area.condition_score,
                crack_count=area.crack_count,
                pothole_count=area.pothole_count,
                crack_density=area.crack_density,
            )
            for area in areas
        ],
        business_id=analysis.business_id,
        parking_lot_id=analysis.parking_lot_id,
        analyzed_at=analysis.analyzed_at,
        created_at=analysis.created_at,
        error_message=analysis.error_message,
    )


@router.get("", response_model=PropertyAnalysisListResponse)
async def list_property_analyses(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List property analyses for the current user.
    """
    query = db.query(PropertyAnalysis).filter(
        PropertyAnalysis.user_id == current_user.id
    )
    
    if status:
        query = query.filter(PropertyAnalysis.status == status)
    
    total = query.count()
    
    analyses = query.order_by(
        PropertyAnalysis.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    results = []
    for analysis in analyses:
        # Get asphalt areas for each
        areas = db.query(AsphaltArea).filter(
            AsphaltArea.property_analysis_id == analysis.id
        ).all()
        
        lat, lng = None, None
        if analysis.business_location:
            point = to_shape(analysis.business_location)
            lat, lng = point.y, point.x
        
        results.append(PropertyAnalysisResponse(
            id=analysis.id,
            status=analysis.status,
            latitude=lat,
            longitude=lng,
            total_asphalt_area_m2=analysis.total_asphalt_area_m2,
            weighted_condition_score=analysis.weighted_condition_score,
            total_crack_count=int(analysis.total_crack_count) if analysis.total_crack_count else None,
            total_pothole_count=int(analysis.total_pothole_count) if analysis.total_pothole_count else None,
            images=PropertyAnalysisImages(
                wide_satellite=analysis.wide_image_base64,
                segmentation=analysis.segmentation_image_base64,
                property_boundary=analysis.property_boundary_image_base64,
                condition_analysis=analysis.condition_analysis_image_base64,
            ),
            asphalt_areas=[
                AsphaltAreaResponse(
                    id=area.id,
                    area_type=area.area_type,
                    area_m2=area.area_m2,
                    is_associated=area.is_associated,
                    association_reason=area.association_reason,
                    distance_to_building_m=area.distance_to_building_m,
                    condition_score=area.condition_score,
                    crack_count=area.crack_count,
                    pothole_count=area.pothole_count,
                    crack_density=area.crack_density,
                )
                for area in areas
            ],
            business_id=analysis.business_id,
            parking_lot_id=analysis.parking_lot_id,
            analyzed_at=analysis.analyzed_at,
            created_at=analysis.created_at,
            error_message=analysis.error_message,
        ))
    
    return PropertyAnalysisListResponse(
        total=total,
        limit=limit,
        offset=offset,
        results=results
    )


@router.get("/images/{analysis_id}/{image_type}")
async def get_analysis_image(
    analysis_id: UUID,
    image_type: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific CV image for an analysis (returns base64 from database).
    
    Image types:
    - wide_satellite: Original satellite image
    - segmentation: All detected buildings and paved surfaces
    - property_boundary: Only associated asphalt highlighted
    - condition_analysis: Damage annotations
    """
    import base64
    from fastapi.responses import Response
    
    # Verify ownership
    analysis = db.query(PropertyAnalysis).filter(
        PropertyAnalysis.id == analysis_id,
        PropertyAnalysis.user_id == current_user.id
    ).first()
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Validate image type and get base64
    base64_map = {
        "wide_satellite": analysis.wide_image_base64,
        "segmentation": analysis.segmentation_image_base64,
        "property_boundary": analysis.property_boundary_image_base64,
        "condition_analysis": analysis.condition_analysis_image_base64,
    }
    
    if image_type not in base64_map:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid image type. Valid types: {list(base64_map.keys())}"
        )
    
    b64_data = base64_map.get(image_type)
    if not b64_data:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Decode base64 and return as image
    image_bytes = base64.b64decode(b64_data)
    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={"Content-Disposition": f'inline; filename="{analysis_id}_{image_type}.jpg"'}
    )

