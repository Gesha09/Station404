import discord
from discord.ext import commands
from discord import app_commands
from database.repositories.player_repo import PlayerRepository
from database.repositories.vault_repo import VaultRepository
from bot.core.event_logger import EventLogger
import uuid
from datetime import datetime
from database.db import db

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="give", description="Give Pocket Credits to another player")
    @app_commands.describe(user="The player to give credits to", amount="Amount to give")
    async def give(self, interaction: discord.Interaction, user: discord.User, amount: int):
        await interaction.response.defer(ephemeral=True)
        
        sender = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not sender:
            await interaction.followup.send("❌ Not registered!", ephemeral=True)
            return
        
        if str(user.id) == str(interaction.user.id):
            await interaction.followup.send("❌ You can't give credits to yourself!", ephemeral=True)
            return
        
        receiver = PlayerRepository.get_by_discord_id(str(user.id))
        if not receiver:
            await interaction.followup.send("❌ That player isn't registered!", ephemeral=True)
            return
        
        if amount < 1:
            await interaction.followup.send("❌ Amount must be at least 1!", ephemeral=True)
            return
        
        if sender['pocket_credits'] < amount:
            await interaction.followup.send(
                f"❌ Not enough credits! You have {sender['pocket_credits']}.",
                ephemeral=True
            )
            return
        
        # Execute transfer
        new_sender_balance = sender['pocket_credits'] - amount
        new_receiver_balance = receiver['pocket_credits'] + amount
        
        PlayerRepository.update_balance(sender['id'], pocket_credits=new_sender_balance)
        PlayerRepository.update_balance(receiver['id'], pocket_credits=new_receiver_balance)
        
        # Log transactions
        now = datetime.now().isoformat()
        db.execute(
            """INSERT INTO vault_transactions 
               (id, player_id, discord_id, transaction_type, amount, balance_after, description, created_at)
               VALUES (?, ?, ?, 'sent', ?, ?, ?, ?)""",
            (str(uuid.uuid4()), sender['id'], str(interaction.user.id), 
             -amount, new_sender_balance, f"Sent to {receiver['username']}", now)
        )
        db.execute(
            """INSERT INTO vault_transactions 
               (id, player_id, discord_id, transaction_type, amount, balance_after, description, created_at)
               VALUES (?, ?, ?, 'received', ?, ?, ?, ?)""",
            (str(uuid.uuid4()), receiver['id'], str(user.id),
             amount, new_receiver_balance, f"Received from {sender['username']}", now)
        )
        
        EventLogger.log(
            event_type="credits_transferred",
            actor_id=str(interaction.user.id),
            actor_name=sender['username'],
            target_id=str(user.id),
            target_name=receiver['username'],
            details={"amount": amount}
        )
        
        await interaction.followup.send(
            f"✅ **Sent {amount} 💰 to {receiver['username']}!**\n\n"
            f"Your balance: {new_sender_balance} 💰",
            ephemeral=True
        )
        
        # Notify receiver
        try:
            receiver_user = await self.bot.fetch_user(int(user.id))
            await receiver_user.send(
                f"💰 **You received {amount} credits!**\n\n"
                f"From: {sender['username']}\n"
                f"New balance: {new_receiver_balance} 💰"
            )
        except:
            pass
    
    @app_commands.command(name="send", description="Alias for /give — send credits to a player")
    @app_commands.describe(user="The player to send credits to", amount="Amount to send")
    async def send(self, interaction: discord.Interaction, user: discord.User, amount: int):
        # Just call give
        await self.give(interaction, user, amount)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))