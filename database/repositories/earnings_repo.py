import uuid
from database.db import db

class EarningsRepository:
    @staticmethod
    def ensure_entry(round_id: str, player_id: str, discord_id: str, username: str):
        """Create earnings entry if it doesn't exist"""
        existing = db.fetch_one(
            "SELECT id FROM round_earnings WHERE round_id = ? AND player_id = ?",
            (round_id, player_id)
        )
        if not existing:
            db.execute(
                """
                INSERT INTO round_earnings (id, round_id, player_id, discord_id, username)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), round_id, player_id, discord_id, username)
            )
    
    @staticmethod
    def add_earned(round_id: str, player_id: str, amount: int):
        """Add to pocket_credits_earned (from tasks, chests, etc.)"""
        db.execute(
            """
            UPDATE round_earnings 
            SET pocket_credits_earned = pocket_credits_earned + ?
            WHERE round_id = ? AND player_id = ?
            """,
            (amount, round_id, player_id)
        )
    
    @staticmethod
    def add_stolen(round_id: str, player_id: str, amount: int):
        """Add to pocket_credits_stolen (from robbery/kill)"""
        db.execute(
            """
            UPDATE round_earnings 
            SET pocket_credits_stolen = pocket_credits_stolen + ?
            WHERE round_id = ? AND player_id = ?
            """,
            (amount, round_id, player_id)
        )
    
    @staticmethod
    def get_player_earnings(round_id: str, player_id: str):
        return db.fetch_one(
            "SELECT * FROM round_earnings WHERE round_id = ? AND player_id = ?",
            (round_id, player_id)
        )
    
    @staticmethod
    def get_leaderboard(round_id: str, limit=10):
        """Get top earners this round (earned + stolen)"""
        return db.fetch_all(
            """
            SELECT *, (pocket_credits_earned + pocket_credits_stolen) as total
            FROM round_earnings 
            WHERE round_id = ?
            ORDER BY total DESC
            LIMIT ?
            """,
            (round_id, limit)
        )
    
    @staticmethod
    def get_winner(round_id: str):
        """Get the player with most total earnings this round"""
        return db.fetch_one(
            """
            SELECT *, (pocket_credits_earned + pocket_credits_stolen) as total
            FROM round_earnings 
            WHERE round_id = ?
            ORDER BY total DESC
            LIMIT 1
            """,
            (round_id,)
        )
    
    @staticmethod
    def get_top_3(round_id: str):
        """Get top 3 earners for round end announcement"""
        return db.fetch_all(
            """
            SELECT *, (pocket_credits_earned + pocket_credits_stolen) as total
            FROM round_earnings 
            WHERE round_id = ?
            ORDER BY total DESC
            LIMIT 3
            """,
            (round_id,)
        )