import base64
import time
import threading
import cv2
import re
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from config import GEMINI_MODEL, GEMINI_TEMPERATURE, ANALYSIS_INTERVAL

class AnalysisService:
    def __init__(self):
        self.gemini_model = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL, 
            temperature=GEMINI_TEMPERATURE
        )
        self.last_sent_times = {}
        self.track_results = {}
    
    def encode_image_to_base64(self, image):
        _, buffer = cv2.imencode(".jpg", image)
        return base64.b64encode(buffer).decode("utf-8")
    
    def analyze_damage_with_gemini(self, base64_image, track_id, damage_type):
        try:
            prompt = f"""Analyze this road damage image of a {damage_type} and provide:
1. Severity level (low, medium, or high)
2. A short maintenance recommendation (one sentence)

Format your response as:
Severity: [low|medium|high]
Recommendation: [your recommendation]"""
            
            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            )
            response = self.gemini_model.invoke([message])
            result = response.content.strip()
            
            # Parse the response to extract severity and recommendation
            severity_match = re.search(r'Severity:\s*(low|medium|high)', result, re.IGNORECASE)
            recommendation_match = re.search(r'Recommendation:\s*(.+)', result, re.IGNORECASE | re.DOTALL)
            
            severity = severity_match.group(1).lower() if severity_match else "medium"
            recommendation = recommendation_match.group(1).strip() if recommendation_match else "Schedule inspection"
            
            self.track_results[track_id] = {
                "severity": severity,
                "recommendation": recommendation
            }
        except Exception as e:
            print(f"[Track {track_id}] Gemini Error:", e)
            self.track_results[track_id] = {
                "severity": "medium",
                "recommendation": "Schedule inspection"
            }
    
    def process_detection(self, detection):
        track_id = detection["track_id"]
        damage_type = detection["class_name"]
        crop = detection["crop"]
        
        current_time = time.time()
        last_time = self.last_sent_times.get(track_id, 0)
        
        if current_time - last_time > ANALYSIS_INTERVAL and crop.size > 0:
            self.last_sent_times[track_id] = current_time
            base64_img = self.encode_image_to_base64(crop)
            
            threading.Thread(
                target=self.analyze_damage_with_gemini,
                args=(base64_img, track_id, damage_type)
            ).start()
        
        if track_id in self.track_results:
            return self.track_results[track_id]
        
        return None