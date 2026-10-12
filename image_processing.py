import os
import shutil
from collections import deque

try:
    import cv2
    import numpy as np
    import matplotlib.pyplot as plt
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

class ImagePreprocessor:
    @staticmethod
    def preprocess(image_path):
        """Loads an image, converts to grayscale, and applies noise reduction."""
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not load image at {image_path}")
        
        # Convert to Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian Blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Contrast Limited Adaptive Histogram Equalization (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)
        
        return img, enhanced

class FeatureExtractor:
    @staticmethod
    def extract_features(enhanced_image):
        """Uses thresholding to extract potential regions of interest (ROI)."""
        _, binary_matrix = cv2.threshold(enhanced_image, 180, 255, cv2.THRESH_BINARY)
        return binary_matrix

class RegionAnalyzer:
    @staticmethod
    def find_connected_components_bfs(binary_matrix):
        """DSA Implementation: Uses Breadth-First Search (BFS) to find connected components."""
        rows, cols = binary_matrix.shape
        visited = np.zeros_like(binary_matrix, dtype=bool)
        regions = []
        
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        
        for r in range(rows):
            for c in range(cols):
                if binary_matrix[r, c] == 255 and not visited[r, c]:
                    current_region_pixels = []
                    queue = deque([(r, c)])
                    visited[r, c] = True
                    
                    while queue:
                        curr_r, curr_c = queue.popleft()
                        current_region_pixels.append((curr_r, curr_c))
                        
                        for dr, dc in directions:
                            nr, nc = curr_r + dr, curr_c + dc
                            if 0 <= nr < rows and 0 <= nc < cols:
                                if binary_matrix[nr, nc] == 255 and not visited[nr, nc]:
                                    visited[nr, nc] = True
                                    queue.append((nr, nc))
                    
                    if len(current_region_pixels) > 150:
                        regions.append(current_region_pixels)
                        
        return regions

    @staticmethod
    def calculate_statistics(enhanced_image, regions):
        """Calculates statistical metrics (mean, variance) for each region."""
        region_stats = []
        for i, pixels in enumerate(regions):
            intensities = [enhanced_image[r, c] for r, c in pixels]
            
            mean_intensity = np.mean(intensities)
            variance = np.var(intensities)
            std_dev = np.std(intensities)
            area = len(pixels)
            
            rows = [p[0] for p in pixels]
            cols = [p[1] for p in pixels]
            min_r, max_r = min(rows), max(rows)
            min_c, max_c = min(cols), max(cols)
            bbox = (min_c, min_r, max_c - min_c, max_r - min_r)
            
            region_stats.append({
                "id": i + 1,
                "area": area,
                "mean_intensity": mean_intensity,
                "variance": variance,
                "std_dev": std_dev,
                "bbox": bbox,
                "pixels": pixels
            })
            
        return region_stats

class RuleBasedEvaluator:
    @staticmethod
    def evaluate(region_stats):
        """Applies hardcoded mathematical/statistical rules to flag anomalies."""
        flagged_regions = []
        max_severity = "Normal"
        anomaly_score = 0
        
        for stat in region_stats:
            if stat["area"] > 500 and stat["mean_intensity"] > 200:
                flagged_regions.append(stat)
                max_severity = "Abnormal Findings Detected"
                anomaly_score = max(anomaly_score, min((stat["area"] / 5000) * 100, 99.0))
            
        if not flagged_regions and region_stats:
            max_severity = "Minor Variations"
            anomaly_score = 25.0
            
        return max_severity, round(anomaly_score, 2), flagged_regions

class MedicalImageProcessor:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def process(self, image_path, filename):
        """Orchestrates the entire image processing and reporting workflow."""
        if not HAS_CV2:
            # Fallback for environments where OpenCV cannot be installed (like Python 3.14)
            # This allows the Flask app to still run and demonstrate the UI
            output_filename = f"analyzed_{filename}"
            output_path = os.path.join(self.output_dir, output_filename)
            shutil.copy2(image_path, output_path)
            
            return {
                "severity": "Abnormal Findings Detected (Mocked for Demo)",
                "anomaly_score": 88.5,
                "flagged_regions_count": 2,
                "analyzed_image": output_filename,
                "total_regions_found": 4
            }
            
        # 1. Preprocessing
        original_img, enhanced_img = ImagePreprocessor.preprocess(image_path)
        
        # 2. Feature Extraction
        binary_matrix = FeatureExtractor.extract_features(enhanced_img)
        
        # 3. DSA-based Connected Components (BFS)
        regions = RegionAnalyzer.find_connected_components_bfs(binary_matrix)
        
        # 4. Statistical Analysis
        region_stats = RegionAnalyzer.calculate_statistics(enhanced_img, regions)
        
        # 5. Rule-based Evaluation
        severity, score, flagged = RuleBasedEvaluator.evaluate(region_stats)
        
        # 6. Visualization & Reporting
        output_img = original_img.copy()
        for region in flagged:
            x, y, w, h = region["bbox"]
            cv2.rectangle(output_img, (x, y), (x + w, y + h), (0, 0, 255), 2)
            cv2.putText(output_img, f"ROI {region['id']}", (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                        
        output_filename = f"analyzed_{filename}"
        output_path = os.path.join(self.output_dir, output_filename)
        cv2.imwrite(output_path, output_img)
        
        return {
            "severity": severity,
            "anomaly_score": score,
            "flagged_regions_count": len(flagged),
            "analyzed_image": output_filename,
            "total_regions_found": len(region_stats)
        }
