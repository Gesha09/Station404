"""
Station 404 - Combined Launcher
Web server runs in the main thread (required for uvloop signal handlers).
Discord bot runs in a background thread.
"""
import asyncio
import threading
import sys
import os
import time
from dotenv import load_dotenv

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()


async def run_bot():
    """Run the Discord bot"""
    from bot.main import bot
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("❌ DISCORD_TOKEN not found in .env!")
        return
    
    print("✅ Logged in as " + str(bot.user))
    print("✅ Bot is ready!")
    print("✅ Game manager initialized (status: idle)")
    
    await bot.start(token)


def start_bot_thread():
    """Start the bot in a background thread with its own event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_bot())
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()


def main():
    print("=" * 50)
    print("Station 404 Starting...")
    print("=" * 50)
    
    # 1. Start bot in background thread
    print("🤖 Starting Discord Bot in background...")
    bot_thread = threading.Thread(target=start_bot_thread, daemon=True)
    bot_thread.start()
    
    # Give bot a moment to initialize and sync commands
    time.sleep(3)
    print("✅ Bot thread started")
    
    # 2. Run web server in MAIN thread (required for uvloop signal handlers)
    print("🌐 Starting Web Server...")
    try:
        from web.main import create_app
        from aiohttp import web
        
        app = create_app()
        
        # Read directly from .env to avoid Settings class mismatches
        host = os.getenv("API_HOST", "0.0.0.0")
        port = int(os.getenv("API_PORT", "14851"))
        
        print(f"🌐 Binding to http://{host}:{port}")
        web.run_app(app, host=host, port=port, print=None)
        print(f"✅ Web server successfully running on http://{host}:{port}")
        
    except Exception as e:
        print(f"❌ Web server failed to start: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()