import discord
from discord.ext import commands
from shared.config import settings
from bot.core.game_manager import GameManager
from web.main import create_app, set_bot_instance

class Station404Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = False
        super().__init__(command_prefix="!", intents=intents)
        
        # Initialize game manager
        self.game_manager = GameManager(self)
        
        # NEW: Give web server access to the bot
        try:
            from web.main import set_bot_instance
            set_bot_instance(self)
            print("✅ Web server can access bot instance")
        except Exception as e:
            print(f"⚠️ Could not set bot instance for web: {e}")
    
    async def setup_hook(self):
        await self.load_extension("bot.cogs.registration")
        await self.load_extension("bot.cogs.info")
        await self.load_extension("bot.cogs.rounds")
        await self.load_extension("bot.cogs.admin")
        await self.load_extension("bot.cogs.gameplay")
        await self.load_extension("bot.cogs.combat")
        await self.load_extension("bot.cogs.shop")
        await self.load_extension("bot.cogs.approvals")
        await self.load_extension("bot.cogs.bank")
        await self.load_extension("bot.cogs.trading")
        await self.load_extension("bot.cogs.economy")   # NEW
        
        await self.tree.sync()
        print("✅ Slash commands synced!")
    
    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")
        print(f"✅ Bot is ready!")
        print(f"✅ Game manager initialized (status: {self.game_manager.state.status})")

bot = Station404Bot()

if __name__ == "__main__":
    bot.run(settings.DISCORD_TOKEN)