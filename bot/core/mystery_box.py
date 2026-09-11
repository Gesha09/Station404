import random
from database.repositories.shop_repo import ShopRepository
from database.repositories.inventory_repo import InventoryRepository
from database.repositories.player_repo import PlayerRepository
from database.repositories.approval_repo import ApprovalRepository
from database.db import db

# Credit drop tiers (bonus credits on top of items)
CREDIT_DROPS = [
    {"amount": 50, "weight": 15, "label": "💰 50 Credits"},
    {"amount": 100, "weight": 8, "label": "💰 100 Credits"},
    {"amount": 250, "weight": 3, "label": "💰 250 Credits"},
    {"amount": 500, "weight": 1, "label": "💰 500 Credits"},
]

# Rarity display info
RARITY_INFO = {
    "common": {"emoji": "⚪", "color": 0x888888, "label": "Common"},
    "rare": {"emoji": "🔵", "color": 0x4488ff, "label": "Rare"},
    "epic": {"emoji": "🟣", "color": 0xaa44ff, "label": "Epic"},
    "legendary": {"emoji": "🟡", "color": 0xffaa00, "label": "Legendary"},
}

class MysteryBoxService:
    """Handles mystery box opening logic with weighted drops"""
    
    @staticmethod
    def get_drop_rates() -> dict:
        """Calculate drop rates for display"""
        items = ShopRepository.get_loot_table_items()
        if not items:
            return {"items": [], "credits": [], "total_weight": 0}
        
        total_weight = sum(item['loot_weight'] for item in items)
        credit_weight = sum(c['weight'] for c in CREDIT_DROPS)
        grand_total = total_weight + credit_weight
        
        item_rates = []
        for item in items:
            chance = (item['loot_weight'] / grand_total) * 100
            rarity = RARITY_INFO.get(item['rarity'], RARITY_INFO['common'])
            item_rates.append({
                "name": item['name'],
                "rarity": item['rarity'],
                "emoji": rarity['emoji'],
                "chance": round(chance, 2)
            })
        
        credit_rates = []
        for credit in CREDIT_DROPS:
            chance = (credit['weight'] / grand_total) * 100
            credit_rates.append({
                "label": credit['label'],
                "chance": round(chance, 2)
            })
        
        return {
            "items": item_rates,
            "credits": credit_rates,
            "total_weight": grand_total
        }
    
    @staticmethod
    def open_box(player_id: str, discord_id: str) -> dict:
        """Open a mystery box and return structured loot data"""
        player_data = PlayerRepository.get_by_discord_id(discord_id)
        if not player_data:
            return {"error": "Player not found!"}
        
        # NEW: Remove the mystery box from inventory
        if not InventoryRepository.remove_item(player_id, 'mystery_box', 1):
            return {"error": "You don't have a mystery box to open!"}
        
        # Update boxes opened counter
        db.execute(
            "UPDATE players SET mystery_boxes_opened = mystery_boxes_opened + 1 WHERE id = ?",
            (player_id,)
        )
        
        loot_items = ShopRepository.get_loot_table_items()
        
        if not loot_items:
            return {"error": "No loot available!"}
        
        # Calculate total weight
        total_weight = sum(item['loot_weight'] for item in loot_items)
        roll = random.randint(1, total_weight)
        
        cumulative = 0
        won_item = None
        for item in loot_items:
            cumulative += item['loot_weight']
            if roll <= cumulative:
                won_item = item
                break
        
        if not won_item:
            won_item = loot_items[0]
        
        # Add won item to inventory
        InventoryRepository.add_item(player_id, won_item['item_id'], 1)
        
        # Return structured data
        result = {
            "item_id": won_item['item_id'],
            "item_name": won_item['name'],
            "rarity": won_item['rarity'],
            "requires_approval": bool(won_item['requires_approval']),
            "code": None
        }
        
        # If item requires approval, generate code
        if won_item['requires_approval']:
            code = ApprovalRepository.create_request(player_id, discord_id, won_item['item_id'])
            result["code"] = code
        
        return result