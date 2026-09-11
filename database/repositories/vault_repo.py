import uuid
from datetime import datetime
from database.db import db

class VaultRepository:
    @staticmethod
    def deposit(player_id: str, discord_id: str, amount: int) -> dict:
        """Deposit credits from pocket to vault. Returns transaction info."""
        from database.repositories.player_repo import PlayerRepository
        
        player = db.fetch_one("SELECT * FROM players WHERE id = ?", (player_id,))
        if not player:
            return {"success": False, "message": "Player not found"}
        
        if player['pocket_credits'] < amount:
            return {"success": False, "message": "Not enough pocket credits"}
        
        if amount < 10:
            return {"success": False, "message": "Minimum deposit is 10 credits"}
        
        new_pocket = player['pocket_credits'] - amount
        new_vault = player['vault_bonds'] + amount
        
        PlayerRepository.update_balance(player_id, 
                                        pocket_credits=new_pocket, 
                                        vault_bonds=new_vault)
        
        # Log transaction
        tx_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        db.execute(
            """INSERT INTO vault_transactions 
               (id, player_id, discord_id, transaction_type, amount, balance_after, description, created_at)
               VALUES (?, ?, ?, 'deposit', ?, ?, ?, ?)""",
            (tx_id, player_id, discord_id, amount, new_vault, 
             f"Deposited {amount} credits", now)
        )
        
        return {
            "success": True,
            "amount": amount,
            "new_pocket": new_pocket,
            "new_vault": new_vault
        }
    
    @staticmethod
    def withdraw(player_id: str, discord_id: str, amount: int) -> dict:
        """Withdraw credits from vault to pocket."""
        from database.repositories.player_repo import PlayerRepository
        
        player = db.fetch_one("SELECT * FROM players WHERE id = ?", (player_id,))
        if not player:
            return {"success": False, "message": "Player not found"}
        
        if player['vault_bonds'] < amount:
            return {"success": False, "message": "Not enough vault balance"}
        
        if amount < 10:
            return {"success": False, "message": "Minimum withdraw is 10 credits"}
        
        new_pocket = player['pocket_credits'] + amount
        new_vault = player['vault_bonds'] - amount
        
        PlayerRepository.update_balance(player_id,
                                        pocket_credits=new_pocket,
                                        vault_bonds=new_vault)
        
        tx_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        db.execute(
            """INSERT INTO vault_transactions 
               (id, player_id, discord_id, transaction_type, amount, balance_after, description, created_at)
               VALUES (?, ?, ?, 'withdraw', ?, ?, ?, ?)""",
            (tx_id, player_id, discord_id, amount, new_vault,
             f"Withdrew {amount} credits", now)
        )
        
        return {
            "success": True,
            "amount": amount,
            "new_pocket": new_pocket,
            "new_vault": new_vault
        }
    
    @staticmethod
    def get_history(player_id: str, limit: int = 10):
        """Get recent vault transactions for a player"""
        return db.fetch_all(
            """SELECT * FROM vault_transactions 
               WHERE player_id = ? 
               ORDER BY created_at DESC LIMIT ?""",
            (player_id, limit)
        )
    
    @staticmethod
    def apply_interest(round_id: str):
        """Apply interest to all vault holders at round end. Returns list of beneficiaries."""
        from database.repositories.config_repo import ConfigRepository
        
        rate = ConfigRepository.get_int("vault_interest_rate", 5)
        if rate <= 0:
            return []
        
        players = db.fetch_all(
            "SELECT * FROM players WHERE vault_bonds > 0"
        )
        
        beneficiaries = []
        now = datetime.now().isoformat()
        
        for player in players:
            interest = int(player['vault_bonds'] * (rate / 100))
            if interest <= 0:
                continue
            
            new_vault = player['vault_bonds'] + interest
            db.execute(
                "UPDATE players SET vault_bonds = ? WHERE id = ?",
                (new_vault, player['id'])
            )
            
            tx_id = str(uuid.uuid4())
            db.execute(
                """INSERT INTO vault_transactions 
                   (id, player_id, discord_id, transaction_type, amount, balance_after, description, created_at)
                   VALUES (?, ?, ?, 'interest', ?, ?, ?, ?)""",
                (tx_id, player['id'], player['discord_id'], interest, new_vault,
                 f"Round interest ({rate}%)", now)
            )
            
            beneficiaries.append({
                "discord_id": player['discord_id'],
                "username": player['username'],
                "interest": interest,
                "new_vault": new_vault
            })
        
        return beneficiaries
    
    @staticmethod
    def get_top_holders(limit: int = 10):
        """Get top vault holders"""
        return db.fetch_all(
            """SELECT discord_id, username, vault_bonds 
               FROM players 
               WHERE vault_bonds > 0 
               ORDER BY vault_bonds DESC LIMIT ?""",
            (limit,)
        )