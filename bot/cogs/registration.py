import discord
from discord.ext import commands
from discord import app_commands
from database.repositories.player_repo import PlayerRepository
from shared.config import settings

class RegistrationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="register", description="Create your game profile")
    async def register(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        existing = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if existing:
            await interaction.followup.send(
                f"✅ You're already registered!\nProfile: {existing['profile_url']}",
                ephemeral=True
            )
            return
        
        profile_url = f"{settings.WEB_URL}/profile/{interaction.user.id}"
        player = PlayerRepository.create(
            discord_id=str(interaction.user.id),
            username=interaction.user.name,
            profile_url=profile_url
        )
        
        try:
            dm_message = await interaction.user.send(
                f"✅ **Registration Complete!**\n\n"
                f"Welcome to Station 404!\n"
                f"Your profile: {profile_url}\n"
                f"Starting funds: 100 Pocket Credits\n\n"
                f"Use `/help` to see all commands."
            )
            
            # Save the DM message ID
            PlayerRepository.update_registration_dm(player['id'], str(dm_message.id))
            
            await interaction.followup.send(
                "✅ Registration successful! Check your DMs for your profile link.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"✅ Registered! Enable DMs to get your profile link.\nProfile: {profile_url}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(RegistrationCog(bot))