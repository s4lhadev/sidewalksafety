import logging
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.usage_log import UsageLog

logger = logging.getLogger(__name__)


# Estimated costs per API call (in USD)
COST_ESTIMATES = {
    "inrix": 0.001,           # ~$1 per 1000 calls
    "here": 0.0005,           # ~$0.50 per 1000 calls
    "osm": 0.0,               # Free
    "google_maps": 0.002,     # ~$2 per 1000 calls (Static Maps)
    "google_places": 0.017,   # ~$17 per 1000 calls (Places Details)
    "roboflow": 0.001,        # ~$1 per 1000 inferences (varies by plan)
}


class UsageTrackingService:
    """Service to track and report API/compute usage per user."""
    
    def log_api_call(
        self,
        db: Session,
        user_id: UUID,
        resource: str,
        job_id: Optional[UUID] = None,
        count: int = 1,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UsageLog:
        """Log an API call."""
        estimated_cost = COST_ESTIMATES.get(resource, 0.001) * count
        
        log = UsageLog(
            user_id=user_id,
            action="api_call",
            resource=resource,
            count=count,
            estimated_cost=estimated_cost,
            job_id=job_id,
            details=metadata,
        )
        
        db.add(log)
        db.commit()
        
        logger.info(f"📊 [Usage] API call: {resource} x{count} (${estimated_cost:.4f}) user={user_id}")
        
        return log
    
    def log_cv_evaluation(
        self,
        db: Session,
        user_id: UUID,
        parking_lot_id: UUID,
        job_id: Optional[UUID] = None,
        bytes_processed: int = 0,
        evaluation_time_seconds: float = 0,
        detections: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UsageLog:
        """Log a CV evaluation."""
        # Roboflow cost estimate
        estimated_cost = COST_ESTIMATES.get("roboflow", 0.001)
        
        log_metadata = {
            "evaluation_time_seconds": evaluation_time_seconds,
            "detections": detections,
            **(metadata or {}),
        }
        
        log = UsageLog(
            user_id=user_id,
            action="cv_evaluation",
            resource="roboflow",
            count=1,
            bytes_processed=bytes_processed,
            estimated_cost=estimated_cost,
            job_id=job_id,
            parking_lot_id=parking_lot_id,
            details=log_metadata,
        )
        
        db.add(log)
        db.commit()
        
        logger.info(
            f"📊 [Usage] CV evaluation: {bytes_processed/1024:.1f}KB, "
            f"{detections} detections, {evaluation_time_seconds:.2f}s "
            f"(${estimated_cost:.4f}) user={user_id}"
        )
        
        return log
    
    def log_discovery_job(
        self,
        db: Session,
        user_id: UUID,
        job_id: UUID,
        parking_lots_found: int = 0,
        parking_lots_evaluated: int = 0,
        businesses_loaded: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UsageLog:
        """Log a complete discovery job."""
        # Estimate total cost for the job
        estimated_cost = (
            COST_ESTIMATES.get("inrix", 0) +  # 1 INRIX call
            COST_ESTIMATES.get("here", 0) +   # 1 HERE call
            COST_ESTIMATES.get("osm", 0) +    # 1 OSM call
            (COST_ESTIMATES.get("google_maps", 0) * parking_lots_evaluated) +  # Image per lot
            (COST_ESTIMATES.get("roboflow", 0) * parking_lots_evaluated) +     # CV per lot
            (COST_ESTIMATES.get("google_places", 0) * businesses_loaded)       # Places per business
        )
        
        log_metadata = {
            "parking_lots_found": parking_lots_found,
            "parking_lots_evaluated": parking_lots_evaluated,
            "businesses_loaded": businesses_loaded,
            **(metadata or {}),
        }
        
        log = UsageLog(
            user_id=user_id,
            action="discovery",
            resource="discovery_pipeline",
            count=1,
            estimated_cost=estimated_cost,
            job_id=job_id,
            details=log_metadata,
        )
        
        db.add(log)
        db.commit()
        
        logger.info(
            f"📊 [Usage] Discovery job completed: "
            f"{parking_lots_found} lots, {parking_lots_evaluated} evaluated, "
            f"{businesses_loaded} businesses (${estimated_cost:.4f}) user={user_id}"
        )
        
        return log
    
    def get_user_usage_summary(
        self,
        db: Session,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get usage summary for a user over the past N days."""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Query usage logs
        logs = db.query(UsageLog).filter(
            UsageLog.user_id == user_id,
            UsageLog.created_at >= since
        ).all()
        
        # Aggregate by action
        by_action = {}
        for log in logs:
            if log.action not in by_action:
                by_action[log.action] = {
                    "count": 0,
                    "total_cost": 0,
                    "bytes_processed": 0,
                }
            by_action[log.action]["count"] += log.count or 1
            by_action[log.action]["total_cost"] += float(log.estimated_cost or 0)
            by_action[log.action]["bytes_processed"] += log.bytes_processed or 0
        
        # Aggregate by resource
        by_resource = {}
        for log in logs:
            if log.resource and log.resource not in by_resource:
                by_resource[log.resource] = {
                    "count": 0,
                    "total_cost": 0,
                }
            if log.resource:
                by_resource[log.resource]["count"] += log.count or 1
                by_resource[log.resource]["total_cost"] += float(log.estimated_cost or 0)
        
        total_cost = sum(float(log.estimated_cost or 0) for log in logs)
        total_bytes = sum(log.bytes_processed or 0 for log in logs)
        
        return {
            "period_days": days,
            "total_requests": len(logs),
            "total_cost_usd": round(total_cost, 4),
            "total_bytes_processed": total_bytes,
            "by_action": by_action,
            "by_resource": by_resource,
        }
    
    def get_daily_usage(
        self,
        db: Session,
        user_id: UUID,
        days: int = 7
    ) -> list:
        """Get daily usage breakdown for a user."""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Query with date grouping
        results = db.query(
            func.date(UsageLog.created_at).label("date"),
            func.count(UsageLog.id).label("request_count"),
            func.sum(UsageLog.estimated_cost).label("total_cost"),
            func.sum(UsageLog.bytes_processed).label("bytes_processed"),
        ).filter(
            UsageLog.user_id == user_id,
            UsageLog.created_at >= since
        ).group_by(
            func.date(UsageLog.created_at)
        ).order_by(
            func.date(UsageLog.created_at)
        ).all()
        
        return [
            {
                "date": str(r.date),
                "request_count": r.request_count,
                "total_cost_usd": float(r.total_cost or 0),
                "bytes_processed": r.bytes_processed or 0,
            }
            for r in results
        ]


# Singleton instance
usage_tracking_service = UsageTrackingService()

