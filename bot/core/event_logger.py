import uuid
import json
from datetime import datetime
from database.db import db

class EventLogger:
    """Logs significant game events for the admin dashboard audit trail"""
    
    @staticmethod
    def log(event_type: str, actor_id: str = None, actor_name: str = None,
            target_id: str = None, target_name: str = None, 
            details: dict = None, round_id: str = None):
        """Log an event to the database"""
        event_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        details_json = json.dumps(details or {})
        
        db.execute(
            """INSERT INTO event_log 
               (id, timestamp, event_type, actor_id, actor_name, target_id, target_name, details, round_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, now, event_type, actor_id, actor_name, 
             target_id, target_name, details_json, round_id)
        )
    
    # ============ CONVENIENCE METHODS ============
    
    @staticmethod
    def player_registered(discord_id: str, username: str):
        EventLogger.log(
            event_type="player_registered",
            actor_id=discord_id,
            actor_name=username,
            details={"action": "new_registration"}
        )
    
    @staticmethod
    def round_started(round_id: str, player_count: int):
        EventLogger.log(
            event_type="round_started",
            details={"player_count": player_count},
            round_id=round_id
        )
    
    @staticmethod
    def round_ended(round_id: str, reason: str, winner_id: str = None, winner_name: str = None):
        EventLogger.log(
            event_type="round_ended",
            target_id=winner_id,
            target_name=winner_name,
            details={"reason": reason},
            round_id=round_id
        )
    
    @staticmethod
    def imposter_assigned(round_id: str, imposter_id: str, imposter_name: str, phase: int):
        EventLogger.log(
            event_type="imposter_assigned",
            target_id=imposter_id,
            target_name=imposter_name,
            details={"phase": phase},
            round_id=round_id
        )
    
    @staticmethod
    def player_killed(round_id: str, killer_id: str, killer_name: str,
                      victim_id: str, victim_name: str, room: str, stolen: int):
        EventLogger.log(
            event_type="player_killed",
            actor_id=killer_id,
            actor_name=killer_name,
            target_id=victim_id,
            target_name=victim_name,
            details={"room": room, "stolen": stolen},
            round_id=round_id
        )
    
    @staticmethod
    def player_robbed(round_id: str, robber_id: str, robber_name: str,
                      victim_id: str, victim_name: str, room: str, stolen: int):
        EventLogger.log(
            event_type="player_robbed",
            actor_id=robber_id,
            actor_name=robber_name,
            target_id=victim_id,
            target_name=victim_name,
            details={"room": room, "stolen": stolen},
            round_id=round_id
        )
    
    @staticmethod
    def player_jailed(round_id: str, player_id: str, player_name: str,
                      duration: int, offense_count: int, reported_by: str = None):
        EventLogger.log(
            event_type="player_jailed",
            target_id=player_id,
            target_name=player_name,
            actor_id=reported_by,
            details={"duration": duration, "offense_count": offense_count},
            round_id=round_id
        )
    
    @staticmethod
    def item_purchased(player_id: str, player_name: str, 
                       item_id: str, item_name: str, quantity: int, total_cost: int):
        EventLogger.log(
            event_type="item_purchased",
            actor_id=player_id,
            actor_name=player_name,
            target_id=item_id,
            target_name=item_name,
            details={"quantity": quantity, "total_cost": total_cost}
        )
    
    @staticmethod
    def loot_spawned(round_id: str, room: str, amount: int):
        EventLogger.log(
            event_type="loot_spawned",
            details={"room": room, "amount": amount},
            round_id=round_id
        )
    
    @staticmethod
    def admin_action(admin_id: str, admin_name: str, action: str, details: dict = None):
        EventLogger.log(
            event_type="admin_action",
            actor_id=admin_id,
            actor_name=admin_name,
            details={"action": action, **(details or {})}
        )