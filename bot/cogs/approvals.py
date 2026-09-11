import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.permissions import is_admin
from database.repositories.approval_repo import ApprovalRepository
from database.repositories.shop_repo import ShopRepository

class ApprovalsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="approvals", description="View pending item approvals (Admin only)")
    @is_admin()
    async def approvals(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        pending = ApprovalRepository.get_pending()
        
        if not pending:
            await interaction.followup.send("✅ No pending approvals!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔐 Pending Item Approvals",
            description=f"{len(pending)} request(s) awaiting approval",
            color=discord.Color.orange()
        )
        
        for req in pending[:10]:
            embed.add_field(
                name=f"{req['item_name']} — {req['username']}",
                value=f"Code: `{req['approval_code']}`\nRequested: <t:{int(__import__('datetime').datetime.fromisoformat(req['requested_at']).timestamp())}:R>",
                inline=False
            )
        
        embed.set_footer(text="Use /approve <code> or /reject <code>")
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="approve", description="Approve an item request (Admin only)")
    @is_admin()
    @app_commands.describe(code="The approval code")
    async def approve(self, interaction: discord.Interaction, code: str):
        await interaction.response.defer(ephemeral=True)
        
        request = ApprovalRepository.get_by_code(code.upper())
        if not request:
            await interaction.followup.send("❌ Invalid approval code!", ephemeral=True)
            return
        
        if request['status'] != 'pending':
            await interaction.followup.send(f"❌ Already {request['status']}!", ephemeral=True)
            return
        
        # Approve request
        ApprovalRepository.approve(code.upper(), str(interaction.user.id))
        
        # Mark item as approved globally
        ShopRepository.approve_item(request['item_id'])
        
        # Notify player
        try:
            user = await self.bot.fetch_user(int(request['discord_id']))
            await user.send(
                f"✅ **Item Approved!**\n\n"
                f"Your **{request['item_name']}** has been approved by an admin!\n"
                f"You can now use it with `/use {request['item_id']}`"
            )
        except:
            pass
        
        await interaction.followup.send(
            f"✅ Approved! Player has been notified.",
            ephemeral=True
        )
    
    @app_commands.command(name="reject", description="Reject an item request (Admin only)")
    @is_admin()
    @app_commands.describe(code="The approval code", reason="Why it was rejected")
    async def reject(self, interaction: discord.Interaction, code: str, reason: str = None):
        await interaction.response.defer(ephemeral=True)
        
        request = ApprovalRepository.get_by_code(code.upper())
        if not request:
            await interaction.followup.send("❌ Invalid approval code!", ephemeral=True)
            return
        
        if request['status'] != 'pending':
            await interaction.followup.send(f"❌ Already {request['status']}!", ephemeral=True)
            return
        
        ApprovalRepository.reject(code.upper(), str(interaction.user.id), reason)
        
        try:
            user = await self.bot.fetch_user(int(request['discord_id']))
            message = f"❌ **Item Rejected**\n\nYour **{request['item_name']}** request was rejected."
            if reason:
                message += f"\nReason: {reason}"
            await user.send(message)
        except:
            pass
        
        await interaction.followup.send("✅ Rejected! Player has been notified.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ApprovalsCog(bot))