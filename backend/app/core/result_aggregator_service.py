"""
ResultAggregatorService - Combine tile results into property-level metrics.

This service aggregates analysis results from multiple tiles into
a single comprehensive property analysis.

Design Principles:
- Sum up totals (area, damage counts)
- Calculate weighted averages (condition scores)
- Identify hotspots (worst tiles)
- Generate summary statistics
"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from app.core.tile_analyzer_service import TileAnalysisResult, TileGridAnalysisResult
from app.core.tile_service import TileGrid

logger = logging.getLogger(__name__)


@dataclass
class PropertyAsphaltSummary:
    """Summary of asphalt areas across the property."""
    # Total asphalt from CV (includes public roads)
    total_area_m2: float = 0
    total_area_sqft: float = 0
    
    # Private asphalt (after filtering public roads) - THIS IS WHAT MATTERS
    private_asphalt_area_m2: float = 0
    private_asphalt_area_sqft: float = 0
    
    # Public roads that were filtered out
    public_road_area_m2: float = 0
    public_road_area_sqft: float = 0
    
    # Legacy fields (now using private_asphalt instead)
    parking_area_m2: float = 0
    parking_area_sqft: float = 0
    road_area_m2: float = 0  # Private roads
    road_area_sqft: float = 0
    
    tiles_with_asphalt: int = 0
    coverage_percentage: float = 0  # % of property that is asphalt


@dataclass
class PropertyConditionSummary:
    """Summary of condition across the property."""
    overall_score: float = 100  # Weighted average
    worst_tile_score: float = 100
    best_tile_score: float = 100
    total_crack_count: int = 0
    total_pothole_count: int = 0
    total_detection_count: int = 0
    tiles_with_damage: int = 0
    damage_density: float = 0  # Detections per 1000 sqft


@dataclass
class PropertyHotspot:
    """A tile with significant damage."""
    tile_index: int
    center_lat: float
    center_lng: float
    condition_score: float
    crack_count: int
    pothole_count: int
    asphalt_area_m2: float
    severity: str  # "critical", "high", "moderate"


@dataclass
class AggregatedPropertyAnalysis:
    """Complete aggregated analysis for a property."""
    # Property identification
    property_id: Optional[str] = None
    business_name: Optional[str] = None
    address: Optional[str] = None
    
    # Coverage info
    tile_grid: Optional[TileGrid] = None
    total_tiles: int = 0
    analyzed_tiles: int = 0
    
    # Aggregated metrics
    asphalt: Optional[PropertyAsphaltSummary] = None
    condition: Optional[PropertyConditionSummary] = None
    
    # Hotspots (worst areas)
    hotspots: List[PropertyHotspot] = field(default_factory=list)
    
    # Per-tile data (for detailed view)
    tile_results: List[TileAnalysisResult] = field(default_factory=list)
    
    # Status
    status: str = "pending"  # pending, completed, partial, failed
    analyzed_at: Optional[datetime] = None
    total_duration_seconds: float = 0
    
    @property
    def is_high_value_lead(self) -> bool:
        """Determine if this property is a high-value lead."""
        if not self.asphalt or not self.condition:
            return False
        
        # High value = large PRIVATE asphalt area + poor condition
        large_area = self.asphalt.private_asphalt_area_sqft >= 10000  # 10k sqft
        poor_condition = self.condition.overall_score <= 60
        has_damage = self.condition.total_detection_count >= 10
        
        return large_area and (poor_condition or has_damage)
    
    @property
    def lead_quality(self) -> str:
        """Categorize lead quality based on PRIVATE asphalt area and condition."""
        if not self.asphalt or not self.condition:
            return "unknown"
        
        # Use private asphalt area (not total which includes public roads)
        area = self.asphalt.private_asphalt_area_sqft
        score = self.condition.overall_score
        
        if area >= 50000 and score <= 40:
            return "premium"
        elif area >= 25000 and score <= 50:
            return "high"
        elif area >= 10000 and score <= 60:
            return "standard"
        else:
            return "low"


class ResultAggregatorService:
    """
    Aggregate tile results into property-level analysis.
    
    Takes results from multiple tiles and combines them into
    a single comprehensive property analysis with:
    - Total metrics (area, damage counts)
    - Weighted averages (condition scores)
    - Hotspot identification
    - Lead quality scoring
    """
    
    # Conversion constants
    M2_TO_SQFT = 10.7639
    
    # Hotspot thresholds
    CRITICAL_SCORE = 30
    HIGH_SCORE = 50
    MODERATE_SCORE = 70
    
    def aggregate(
        self,
        tile_grid: TileGrid,
        analysis_result: TileGridAnalysisResult,
        property_id: Optional[str] = None,
        business_name: Optional[str] = None,
        address: Optional[str] = None
    ) -> AggregatedPropertyAnalysis:
        """
        Aggregate tile results into property-level analysis.
        
        Args:
            tile_grid: The tile grid used for analysis
            analysis_result: Results from tile analysis
            property_id: Optional property identifier
            business_name: Optional business name
            address: Optional address
            
        Returns:
            AggregatedPropertyAnalysis with combined metrics
        """
        logger.info(f"📊 Aggregating results from {len(analysis_result.tile_results)} tiles...")
        
        # Get valid results
        valid_results = [r for r in analysis_result.tile_results if r.is_valid]
        
        # Aggregate asphalt metrics
        asphalt = self._aggregate_asphalt(valid_results, tile_grid)
        
        # Aggregate condition metrics
        condition = self._aggregate_condition(valid_results, asphalt.total_area_sqft)
        
        # Identify hotspots
        hotspots = self._identify_hotspots(valid_results)
        
        logger.info(f"   ✅ Aggregation complete:")
        logger.info(f"      Total asphalt: {asphalt.total_area_sqft:,.0f} sqft")
        logger.info(f"      Condition score: {condition.overall_score:.0f}/100")
        logger.info(f"      Total damage: {condition.total_crack_count} cracks, {condition.total_pothole_count} potholes")
        logger.info(f"      Hotspots: {len(hotspots)}")
        
        return AggregatedPropertyAnalysis(
            property_id=property_id,
            business_name=business_name,
            address=address,
            tile_grid=tile_grid,
            total_tiles=analysis_result.total_tiles,
            analyzed_tiles=analysis_result.analyzed_tiles,
            asphalt=asphalt,
            condition=condition,
            hotspots=hotspots,
            tile_results=analysis_result.tile_results,
            status="completed" if analysis_result.analyzed_tiles > 0 else "failed",
            analyzed_at=datetime.utcnow(),
            total_duration_seconds=analysis_result.total_duration_seconds
        )
    
    def _aggregate_asphalt(
        self,
        results: List[TileAnalysisResult],
        tile_grid: TileGrid
    ) -> PropertyAsphaltSummary:
        """Aggregate asphalt area metrics, prioritizing PRIVATE asphalt."""
        total_m2 = 0
        private_asphalt_m2 = 0
        public_road_m2 = 0
        parking_m2 = 0
        road_m2 = 0
        tiles_with = 0
        
        for result in results:
            if result.segmentation:
                # Total asphalt from CV (before filtering)
                total_m2 += result.segmentation.total_asphalt_area_m2 or 0
                
                # Private asphalt (after filtering public roads)
                private_asphalt_m2 += result.segmentation.private_asphalt_area_m2 or 0
                
                # Public roads that were filtered out
                public_road_m2 += result.segmentation.public_road_area_m2 or 0
                
                # Legacy fields
                parking_m2 += result.segmentation.parking_area_m2 or 0
                road_m2 += result.segmentation.road_area_m2 or 0
                
                # Count tiles with private asphalt
                if result.segmentation.private_asphalt_area_m2 > 0:
                    tiles_with += 1
        
        # Calculate coverage percentage based on private asphalt
        coverage_pct = 0
        if tile_grid.property_area_m2 > 0:
            coverage_pct = (private_asphalt_m2 / tile_grid.property_area_m2) * 100
        
        logger.info(f"   📊 Asphalt breakdown:")
        logger.info(f"      Total (CV): {total_m2:,.0f}m²")
        logger.info(f"      Private: {private_asphalt_m2:,.0f}m²")
        logger.info(f"      Public roads (filtered): {public_road_m2:,.0f}m²")
        
        return PropertyAsphaltSummary(
            total_area_m2=total_m2,
            total_area_sqft=total_m2 * self.M2_TO_SQFT,
            private_asphalt_area_m2=private_asphalt_m2,
            private_asphalt_area_sqft=private_asphalt_m2 * self.M2_TO_SQFT,
            public_road_area_m2=public_road_m2,
            public_road_area_sqft=public_road_m2 * self.M2_TO_SQFT,
            parking_area_m2=parking_m2,
            parking_area_sqft=parking_m2 * self.M2_TO_SQFT,
            road_area_m2=road_m2,
            road_area_sqft=road_m2 * self.M2_TO_SQFT,
            tiles_with_asphalt=tiles_with,
            coverage_percentage=coverage_pct
        )
    
    def _aggregate_condition(
        self,
        results: List[TileAnalysisResult],
        total_area_sqft: float
    ) -> PropertyConditionSummary:
        """Aggregate condition metrics based on PRIVATE asphalt areas."""
        scores = []
        areas = []
        total_cracks = 0
        total_potholes = 0
        total_detections = 0
        tiles_with_damage = 0
        
        for result in results:
            if result.condition and result.has_asphalt:
                score = result.condition.condition_score
                # Use private asphalt area for weighting (not total which includes public roads)
                area = result.segmentation.private_asphalt_area_m2 if result.segmentation else 0
                
                # Only include tiles with valid scores
                if score is not None and area is not None and area > 0:
                    scores.append(score)
                    areas.append(area)
                
                total_cracks += result.condition.crack_count or 0
                total_potholes += result.condition.pothole_count or 0
                total_detections += len(result.condition.detections) if result.condition.detections else 0
                
                if result.has_damage:
                    tiles_with_damage += 1
        
        # Calculate weighted average score
        overall_score = 100
        if scores and areas and sum(areas) > 0:
            # Filter out any None values that might have slipped through
            valid_pairs = [(s, a) for s, a in zip(scores, areas) if s is not None and a is not None]
            if valid_pairs:
                weighted_sum = sum(s * a for s, a in valid_pairs)
                total_valid_area = sum(a for _, a in valid_pairs)
                if total_valid_area > 0:
                    overall_score = weighted_sum / total_valid_area
        elif scores:
            valid_scores = [s for s in scores if s is not None]
            if valid_scores:
                overall_score = sum(valid_scores) / len(valid_scores)
        
        # Calculate damage density
        damage_density = 0
        if total_area_sqft > 0:
            damage_density = total_detections / (total_area_sqft / 1000)  # Per 1000 sqft
        
        # Filter valid scores for min/max
        valid_scores = [s for s in scores if s is not None]
        
        return PropertyConditionSummary(
            overall_score=overall_score,
            worst_tile_score=min(valid_scores) if valid_scores else 100,
            best_tile_score=max(valid_scores) if valid_scores else 100,
            total_crack_count=total_cracks,
            total_pothole_count=total_potholes,
            total_detection_count=total_detections,
            tiles_with_damage=tiles_with_damage,
            damage_density=damage_density
        )
    
    def _identify_hotspots(
        self,
        results: List[TileAnalysisResult],
        max_hotspots: int = 10
    ) -> List[PropertyHotspot]:
        """Identify tiles with significant damage."""
        hotspots = []
        
        for result in results:
            if not result.condition or not result.has_damage:
                continue
            
            score = result.condition.condition_score
            
            # Determine severity
            if score <= self.CRITICAL_SCORE:
                severity = "critical"
            elif score <= self.HIGH_SCORE:
                severity = "high"
            elif score <= self.MODERATE_SCORE:
                severity = "moderate"
            else:
                continue  # Not a hotspot
            
            tile = result.tile_image.tile
            hotspots.append(PropertyHotspot(
                tile_index=tile.index,
                center_lat=tile.center_lat,
                center_lng=tile.center_lng,
                condition_score=score,
                crack_count=result.condition.crack_count,
                pothole_count=result.condition.pothole_count,
                asphalt_area_m2=result.segmentation.private_asphalt_area_m2 if result.segmentation else 0,
                severity=severity
            ))
        
        # Sort by severity (worst first)
        severity_order = {"critical": 0, "high": 1, "moderate": 2}
        hotspots.sort(key=lambda h: (severity_order[h.severity], h.condition_score))
        
        return hotspots[:max_hotspots]


# Singleton instance
result_aggregator_service = ResultAggregatorService()

