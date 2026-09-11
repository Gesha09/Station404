import discord
from discord import app_commands
from shared.config import settings

def is_admin():
    """Check if the user has the admin role"""
    async def predicate(interaction: discord.Interaction) -> bool:
        try:
            if not isinstance(interaction.user, discord.Member):
                raise app_commands.CheckFailure("This command can only be used in a server.")
            
            admin_role_id = int(settings.ADMIN_ROLE_ID)
            admin_role = interaction.guild.get_role(admin_role_id)
            
            if admin_role is None:
                raise app_commands.CheckFailure(f"❌ Admin role not found. Check ADMIN_ROLE_ID in .env")
            
            if admin_role not in interaction.user.roles:
                raise app_commands.CheckFailure("❌ You need the Admin role to use this command.")
            
            return True
        except ValueError:
            raise app_commands.CheckFailure("❌ Invalid ADMIN_ROLE_ID in .env file")
        except Exception as e:
            raise app_commands.CheckFailure(f"❌ Error checking admin role: {str(e)}")
    
    return app_commands.check(predicate)