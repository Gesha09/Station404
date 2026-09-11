import discord
from discord.ext import commands
from discord import app_commands
from database.repositories.player_repo import PlayerRepository
from database.repositories.shop_repo import ShopRepository
from database.repositories.inventory_repo import InventoryRepository
from database.repositories.vault_repo import VaultRepository
from bot.core.event_logger import EventLogger
import uuid
from datetime import datetime
from database.db import db

RARITY_EMOJIS = {
    "common": "⚪",
    "rare": "🔵",
    "epic": "🟣",
    "legendary": "🟡",
}

class TradeView(discord.ui.View):
    def __init__(self, sender_id: str, receiver_id: str, 
                 offer_item_id: str = None, offer_item_qty: int = 0, offer_coins: int = 0,
                 request_item_id: str = None, request_item_qty: int = 0, request_coins: int = 0):
        super().__init__(timeout=120)
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        
        # What sender is offering
        self.offer_item_id = offer_item_id
        self.offer_item_qty = offer_item_qty
        self.offer_coins = offer_coins
        
        # What sender is requesting in return
        self.request_item_id = request_item_id
        self.request_item_qty = request_item_qty
        self.request_coins = request_coins
        
        self.sender_accepted = False
        self.receiver_accepted = False
        self.message = None
    
    def _build_offer_text(self) -> str:
        """Build readable text for what sender offers"""
        parts = []
        if self.offer_item_qty > 0 and self.offer_item_id:
            item = ShopRepository.get_item_by_id(self.offer_item_id)
            emoji = RARITY_EMOJIS.get(item['rarity'], "⚪") if item else "⚪"
            name = item['name'] if item else self.offer_item_id
            parts.append(f"{emoji} **{name}** x{self.offer_item_qty}")
        if self.offer_coins > 0:
            parts.append(f"💰 **{self.offer_coins}** credits")
        return "\n".join(parts) if parts else "*nothing*"
    
    def _build_request_text(self) -> str:
        """Build readable text for what sender requests"""
        parts = []
        if self.request_item_qty > 0 and self.request_item_id:
            item = ShopRepository.get_item_by_id(self.request_item_id)
            emoji = RARITY_EMOJIS.get(item['rarity'], "⚪") if item else "⚪"
            name = item['name'] if item else self.request_item_id
            parts.append(f"{emoji} **{name}** x{self.request_item_qty}")
        if self.request_coins > 0:
            parts.append(f"💰 **{self.request_coins}** credits")
        return "\n".join(parts) if parts else "*nothing*"
    
    def _build_content(self, status_override: str = None) -> str:
        if status_override:
            return status_override
        
        sender_status = "✅ Accepted" if self.sender_accepted else "⏳ Pending"
        receiver_status = "✅ Accepted" if self.receiver_accepted else "⏳ Pending"
        
        return (
            f"🤝 **TRADE PROPOSAL**\n\n"
            f"**<@{self.sender_id}> offers:**\n{self._build_offer_text()}\n\n"
            f"**In return for:**\n{self._build_request_text()}\n\n"
            f"**From:** <@{self.receiver_id}>\n\n"
            f"**Status:**\n"
            f"• Sender (<@{self.sender_id}>): {sender_status}\n"
            f"• Receiver (<@{self.receiver_id}>): {receiver_status}\n\n"
            f"Both parties must accept to complete the trade."
        )
    
    async def _update_message(self, interaction: discord.Interaction):
        await interaction.message.edit(content=self._build_content(), view=self)
    
    @discord.ui.button(label="✅ Accept (Sender)", style=discord.ButtonStyle.success)
    async def sender_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.sender_id:
            await interaction.response.send_message("❌ Only the sender can click this!", ephemeral=True)
            return
        if self.sender_accepted:
            await interaction.response.send_message("❌ You already accepted!", ephemeral=True)
            return
        
        self.sender_accepted = True
        await self._update_message(interaction)
        await interaction.response.send_message("✅ You accepted the trade!", ephemeral=True)
        
        if self.receiver_accepted:
            await self._complete_trade(interaction)
    
    @discord.ui.button(label="✅ Accept (Receiver)", style=discord.ButtonStyle.success)
    async def receiver_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.receiver_id:
            await interaction.response.send_message("❌ Only the receiver can click this!", ephemeral=True)
            return
        if self.receiver_accepted:
            await interaction.response.send_message("❌ You already accepted!", ephemeral=True)
            return
        
        self.receiver_accepted = True
        await self._update_message(interaction)
        await interaction.response.send_message("✅ You accepted the trade!", ephemeral=True)
        
        if self.sender_accepted:
            await self._complete_trade(interaction)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) not in [self.sender_id, self.receiver_id]:
            await interaction.response.send_message("❌ You're not part of this trade!", ephemeral=True)
            return
        
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(
            content=f"❌ **Trade cancelled** by <@{interaction.user.id}>.",
            view=self
        )
        await interaction.response.send_message("❌ Trade cancelled.", ephemeral=True)
        self.stop()
    
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(content="⏰ **Trade expired** — no response in time.", view=self)
        except:
            pass
        self.stop()
    
    async def _complete_trade(self, interaction: discord.Interaction):
        """Execute the trade"""
        sender = PlayerRepository.get_by_discord_id(self.sender_id)
        receiver = PlayerRepository.get_by_discord_id(self.receiver_id)
        
        if not sender or not receiver:
            await interaction.message.edit(content="❌ Trade failed — player not found.")
            return
        
        # ============ VALIDATION ============
        errors = []
        
        # Check sender can afford what they're offering
        if self.offer_item_qty > 0 and self.offer_item_id:
            if not InventoryRepository.has_item(sender['id'], self.offer_item_id, self.offer_item_qty):
                errors.append(f"Sender no longer has the offered item")
        if self.offer_coins > 0:
            if sender['pocket_credits'] < self.offer_coins:
                errors.append(f"Sender doesn't have enough credits")
        
        # Check receiver can afford what they're giving
        if self.request_item_qty > 0 and self.request_item_id:
            if not InventoryRepository.has_item(receiver['id'], self.request_item_id, self.request_item_qty):
                errors.append(f"Receiver no longer has the requested item")
        if self.request_coins > 0:
            if receiver['pocket_credits'] < self.request_coins:
                errors.append(f"Receiver doesn't have enough credits")
        
        if errors:
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(
                content=f"❌ **Trade failed!**\n\n" + "\n".join([f"• {e}" for e in errors]),
                view=self
            )
            return
        
        # ============ EXECUTE TRADE ============
        now = datetime.now().isoformat()
        
        # Sender gives to receiver
        if self.offer_item_qty > 0 and self.offer_item_id:
            InventoryRepository.remove_item(sender['id'], self.offer_item_id, self.offer_item_qty)
            InventoryRepository.add_item(receiver['id'], self.offer_item_id, self.offer_item_qty)
        
        if self.offer_coins > 0:
            new_sender_pocket = sender['pocket_credits'] - self.offer_coins
            new_receiver_pocket = receiver['pocket_credits'] + self.offer_coins
            PlayerRepository.update_balance(sender['id'], pocket_credits=new_sender_pocket)
            PlayerRepository.update_balance(receiver['id'], pocket_credits=new_receiver_pocket)
            
            # Log credit transfer
            db.execute(
                """INSERT INTO vault_transactions 
                   (id, player_id, discord_id, transaction_type, amount, balance_after, description, created_at)
                   VALUES (?, ?, ?, 'sent', ?, ?, ?, ?)""",
                (str(uuid.uuid4()), sender['id'], self.sender_id,
                 -self.offer_coins, new_sender_pocket, f"Trade to {receiver['username']}", now)
            )
            db.execute(
                """INSERT INTO vault_transactions 
                   (id, player_id, discord_id, transaction_type, amount, balance_after, description, created_at)
                   VALUES (?, ?, ?, 'received', ?, ?, ?, ?)""",
                (str(uuid.uuid4()), receiver['id'], self.receiver_id,
                 self.offer_coins, new_receiver_pocket, f"Trade from {sender['username']}", now)
            )
        
        # Receiver gives to sender
        if self.request_item_qty > 0 and self.request_item_id:
            InventoryRepository.remove_item(receiver['id'], self.request_item_id, self.request_item_qty)
            InventoryRepository.add_item(sender['id'], self.request_item_id, self.request_item_qty)
        
        if self.request_coins > 0:
            # Note: if coins already transferred above, we need to account for that
            # Recalculate from current balances
            current_sender = db.fetch_one("SELECT pocket_credits FROM players WHERE id = ?", (sender['id'],))
            current_receiver = db.fetch_one("SELECT pocket_credits FROM players WHERE id = ?", (receiver['id'],))
            
            new_sender_pocket = current_sender['pocket_credits'] + self.request_coins
            new_receiver_pocket = current_receiver['pocket_credits'] - self.request_coins
            PlayerRepository.update_balance(sender['id'], pocket_credits=new_sender_pocket)
            PlayerRepository.update_balance(receiver['id'], pocket_credits=new_receiver_pocket)
            
            db.execute(
                """INSERT INTO vault_transactions 
                   (id, player_id, discord_id, transaction_type, amount, balance_after, description, created_at)
                   VALUES (?, ?, ?, 'received', ?, ?, ?, ?)""",
                (str(uuid.uuid4()), sender['id'], self.sender_id,
                 self.request_coins, new_sender_pocket, f"Trade from {receiver['username']}", now)
            )
            db.execute(
                """INSERT INTO vault_transactions 
                   (id, player_id, discord_id, transaction_type, amount, balance_after, description, created_at)
                   VALUES (?, ?, ?, 'sent', ?, ?, ?, ?)""",
                (str(uuid.uuid4()), receiver['id'], self.receiver_id,
                 -self.request_coins, new_receiver_pocket, f"Trade to {sender['username']}", now)
            )
        
        # Log the trade
        db.execute(
            """INSERT INTO trade_history (id, sender_id, receiver_id, item_id, quantity, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), sender['id'], receiver['id'], 
             self.offer_item_id or self.request_item_id or "coins",
             self.offer_item_qty + self.request_item_qty + self.offer_coins + self.request_coins,
             now)
        )
        
        EventLogger.log(
            event_type="trade_completed",
            actor_id=self.sender_id,
            actor_name=sender['username'],
            target_id=self.receiver_id,
            target_name=receiver['username'],
            details={
                "offer_item": self.offer_item_id,
                "offer_qty": self.offer_item_qty,
                "offer_coins": self.offer_coins,
                "request_item": self.request_item_id,
                "request_qty": self.request_item_qty,
                "request_coins": self.request_coins
            }
        )
        
        for child in self.children:
            child.disabled = True
        
        await interaction.message.edit(
            content=(
                f"✅ **TRADE COMPLETED!**\n\n"
                f"<@{self.sender_id}> gave:\n{self._build_offer_text()}\n\n"
                f"<@{self.receiver_id}> gave:\n{self._build_request_text()}"
            ),
            view=self
        )
        self.stop()


class TradingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="trade", description="Propose a trade with another player")
    @app_commands.describe(
        user="The player to trade with",
        give_item="Item ID you're giving (optional)",
        give_qty="Quantity of item you're giving (default: 1)",
        give_coins="Coins you're giving (optional)",
        want_item="Item ID you want in return (optional)",
        want_qty="Quantity of item you want (default: 1)",
        want_coins="Coins you want in return (optional)"
    )
    async def trade(
        self, interaction: discord.Interaction,
        user: discord.User,
        give_item: str = None,
        give_qty: int = 1,
        give_coins: int = 0,
        want_item: str = None,
        want_qty: int = 1,
        want_coins: int = 0
    ):
        await interaction.response.defer(ephemeral=False)
        
        sender = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not sender:
            await interaction.followup.send("❌ Not registered!", ephemeral=True)
            return
        
        if str(user.id) == str(interaction.user.id):
            await interaction.followup.send("❌ You can't trade with yourself!", ephemeral=True)
            return
        
        receiver = PlayerRepository.get_by_discord_id(str(user.id))
        if not receiver:
            await interaction.followup.send("❌ That player isn't registered!", ephemeral=True)
            return
        
        # Must offer OR request something
        if not any([give_item, give_coins > 0, want_item, want_coins > 0]):
            await interaction.followup.send(
                "❌ You must offer or request something!\n"
                "Use `give_item`, `give_coins`, `want_item`, or `want_coins`.",
                ephemeral=True
            )
            return
        
        # Validate items exist
        if give_item:
            item = ShopRepository.get_item_by_id(give_item)
            if not item:
                await interaction.followup.send(f"❌ Item `{give_item}` not found!", ephemeral=True)
                return
            if give_qty < 1:
                await interaction.followup.send("❌ Quantity must be at least 1!", ephemeral=True)
                return
            if not InventoryRepository.has_item(sender['id'], give_item, give_qty):
                await interaction.followup.send(
                    f"❌ You don't have {give_qty}x {item['name']}!",
                    ephemeral=True
                )
                return
        
        if want_item:
            item = ShopRepository.get_item_by_id(want_item)
            if not item:
                await interaction.followup.send(f"❌ Item `{want_item}` not found!", ephemeral=True)
                return
        
        # Validate coins
        if give_coins < 0 or want_coins < 0:
            await interaction.followup.send("❌ Coin amounts can't be negative!", ephemeral=True)
            return
        
        if give_coins > sender['pocket_credits']:
            await interaction.followup.send(
                f"❌ You don't have that many coins! You have {sender['pocket_credits']}.",
                ephemeral=True
            )
            return
        
        # Build the trade view
        view = TradeView(
            sender_id=str(interaction.user.id),
            receiver_id=str(user.id),
            offer_item_id=give_item,
            offer_item_qty=give_qty if give_item else 0,
            offer_coins=give_coins,
            request_item_id=want_item,
            request_item_qty=want_qty if want_item else 0,
            request_coins=want_coins
        )
        
        message = await interaction.followup.send(
            view._build_content(), 
            view=view,
            ephemeral=False  # ← CRITICAL: Make visible to everyone
        )
        view.message = message
    
    @app_commands.command(name="sell", description="Quick-sell an item to another player for coins")
    @app_commands.describe(
        user="The buyer",
        item_id="Item to sell",
        quantity="Quantity (default: 1)",
        price="Price in coins"
    )
    async def sell(
        self, interaction: discord.Interaction,
        user: discord.User,
        item_id: str,
        quantity: int = 1,
        price: int = 0
    ):
        """Shortcut: seller gives item, buyer gives coins"""
        await self.trade(
            interaction, user,
            give_item=item_id, give_qty=quantity,
            want_coins=price
        )
    
    @app_commands.command(name="buyfrom", description="Quick-buy an item from another player for coins")
    @app_commands.describe(
        user="The seller",
        item_id="Item to buy",
        quantity="Quantity (default: 1)",
        price="Price in coins"
    )
    async def buyfrom(
        self, interaction: discord.Interaction,
        user: discord.User,
        item_id: str,
        quantity: int = 1,
        price: int = 0
    ):
        """Shortcut: buyer gives coins, seller gives item"""
        await self.trade(
            interaction, user,
            give_coins=price,
            want_item=item_id, want_qty=quantity
        )

async def setup(bot):
    await bot.add_cog(TradingCog(bot))