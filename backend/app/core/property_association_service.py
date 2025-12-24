"""
PropertyAssociationService - Associate paved surfaces with business

Filters detected paved surfaces to keep only those that belong to the business.
Uses spatial analysis to determine connectivity to the business building.
"""
import logging
import math
from typing import List, Tuple, Optional
from dataclasses import dataclass
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

from app.core.asphalt_segmentation_service import DetectedPolygon

logger = logging.getLogger(__name__)


@dataclass
class AssociatedAsphaltArea:
    """A paved surface with its association status."""
    polygon: Polygon
    pixel_points: List[dict]
    class_name: str
    confidence: float
    area_m2: float
    is_associated: bool
    association_reason: str
    distance_to_building_m: Optional[float] = None
    area_type: str = "unknown"  # 'parking', 'driveway', 'loading_dock', 'unknown'


class PropertyAssociationService:
    """
    Associates detected paved surfaces with the business building.
    
    Logic:
    1. Find the building closest to the business location
    2. Keep paved surfaces that touch or are near this building
    3. Recursively keep surfaces connected to already-kept surfaces
    4. Exclude surfaces that are clearly separated (public roads, neighbors)
    """
    
    # Configuration - Relaxed thresholds for better association
    MAX_INITIAL_DISTANCE_M = 50.0  # Max distance for initial association (was 10m, too strict)
    MAX_CONNECTION_DISTANCE_M = 25.0  # Max gap between connected surfaces (was 5m)
    MIN_AREA_M2 = 10.0  # Minimum area to consider (filter noise) - reduced
    ROAD_WIDTH_THRESHOLD_M = 12.0  # Typical road width for filtering
    
    def associate_with_business(
        self,
        buildings: List[DetectedPolygon],
        paved_surfaces: List[DetectedPolygon],
        business_location: Tuple[float, float]  # (lat, lng)
    ) -> Tuple[Optional[DetectedPolygon], List[AssociatedAsphaltArea]]:
        """
        Find which paved surfaces belong to the business.
        
        Args:
            buildings: Detected building polygons
            paved_surfaces: Detected paved surface polygons
            business_location: (lat, lng) of the business
        
        Returns:
            Tuple of (business_building, list of AssociatedAsphaltArea)
        """
        logger.info(f"🔗 Associating {len(paved_surfaces)} surfaces with business at {business_location}")
        
        # Filter small surfaces (likely noise)
        valid_surfaces = [
            p for p in paved_surfaces 
            if p.area_m2 and p.area_m2 >= self.MIN_AREA_M2
        ]
        logger.info(f"   Filtered to {len(valid_surfaces)} surfaces >= {self.MIN_AREA_M2}m²")
        
        # Step 1: Find business building
        business_building = self._find_closest_building(buildings, business_location)
        
        if business_building:
            logger.info(f"   🏢 Found business building: {business_building.area_m2:.0f}m²")
        else:
            logger.warning("   ⚠️ No building found near business location")
            # Fallback: associate surfaces near the location
            return None, self._fallback_association(valid_surfaces, business_location)
        
        # Step 2: Initial association - surfaces near the building
        associated: List[AssociatedAsphaltArea] = []
        pending = list(valid_surfaces)
        
        for surface in pending[:]:
            distance_m = self._distance_between_m(surface.polygon, business_building.polygon)
            
            if distance_m <= self.MAX_INITIAL_DISTANCE_M:
                area = AssociatedAsphaltArea(
                    polygon=surface.polygon,
                    pixel_points=surface.pixel_points,
                    class_name=surface.class_name,
                    confidence=surface.confidence,
                    area_m2=surface.area_m2 or 0,
                    is_associated=True,
                    association_reason="near_building",
                    distance_to_building_m=distance_m,
                    area_type=self._classify_area_type(surface, business_building)
                )
                associated.append(area)
                pending.remove(surface)
                logger.debug(f"   ✅ Associated (near building): {area.area_m2:.0f}m², dist={distance_m:.1f}m")
        
        logger.info(f"   Initial association: {len(associated)} surfaces")
        
        # Step 3: Recursive association - surfaces connected to associated surfaces
        iterations = 0
        max_iterations = 20  # Prevent infinite loops
        
        while iterations < max_iterations:
            iterations += 1
            added_this_round = 0
            
            for surface in pending[:]:
                for assoc in associated:
                    distance_m = self._distance_between_m(surface.polygon, assoc.polygon)
                    
                    if distance_m <= self.MAX_CONNECTION_DISTANCE_M:
                        # Calculate distance to building for the new surface
                        dist_to_building = self._distance_between_m(
                            surface.polygon, business_building.polygon
                        )
                        
                        area = AssociatedAsphaltArea(
                            polygon=surface.polygon,
                            pixel_points=surface.pixel_points,
                            class_name=surface.class_name,
                            confidence=surface.confidence,
                            area_m2=surface.area_m2 or 0,
                            is_associated=True,
                            association_reason="connected_to_associated",
                            distance_to_building_m=dist_to_building,
                            area_type=self._classify_area_type(surface, business_building)
                        )
                        associated.append(area)
                        pending.remove(surface)
                        added_this_round += 1
                        logger.debug(f"   ✅ Associated (connected): {area.area_m2:.0f}m²")
                        break
            
            if added_this_round == 0:
                break
        
        logger.info(f"   After {iterations} iterations: {len(associated)} associated surfaces")
        
        # Step 4: Mark remaining as not associated (public roads, neighbors)
        for surface in pending:
            dist_to_building = self._distance_between_m(surface.polygon, business_building.polygon)
            
            area = AssociatedAsphaltArea(
                polygon=surface.polygon,
                pixel_points=surface.pixel_points,
                class_name=surface.class_name,
                confidence=surface.confidence,
                area_m2=surface.area_m2 or 0,
                is_associated=False,
                association_reason="not_connected",
                distance_to_building_m=dist_to_building,
                area_type="public_road" if self._looks_like_road(surface) else "unknown"
            )
            associated.append(area)
            logger.debug(f"   ❌ Not associated: {area.area_m2:.0f}m², dist={dist_to_building:.1f}m")
        
        # Log summary
        associated_count = sum(1 for a in associated if a.is_associated)
        excluded_count = len(associated) - associated_count
        total_area = sum(a.area_m2 for a in associated if a.is_associated)
        
        logger.info(f"   ✅ Final: {associated_count} associated ({total_area:.0f}m²), {excluded_count} excluded")
        
        return business_building, associated
    
    def _find_closest_building(
        self,
        buildings: List[DetectedPolygon],
        location: Tuple[float, float]
    ) -> Optional[DetectedPolygon]:
        """Find the building closest to the business location."""
        if not buildings:
            return None
        
        lat, lng = location
        point = Point(lng, lat)  # Shapely uses (lng, lat)
        
        closest = None
        min_distance = float('inf')
        
        for building in buildings:
            distance = building.polygon.distance(point)
            if distance < min_distance:
                min_distance = distance
                closest = building
        
        return closest
    
    def _distance_between_m(self, poly1: Polygon, poly2: Polygon) -> float:
        """Calculate distance between two polygons in meters."""
        # Get distance in degrees
        distance_deg = poly1.distance(poly2)
        
        if distance_deg <= 0:
            return 0.0  # Polygons touch or overlap
        
        # Convert to meters (approximate at equator)
        # More accurate would use the centroid latitude
        center1 = poly1.centroid
        center2 = poly2.centroid
        avg_lat = (center1.y + center2.y) / 2
        
        # 1 degree ≈ 111km, adjusted for latitude
        m_per_deg = 111000 * math.cos(math.radians(avg_lat))
        
        return distance_deg * m_per_deg
    
    def _classify_area_type(
        self,
        surface: DetectedPolygon,
        building: DetectedPolygon
    ) -> str:
        """
        Classify the type of paved area based on geometry and position.
        
        Returns: 'parking', 'driveway', 'loading_dock', or 'unknown'
        """
        area = surface.area_m2 or 0
        
        # Large areas are likely parking lots
        if area > 500:
            return "parking"
        
        # Check aspect ratio for driveway detection
        bounds = surface.polygon.bounds
        width = bounds[2] - bounds[0]  # max_lng - min_lng
        height = bounds[3] - bounds[1]  # max_lat - min_lat
        
        # Adjust for latitude
        center_lat = (bounds[1] + bounds[3]) / 2
        width_adjusted = width * math.cos(math.radians(center_lat))
        
        if width_adjusted > 0 and height > 0:
            aspect_ratio = max(width_adjusted, height) / min(width_adjusted, height)
            
            # Long narrow areas are likely driveways
            if aspect_ratio > 3 and area < 200:
                return "driveway"
        
        # Medium areas near the back might be loading docks
        # (This is a simplified heuristic)
        if 100 < area < 500:
            return "loading_dock"
        
        return "unknown"
    
    def _looks_like_road(self, surface: DetectedPolygon) -> bool:
        """Check if a surface looks like a public road (long and narrow)."""
        bounds = surface.polygon.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        
        center_lat = (bounds[1] + bounds[3]) / 2
        width_m = width * 111000 * math.cos(math.radians(center_lat))
        height_m = height * 111000
        
        # Long and narrow with typical road width
        short_side = min(width_m, height_m)
        long_side = max(width_m, height_m)
        
        if long_side > 50 and short_side < 15:
            return True
        
        return False
    
    def _fallback_association(
        self,
        surfaces: List[DetectedPolygon],
        location: Tuple[float, float]
    ) -> List[AssociatedAsphaltArea]:
        """
        Fallback when no building is found.
        Associates surfaces within 50m of the business location.
        """
        logger.info("   Using fallback association (no building found)")
        
        lat, lng = location
        point = Point(lng, lat)
        
        result = []
        max_distance_deg = 50 / 111000  # 50 meters in degrees
        
        for surface in surfaces:
            distance = surface.polygon.distance(point)
            distance_m = distance * 111000
            
            is_associated = distance <= max_distance_deg
            
            result.append(AssociatedAsphaltArea(
                polygon=surface.polygon,
                pixel_points=surface.pixel_points,
                class_name=surface.class_name,
                confidence=surface.confidence,
                area_m2=surface.area_m2 or 0,
                is_associated=is_associated,
                association_reason="near_location" if is_associated else "too_far",
                distance_to_building_m=distance_m,
                area_type="unknown"
            ))
        
        return result
    
    def associate_with_property_boundary(
        self,
        buildings: List[DetectedPolygon],
        paved_surfaces: List[DetectedPolygon],
        property_boundary: Polygon,
        business_location: Tuple[float, float]
    ) -> Tuple[Optional[DetectedPolygon], List[AssociatedAsphaltArea]]:
        """
        Associate paved surfaces using the legal property boundary from Regrid.
        
        This is more accurate than proximity-based association because:
        - We know the exact property boundary
        - We only include surfaces that are within or touching the property
        - No guessing about which surfaces belong to the business
        
        Args:
            buildings: Detected building polygons
            paved_surfaces: Detected paved surface polygons
            property_boundary: Legal property boundary polygon from Regrid
            business_location: (lat, lng) of the business
        
        Returns:
            Tuple of (business_building, list of AssociatedAsphaltArea)
        """
        logger.info(f"🔗 Associating surfaces with property boundary (Regrid)")
        logger.info(f"   Property boundary area: ~{self._polygon_area_m2(property_boundary):.0f} m²")
        
        # Filter small surfaces (likely noise)
        valid_surfaces = [
            p for p in paved_surfaces 
            if p.area_m2 and p.area_m2 >= self.MIN_AREA_M2
        ]
        logger.info(f"   Filtered to {len(valid_surfaces)} surfaces >= {self.MIN_AREA_M2}m²")
        
        # Find business building (for classification purposes)
        business_building = self._find_closest_building(buildings, business_location)
        if business_building:
            logger.info(f"   🏢 Found business building: {business_building.area_m2:.0f}m²")
        
        # Buffer the property boundary slightly (2m) to catch surfaces on the edge
        boundary_buffered = property_boundary.buffer(0.00002)  # ~2m in degrees
        
        associated: List[AssociatedAsphaltArea] = []
        
        for surface in valid_surfaces:
            # Check if surface intersects with property boundary
            is_within = property_boundary.contains(surface.polygon.centroid)
            is_intersecting = boundary_buffered.intersects(surface.polygon)
            
            # Calculate intersection percentage
            if is_intersecting:
                try:
                    intersection = surface.polygon.intersection(boundary_buffered)
                    intersection_pct = (intersection.area / surface.polygon.area * 100) if surface.polygon.area > 0 else 0
                except:
                    intersection_pct = 0
            else:
                intersection_pct = 0
            
            # Associate if mostly within property boundary (>30% overlap)
            is_associated = is_within or intersection_pct > 30
            
            # Calculate distance to building if we have one
            dist_to_building = None
            area_type = "unknown"
            if business_building:
                dist_to_building = self._distance_between_m(surface.polygon, business_building.polygon)
                area_type = self._classify_area_type(surface, business_building)
            
            # Determine reason
            if is_associated:
                if is_within:
                    reason = "within_property_boundary"
                else:
                    reason = f"intersects_boundary_{intersection_pct:.0f}pct"
            else:
                if intersection_pct > 0:
                    reason = f"minimal_intersection_{intersection_pct:.0f}pct"
                else:
                    reason = "outside_property_boundary"
            
            area = AssociatedAsphaltArea(
                polygon=surface.polygon,
                pixel_points=surface.pixel_points,
                class_name=surface.class_name,
                confidence=surface.confidence,
                area_m2=surface.area_m2 or 0,
                is_associated=is_associated,
                association_reason=reason,
                distance_to_building_m=dist_to_building,
                area_type=area_type
            )
            associated.append(area)
            
            if is_associated:
                logger.debug(f"   ✅ Associated: {area.area_m2:.0f}m² - {reason}")
            else:
                logger.debug(f"   ❌ Excluded: {area.area_m2:.0f}m² - {reason}")
        
        # Log summary
        associated_count = sum(1 for a in associated if a.is_associated)
        excluded_count = len(associated) - associated_count
        total_area = sum(a.area_m2 for a in associated if a.is_associated)
        
        logger.info(f"   ✅ Final: {associated_count} associated ({total_area:.0f}m²), {excluded_count} excluded")
        
        return business_building, associated
    
    def _polygon_area_m2(self, polygon: Polygon) -> float:
        """Calculate area of polygon in square meters."""
        from pyproj import Geod
        
        try:
            geod = Geod(ellps="WGS84")
            coords = list(polygon.exterior.coords)
            area, _ = geod.polygon_area_perimeter(
                [c[0] for c in coords],
                [c[1] for c in coords]
            )
            return abs(area)
        except:
            # Fallback: approximate conversion
            return polygon.area * (111000 ** 2)


# Singleton instance
property_association_service = PropertyAssociationService()

