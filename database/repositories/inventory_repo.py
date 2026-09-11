import uuid
from datetime import datetime
from database.db import db

class InventoryRepository:
    @staticmethod
    def get_player_inventory(player_id: str):
        """Get all items for a player with item details"""
        return db.fetch_all(
            """
            SELECT pi.*, si.name, si.description, si.rarity, si.item_type, si.requires_approval, si.is_approved
            FROM player_inventory pi
            JOIN shop_items si ON pi.item_id = si.item_id
            WHERE pi.player_id = ?
            ORDER BY si.rarity, si.name
            """,
            (player_id,)
        )
    
    @staticmethod
    def get_player_item(player_id: str, item_id: str):
        return db.fetch_one(
            "SELECT * FROM player_inventory WHERE player_id = ? AND item_id = ?",
            (player_id, item_id)
        )
    
    @staticmethod
    def add_item(player_id: str, item_id: str, quantity: int = 1):
        """Add item to player inventory (or increase quantity)"""
        existing = InventoryRepository.get_player_item(player_id, item_id)
        now = datetime.now().isoformat()
        
        if existing:
            db.execute(
                "UPDATE player_inventory SET quantity = quantity + ? WHERE id = ?",
                (quantity, existing['id'])
            )
        else:
            db.execute(
                """INSERT INTO player_inventory (id, player_id, item_id, quantity, acquired_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), player_id, item_id, quantity, now)
            )
    
    @staticmethod
    def remove_item(player_id: str, item_id: str, quantity: int = 1):
        """Remove item from inventory. Returns True if successful."""
        existing = InventoryRepository.get_player_item(player_id, item_id)
        if not existing or existing['quantity'] < quantity:
            return False
        
        if existing['quantity'] == quantity:
            db.execute("DELETE FROM player_inventory WHERE id = ?", (existing['id'],))
        else:
            db.execute(
                "UPDATE player_inventory SET quantity = quantity - ? WHERE id = ?",
                (quantity, existing['id'])
            )
        return True
    
    @staticmethod
    def has_item(player_id: str, item_id: str, quantity: int = 1) -> bool:
        item = InventoryRepository.get_player_item(player_id, item_id)
        return item is not None and item['quantity'] >= quantity