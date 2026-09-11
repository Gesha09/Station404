import uuid
from datetime import datetime
from database.db import db

class PlayerRepository:
    @staticmethod
    def get_by_discord_id(discord_id: str):
        return db.fetch_one(
            "SELECT * FROM players WHERE discord_id = ?",
            (discord_id,)
        )
    
    @staticmethod
    def create(discord_id: str, username: str, profile_url: str):
        player_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        db.execute(
            """
            INSERT INTO players (id, discord_id, username, profile_url, registered_at, last_active_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (player_id, discord_id, username, profile_url, now, now)
        )
        
        return db.fetch_one("SELECT * FROM players WHERE id = ?", (player_id,))
    
    @staticmethod
    def update_balance(player_id: str, pocket_credits: int = None, vault_bonds: int = None):
        if pocket_credits is not None:
            db.execute(
                "UPDATE players SET pocket_credits = ? WHERE id = ?",
                (pocket_credits, player_id)
            )
        if vault_bonds is not None:
            db.execute(
                "UPDATE players SET vault_bonds = ? WHERE id = ?",
                (vault_bonds, player_id)
            )
    
    @staticmethod
    def set_on_duty(player_id: str, is_on_duty: bool):
        now = datetime.now().isoformat()
        db.execute(
            "UPDATE players SET is_on_duty = ?, last_active_at = ? WHERE id = ?",
            (1 if is_on_duty else 0, now, player_id)
        )
    
    @staticmethod
    def get_all_on_duty():
        return db.fetch_all("SELECT * FROM players WHERE is_on_duty = 1")
    
    @staticmethod
    def get_all():
        return db.fetch_all("SELECT * FROM players")
    
    @staticmethod
    def update_registration_dm(player_id: str, dm_id: str):
        db.execute(
            "UPDATE players SET registration_dm_id = ? WHERE id = ?",
            (dm_id, player_id)
        )
    
    @staticmethod
    def update_room(player_id: str, room: str):
        db.execute(
            "UPDATE players SET current_room = ? WHERE id = ?",
            (room, player_id)
        )
    
    @staticmethod
    def update_cooldown(player_id: str, action: str, timestamp: str):
        column = f"last_{action}_at"
        db.execute(
            f"UPDATE players SET {column} = ? WHERE id = ?",
            (timestamp, player_id)
        )
    
    @staticmethod
    def increment_action_steps(player_id: str):
        db.execute(
            "UPDATE players SET action_steps_used = action_steps_used + 1 WHERE id = ?",
            (player_id,)
        )
    
    @staticmethod
    def reset_action_steps(player_id: str):
        db.execute(
            "UPDATE players SET action_steps_used = 0 WHERE id = ?",
            (player_id,)
        )
    
    @staticmethod
    def set_jail_release(player_id: str, release_time: str):
        db.execute(
            "UPDATE players SET jail_release_at = ? WHERE id = ?",
            (release_time, player_id)
        )
    
    @staticmethod
    def is_in_jail(player: dict) -> bool:
        if not player['jail_release_at']:
            return False
        try:
            release_time = datetime.fromisoformat(player['jail_release_at'])
            return release_time > datetime.now()
        except:
            return False

    @staticmethod
    def kill_player(player_id: str):
        """Mark player as dead"""
        db.execute(
            "UPDATE players SET is_alive = 0 WHERE id = ?",
            (player_id,)
        )
    
    @staticmethod
    def set_respawn_time(player_id: str, respawn_time: str):
        """Set when player can respawn"""
        db.execute(
            "UPDATE players SET respawn_at = ? WHERE id = ?",
            (respawn_time, player_id)
        )
    
    @staticmethod
    def respawn_player(player_id: str):
        """Respawn player in cafeteria"""
        now = datetime.now().isoformat()
        db.execute(
            """
            UPDATE players 
            SET is_alive = 1, respawn_at = NULL, current_room = 'cafeteria',
                pocket_credits = 0, last_active_at = ?
            WHERE id = ?
            """,
            (now, player_id)
        )
    
    @staticmethod
    def increment_jail_offense(player_id: str):
        """Increment jail offense count"""
        db.execute(
            "UPDATE players SET jail_offense_count = jail_offense_count + 1 WHERE id = ?",
            (player_id,)
        )
    
    @staticmethod
    def get_all_dead():
        """Get all dead players"""
        return db.fetch_all("SELECT * FROM players WHERE is_alive = 0")
    
    @staticmethod
    def get_all_jailed():
        """Get all jailed players"""
        return db.fetch_all(
            "SELECT * FROM players WHERE jail_release_at IS NOT NULL"
        )

    @staticmethod
    def update_spawn_protection(player_id: str, protected_until: str):
        db.execute(
            "UPDATE players SET spawn_protected_until = ? WHERE id = ?",
            (protected_until, player_id)
        )
    
    @staticmethod
    def reset_first_action(player_id: str):
        db.execute(
            "UPDATE players SET first_action_taken = 0 WHERE id = ?",
            (player_id,)
        )
    
    @staticmethod
    def mark_first_action(player_id: str):
        db.execute(
            "UPDATE players SET first_action_taken = 1, spawn_protected_until = NULL WHERE id = ?",
            (player_id,)
        )
    
    @staticmethod
    def is_spawn_protected(player) -> bool:
        """Check if player is currently spawn protected"""
        try:
            protected_until = player['spawn_protected_until']
            first_action = player['first_action_taken']
        except (KeyError, IndexError):
            return False
        
        if not protected_until:
            return False
        if first_action:
            return False
        
        try:
            from datetime import datetime
            protected_until_dt = datetime.fromisoformat(protected_until)
            return datetime.now() < protected_until_dt
        except:
            return False