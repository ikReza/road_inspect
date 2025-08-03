import sqlite3
import json
from datetime import datetime
import numpy as np
from config import DB_NAME

class DatabaseService:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self._create_tables()
        self._create_indexes()
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        
        # Create detections table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER UNIQUE,
            damage_type TEXT,
            confidence REAL,
            location TEXT,
            timestamp DATETIME,
            image_path TEXT,
            recommendations TEXT
        )
        ''')
        
        self.conn.commit()
    
    def _create_indexes(self):
        cursor = self.conn.cursor()
        
        # Create index for track_id to speed up lookups
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_track_id ON detections (track_id)
        ''')
        
        self.conn.commit()
    
    def save_detection(self, detection, recommendations=None):
        cursor = self.conn.cursor()
        
        # Check if detection with this track_id already exists
        cursor.execute('SELECT id FROM detections WHERE track_id = ?', (int(detection["track_id"]),))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing detection with new information
            self._update_detection(cursor, detection, recommendations)
            return existing[0]
        else:
            # Insert new detection
            return self._insert_detection(cursor, detection, recommendations)
    
    def _insert_detection(self, cursor, detection, recommendations=None):
        # Convert box coordinates to Python int for JSON serialization
        box = [int(coord) for coord in detection["box"]]
        
        # Convert box to JSON string
        location = json.dumps(box)
        
        # Convert recommendations to JSON string
        rec_json = json.dumps(recommendations) if recommendations else None
        
        cursor.execute('''
        INSERT INTO detections (track_id, damage_type, confidence, location, timestamp, recommendations)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            int(detection["track_id"]),  # Convert to Python int
            detection["class_name"],
            float(detection["confidence"]),  # Convert to Python float
            location,
            datetime.now(),
            rec_json
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def _update_detection(self, cursor, detection, recommendations=None):
        # Convert box coordinates to Python int for JSON serialization
        box = [int(coord) for coord in detection["box"]]
        
        # Convert box to JSON string
        location = json.dumps(box)
        
        # Convert recommendations to JSON string
        rec_json = json.dumps(recommendations) if recommendations else None
        
        cursor.execute('''
        UPDATE detections
        SET damage_type = ?, confidence = ?, location = ?, timestamp = ?, recommendations = ?
        WHERE track_id = ?
        ''', (
            detection["class_name"],
            float(detection["confidence"]),
            location,
            datetime.now(),
            rec_json,
            int(detection["track_id"])
        ))
        
        self.conn.commit()
    
    def get_detection_history(self, limit=10):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT track_id, damage_type, confidence, location, timestamp, recommendations
        FROM detections
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (limit,))
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_detection_by_track_id(self, track_id):
        cursor = self.conn.cursor()
        cursor.execute('''
        SELECT track_id, damage_type, confidence, location, timestamp, recommendations
        FROM detections
        WHERE track_id = ?
        ''', (track_id,))
        
        columns = [desc[0] for desc in cursor.description]
        result = cursor.fetchone()
        
        if result:
            return dict(zip(columns, result))
        return None
    
    def close(self):
        self.conn.close()