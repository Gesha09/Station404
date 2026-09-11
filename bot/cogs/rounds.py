import discord
from discord.ext import commands
from discord import app_commands
from database.repositories.player_repo import PlayerRepository

class RoundsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="clockin", description="Clock in to join the next round")
    async def clockin(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player:
            await interaction.followup.send("❌ Not registered! Use `/register` first.", ephemeral=True)
            return
        
        if player['is_on_duty']:
            await interaction.followup.send("❌ You're already on duty!", ephemeral=True)
            return
        
        gm = self.bot.game_manager
        if gm.state.status not in ["idle", "prep"]:
            await interaction.followup.send("❌ Can only clock in before a round starts!", ephemeral=True)
            return
        
        # Assign random spawn room
        import random
        spawn_rooms = ["cafeteria", "medbay", "electrical", "reactor", "security", 
                       "admin", "navigation", "weapons", "shields", "comms"]
        spawn_room = random.choice(spawn_rooms)
        
        # Set spawn protection (20 seconds from now, or until first action)
        from datetime import datetime, timedelta
        protection_until = (datetime.now() + timedelta(seconds=20)).isoformat()
        
        PlayerRepository.set_on_duty(player['id'], True)
        PlayerRepository.update_room(player['id'], spawn_room)
        PlayerRepository.update_spawn_protection(player['id'], protection_until)
        PlayerRepository.reset_first_action(player['id'])
        
        room_name = gm.get_room_name(spawn_room)
        
        await interaction.followup.send(
            f"✅ You're now on duty!\n"
            f"📍 Spawn location: **{room_name}**\n"
            f"🛡️ Spawn protection: **20 seconds** (or until your first action)\n\n"
            f"Wait for the round to start!",
            ephemeral=True
        )
    
    @app_commands.command(name="offduty", description="Leave the game (go Off-Duty)")
    async def offduty(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        result = await self.bot.game_manager.clock_out(str(interaction.user.id))
        await interaction.followup.send(result["message"], ephemeral=True)
    
    @app_commands.command(name="round", description="View current round status")
    async def round_status(self, interaction: discord.Interaction):
        status = self.bot.game_manager.get_status()
        
        embed = discord.Embed(
            title="🎮 Round Status",
            description=status["message"],
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="votestop", description="Vote to end the current round")
    async def votestop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        result = await self.bot.game_manager.vote_stop(str(interaction.user.id))
        
        if not result["success"]:
            await interaction.followup.send(result["message"])
            return
        
        if result["ended"]:
            await interaction.followup.send(result["message"])
        else:
            await interaction.followup.send(
                f"🗳️ {interaction.user.mention} voted to stop the round. "
                f"({result['votes']}/{result['needed']} needed)"
            )

async def setup(bot):
    await bot.add_cog(RoundsCog(bot))