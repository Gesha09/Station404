import discord
from discord.ext import commands
from discord import app_commands
from database.repositories.player_repo import PlayerRepository
from bot.utils.permissions import is_admin
from shared.config import settings

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="balance", description="View your credits")
    async def balance(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player:
            await interaction.followup.send("❌ Not registered! Use `/register` first.", ephemeral=True)
            return
        
        embed = discord.Embed(title="💰 Your Balance", color=discord.Color.gold())
        embed.add_field(name="Pocket Credits", value=f"{player['pocket_credits']:,}", inline=True)
        embed.add_field(name="Vault Bonds", value=f"{player['vault_bonds']:,}", inline=True)
        embed.add_field(name="Current Room", value=player['current_room'].title(), inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="help", description="View all commands")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Station 404 Commands",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎮 Core",
            value="`/register` ` /balance` ` /clockin` ` /offduty` ` /round`",
            inline=False
        )
        
        embed.add_field(
            name="🚶 Gameplay",
            value="`/move <room>` ` /search` ` /tasks` ` /complete <task>` ` /loot`",
            inline=False
        )
        
        embed.add_field(
            name="🥷 Combat",
            value="`/rob @user` ` /votestop`\n*Witnesses get DM buttons to report crimes*",
            inline=False
        )
        
        embed.add_field(
            name="📚 Info",
            value="`/help` ` /about`",
            inline=False
        )

        embed.add_field(
            name="🛒 Shop",
            value="`/shop` ` /buy <item>` ` /inventory` ` /use <item>`",
            inline=False
        )

        embed.add_field(
            name="👑 Admin",
            value="`/startgame` ` /forcestop` ` /config view` ` /config set`\n`/approvals` ` /approve <code>` ` /reject <code>`",
            inline=False
        )

        embed.add_field(
            name="🏦 Bank",
            value="`/deposit <amount>` ` /withdraw <amount>` ` /bank`",
            inline=False
        )

        embed.add_field(
            name="💸 Economy",
            value="`/give @user <amount>` ` /send @user <amount>`",
            inline=False
        )
        
        embed.add_field(
            name="🤝 Trading",
            value=(
                "`/trade @user [give_item] [give_coins] [want_item] [want_coins]`\n"
                "`/sell @user <item> <price>` ` /buyfrom @user <item> <price>`"
            ),
            inline=False
        )
        
        if interaction.guild:
            admin_role = interaction.guild.get_role(int(settings.ADMIN_ROLE_ID))
            if admin_role and admin_role in interaction.user.roles:
                embed.add_field(
                    name="👑 Admin",
                    value="`/startgame` ` /forcestop` ` /config view` ` /config set`",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="about", description="About Station 404")
    async def about(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎮 About Station 404",
            description="A social deduction economy game inspired by Among Us.",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🎯 Objective",
            value="Complete tasks, rob friends, survive the Imposter, and earn the most!",
            inline=False
        )
        embed.add_field(
            name="💰 Economy",
            value="• **Pocket Credits**: Liquid cash, can be robbed\n• **Vault Bonds**: Safe savings",
            inline=False
        )
        embed.add_field(
            name="🔄 Imposter Rotation",
            value="The Imposter role changes every few minutes. Check your DMs!",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="admin_test", description="Test admin access (Admin only)")
    @is_admin()
    async def admin_test(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Admin access confirmed!", ephemeral=True)

    @commands.command(name="cleandm")
    async def clean_dm(self, ctx):
        """Delete all bot messages in your DM (testing only)"""
        # Only works in DMs
        if ctx.guild is not None:
            await ctx.send("❌ This command only works in DMs with the bot!")
            return
        
        # Delete all bot messages
        deleted_count = 0
        async for message in ctx.channel.history(limit=100):
            if message.author == self.bot.user:
                try:
                    await message.delete()
                    deleted_count += 1
                except discord.Forbidden:
                    await ctx.send("❌ I don't have permission to delete messages!")
                    return
                except discord.HTTPException:
                    pass
        
        #await ctx.send(f"✅ Deleted {deleted_count} messages!")
async def setup(bot):
    await bot.add_cog(InfoCog(bot))