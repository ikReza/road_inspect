import cv2
import time
import cvzone
import os
import json
from config import MODEL_PATH, VIDEO_SOURCE, CONFIDENCE_THRESHOLD, OVERLAP_THRESHOLD, FRAME_SKIP_INTERVAL
from detection_service import DetectionService
from analysis_service import AnalysisService
from database_service import DatabaseService

def main():
    # Initialize services
    detection_service = DetectionService(MODEL_PATH, CONFIDENCE_THRESHOLD, OVERLAP_THRESHOLD)
    analysis_service = AnalysisService()
    db_service = DatabaseService()
    
    # Check if video file exists
    if not os.path.exists(VIDEO_SOURCE):
        print(f"Error: Video file '{VIDEO_SOURCE}' not found!")
        print("Please make sure the video file exists in the correct location.")
        return
    
    # Open video source
    cap = cv2.VideoCapture(VIDEO_SOURCE)
    if not cap.isOpened():
        print(f"Error: Could not open video file '{VIDEO_SOURCE}'")
        print("Possible reasons:")
        print("1. The video file is corrupted")
        print("2. The video format is not supported")
        print("3. Insufficient permissions to read the file")
        return
    
    # Get video properties
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Video opened successfully!")
    print(f"Resolution: {frame_width}x{frame_height}")
    print(f"FPS: {fps:.2f}")
    print(f"Total frames: {total_frames}")
    
    # Frame processing variables
    frame_count = 0
    start_time = time.time()
    
    # Create window
    cv2.namedWindow("Road Damage Detection", cv2.WINDOW_NORMAL)
    
    while True:
        success, frame = cap.read()
        if not success:
            print("End of video or error reading frame")
            break
        
        frame_count += 1
        if frame_count % FRAME_SKIP_INTERVAL != 0:
            continue
        
        # Process frame for detections
        processed_frame, detections = detection_service.process_frame(frame)
        
        # Process each detection
        for detection in detections:
            track_id = detection["track_id"]
            
            # Check if this is a new detection
            existing_detection = db_service.get_detection_by_track_id(track_id)
            
            if existing_detection is None:
                # New detection - get analysis and save
                analysis_result = analysis_service.process_detection(detection)
                
                # Save to database with analysis results
                db_service.save_detection(detection, analysis_result)
        
        # Display FPS and frame count
        elapsed_time = time.time() - start_time
        current_fps = frame_count / elapsed_time if elapsed_time > 0 else 0
        cvzone.putTextRect(
            processed_frame, f"FPS: {current_fps:.1f} | Frame: {frame_count}/{total_frames}", (10, 30),
            scale=1, thickness=1, offset=5,
            colorT=(255, 255, 255), colorR=(0, 0, 0)
        )
        
        # Show the frame
        cv2.imshow("Road Damage Detection", processed_frame)
        
        # Exit on ESC key
        if cv2.waitKey(1) & 0xFF == 27:
            print("User pressed ESC - exiting")
            break
    
    # Clean up
    cap.release()
    cv2.destroyAllWindows()
    db_service.close()
    
    # Print detection history
    print("\nRecent Detection History:")
    for record in db_service.get_detection_history():
        # Parse recommendations if they exist
        recommendations = None
        if record['recommendations']:
            try:
                recommendations = json.loads(record['recommendations'])
            except:
                recommendations = record['recommendations']
        
        severity = recommendations.get('severity', 'N/A') if isinstance(recommendations, dict) else 'N/A'
        recommendation = recommendations.get('recommendation', 'N/A') if isinstance(recommendations, dict) else recommendations
        
        print(f"{record['timestamp']} - {record['damage_type']} #{record['track_id']} "
              f"(Confidence: {record['confidence']:.2f}, Severity: {severity})")
        print(f"  Recommendation: {recommendation}")

if __name__ == "__main__":
    main()