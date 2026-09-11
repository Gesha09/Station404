import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file
load_dotenv()

class Settings:
    def __init__(self):
        # Discord
        self.DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
        
        # Admin
        self.ADMIN_ROLE_ID = os.getenv("ADMIN_ROLE_ID")
        self.WEB_ADMIN_SECRET = os.getenv("WEB_ADMIN_SECRET", "default_secret")
        
        # Web
        self.WEB_URL = os.getenv("WEB_URL", "http://localhost:8000")
        self.API_HOST = os.getenv("API_HOST", "127.0.0.1")
        self.API_PORT = int(os.getenv("API_PORT", "8000"))
        
        # Database
        self.DATABASE_PATH = os.getenv("DATABASE_PATH", "station404.db")
        
        # Validate
        if not self.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN not set in .env")
        if not self.ADMIN_ROLE_ID:
            raise ValueError("ADMIN_ROLE_ID not set in .env")

settings = Settings()