from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.permissions import is_admin
from database.repositories.config_repo import ConfigRepository
from bot.core.game_manager import format_timestamp

CONFIG_KEYS = {
    "prep_phase_duration": int,
    "round_duration": int,
    "imposters_count": int,
    "imposter_rotation_interval": int,
    "witness_timer": int,
    "jail_time_1": int,
    "jail_time_2": int,
    "jail_time_3": int,
    "daily_tax": int,
    "robbery_cut": int,
    "kill_steal": int,
    "task_reward_min": int,
    "task_reward_max": int,
    "move_cooldown": int,
    "search_cooldown": int,
    "rob_cooldown": int,
    "task_cooldown": int,
    "kill_cooldown": int,
    "kill_cooldown_final": int,
    "loot_spawn_interval": int,
    "loot_amount_min": int,
    "loot_amount_max": int,
    "loot_despawn_time": int,
    "final_phase_kill_pct": int,
}

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="startgame", description="Start a new round (Admin only)")
    @is_admin()
    async def startgame(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "🧹 Clearing channel and starting round...",
            ephemeral=True
        )
        
        self.bot.game_manager.set_announcement_channel(interaction.channel_id)
        result = await self.bot.game_manager.start_game()
        
        if not result["success"]:
            await interaction.channel.send(result["message"])
            return
        
        mins, secs = divmod(result["prep_duration"], 60)
        
        cleared = result.get("cleared_messages", 0)
        clear_info = ""
        if cleared == -1:
            clear_info = "\n⚠️ *Channel not cleared (missing permission)*"
        elif cleared > 0:
            clear_info = f"\n🧹 *Cleared {cleared} messages*"
        
        await interaction.channel.send(
            f"🎮 **Round starting!**{clear_info}\n"
            f"⏱️ Preparation phase: {mins}:{secs:02d}\n"
            f"Use `/clockin` to join!"
        )
    
    @app_commands.command(name="forcestop", description="Force end the current round (Admin only)")
    @is_admin()
    async def forcestop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.bot.game_manager.set_announcement_channel(interaction.channel_id)
        result = await self.bot.game_manager.force_stop("admin")
        await interaction.followup.send(result["message"])
    
    @app_commands.command(name="config", description="View or change game settings (Admin only)")
    @is_admin()
    @app_commands.describe(
        action="view or set",
        key="Setting name",
        value="New value (only for 'set')"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="view", value="view"),
        app_commands.Choice(name="set", value="set"),
    ])
    async def config(self, interaction: discord.Interaction, action: app_commands.Choice[str], 
                     key: str = None, value: str = None):
        await interaction.response.defer(ephemeral=True)
        
        if action.value == "view":
            all_config = ConfigRepository.get_all()
            embed = discord.Embed(title="⚙️ Game Configuration", color=discord.Color.orange())
            
            for row in all_config:
                embed.add_field(
                    name=f"`{row['key']}`",
                    value=f"**{row['value']}**\n*{row['description']}*",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if not key or value is None:
            await interaction.followup.send("❌ Must provide both `key` and `value`.", ephemeral=True)
            return
        
        if key not in CONFIG_KEYS:
            await interaction.followup.send(
                f"❌ Unknown config key: `{key}`\nValid: {', '.join(f'`{k}`' for k in CONFIG_KEYS.keys())}",
                ephemeral=True
            )
            return
        
        try:
            converted = CONFIG_KEYS[key](value)
        except ValueError:
            await interaction.followup.send(f"❌ Invalid value for `{key}`.", ephemeral=True)
            return
        
        ConfigRepository.set_value(key, converted)
        await interaction.followup.send(f"✅ Updated `{key}` to **{converted}**", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))