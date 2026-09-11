import uuid
from datetime import datetime
from database.db import db

class ShopRepository:
    @staticmethod
    def get_all_items():
        return db.fetch_all("SELECT * FROM shop_items WHERE is_available = 1 ORDER BY rarity, price")
    
    @staticmethod
    def get_item_by_id(item_id: str):
        return db.fetch_one("SELECT * FROM shop_items WHERE item_id = ?", (item_id,))
    
    @staticmethod
    def buy_item(item_id: str):
        """Decrease stock by 1 if stock-limited. Returns True if successful."""
        item = ShopRepository.get_item_by_id(item_id)
        if not item:
            return False
        
        if item['stock_limit'] is not None:
            if item['current_stock'] is None or item['current_stock'] <= 0:
                return False
            db.execute(
                "UPDATE shop_items SET current_stock = current_stock - 1 WHERE item_id = ?",
                (item_id,)
            )
        return True
    
    @staticmethod
    def get_loot_table_items():
        """Get all items that can drop in mystery boxes"""
        return db.fetch_all(
            "SELECT * FROM shop_items WHERE can_drop_in_loot = 1 AND is_available = 1"
        )
    
    @staticmethod
    def create_item(item_id: str, name: str, description: str, price: int, 
                    rarity: str = "common", item_type: str = "consumable",
                    stock_limit: int = None, can_drop_in_loot: bool = False,
                    loot_weight: int = 1, requires_approval: bool = False):
        new_id = str(uuid.uuid4())
        current_stock = stock_limit if stock_limit is not None else None
        
        db.execute(
            """INSERT INTO shop_items 
               (id, item_id, name, description, price, rarity, item_type, is_available, 
                stock_limit, current_stock, can_drop_in_loot, loot_weight, requires_approval, is_approved)
               VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)""",
            (new_id, item_id, name, description, price, rarity, item_type,
             stock_limit, current_stock, 1 if can_drop_in_loot else 0, loot_weight,
             1 if requires_approval else 0, 0)
        )
    
    @staticmethod
    def update_item(item_id: str, **kwargs):
        """Update item fields"""
        allowed = ["name", "description", "price", "rarity", "is_available", 
                   "stock_limit", "current_stock", "can_drop_in_loot", "loot_weight",
                   "requires_approval", "is_approved"]
        
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return
        
        values.append(item_id)
        db.execute(
            f"UPDATE shop_items SET {', '.join(updates)} WHERE item_id = ?",
            tuple(values)
        )
    
    @staticmethod
    def approve_item(item_id: str):
        db.execute(
            "UPDATE shop_items SET is_approved = 1 WHERE item_id = ?",
            (item_id,)
        )