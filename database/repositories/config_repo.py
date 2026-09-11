from database.db import db

class ConfigRepository:
    @staticmethod
    def get(key: str, default=None):
        row = db.fetch_one("SELECT value FROM game_config WHERE key = ?", (key,))
        if row:
            return row['value']
        return default
    
    @staticmethod
    def get_int(key: str, default=0) -> int:
        value = ConfigRepository.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default
    
    @staticmethod
    def set_value(key: str, value):
        db.execute(
            "UPDATE game_config SET value = ? WHERE key = ?",
            (str(value), key)
        )
    
    @staticmethod
    def get_all():
        return db.fetch_all("SELECT key, value, description FROM game_config")