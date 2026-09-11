import uuid
import json
from datetime import datetime
from database.db import db

class RoundRepository:
    @staticmethod
    def get_current():
        """Get the current active/prep round, or None if idle"""
        return db.fetch_one(
            "SELECT * FROM rounds WHERE status IN ('prep', 'active') ORDER BY round_number DESC LIMIT 1"
        )
    
    @staticmethod
    def get_latest():
        """Get the most recent round (any status)"""
        return db.fetch_one(
            "SELECT * FROM rounds ORDER BY round_number DESC LIMIT 1"
        )
    
    @staticmethod
    def get_by_id(round_id: str):
        return db.fetch_one("SELECT * FROM rounds WHERE id = ?", (round_id,))
    
    @staticmethod
    def create_new() -> dict:
        """Create a new round in 'prep' status"""
        latest = RoundRepository.get_latest()
        next_number = 1 if not latest else latest['round_number'] + 1
        
        round_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        db.execute(
            """
            INSERT INTO rounds (id, round_number, status, started_at, imposter_ids)
            VALUES (?, ?, 'prep', ?, '[]')
            """,
            (round_id, next_number, now)
        )
        
        return db.fetch_one("SELECT * FROM rounds WHERE id = ?", (round_id,))
    
    @staticmethod
    def update_status(round_id: str, status: str):
        now = datetime.now().isoformat()
        if status == 'active':
            db.execute(
                "UPDATE rounds SET status = ? WHERE id = ?",
                (status, round_id)
            )
        elif status == 'ended':
            db.execute(
                "UPDATE rounds SET status = ?, ended_at = ? WHERE id = ?",
                (status, now, round_id)
            )
        else:
            db.execute(
                "UPDATE rounds SET status = ? WHERE id = ?",
                (status, round_id)
            )
    
    @staticmethod
    def set_imposters(round_id: str, imposter_ids: list):
        db.execute(
            "UPDATE rounds SET imposter_ids = ? WHERE id = ?",
            (json.dumps(imposter_ids), round_id)
        )
    
    @staticmethod
    def set_winner(round_id: str, winner_id: str, win_type: str):
        db.execute(
            "UPDATE rounds SET winner_id = ?, win_type = ? WHERE id = ?",
            (winner_id, win_type, round_id)
        )
    
    @staticmethod
    def get_all_recent(limit=10):
        return db.fetch_all(
            "SELECT * FROM rounds ORDER BY round_number DESC LIMIT ?",
            (limit,)
        )