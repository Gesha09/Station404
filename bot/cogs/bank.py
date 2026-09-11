import discord
from discord.ext import commands
from discord import app_commands
from database.repositories.effects_repo import EffectsRepository
from database.repositories.player_repo import PlayerRepository
from database.repositories.vault_repo import VaultRepository
from database.repositories.config_repo import ConfigRepository

class BankCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="deposit", description="Deposit credits from pocket to vault")
    @app_commands.describe(amount="Amount to deposit")
    async def deposit(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player:
            await interaction.followup.send("❌ Not registered!", ephemeral=True)
            return
        
        gm = self.bot.game_manager
        if gm.state.status == "active":
            # Check if player has bank pass effect
            if not EffectsRepository.has_effect(player['id'], "bank_pass"):
                await interaction.followup.send(
                    "❌ Can't deposit during an active round!\n"
                    "Use a **Bank Pass** to deposit during rounds.",
                    ephemeral=True
                )
                return
            else:
                # Consume the bank pass
                EffectsRepository.consume_effect(player['id'], "bank_pass")
        
        result = VaultRepository.deposit(player['id'], str(interaction.user.id), amount)
        
        if not result['success']:
            await interaction.followup.send(f"❌ {result['message']}", ephemeral=True)
            return
        
        await interaction.followup.send(
            f"✅ **Deposited {amount} credits to vault!**\n\n"
            f"💰 Pocket: {result['new_pocket']}\n"
            f"🏦 Vault: {result['new_vault']}",
            ephemeral=True
        )
    
    @app_commands.command(name="withdraw", description="Withdraw credits from vault to pocket")
    @app_commands.describe(amount="Amount to withdraw")
    async def withdraw(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player:
            await interaction.followup.send("❌ Not registered!", ephemeral=True)
            return
        
        gm = self.bot.game_manager
        if gm.state.status == "active":
            await interaction.followup.send(
                "❌ Can't withdraw during an active round!",
                ephemeral=True
            )
            return
        
        result = VaultRepository.withdraw(player['id'], str(interaction.user.id), amount)
        
        if not result['success']:
            await interaction.followup.send(f"❌ {result['message']}", ephemeral=True)
            return
        
        await interaction.followup.send(
            f"✅ **Withdrew {amount} credits from vault!**\n\n"
            f"💰 Pocket: {result['new_pocket']}\n"
            f"🏦 Vault: {result['new_vault']}",
            ephemeral=True
        )
    
    @app_commands.command(name="bank", description="View your vault and transaction history")
    async def bank(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player:
            await interaction.followup.send("❌ Not registered!", ephemeral=True)
            return
        
        history = VaultRepository.get_history(player['id'], limit=10)
        interest_rate = ConfigRepository.get_int("vault_interest_rate", 5)
        
        embed = discord.Embed(
            title=f"🏦 {player['username']}'s Vault",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="💰 Pocket Credits",
            value=str(player['pocket_credits']),
            inline=True
        )
        embed.add_field(
            name="🏦 Vault Balance",
            value=str(player['vault_bonds']),
            inline=True
        )
        embed.add_field(
            name="📈 Interest Rate",
            value=f"{interest_rate}% per round",
            inline=True
        )
        
        if history:
            history_lines = []
            for tx in history:
                emoji = {
                    "deposit": "📥",
                    "withdraw": "📤",
                    "interest": "💎",
                    "robbery": "🥷",
                    "kill": "💀"
                }.get(tx['transaction_type'], "•")
                
                history_lines.append(
                    f"{emoji} **{tx['amount']}** — {tx['description']}\n"
                    f"   <t:{int(__import__('datetime').datetime.fromisoformat(tx['created_at']).timestamp())}:R>"
                )
            
            embed.add_field(
                name="📜 Recent Transactions",
                value="\n".join(history_lines),
                inline=False
            )
        else:
            embed.add_field(
                name="📜 Recent Transactions",
                value="No transactions yet.",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(BankCog(bot))