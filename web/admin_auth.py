import uuid
import secrets
from datetime import datetime, timedelta
from database.db import db
from shared.config import settings

SESSION_DURATION_HOURS = 8

class AdminAuth:
    """Simple admin authentication using session tokens stored in cookies"""
    
    @staticmethod
    def validate_secret(secret: str) -> bool:
        """Check if the provided secret matches the admin secret"""
        return secret == settings.WEB_ADMIN_SECRET
    
    @staticmethod
    def create_session(ip_address: str = None) -> str:
        """Create a new admin session and return the token"""
        token = secrets.token_urlsafe(32)
        now = datetime.now().isoformat()
        
        db.execute(
            """INSERT INTO admin_sessions (token, created_at, last_active, ip_address)
               VALUES (?, ?, ?, ?)""",
            (token, now, now, ip_address)
        )
        return token
    
    @staticmethod
    def validate_session(token: str) -> bool:
        """Check if a session token is valid and not expired"""
        if not token:
            return False
        
        row = db.fetch_one(
            "SELECT created_at FROM admin_sessions WHERE token = ?",
            (token,)
        )
        
        if not row:
            return False
        
        created = datetime.fromisoformat(row['created_at'])
        if datetime.now() - created > timedelta(hours=SESSION_DURATION_HOURS):
            # Session expired, clean it up
            db.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
            return False
        
        # Update last active
        db.execute(
            "UPDATE admin_sessions SET last_active = ? WHERE token = ?",
            (datetime.now().isoformat(), token)
        )
        return True
    
    @staticmethod
    def destroy_session(token: str):
        """Log out by destroying the session"""
        db.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
    
    @staticmethod
    def cleanup_expired():
        """Remove expired sessions"""
        cutoff = (datetime.now() - timedelta(hours=SESSION_DURATION_HOURS)).isoformat()
        db.execute("DELETE FROM admin_sessions WHERE created_at < ?", (cutoff,))