import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from geoalchemy2.shape import to_shape
from rapidfuzz import fuzz
import uuid

from app.models.parking_lot import ParkingLot
from app.models.business import Business
from app.models.association import ParkingLotBusinessAssociation
from app.core.business_data_service import RELEVANT_CATEGORIES

logger = logging.getLogger(__name__)


class AssociationService:
    """Service to associate parking lots with businesses using spatial matching."""
    
    # Distance thresholds in meters
    MAX_DISTANCE_METERS = 80
    CLOSE_DISTANCE_METERS = 20
    MEDIUM_DISTANCE_METERS = 40
    
    # Score weights
    DISTANCE_WEIGHT = 40
    CATEGORY_WEIGHT = 30
    NAME_SIMILARITY_WEIGHT = 20
    ADJACENCY_WEIGHT = 10
    
    def associate_parking_lots_with_businesses(
        self,
        parking_lot_ids: List[uuid.UUID],
        db: Session
    ) -> Dict[str, int]:
        """
        Associate parking lots with nearby businesses.
        Returns stats about associations made.
        """
        stats = {
            "total_parking_lots": len(parking_lot_ids),
            "associations_made": 0,
            "lots_with_business": 0,
            "no_business_found": 0,
            "total_match_score": 0,
        }
        
        logger.info(f"   🔗 Processing {len(parking_lot_ids)} parking lots...")
        
        for idx, lot_id in enumerate(parking_lot_ids):
            try:
                associations = self._find_business_matches(lot_id, db)
                
                if associations:
                    # Save all associations
                    for assoc in associations:
                        db.add(assoc)
                        stats["total_match_score"] += float(assoc.match_score)
                    
                    stats["associations_made"] += len(associations)
                    stats["lots_with_business"] += 1
                    
                    # Log first association (primary business)
                    primary = associations[0]
                    biz = db.query(Business).filter(Business.id == primary.business_id).first()
                    if biz and idx < 5:  # Log first 5
                        logger.info(f"      [{idx+1}] Lot matched to: {biz.name} (score: {primary.match_score:.1f}, dist: {primary.distance_meters:.0f}m)")
                else:
                    stats["no_business_found"] += 1
                    
            except Exception as e:
                logger.error(f"      ❌ Failed to associate lot {lot_id}: {e}")
                stats["no_business_found"] += 1
        
        db.commit()
        
        # Calculate average match score
        if stats["associations_made"] > 0:
            stats["avg_match_score"] = stats["total_match_score"] / stats["associations_made"]
        else:
            stats["avg_match_score"] = 0
        
        logger.info(f"   📊 Association summary:")
        logger.info(f"      Lots with business: {stats['lots_with_business']}/{len(parking_lot_ids)}")
        logger.info(f"      Total associations: {stats['associations_made']}")
        logger.info(f"      No match found: {stats['no_business_found']}")
        
        return stats
    
    def _find_business_matches(
        self,
        parking_lot_id: uuid.UUID,
        db: Session
    ) -> List[ParkingLotBusinessAssociation]:
        """Find and score business matches for a parking lot."""
        
        # Get parking lot
        parking_lot = db.query(ParkingLot).filter(ParkingLot.id == parking_lot_id).first()
        if not parking_lot:
            return []
        
        # Find nearby businesses using PostGIS
        nearby_businesses = self._find_nearby_businesses(parking_lot, db)
        
        if not nearby_businesses:
            return []
        
        # Score each business
        scored_matches: List[Tuple[Business, float, float, Dict[str, Any]]] = []
        
        for business, distance_meters in nearby_businesses:
            score, details = self._calculate_match_score(
                parking_lot, business, distance_meters
            )
            
            if score > 0:
                scored_matches.append((business, score, distance_meters, details))
        
        if not scored_matches:
            return []
        
        # Sort by score (highest first)
        scored_matches.sort(key=lambda x: x[1], reverse=True)
        
        # Create associations
        associations = []
        for i, (business, score, distance, details) in enumerate(scored_matches):
            assoc = ParkingLotBusinessAssociation(
                parking_lot_id=parking_lot_id,
                business_id=business.id,
                match_score=score,
                distance_meters=distance,
                association_method=details.get("method", "spatial_proximity"),
                category_weight=details.get("category_weight"),
                name_similarity=details.get("name_similarity"),
                is_primary=(i == 0),  # First match is primary
            )
            associations.append(assoc)
            
            # Only keep top 3 matches per parking lot
            if len(associations) >= 3:
                break
        
        return associations
    
    def _find_nearby_businesses(
        self,
        parking_lot: ParkingLot,
        db: Session
    ) -> List[Tuple[Business, float]]:
        """Find businesses within MAX_DISTANCE_METERS of parking lot centroid."""
        
        # Get centroid as WKT
        centroid_shape = to_shape(parking_lot.centroid)
        centroid_wkt = f"SRID=4326;POINT({centroid_shape.x} {centroid_shape.y})"
        
        # Use raw SQL for PostGIS spatial query
        # Note: Use string formatting for geometry literal, parameter for distance
        query = text(f"""
            SELECT 
                b.id,
                ST_Distance(
                    b.geometry::geography,
                    ST_GeomFromEWKT('{centroid_wkt}')::geography
                ) as distance_meters
            FROM businesses b
            WHERE ST_DWithin(
                b.geometry::geography,
                ST_GeomFromEWKT('{centroid_wkt}')::geography,
                :max_distance
            )
            ORDER BY distance_meters
            LIMIT 20
        """)
        
        result = db.execute(query, {
            "max_distance": self.MAX_DISTANCE_METERS,
        })
        
        nearby = []
        for row in result:
            business = db.query(Business).filter(Business.id == row.id).first()
            if business:
                nearby.append((business, row.distance_meters))
        
        return nearby
    
    def _calculate_match_score(
        self,
        parking_lot: ParkingLot,
        business: Business,
        distance_meters: float
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate match score between parking lot and business.
        Returns score (0-100) and details dict.
        """
        score = 0
        details = {
            "method": "spatial_proximity",
        }
        
        # 1. Distance score (40 points max)
        if distance_meters <= self.CLOSE_DISTANCE_METERS:
            distance_score = self.DISTANCE_WEIGHT
        elif distance_meters <= self.MEDIUM_DISTANCE_METERS:
            distance_score = self.DISTANCE_WEIGHT * 0.75
        elif distance_meters <= 60:
            distance_score = self.DISTANCE_WEIGHT * 0.5
        elif distance_meters <= self.MAX_DISTANCE_METERS:
            distance_score = self.DISTANCE_WEIGHT * 0.25
        else:
            distance_score = 0
        
        score += distance_score
        
        # 2. Category relevance score (30 points max)
        category_score = 0
        if business.category:
            category_lower = business.category.lower()
            
            # Check high priority categories
            for keyword in RELEVANT_CATEGORIES.get("high", []):
                if keyword in category_lower:
                    category_score = self.CATEGORY_WEIGHT
                    break
            
            # Check medium priority if not high
            if category_score == 0:
                for keyword in RELEVANT_CATEGORIES.get("medium", []):
                    if keyword in category_lower:
                        category_score = self.CATEGORY_WEIGHT * 0.66
                        break
            
            # Low priority fallback
            if category_score == 0:
                category_score = self.CATEGORY_WEIGHT * 0.33
        
        score += category_score
        details["category_weight"] = category_score / self.CATEGORY_WEIGHT
        
        # 3. Name similarity score (20 points max)
        name_score = 0
        if parking_lot.operator_name and business.name:
            # Use fuzzy matching
            similarity = fuzz.token_sort_ratio(
                parking_lot.operator_name.lower(),
                business.name.lower()
            ) / 100.0
            
            if similarity > 0.8:
                name_score = self.NAME_SIMILARITY_WEIGHT
                details["method"] = "operator_match"
            elif similarity > 0.5:
                name_score = self.NAME_SIMILARITY_WEIGHT * 0.5
            
            details["name_similarity"] = similarity
        
        score += name_score
        
        # 4. Building adjacency score (10 points max)
        # This would require building polygon data, skip for now
        # TODO: Implement if building polygons are available
        adjacency_score = 0
        score += adjacency_score
        
        return score, details
    
    def get_primary_business_for_parking_lot(
        self,
        parking_lot_id: uuid.UUID,
        db: Session
    ) -> Optional[Business]:
        """Get the primary (best match) business for a parking lot."""
        assoc = db.query(ParkingLotBusinessAssociation).filter(
            ParkingLotBusinessAssociation.parking_lot_id == parking_lot_id,
            ParkingLotBusinessAssociation.is_primary == True
        ).first()
        
        if assoc:
            return db.query(Business).filter(Business.id == assoc.business_id).first()
        
        return None


# Singleton instance
association_service = AssociationService()

