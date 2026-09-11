import uuid
import secrets
from datetime import datetime
from database.db import db

class ApprovalRepository:
    @staticmethod
    def create_request(player_id: str, discord_id: str, item_id: str, usage_limit: int = 1):
        """Create a new approval request with a unique code"""
        code = secrets.token_urlsafe(8).upper()
        now = datetime.now().isoformat()
        
        db.execute(
            """INSERT INTO approval_requests 
               (id, player_id, discord_id, item_id, approval_code, requested_at, usage_limit, usage_remaining)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), player_id, discord_id, item_id, code, now, usage_limit, usage_limit)
        )
        return code
    
    @staticmethod
    def get_pending():
        """Get all pending approval requests with item names AND usernames"""
        return db.fetch_all(
            """
            SELECT ar.*, si.name as item_name, p.username
            FROM approval_requests ar
            JOIN shop_items si ON ar.item_id = si.item_id
            JOIN players p ON ar.player_id = p.id
            WHERE ar.status = 'pending'
            ORDER BY ar.requested_at DESC
            """
        )
    
    @staticmethod
    def get_by_code(code: str):
        """Get a single approval request by code, with item name and username"""
        return db.fetch_one(
            """
            SELECT ar.*, si.name as item_name, p.username
            FROM approval_requests ar
            JOIN shop_items si ON ar.item_id = si.item_id
            JOIN players p ON ar.player_id = p.id
            WHERE ar.approval_code = ?
            """,
            (code,)
        )
    
    @staticmethod
    def approve(code: str, admin_id: str):
        now = datetime.now().isoformat()
        db.execute(
            """UPDATE approval_requests 
               SET status = 'approved', resolved_at = ?, resolved_by = ?
               WHERE approval_code = ?""",
            (now, admin_id, code)
        )
    
    @staticmethod
    def reject(code: str, admin_id: str, reason: str = None):
        now = datetime.now().isoformat()
        db.execute(
            """UPDATE approval_requests 
               SET status = 'rejected', resolved_at = ?, resolved_by = ?, rejection_reason = ?
               WHERE approval_code = ?""",
            (now, admin_id, reason, code)
        )
    
    @staticmethod
    def get_all():
        return db.fetch_all(
            """
            SELECT ar.*, si.name as item_name, p.username
            FROM approval_requests ar
            JOIN shop_items si ON ar.item_id = si.item_id
            JOIN players p ON ar.player_id = p.id
            ORDER BY ar.requested_at DESC
            LIMIT 50
            """
        )
    
    @staticmethod
    def count_active_uses(item_id: str) -> int:
        """Count total active uses across all players for a pass type."""
        result = db.fetch_one(
            """
            SELECT COALESCE(SUM(usage_remaining), 0) as total
            FROM approval_requests
            WHERE item_id = ? AND status = 'approved' AND usage_remaining > 0
            """,
            (item_id,)
        )
        return result['total'] if result else 0
    
    @staticmethod
    def count_active_accounts(item_id: str) -> int:
        """Count how many unique accounts have active uses for a pass."""
        result = db.fetch_one(
            """
            SELECT COUNT(DISTINCT player_id) as total
            FROM approval_requests
            WHERE item_id = ? AND status = 'approved' AND usage_remaining > 0
            """,
            (item_id,)
        )
        return result['total'] if result else 0
    
    @staticmethod
    def use_code(code: str) -> bool:
        """Decrement usage count. Returns True if still has uses remaining."""
        req = db.fetch_one(
            "SELECT usage_remaining FROM approval_requests WHERE approval_code = ? AND status = 'approved'",
            (code,)
        )
        if not req or req['usage_remaining'] <= 0:
            return False
        
        db.execute(
            "UPDATE approval_requests SET usage_remaining = usage_remaining - 1 WHERE approval_code = ?",
            (code,)
        )
        return True
    
    @staticmethod
    def get_usage(code: str):
        """Get usage info for a code"""
        return db.fetch_one(
            "SELECT usage_limit, usage_remaining FROM approval_requests WHERE approval_code = ?",
            (code,)
        )
    
    @staticmethod
    def set_pinned_message(code: str, message_id: str):
        """Store the pinned message ID for this approval"""
        db.execute(
            "UPDATE approval_requests SET pinned_message_id = ? WHERE approval_code = ?",
            (message_id, code)
        )