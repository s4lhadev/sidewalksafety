import logging
import numpy as np
from typing import Dict, Any, Optional, List
from io import BytesIO
from PIL import Image
import httpx
import base64
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class ConditionEvaluationService:
    """
    Service to evaluate parking lot condition using Roboflow hosted YOLOv8 model.
    
    Uses the pavement-crack-detection model which detects:
    - Alligator crack
    - Block crack
    - Longitudinal crack
    - Oblique crack
    - Pothole
    - Repair
    - Transverse crack
    """
    
    # Detection class weights for scoring (higher = more severe)
    SEVERITY_WEIGHTS = {
        "alligator crack": 1.0,      # Most severe - indicates structural failure
        "pothole": 0.9,              # Very severe - safety hazard
        "block crack": 0.7,          # Moderate-severe
        "longitudinal crack": 0.6,   # Moderate
        "transverse crack": 0.6,     # Moderate
        "oblique crack": 0.5,        # Moderate
        "repair": 0.2,               # Low - already repaired
    }
    
    def __init__(self):
        self.api_key = settings.ROBOFLOW_API_KEY
        self.model_id = settings.ROBOFLOW_MODEL_ID
        
        if self.api_key:
            logger.info(f"✅ Roboflow configured: model={self.model_id}")
            logger.info(f"   API endpoint: https://detect.roboflow.com/{self.model_id}")
        else:
            logger.warning("⚠️  Roboflow API key not configured - CV analysis disabled")
    
    async def evaluate_condition(
        self,
        image_bytes: bytes,
        parking_lot_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate parking lot condition from satellite imagery using Roboflow.
        
        Args:
            image_bytes: Raw image bytes (JPEG/PNG)
            parking_lot_id: Optional ID for logging
        
        Returns:
            Dict with condition metrics:
            - condition_score: 0-100 (lower = worse condition = better lead)
            - crack_density: percentage of surface with damage
            - pothole_score: 0-10 severity
            - detections: list of detected damage areas
        """
        lot_id = parking_lot_id or "unknown"
        start_time = datetime.now()
        
        logger.info(f"🔍 [CV] Starting evaluation for lot {lot_id}")
        logger.info(f"   📦 Image size: {len(image_bytes) / 1024:.1f} KB")
        
        if not self.api_key:
            logger.error(f"❌ [CV] Roboflow API key not configured")
            return self._empty_result("Roboflow API key not configured")
        
        try:
            # Load and validate image
            image = Image.open(BytesIO(image_bytes))
            logger.info(f"   📐 Image dimensions: {image.width}x{image.height}")
            
            # Run Roboflow detection
            logger.info(f"   🤖 Sending to Roboflow ({self.model_id})...")
            detections = await self._run_roboflow_detection(image_bytes)
            
            if detections is None:
                logger.warning(f"   ⚠️  Roboflow returned no detections")
                return self._empty_result("Roboflow detection failed")
            
            logger.info(f"   ✅ Roboflow returned {len(detections)} detections")
            
            # Log each detection
            for i, det in enumerate(detections[:10]):  # Log first 10
                class_name = det.get("class", "unknown")
                confidence = det.get("confidence", 0)
                logger.info(f"      [{i+1}] {class_name}: {confidence:.1%}")
            
            if len(detections) > 10:
                logger.info(f"      ... and {len(detections) - 10} more")
            
            # Calculate metrics from detections
            crack_results = self._calculate_crack_metrics(detections, image.width, image.height)
            pothole_results = self._calculate_pothole_metrics(detections)
            
            # Calculate overall condition score
            condition_score = self._calculate_condition_score(
                crack_results,
                pothole_results,
                detections
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"   📊 Condition score: {condition_score}/100")
            logger.info(f"   ⏱️  Evaluation completed in {elapsed:.2f}s")
            
            return {
                "condition_score": condition_score,
                "crack_density": crack_results.get("density", 0),
                "pothole_score": pothole_results.get("score", 0),
                "line_fading_score": 0,  # Not used - Roboflow doesn't detect this
                "degradation_areas": detections,
                "detection_count": len(detections),
                "evaluation_time_seconds": elapsed,
            }
            
        except Exception as e:
            logger.error(f"❌ [CV] Evaluation failed for lot {lot_id}: {e}")
            return self._empty_result(str(e))
    
    async def _run_roboflow_detection(self, image_bytes: bytes) -> Optional[List[Dict]]:
        """Send image to Roboflow API and get detections."""
        try:
            # Encode image as base64
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            
            url = f"https://detect.roboflow.com/{self.model_id}"
            
            logger.info(f"   🌐 POST {url}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    params={"api_key": self.api_key},
                    content=image_base64,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                
                logger.info(f"   📡 Response status: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = response.text[:500]
                    logger.error(f"   ❌ Roboflow API error: {error_text}")
                    return None
                
                data = response.json()
                logger.info(f"   📋 Response keys: {list(data.keys())}")
                
                if "predictions" in data:
                    return data["predictions"]
                elif "output" in data:
                    return data["output"].get("predictions", [])
                else:
                    logger.warning(f"   ⚠️  Unexpected response format: {data}")
                    return []
                
        except httpx.TimeoutException:
            logger.error(f"   ❌ Roboflow API timeout (60s)")
            return None
        except Exception as e:
            logger.error(f"   ❌ Roboflow API error: {e}")
            return None
    
    def _calculate_crack_metrics(
        self,
        detections: List[Dict],
        image_width: int,
        image_height: int
    ) -> Dict[str, Any]:
        """Calculate crack-related metrics from detections."""
        crack_classes = [
            "alligator crack", "block crack", "longitudinal crack",
            "oblique crack", "transverse crack"
        ]
        
        cracks = [d for d in detections if d.get("class", "").lower() in crack_classes]
        
        if not cracks:
            return {"density": 0, "count": 0, "areas": []}
        
        # Calculate total crack area
        total_image_area = image_width * image_height
        total_crack_area = 0
        
        for crack in cracks:
            width = crack.get("width", 0)
            height = crack.get("height", 0)
            total_crack_area += width * height
        
        density = (total_crack_area / total_image_area) * 100 if total_image_area > 0 else 0
        
        logger.info(f"   🔨 Cracks: {len(cracks)} detected, {density:.2f}% coverage")
        
        return {
            "density": min(density, 100),
            "count": len(cracks),
            "areas": cracks,
        }
    
    def _calculate_pothole_metrics(self, detections: List[Dict]) -> Dict[str, Any]:
        """Calculate pothole-related metrics from detections."""
        potholes = [d for d in detections if d.get("class", "").lower() == "pothole"]
        
        pothole_count = len(potholes)
        
        if pothole_count == 0:
            score = 0
        else:
            avg_confidence = sum(p.get("confidence", 0.5) for p in potholes) / pothole_count
            
            if pothole_count <= 2:
                score = 2 + (avg_confidence * 2)
            elif pothole_count <= 5:
                score = 4 + (avg_confidence * 2)
            elif pothole_count <= 10:
                score = 6 + (avg_confidence * 2)
            else:
                score = 8 + (avg_confidence * 2)
            
            score = min(score, 10)
        
        logger.info(f"   🕳️  Potholes: {pothole_count} detected, score {score:.1f}/10")
        
        return {
            "score": round(score, 1),
            "count": pothole_count,
            "areas": potholes,
        }
    
    def _calculate_condition_score(
        self,
        crack_results: Dict[str, Any],
        pothole_results: Dict[str, Any],
        detections: List[Dict]
    ) -> float:
        """
        Calculate overall condition score (0-100).
        Lower score = worse condition = better lead for repair companies.
        """
        # Start with perfect score
        score = 100
        
        # Calculate severity-weighted damage score
        severity_score = 0
        for det in detections:
            class_name = det.get("class", "").lower()
            confidence = det.get("confidence", 0.5)
            weight = self.SEVERITY_WEIGHTS.get(class_name, 0.5)
            severity_score += weight * confidence
        
        # Normalize severity score (cap at 50 points deduction)
        severity_deduction = min(severity_score * 5, 50)
        score -= severity_deduction
        
        # Deduct for crack density (max 25 points)
        crack_density = crack_results.get("density", 0)
        crack_deduction = min(crack_density * 2.5, 25)
        score -= crack_deduction
        
        # Deduct for potholes (max 25 points)
        pothole_score = pothole_results.get("score", 0)
        pothole_deduction = pothole_score * 2.5
        score -= pothole_deduction
        
        final_score = max(0, min(100, round(score, 2)))
        
        logger.info(f"   📈 Score breakdown:")
        logger.info(f"      Base: 100")
        logger.info(f"      Severity deduction: -{severity_deduction:.1f}")
        logger.info(f"      Crack density deduction: -{crack_deduction:.1f}")
        logger.info(f"      Pothole deduction: -{pothole_deduction:.1f}")
        logger.info(f"      Final: {final_score}")
        
        return final_score
    
    def _empty_result(self, error: str) -> Dict[str, Any]:
        """Return empty result with error."""
        return {
            "condition_score": None,
            "crack_density": None,
            "pothole_score": None,
            "line_fading_score": None,
            "degradation_areas": [],
            "detection_count": 0,
            "error": error,
        }


# Singleton instance
condition_evaluation_service = ConditionEvaluationService()
