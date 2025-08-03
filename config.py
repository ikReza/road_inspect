import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Model Configuration
MODEL_PATH = "best.pt"  # Path to trained YOLO model
VIDEO_SOURCE = "video-1.mp4"  # Path to input video

# Detection Configuration
CONFIDENCE_THRESHOLD = 0.5  # Minimum confidence for detection
OVERLAP_THRESHOLD = 50.0  # Percentage
FRAME_SKIP_INTERVAL = 3  # Process every 3rd frame
TARGET_WIDTH, TARGET_HEIGHT = 700, 800 #1280, 720

# Gemini API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_TEMPERATURE = 0.4

# Analysis Configuration
ANALYSIS_INTERVAL = 5  # Send to Gemini every 5 seconds per detection

# Database Configuration
DB_NAME = "road_damage.db"