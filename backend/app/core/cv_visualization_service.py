"""
CVVisualizationService - Generate annotated images showing CV results

Creates visual outputs for users to see the analysis results:
1. Segmentation image - all detected buildings and paved surfaces
2. Property boundary image - only associated asphalt highlighted
3. Condition analysis image - damage annotations on asphalt
"""
import logging
import io
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from app.core.asphalt_segmentation_service import SegmentationResult, DetectedPolygon
from app.core.property_association_service import AssociatedAsphaltArea

logger = logging.getLogger(__name__)


@dataclass
class ConditionResult:
    """Condition evaluation result for an asphalt area."""
    area: AssociatedAsphaltArea
    condition_score: float
    crack_count: int
    pothole_count: int
    crack_density: float
    detections: List[Dict[str, Any]]


@dataclass
class AnnotatedImages:
    """Collection of annotated images from CV analysis."""
    segmentation: bytes  # All detected polygons
    property_boundary: bytes  # Only associated asphalt
    condition_analysis: bytes  # Damage annotations


class CVVisualizationService:
    """
    Generates annotated images showing CV results.
    Creates visual outputs for user to see the analysis.
    """
    
    # Colors for different elements (RGBA)
    COLORS = {
        "building": (0, 255, 0, 100),  # Green, semi-transparent
        "building_outline": (0, 255, 0, 255),  # Solid green
        "paved_associated": (0, 150, 255, 120),  # Blue, semi-transparent
        "paved_associated_outline": (0, 200, 255, 255),  # Bright blue
        "paved_excluded": (128, 128, 128, 60),  # Gray, more transparent
        "paved_excluded_outline": (100, 100, 100, 128),  # Gray
        "business_building": (255, 200, 0, 150),  # Gold for business building
        "business_building_outline": (255, 220, 0, 255),  # Bright gold
        "crack": (255, 255, 0),  # Yellow
        "pothole": (255, 0, 0),  # Red
        "alligator_crack": (255, 165, 0),  # Orange
        "text_bg": (0, 0, 0, 180),  # Dark background for text
        "text": (255, 255, 255),  # White text
    }
    
    async def generate_all_images(
        self,
        original_image: bytes,
        segmentation: SegmentationResult,
        business_building: Optional[DetectedPolygon],
        associated_areas: List[AssociatedAsphaltArea],
        condition_results: Optional[List[ConditionResult]] = None
    ) -> AnnotatedImages:
        """
        Generate all annotated images.
        
        Args:
            original_image: Original satellite image bytes
            segmentation: Raw segmentation results
            business_building: The detected business building
            associated_areas: List of asphalt areas with association status
            condition_results: Optional condition evaluation results
        
        Returns:
            AnnotatedImages with all three image types
        """
        logger.info("🎨 Generating annotated images")
        
        # Load base image
        base_image = Image.open(io.BytesIO(original_image)).convert("RGBA")
        image_size = (base_image.width, base_image.height)
        
        logger.info(f"   Base image size: {image_size[0]}x{image_size[1]}")
        
        # Generate each image type
        segmentation_img = await self._draw_segmentation(
            base_image.copy(),
            segmentation,
            business_building
        )
        
        boundary_img = await self._draw_property_boundary(
            base_image.copy(),
            associated_areas,
            business_building
        )
        
        condition_img = await self._draw_condition_analysis(
            base_image.copy(),
            associated_areas,
            condition_results or []
        )
        
        return AnnotatedImages(
            segmentation=self._image_to_bytes(segmentation_img),
            property_boundary=self._image_to_bytes(boundary_img),
            condition_analysis=self._image_to_bytes(condition_img)
        )
    
    async def _draw_segmentation(
        self,
        image: Image.Image,
        segmentation: SegmentationResult,
        business_building: Optional[DetectedPolygon]
    ) -> Image.Image:
        """Draw all detected buildings and paved surfaces."""
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Draw paved surfaces first (so buildings appear on top)
        for paved in segmentation.paved_surfaces:
            pixel_coords = self._get_pixel_coords(paved.pixel_points)
            if len(pixel_coords) >= 3:
                draw.polygon(pixel_coords, fill=self.COLORS["paved_associated"])
                draw.line(pixel_coords + [pixel_coords[0]], 
                         fill=self.COLORS["paved_associated_outline"], width=2)
        
        # Draw buildings
        for building in segmentation.buildings:
            pixel_coords = self._get_pixel_coords(building.pixel_points)
            if len(pixel_coords) >= 3:
                # Highlight the business building differently
                if business_building and building.polygon.equals(business_building.polygon):
                    draw.polygon(pixel_coords, fill=self.COLORS["business_building"])
                    draw.line(pixel_coords + [pixel_coords[0]], 
                             fill=self.COLORS["business_building_outline"], width=3)
                else:
                    draw.polygon(pixel_coords, fill=self.COLORS["building"])
                    draw.line(pixel_coords + [pixel_coords[0]], 
                             fill=self.COLORS["building_outline"], width=2)
        
        # Composite
        result = Image.alpha_composite(image, overlay)
        
        # Add legend
        result = self._add_legend(result, [
            ("Business Building", self.COLORS["business_building_outline"][:3]),
            ("Other Buildings", self.COLORS["building_outline"][:3]),
            ("Paved Surfaces", self.COLORS["paved_associated_outline"][:3]),
        ])
        
        # Add title
        result = self._add_title(result, "CV Segmentation Result")
        
        return result
    
    async def _draw_property_boundary(
        self,
        image: Image.Image,
        associated_areas: List[AssociatedAsphaltArea],
        business_building: Optional[DetectedPolygon]
    ) -> Image.Image:
        """Draw only associated asphalt, dim excluded areas."""
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        total_area = 0
        
        # Draw excluded areas first (dimmed)
        for area in associated_areas:
            if not area.is_associated:
                pixel_coords = self._get_pixel_coords(area.pixel_points)
                if len(pixel_coords) >= 3:
                    draw.polygon(pixel_coords, fill=self.COLORS["paved_excluded"])
                    draw.line(pixel_coords + [pixel_coords[0]], 
                             fill=self.COLORS["paved_excluded_outline"], width=1)
        
        # Draw associated areas (bright)
        for area in associated_areas:
            if area.is_associated:
                pixel_coords = self._get_pixel_coords(area.pixel_points)
                if len(pixel_coords) >= 3:
                    draw.polygon(pixel_coords, fill=self.COLORS["paved_associated"])
                    draw.line(pixel_coords + [pixel_coords[0]], 
                             fill=self.COLORS["paved_associated_outline"], width=3)
                    total_area += area.area_m2
        
        # Draw business building
        if business_building:
            pixel_coords = self._get_pixel_coords(business_building.pixel_points)
            if len(pixel_coords) >= 3:
                draw.polygon(pixel_coords, fill=self.COLORS["business_building"])
                draw.line(pixel_coords + [pixel_coords[0]], 
                         fill=self.COLORS["business_building_outline"], width=3)
        
        # Composite
        result = Image.alpha_composite(image, overlay)
        
        # Add stats bar at bottom
        stats_text = f"Property Asphalt: {total_area:,.0f} m² | {len([a for a in associated_areas if a.is_associated])} areas"
        result = self._add_stats_bar(result, stats_text)
        
        # Add title
        result = self._add_title(result, "Property Asphalt Areas")
        
        return result
    
    async def _draw_condition_analysis(
        self,
        image: Image.Image,
        associated_areas: List[AssociatedAsphaltArea],
        condition_results: List[ConditionResult]
    ) -> Image.Image:
        """Draw damage detections on associated asphalt."""
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Draw associated asphalt areas with subtle fill
        for area in associated_areas:
            if area.is_associated:
                pixel_coords = self._get_pixel_coords(area.pixel_points)
                if len(pixel_coords) >= 3:
                    draw.polygon(pixel_coords, fill=(0, 100, 255, 40))
                    draw.line(pixel_coords + [pixel_coords[0]], 
                             fill=(0, 150, 255, 200), width=2)
        
        # Draw damage detections
        total_cracks = 0
        total_potholes = 0
        
        for result in condition_results:
            for detection in result.detections:
                # Get bounding box
                x = detection.get("x", 0)
                y = detection.get("y", 0)
                w = detection.get("width", 20)
                h = detection.get("height", 20)
                
                class_name = detection.get("class", "").lower()
                confidence = detection.get("confidence", 0)
                
                # Determine color based on class
                if "pothole" in class_name:
                    color = self.COLORS["pothole"]
                    total_potholes += 1
                elif "alligator" in class_name:
                    color = self.COLORS["alligator_crack"]
                    total_cracks += 1
                else:
                    color = self.COLORS["crack"]
                    total_cracks += 1
                
                # Draw bounding box
                x1, y1 = int(x - w/2), int(y - h/2)
                x2, y2 = int(x + w/2), int(y + h/2)
                
                draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
                
                # Draw label background
                label = f"{detection.get('class', 'damage')} {confidence:.0%}"
                label_y = max(0, y1 - 18)
                
                # Estimate text size
                text_width = len(label) * 7
                draw.rectangle([x1, label_y, x1 + text_width, label_y + 16], 
                              fill=self.COLORS["text_bg"])
                draw.text((x1 + 2, label_y + 1), label, fill=self.COLORS["text"])
        
        # Composite
        result = Image.alpha_composite(image, overlay)
        
        # Calculate overall condition
        if condition_results:
            avg_score = sum(r.condition_score for r in condition_results if r.condition_score) / len(condition_results)
        else:
            avg_score = 100
        
        # Add stats bar
        stats_text = f"Condition: {avg_score:.0f}/100 | Cracks: {total_cracks} | Potholes: {total_potholes}"
        result = self._add_stats_bar(result, stats_text)
        
        # Add title with condition indicator
        if avg_score < 40:
            condition_label = "POOR - High Priority"
            title_color = (255, 80, 80)
        elif avg_score < 70:
            condition_label = "FAIR - Needs Attention"
            title_color = (255, 200, 0)
        else:
            condition_label = "GOOD"
            title_color = (100, 255, 100)
        
        result = self._add_title(result, f"Condition Analysis - {condition_label}", title_color)
        
        return result
    
    def _get_pixel_coords(self, points: List[Dict]) -> List[Tuple[int, int]]:
        """Convert point dicts to pixel coordinate tuples."""
        coords = []
        for point in points:
            x = int(point.get("x", 0))
            y = int(point.get("y", 0))
            coords.append((x, y))
        return coords
    
    def _add_legend(
        self,
        image: Image.Image,
        items: List[Tuple[str, Tuple[int, int, int]]]
    ) -> Image.Image:
        """Add a legend to the image."""
        draw = ImageDraw.Draw(image)
        
        # Position in top-left
        x, y = 10, 10
        box_size = 16
        padding = 5
        
        for label, color in items:
            # Draw color box
            draw.rectangle([x, y, x + box_size, y + box_size], fill=color + (255,), outline=(255, 255, 255))
            
            # Draw label
            draw.text((x + box_size + padding, y), label, fill=(255, 255, 255))
            
            y += box_size + padding
        
        return image
    
    def _add_title(
        self,
        image: Image.Image,
        title: str,
        color: Tuple[int, int, int] = (255, 255, 255)
    ) -> Image.Image:
        """Add a title bar at the top of the image."""
        draw = ImageDraw.Draw(image)
        
        # Draw title background
        title_height = 30
        draw.rectangle([0, 0, image.width, title_height], fill=(0, 0, 0, 200))
        
        # Center title
        text_x = image.width // 2 - len(title) * 5
        draw.text((text_x, 8), title, fill=color)
        
        return image
    
    def _add_stats_bar(self, image: Image.Image, text: str) -> Image.Image:
        """Add a stats bar at the bottom of the image."""
        draw = ImageDraw.Draw(image)
        
        # Draw background bar
        bar_height = 30
        y = image.height - bar_height
        draw.rectangle([0, y, image.width, image.height], fill=(0, 0, 0, 200))
        
        # Center text
        text_x = image.width // 2 - len(text) * 4
        draw.text((text_x, y + 8), text, fill=(255, 255, 255))
        
        return image
    
    def _image_to_bytes(self, image: Image.Image) -> bytes:
        """Convert PIL Image to JPEG bytes."""
        # Convert to RGB for JPEG
        if image.mode == "RGBA":
            # Create white background
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # Use alpha as mask
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=95)
        output.seek(0)
        return output.read()


# Singleton instance
cv_visualization_service = CVVisualizationService()

