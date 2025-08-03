import cv2
import numpy as np
from ultralytics import YOLO
import cvzone
from config import TARGET_WIDTH, TARGET_HEIGHT
from analysis_service import AnalysisService

class DetectionService:
    def __init__(self, model_path, confidence_threshold, overlap_threshold):
        self.model = YOLO(model_path)
        self.confidence_threshold = confidence_threshold
        self.overlap_threshold = overlap_threshold
        self.class_names = self.model.names
        self.analysis_service = AnalysisService()  # Initialize analysis service
        
    def calculate_overlap_percentage(self, box1, box2):
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        x1_inter = max(x1_1, x1_2)
        y1_inter = max(y1_1, y1_2)
        x2_inter = min(x2_1, x2_2)
        y2_inter = min(y2_1, y2_2)
        
        if x2_inter <= x1_inter or y2_inter <= y1_inter:
            return 0.0
        
        intersection_area = (x2_inter - x1_inter) * (y2_inter - y1_inter)
        box1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
        box2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
        
        smaller_area = min(box1_area, box2_area)
        return (intersection_area / smaller_area) * 100.0 if smaller_area > 0 else 0.0
    
    def filter_overlapping_detections(self, boxes, confidences, track_ids, class_ids):
        if len(boxes) == 0:
            return boxes, confidences, track_ids, class_ids
        
        boxes = np.array(boxes)
        confidences = np.array(confidences)
        track_ids = np.array(track_ids)
        class_ids = np.array(class_ids)
        
        sorted_indices = np.argsort(-confidences)
        keep_indices = []
        
        for i in sorted_indices:
            current_box = boxes[i]
            current_class = class_ids[i]
            keep_current = True
            
            for kept_idx in keep_indices:
                kept_box = boxes[kept_idx]
                kept_class = class_ids[kept_idx]
                
                if current_class != kept_class:
                    continue
                
                overlap_percent = self.calculate_overlap_percentage(current_box, kept_box)
                
                if overlap_percent > self.overlap_threshold:
                    keep_current = False
                    break
            
            if keep_current:
                keep_indices.append(i)
        
        return (boxes[keep_indices], 
                confidences[keep_indices], 
                track_ids[keep_indices], 
                class_ids[keep_indices].tolist())
    
    def get_severity_color(self, severity):
        """Get color based on severity level"""
        if severity == "low":
            return (0, 255, 0)  # Green
        elif severity == "medium":
            return (255, 255, 0)  # Yellow
        else:  # high
            return (255, 0, 0)  # Red
    
    def draw_high_quality_text(self, img, text, position, font_scale=0.4, thickness=1, 
                              text_color=(255, 255, 255), bg_color=(0, 0, 0, 180), 
                              padding=5, font=cv2.FONT_HERSHEY_SIMPLEX):
        """Draw high quality text with background using anti-aliasing"""
        x, y = position
        
        # Get text dimensions
        (text_width, text_height), baseline = cv2.getTextSize(
            text, font, font_scale, thickness)
        
        # Calculate background rectangle coordinates
        bg_x1 = x - padding
        bg_y1 = y - text_height - padding
        bg_x2 = x + text_width + padding
        bg_y2 = y + padding
        
        # Create a copy of the image region
        roi = img[bg_y1:bg_y2, bg_x1:bg_x2].copy()
        
        # Create a semi-transparent background
        overlay = img.copy()
        cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), bg_color[:3], -1)
        
        # Blend the overlay with the original image
        alpha = bg_color[3] / 255.0 if len(bg_color) > 3 else 0.7
        img[bg_y1:bg_y2, bg_x1:bg_x2] = cv2.addWeighted(
            overlay[bg_y1:bg_y2, bg_x1:bg_x2], alpha, roi, 1 - alpha, 0)
        
        # Draw text with anti-aliasing
        cv2.putText(img, text, (x, y), font, font_scale, text_color, 
                   thickness, cv2.LINE_AA)
        
        return img
    
    def process_frame(self, frame):
        # Resize frame for consistent processing
        frame = cv2.resize(frame, (TARGET_WIDTH, TARGET_HEIGHT))
        
        # Run YOLO tracking
        results = self.model.track(frame, persist=True, conf=self.confidence_threshold)
        
        detections = []
        
        if results[0].boxes is not None and results[0].boxes.id is not None:
            ids = results[0].boxes.id.cpu().numpy().astype(int)
            boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
            class_ids = results[0].boxes.cls.int().cpu().tolist()
            confidences = results[0].boxes.conf.cpu().numpy()
            
            boxes, confidences, ids, class_ids = self.filter_overlapping_detections(
                boxes, confidences, ids, class_ids
            )
            
            for track_id, box, class_id, confidence in zip(ids, boxes, class_ids, confidences):
                x1, y1, x2, y2 = box
                class_name = self.class_names[class_id].lower()
                
                if class_name not in ["pothole", "broken_edge"]:
                    continue
                
                # Draw bounding box with class-specific color
                if class_name == "pothole":
                    box_color = (0, 0, 255)  # Red for potholes
                else:  # broken_edge
                    box_color = (255, 0, 0)  # Blue for broken edges
                
                # Draw thicker bounding box for better visibility
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)
                
                # Create label text
                label = f"{class_name.upper()} #{track_id}"
                
                # Draw high-quality label with background
                self.draw_high_quality_text(
                    frame, label, (x1, y1 - 10),
                    font_scale=0.4, thickness=1,
                    text_color=(255, 255, 255),
                    bg_color=(0, 0, 0, 200)  # Semi-transparent black
                )
                
                # Get analysis from Gemini
                analysis_result = self.analysis_service.process_detection({
                    "track_id": track_id,
                    "class_name": class_name,
                    "crop": frame[y1:y2, x1:x2]
                })
                
                # Default values if analysis not available yet
                severity = "low"
                recommendation = "Analyzing..."
                severity_color = (200, 200, 200)  # Gray for default
                
                if analysis_result:
                    severity = analysis_result.get("severity", "medium")
                    recommendation = analysis_result.get("recommendation", "No recommendation")
                    severity_color = self.get_severity_color(severity)
                
                # Draw severity indicator with color coding
                self.draw_high_quality_text(
                    frame, f"Severity: {severity.upper()}", (x1, y1 - 40),
                    font_scale=0.4, thickness=1,
                    text_color=(255, 255, 255),
                    bg_color=severity_color + (180,)  # Semi-transparent color
                )
                
                # Draw recommendation
                self.draw_high_quality_text(
                    frame, recommendation, (x1, y1 - 70),
                    font_scale=0.4, thickness=1,
                    text_color=(255, 255, 255),
                    bg_color=(0, 150, 0, 180)  # Semi-transparent green
                )
                
                # Store detection info
                detections.append({
                    "track_id": track_id,
                    "class_name": class_name,
                    "box": (x1, y1, x2, y2),
                    "confidence": confidence,
                    "severity": severity,
                    "recommendation": recommendation,
                    "crop": frame[y1:y2, x1:x2]
                })
        
        # Draw detection count on frame with high quality text
        detection_count = len(detections)
        self.draw_high_quality_text(
            frame, f"Detections: {detection_count}", (10, TARGET_HEIGHT - 20),
            font_scale=1.0, thickness=1,
            text_color=(255, 255, 255),
            bg_color=(0, 0, 0, 200)
        )
        
        return frame, detections