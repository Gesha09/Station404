from datetime import datetime
from database.db import db

class GameStateRepository:
    """Stores live game state that the web can read in real-time."""
    
    @staticmethod
    def set(key: str, value):
        now = datetime.now().isoformat()
        existing = db.fetch_one("SELECT key FROM game_state WHERE key = ?", (key,))
        if existing:
            db.execute(
                "UPDATE game_state SET value = ?, updated_at = ? WHERE key = ?",
                (str(value), now, key)
            )
        else:
            db.execute(
                "INSERT INTO game_state (key, value, updated_at) VALUES (?, ?, ?)",
                (key, str(value), now)
            )
    
    @staticmethod
    def get(key: str, default=None):
        row = db.fetch_one("SELECT value FROM game_state WHERE key = ?", (key,))
        return row['value'] if row else default
    
    @staticmethod
    def get_all():
        return {row['key']: row['value'] for row in db.fetch_all("SELECT * FROM game_state")}
    
    @staticmethod
    def clear():
        """Clear all live state (called when round ends)"""
        db.execute("DELETE FROM game_state")