# Computer Vision for Parking Lot Condition Assessment

## What We Need

**Task:** Evaluate parking lot condition from satellite imagery
- Detect cracks and fissures
- Identify potholes and surface damage
- Assess line fading
- Calculate damage density and severity
- Generate condition score (0-100)

---

## Approach: YOLOv8/YOLOv9 for Damage Detection ⭐ RECOMMENDED

**Note:** We already have parking lot polygons from INRIX/HERE/OSM, so we don't need to detect parking lot boundaries. We only need to assess their condition.

### YOLOv8/YOLOv9 Segmentation

**What it does:**
- Detects cracks, potholes, and surface damage
- Provides bounding boxes and segmentation masks
- Fast inference (25-50ms per image)
- Can be trained on parking lot damage datasets

**Pros:**
- ✅ **Fast** - 25-50ms per image
- ✅ **Accurate** - 90-95% accuracy for damage detection
- ✅ **Small model** - 6-50MB depending on variant
- ✅ **Can run on CPU** - Reasonable speed without GPU
- ✅ **Easy to train** - Fine-tune on parking lot damage dataset
- ✅ **Active development** - YOLOv9 released 2024

**Cons:**
- ⚠️ **Needs training data** - Requires labeled parking lot damage images
- ⚠️ **Model hosting** - Need to host model or use cloud inference

**Accuracy:** ~90-95% for crack/pothole detection

**Implementation:**
```python
from ultralytics import YOLO
import cv2
import numpy as np

class ParkingLotConditionEvaluator:
    def __init__(self):
        # Load pre-trained YOLOv8 model (fine-tuned on parking lot damage)
        self.crack_model = YOLO('models/yolov8_cracks.pt')
        self.pothole_model = YOLO('models/yolov8_potholes.pt')
    
    def evaluate_condition(self, image, parking_lot_polygon):
        # Clip image to parking lot polygon
        masked_image = self.clip_to_polygon(image, parking_lot_polygon)
        
        # Detect cracks
        crack_results = self.crack_model(masked_image)
        cracks = crack_results[0].boxes
        
        # Detect potholes
        pothole_results = self.pothole_model(masked_image)
        potholes = pothole_results[0].boxes
        
        # Calculate metrics
        parking_lot_area = cv2.contourArea(parking_lot_polygon)
        crack_area = sum([box.area for box in cracks])
        pothole_count = len(potholes)
        
        crack_density = (crack_area / parking_lot_area) * 100
        
        # Calculate scores
        condition_score = self.calculate_condition_score(
            crack_density, pothole_count, parking_lot_area
        )
        
        return {
            "condition_score": condition_score,
            "crack_density": crack_density,
            "pothole_score": self.calculate_pothole_score(pothole_count),
            "line_fading_score": self.detect_line_fading(masked_image),
            "cracks": [box.to_dict() for box in cracks],
            "potholes": [box.to_dict() for box in potholes]
        }
    
    def calculate_condition_score(self, crack_density, pothole_count, area):
        # 0-100 scale (lower = worse condition = better lead)
        score = 100
        
        # Deduct for crack density
        score -= min(crack_density * 3, 50)  # Max 50 points
        
        # Deduct for potholes
        pothole_density = (pothole_count / (area / 1000)) * 10
        score -= min(pothole_density * 5, 30)  # Max 30 points
        
        return max(0, score)
```

---

### Alternative: Roboflow Hosted API

**Approach:**
- Use Roboflow's hosted YOLOv8 models
- Upload image, get detections via API
- No model hosting required

**Pros:**
- ✅ **No hosting** - Cloud API handles everything
- ✅ **Pre-trained models** - Parking lot damage datasets available
- ✅ **Easy integration** - Simple REST API
- ✅ **Scalable** - Handles concurrent requests

**Cons:**
- ⚠️ **API costs** - ~$0.001-0.005 per image
- ⚠️ **Latency** - Network round-trip adds 200-500ms
- ⚠️ **Dependency** - Relies on external service

**Cost:** ~$1-5 per 1000 images

**Implementation:**
```python
import httpx

async def evaluate_with_roboflow(image_bytes, api_key):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://detect.roboflow.com/parking-damage/1",
            params={"api_key": api_key},
            files={"file": image_bytes}
        )
        return response.json()
```

---

## Additional Detection Methods

### Line Fading Detection (OpenCV)

**Approach:**
- Detect white/yellow parking lines
- Assess fading using color intensity
- Calculate percentage of faded lines

```python
def detect_line_fading(image):
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    
    # Detect white lines (parking stripes)
    _, white_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    
    # Detect yellow lines
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    yellow_mask = cv2.inRange(hsv, (20, 100, 100), (30, 255, 255))
    
    # Combine masks
    line_mask = cv2.bitwise_or(white_mask, yellow_mask)
    
    # Calculate line coverage
    total_pixels = image.shape[0] * image.shape[1]
    line_pixels = cv2.countNonZero(line_mask)
    line_coverage = (line_pixels / total_pixels) * 100
    
    # Score: lower coverage = more fading
    fading_score = 10 - min(line_coverage, 10)
    
    return fading_score  # 0-10 (higher = more fading)
```

### Surface Degradation (Texture Analysis)

**Approach:**
- Analyze surface texture uniformity
- Detect rough/uneven areas
- Use Gabor filters or LBP (Local Binary Patterns)

```python
from skimage.feature import local_binary_pattern

def detect_surface_degradation(image):
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    
    # Apply LBP for texture analysis
    lbp = local_binary_pattern(gray, P=8, R=1, method='uniform')
    
    # Calculate texture variance
    variance = np.var(lbp)
    
    # Higher variance = more degradation
    degradation_score = min(variance / 100, 10)
    
    return degradation_score  # 0-10
```

---

## Implementation Strategy

### Phase 1: YOLOv8 for Damage Detection (Recommended)

**Self-hosted approach:**
```python
from ultralytics import YOLO

class ParkingLotEvaluator:
    def __init__(self):
        self.crack_model = YOLO('yolov8n-seg.pt')  # Nano model (6MB)
        # Fine-tune on parking lot damage dataset
    
    def evaluate(self, image, parking_lot_polygon):
        # Clip to parking lot area
        masked = self.clip_to_polygon(image, parking_lot_polygon)
        
        # Run detection
        results = self.crack_model(masked)
        
        # Calculate metrics
        return self.calculate_condition_metrics(results)
```

**Accuracy:** ~90-95%
**Speed:** 25-50ms per image
**Cost:** $0 (self-hosted)

### Phase 2: Roboflow API (If preferred)

**Cloud API approach:**
```python
async def evaluate_with_roboflow(image_url):
    response = await httpx.post(
        "https://detect.roboflow.com/parking-damage/1",
        params={"api_key": ROBOFLOW_KEY},
        json={"image": image_url}
    )
    return response.json()
```

**Accuracy:** ~90-95%
**Speed:** 200-500ms per image (includes network latency)
**Cost:** ~$0.001-0.005 per image

### Phase 3: Hybrid Approach (Best)

**Combine multiple detection methods:**
```python
def comprehensive_evaluation(image, parking_lot_polygon):
    # 1. YOLOv8 for cracks and potholes
    damage_results = yolo_detect_damage(image)
    
    # 2. OpenCV for line fading
    line_score = detect_line_fading(image)
    
    # 3. Texture analysis for surface degradation
    degradation_score = detect_surface_degradation(image)
    
    # Combine scores
    condition_score = calculate_overall_score(
        damage_results, line_score, degradation_score
    )
    
    return {
        "condition_score": condition_score,
        "crack_density": damage_results["crack_density"],
        "pothole_score": damage_results["pothole_score"],
        "line_fading_score": line_score,
        "degradation_score": degradation_score
    }
```

---

## Training Data

### Parking Lot Damage Datasets

**Available datasets:**
1. **Roboflow Universe** - Public parking lot damage datasets
2. **Kaggle** - Road/pavement crack datasets (transferable)
3. **Custom collection** - Collect from Google Maps, Bing Maps

**Recommended approach:**
1. Start with pre-trained YOLOv8 on COCO dataset
2. Fine-tune on parking lot damage dataset (1000-5000 images)
3. Augment with rotations, brightness, contrast variations

**Labeling:**
- Use Roboflow for labeling
- Classes: crack, pothole, line_fading, surface_damage
- Polygon or bounding box annotations

---

## Cost Comparison

### Self-Hosted YOLOv8
- **Setup cost:** $0 (use existing server)
- **Per image:** $0
- **Infrastructure:** CPU sufficient (50-100ms), GPU faster (10-25ms)
- **Total cost per 1000 images:** $0

### Roboflow API
- **Setup cost:** $0
- **Per image:** $0.001-0.005
- **Infrastructure:** None (cloud API)
- **Total cost per 1000 images:** $1-5

### Recommendation
- **Small scale (<10k images/month):** Roboflow API (simplicity)
- **Large scale (>10k images/month):** Self-hosted YOLOv8 (cost savings)

---

## Final Recommendation

### **Use YOLOv8 for damage detection**

**Why YOLOv8 is best:**
1. ✅ **We already have parking lot polygons** (from INRIX/HERE/OSM)
2. ✅ **Fast and accurate** for damage detection
3. ✅ **Small model** - runs on CPU
4. ✅ **Easy to train** - fine-tune on parking lot damage dataset
5. ✅ **Active development** - YOLOv9 available if needed

**Workflow:**
1. Get parking lot polygon from INRIX/HERE/OSM
2. Fetch satellite imagery clipped to polygon
3. Run YOLOv8 for crack/pothole detection
4. Run OpenCV for line fading detection
5. Combine scores for overall condition assessment

**No need for SAM** - we're not detecting parking lot boundaries, we're assessing existing polygons for damage.

---

## Conclusion

**For parking lot condition assessment:**
- ✅ Use YOLOv8/YOLOv9 for crack and pothole detection
- ✅ Use OpenCV for line fading and texture analysis
- ✅ Combine multiple metrics for comprehensive condition score
- ✅ Self-host for cost savings or use Roboflow API for simplicity

**SAM is not needed** - we already have parking lot geometries from data sources.

