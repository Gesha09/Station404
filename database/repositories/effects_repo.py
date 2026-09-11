import uuid
from datetime import datetime
from database.db import db

class EffectsRepository:
    """Manages active effects on players (shield, rob proof, stealth, etc.)"""
    
    # Effect types that use player flags (simple boolean)
    FLAG_EFFECTS = {
        "shield": "has_shield",
        "rob_proof": "has_rob_proof",
        "stealth_rob": "has_stealth_rob",
        "bank_pass": "has_bank_pass",
    }
    
    @staticmethod
    def apply_effect(player_id: str, effect_type: str, uses: int = 1, expires_seconds: int = None):
        """Apply an effect to a player"""
        if effect_type in EffectsRepository.FLAG_EFFECTS:
            # Use simple flag
            flag = EffectsRepository.FLAG_EFFECTS[effect_type]
            db.execute(f"UPDATE players SET {flag} = 1 WHERE id = ?", (player_id,))
        else:
            # Use active_effects table for complex effects
            expires_at = None
            if expires_seconds:
                expires_at = (datetime.now() + __import__('datetime').timedelta(seconds=expires_seconds)).isoformat()
            
            existing = db.fetch_one(
                "SELECT id FROM active_effects WHERE player_id = ? AND effect_type = ?",
                (player_id, effect_type)
            )
            
            if existing:
                db.execute(
                    "UPDATE active_effects SET uses_remaining = uses_remaining + ? WHERE id = ?",
                    (uses, existing['id'])
                )
            else:
                db.execute(
                    """INSERT INTO active_effects 
                       (id, player_id, effect_type, uses_remaining, expires_at, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), player_id, effect_type, uses, expires_at, datetime.now().isoformat())
                )
    
    @staticmethod
    def consume_effect(player_id: str, effect_type: str) -> bool:
        """Consume one use of an effect. Returns True if effect was active."""
        if effect_type in EffectsRepository.FLAG_EFFECTS:
            flag = EffectsRepository.FLAG_EFFECTS[effect_type]
            player = db.fetch_one(f"SELECT {flag} FROM players WHERE id = ?", (player_id,))
            if not player or not player[flag]:
                return False
            db.execute(f"UPDATE players SET {flag} = 0 WHERE id = ?", (player_id,))
            return True
        
        # Complex effect
        effect = db.fetch_one(
            "SELECT * FROM active_effects WHERE player_id = ? AND effect_type = ?",
            (player_id, effect_type)
        )
        if not effect:
            return False
        
        if effect['uses_remaining'] <= 1:
            db.execute("DELETE FROM active_effects WHERE id = ?", (effect['id'],))
        else:
            db.execute(
                "UPDATE active_effects SET uses_remaining = uses_remaining - 1 WHERE id = ?",
                (effect['id'],)
            )
        return True
    
    @staticmethod
    def has_effect(player_id: str, effect_type: str) -> bool:
        """Check if player has an active effect"""
        if effect_type in EffectsRepository.FLAG_EFFECTS:
            flag = EffectsRepository.FLAG_EFFECTS[effect_type]
            player = db.fetch_one(f"SELECT {flag} FROM players WHERE id = ?", (player_id,))
            return bool(player and player[flag])
        
        effect = db.fetch_one(
            "SELECT * FROM active_effects WHERE player_id = ? AND effect_type = ?",
            (player_id, effect_type)
        )
        if not effect:
            return False
        
        # Check expiration
        if effect['expires_at']:
            try:
                expires = datetime.fromisoformat(effect['expires_at'])
                if datetime.now() > expires:
                    db.execute("DELETE FROM active_effects WHERE id = ?", (effect['id'],))
                    return False
            except:
                pass
        
        return effect['uses_remaining'] > 0
    
    @staticmethod
    def get_player_effects(player_id: str) -> list:
        """Get all active effects for a player"""
        effects = []
        
        # Check flag effects
        player = db.fetch_one("SELECT * FROM players WHERE id = ?", (player_id,))
        if player:
            for effect_type, flag in EffectsRepository.FLAG_EFFECTS.items():
                if player[flag]:
                    effects.append({
                        "type": effect_type,
                        "uses": 1,
                        "permanent": True
                    })
        
        # Check table effects
        table_effects = db.fetch_all(
            "SELECT * FROM active_effects WHERE player_id = ?",
            (player_id,)
        )
        for e in table_effects:
            effects.append({
                "type": e['effect_type'],
                "uses": e['uses_remaining'],
                "expires_at": e['expires_at']
            })
        
        return effects
    
    @staticmethod
    def clear_all_effects(player_id: str):
        """Clear all effects for a player (used on round end)"""
        for flag in EffectsRepository.FLAG_EFFECTS.values():
            db.execute(f"UPDATE players SET {flag} = 0 WHERE id = ?", (player_id,))
        
        db.execute("DELETE FROM active_effects WHERE player_id = ?", (player_id,))