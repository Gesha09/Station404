import discord
from discord.ext import commands
from discord import app_commands
import random
from database.repositories.player_repo import PlayerRepository
from database.repositories.shop_repo import ShopRepository
from database.repositories.inventory_repo import InventoryRepository
from database.repositories.approval_repo import ApprovalRepository
from database.repositories.config_repo import ConfigRepository
from database.db import db
from bot.core.mystery_box import MysteryBoxService

RARITY_COLORS = {
    "common": discord.Color.light_grey(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.gold(),
}

RARITY_EMOJIS = {
    "common": "⚪",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡",
}


class BuyConfirmView(discord.ui.View):
    def __init__(self, item_id: str, usage: int, total_cost: int, player: dict, item: dict, is_pass: bool = False):
        super().__init__(timeout=60)
        self.item_id = item_id
        self.usage = usage
        self.total_cost = total_cost
        self.player = player
        self.item = item
        self.is_pass = is_pass
    
    @discord.ui.button(label="✅ Confirm Purchase", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Process purchase
        new_balance = self.player['pocket_credits'] - self.total_cost
        PlayerRepository.update_balance(self.player['id'], pocket_credits=new_balance)
        
        # Decrease stock
        stock_needed = 1 if self.is_pass else self.usage
        for _ in range(stock_needed):
            if not ShopRepository.buy_item(self.item_id):
                await interaction.response.send_message(
                    "❌ Failed to process purchase (out of stock).",
                    ephemeral=True
                )
                return
        
        # Check if this item requires approval
        if self.item['requires_approval']:
            # For passes, create ONE request with usage limit
            # For regular items, create multiple requests
            if self.is_pass:
                code = ApprovalRepository.create_request(
                    self.player['id'], 
                    str(interaction.user.id), 
                    self.item_id,
                    usage_limit=self.usage
                )
                codes_text = f"`{code}` ({self.usage} uses)"
            else:
                codes = []
                for _ in range(self.usage):
                    code = ApprovalRepository.create_request(
                        self.player['id'], 
                        str(interaction.user.id), 
                        self.item_id
                    )
                    codes.append(code)
                codes_text = "\n".join([f"`{code}`" for code in codes])
            
            await interaction.response.send_message(
                f"✅ Purchased **{self.item['name']}**!\n"
                f"New balance: {new_balance} Pocket Credits\n\n"
                f"🔐 **This item requires admin approval.**\n"
                f"Your approval code(s):\n{codes_text}\n"
                f"Admins have been notified.",
                ephemeral=True
            )
        else:
            # Add to inventory
            InventoryRepository.add_item(self.player['id'], self.item_id, self.usage)
            
            emoji = RARITY_EMOJIS.get(self.item['rarity'], "⚪")
            await interaction.response.send_message(
                f"✅ Purchased {emoji} **{self.item['name']}** x{self.usage}!\n"
                f"New balance: {new_balance} Pocket Credits\n"
                f"Use `/inventory` to see your items.",
                ephemeral=True
            )
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Purchase cancelled.", ephemeral=True)
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        await interaction.edit_original_response(view=self)


class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="shop", description="Browse the shop")
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player:
            await interaction.followup.send("❌ Not registered! Use `/register` first.", ephemeral=True)
            return
        
        items = ShopRepository.get_all_items()
        
        if not items:
            await interaction.followup.send("❌ Shop is empty!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🛒 Station 404 Shop",
            description=f"Your balance: **{player['pocket_credits']} Pocket Credits**",
            color=discord.Color.gold()
        )
        
        # Group by rarity
        by_rarity = {}
        for item in items:
            rarity = item['rarity']
            if rarity not in by_rarity:
                by_rarity[rarity] = []
            by_rarity[rarity].append(item)
        
        rarity_order = ["legendary", "epic", "rare", "common"]
        for rarity in rarity_order:
            if rarity not in by_rarity:
                continue
            
            emoji = RARITY_EMOJIS.get(rarity, "⚪")
            lines = []
            for item in by_rarity[rarity]:
                stock_info = ""
                if item['stock_limit'] is not None:
                    stock_info = f" ({item['current_stock']}/{item['stock_limit']} left)"
                
                approval_info = ""
                if item['requires_approval']:
                    approval_info = " 🔐"
                
                # Show usage info for passes
                usage_info = ""
                if item['item_id'] in ["tot_pass", "daily_pass", "all_pass"]:
                    usage_info = " *(use `/buy item_id usage:X` for multiple uses)*"
                
                lines.append(
                    f"`/buy {item['item_id']}` — **{item['price']}** 💰{stock_info}{approval_info}{usage_info}\n"
                    f"*{item['description']}*"
                )
            
            embed.add_field(
                name=f"{emoji} {rarity.upper()}",
                value="\n".join(lines) if lines else "No items",
                inline=False
            )
        
        embed.set_footer(text="🔐 = requires admin approval")
        
        # Add web shop link
        try:
            from shared.config import settings
            web_shop_url = f"{settings.WEB_URL}/shop?user={interaction.user.id}"
            embed.add_field(
                name="🌐 Web Shop",
                value=f"[Browse the full shop online]({web_shop_url})",
                inline=False
            )
        except Exception:
            pass
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="buy", description="Buy an item from the shop")
    @app_commands.describe(item_id="The item ID to buy", usage="Quantity or uses (for passes)")
    async def buy(self, interaction: discord.Interaction, item_id: str, usage: int = 1):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player:
            await interaction.followup.send("❌ Not registered!", ephemeral=True)
            return
        
        item = ShopRepository.get_item_by_id(item_id)
        if not item or not item['is_available']:
            await interaction.followup.send("❌ Item not found or unavailable!", ephemeral=True)
            return
        
        is_pass = item_id in ["tot_pass", "daily_pass", "all_pass"]
        
        # ============ PASS-SPECIFIC CHECKS ============
        if is_pass:
            if usage < 1:
                await interaction.followup.send("❌ Usage must be at least 1!", ephemeral=True)
                return
            
            # Check minimum credits requirement
            min_credits_key = f"{item_id}_min_credits"
            min_credits = ConfigRepository.get_int(min_credits_key, 0)
            if player['pocket_credits'] < min_credits:
                await interaction.followup.send(
                    f"❌ You need at least **{min_credits} Pocket Credits** to buy this pass!\n"
                    f"You currently have: {player['pocket_credits']}",
                    ephemeral=True
                )
                return
            
            # Check max accounts limit
            max_accounts_key = f"{item_id}_max_accounts"
            max_accounts = ConfigRepository.get_int(max_accounts_key, 0)  # 0 = unlimited
            if max_accounts > 0:
                active_accounts = ApprovalRepository.count_active_accounts(item_id)
                # Allow if this player already has an active code for this pass
                player_has_active = db.fetch_one(
                    """
                    SELECT id FROM approval_requests
                    WHERE item_id = ? AND player_id = ? 
                    AND status = 'approved' AND usage_remaining > 0
                    """,
                    (item_id, player['id'])
                )
                if not player_has_active and active_accounts >= max_accounts:
                    await interaction.followup.send(
                        f"❌ **{item['name']}** has reached its account limit!\n"
                        f"Maximum {max_accounts} accounts can use this pass at once.\n"
                        f"Try again later when other players' uses run out.",
                        ephemeral=True
                    )
                    return
        
        # ============ REGULAR ITEM CHECKS ============
        else:
            if usage < 1:
                await interaction.followup.send("❌ Quantity must be at least 1!", ephemeral=True)
                return
        
        # Check stock
        if item['stock_limit'] is not None:
            available_stock = item['current_stock'] or 0
            needed = 1 if is_pass else usage  # Passes only consume 1 stock unit
            if available_stock < needed:
                await interaction.followup.send(
                    f"❌ Out of stock! Only {available_stock} available.",
                    ephemeral=True
                )
                return
        
        # Calculate total cost
        total_cost = item['price'] * usage
        
        # Check balance
        if player['pocket_credits'] < total_cost:
            await interaction.followup.send(
                f"❌ Not enough credits!\n"
                f"Need: **{total_cost}** 💰\n"
                f"Have: **{player['pocket_credits']}** 💰",
                ephemeral=True
            )
            return
        
        # ============ SHOW CONFIRMATION ============
        emoji = RARITY_EMOJIS.get(item['rarity'], "⚪")
        confirm_embed = discord.Embed(
            title="🛒 Confirm Purchase",
            description="Are you sure you want to buy this?",
            color=RARITY_COLORS.get(item['rarity'], discord.Color.light_grey())
        )
        confirm_embed.add_field(name="Item", value=f"{emoji} {item['name']}", inline=False)
        
        if is_pass:
            confirm_embed.add_field(
                name="Usage Limit", 
                value=f"{usage} use{'s' if usage > 1 else ''}", 
                inline=True
            )
            confirm_embed.add_field(
                name="Cost per Use", 
                value=f"{item['price']} 💰", 
                inline=True
            )
        else:
            confirm_embed.add_field(name="Quantity", value=str(usage), inline=True)
        
        confirm_embed.add_field(name="Total Cost", value=f"**{total_cost}** 💰", inline=True)
        confirm_embed.add_field(name="Your Balance", value=f"{player['pocket_credits']} 💰", inline=False)
        confirm_embed.add_field(
            name="After Purchase", 
            value=f"**{player['pocket_credits'] - total_cost}** 💰", 
            inline=False
        )
        
        view = BuyConfirmView(item_id, usage, total_cost, player, item, is_pass)
        await interaction.followup.send(embed=confirm_embed, view=view, ephemeral=True)
    
    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player:
            await interaction.followup.send("❌ Not registered!", ephemeral=True)
            return
        
        items = InventoryRepository.get_player_inventory(player['id'])
        
        if not items:
            await interaction.followup.send(
                "🎒 Your inventory is empty!\nVisit the `/shop` to buy items.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"🎒 {player['username']}'s Inventory",
            color=discord.Color.green()
        )
        
        for item in items:
            emoji = RARITY_EMOJIS.get(item['rarity'], "⚪")
            status = ""
            if item['requires_approval'] and not item['is_approved']:
                status = " 🔐 *pending approval*"
            
            embed.add_field(
                name=f"{emoji} {item['name']} x{item['quantity']}{status}",
                value=f"`/use {item['item_id']}`\n*{item['description']}*",
                inline=False
            )
        
        # Add web inventory link
        try:
            from shared.config import settings
            web_inventory_url = f"{settings.WEB_URL}/inventory/{interaction.user.id}"
            embed.add_field(
                name="🌐 Web Inventory",
                value=f"[View your inventory online]({web_inventory_url})",
                inline=False
            )
        except Exception:
            pass
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="use", description="Use an item from your inventory")
    @app_commands.describe(
        item_id="The item ID to use", 
        code="Approval code (for approved items)",
        quantity="How many to use (mystery boxes only, default: 1)"
    )
    async def use(self, interaction: discord.Interaction, item_id: str, code: str = None, quantity: int = 1):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player:
            await interaction.followup.send("❌ Not registered!", ephemeral=True)
            return
        
        item = ShopRepository.get_item_by_id(item_id)
        if not item:
            await interaction.followup.send("❌ Item not found!", ephemeral=True)
            return
        
        # ============ APPROVAL-BASED ITEMS ============
        if item['requires_approval']:
            if not code:
                await interaction.followup.send(
                    "❌ This item requires an approval code! Use `/use item_id code:YOUR_CODE`",
                    ephemeral=True
                )
                return
            
            # Check if code is valid and approved
            req = ApprovalRepository.get_by_code(code.upper())
            if not req:
                await interaction.followup.send("❌ Invalid approval code!", ephemeral=True)
                return
            
            if req['status'] != 'approved':
                await interaction.followup.send(f"❌ This code is {req['status']}!", ephemeral=True)
                return
            
            if req['player_id'] != player['id']:
                await interaction.followup.send("❌ This code doesn't belong to you!", ephemeral=True)
                return
            
            # Check usage remaining
            usage = ApprovalRepository.get_usage(code.upper())
            if not usage or usage['usage_remaining'] <= 0:
                await interaction.followup.send("❌ This code has no uses remaining!", ephemeral=True)
                return
            
            # Use the code (decrement usage)
            ApprovalRepository.use_code(code.upper())
            remaining = usage['usage_remaining'] - 1
            
            # Handle different pass types
            if item_id == "tot_pass":
                await interaction.followup.send(
                    f"✅ **{item['name']}** used!\n"
                    f"Uses remaining: {remaining}\n"
                    f"(TOT pass functionality coming soon)",
                    ephemeral=True
                )
                return
            
            if item_id == "daily_pass":
                await interaction.followup.send(
                    f"✅ **{item['name']}** used!\n"
                    f"Uses remaining: {remaining}\n"
                    f"(Daily pass functionality coming soon)",
                    ephemeral=True
                )
                return
            
            if item_id == "all_pass":
                await interaction.followup.send(
                    f"✅ **{item['name']}** used!\n"
                    f"Uses remaining: {remaining}\n"
                    f"(All pass functionality coming soon)",
                    ephemeral=True
                )
                return
        
        # ============ REGULAR ITEMS ============
        if not InventoryRepository.has_item(player['id'], item_id):
            await interaction.followup.send("❌ You don't have that item!", ephemeral=True)
            return
        
        # Check inventory quantity
        player_item = InventoryRepository.get_player_item(player['id'], item_id)
        available_qty = player_item['quantity'] if player_item else 0
        
                # ============ MYSTERY BOX: BULK OPENING ============
        if item_id == "mystery_box":
            if quantity < 1:
                await interaction.followup.send("❌ Quantity must be at least 1!", ephemeral=True)
                return
            
            if available_qty < quantity:
                await interaction.followup.send(
                    f"❌ You only have {available_qty} mystery box{'es' if available_qty != 1 else ''}!",
                    ephemeral=True
                )
                return
            
            # Open multiple boxes (service handles inventory removal)
            loot_results = []
            for i in range(quantity):
                result = MysteryBoxService.open_box(player['id'], str(interaction.user.id))
                loot_results.append(result)
            
            # Build clean summary embed
            embed = discord.Embed(
                title=f"📦 Opened {quantity} Mystery Box{'es' if quantity > 1 else ''}!",
                color=discord.Color.gold()
            )
            
            # Group by item for cleaner display
            item_counts = {}
            approval_codes = []
            
            for loot in loot_results:
                if "error" in loot:
                    continue
                key = (loot['item_id'], loot['item_name'], loot['rarity'])
                if key not in item_counts:
                    item_counts[key] = 0
                item_counts[key] += 1
                if loot.get('code'):
                    approval_codes.append((loot['item_name'], loot['code']))
            
            # Display items
            rarity_emojis = {"common": "⚪", "rare": "🔵", "epic": "🟣", "legendary": "🟡"}
            
            if item_counts:
                lines = []
                for (item_id, item_name, rarity), count in item_counts.items():
                    emoji = rarity_emojis.get(rarity, "⚪")
                    qty_text = f" x{count}" if count > 1 else ""
                    lines.append(f"{emoji} `{item_id}` — **{item_name}**{qty_text}")
                
                embed.add_field(
                    name="🎁 Items Received",
                    value="\n".join(lines),
                    inline=False
                )
            
            # Show approval codes if any
            if approval_codes:
                code_lines = [f"• **{name}**: `{code}`" for name, code in approval_codes]
                embed.add_field(
                    name="🔐 Approval Codes (requires admin approval)",
                    value="\n".join(code_lines),
                    inline=False
                )
            
            embed.set_footer(text=f"Total boxes opened: {quantity}")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # ============ OTHER ITEMS: SINGLE USE ============
        InventoryRepository.remove_item(player['id'], item_id, 1)
        
        if item_id == "rob_proof":
            await interaction.followup.send(
                f"✅ **{item['name']}** activated!\n"
                f"You're protected from the next robbery attempt.",
                ephemeral=True
            )
            return
        
        if item_id == "shield_boost":
            await interaction.followup.send(
                f"✅ **{item['name']}** activated!\n"
                f"You'll survive the next imposter kill attempt.",
                ephemeral=True
            )
            return
        
        if item_id == "radar_ping":
            await interaction.followup.send(
                f"✅ **{item['name']}** used!\n"
                f"(Radar functionality coming soon)",
                ephemeral=True
            )
            return
        
        if item_id == "stealth_rob":
            await interaction.followup.send(
                f"✅ **{item['name']}** activated!\n"
                f"Your next `/rob` will be invisible to witnesses.",
                ephemeral=True
            )
            return
        
        if item_id == "bank_pass":
            gm = self.bot.game_manager
            if gm.state.status != "active":
                await interaction.followup.send(
                    "❌ Bank Pass can only be used during an active round!",
                    ephemeral=True
                )
                return
            await interaction.followup.send(
                f"✅ **{item['name']}** used!\n"
                f"(Bank deposit functionality coming soon)",
                ephemeral=True
            )
            return
        
        # Default: just consume the item
        await interaction.followup.send(f"✅ Used **{item['name']}**!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ShopCog(bot))