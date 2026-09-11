from imaplib import Commands

from aiohttp import web
import jinja2
from datetime import datetime, timedelta
# ✅ CORRECT - imports the Database instance
from database.db import db
from database.repositories.player_repo import PlayerRepository
from database.repositories.round_repo import RoundRepository
from database.repositories.config_repo import ConfigRepository
from shared.config import settings
from database.repositories.game_state_repo import GameStateRepository

from database.repositories.shop_repo import ShopRepository
from database.repositories.inventory_repo import InventoryRepository
from database.repositories.approval_repo import ApprovalRepository

from web.admin_auth import SESSION_DURATION_HOURS, AdminAuth
from database.repositories.shop_repo import ShopRepository
from database.repositories.inventory_repo import InventoryRepository
from database.repositories.approval_repo import ApprovalRepository
from database.repositories.game_state_repo import GameStateRepository
from database.repositories.round_repo import RoundRepository
from bot.core.event_logger import EventLogger
import json

import aiohttp

async def send_discord_dm(discord_id: str, content: str) -> bool:
    """Send a DM to a Discord user directly via the Discord API."""
    token = settings.DISCORD_TOKEN
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    
    print(f"📩 Attempting to send DM to {discord_id}")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Create a DM channel with the user
            print("  → Creating DM channel...")
            async with session.post(
                "https://discord.com/api/v10/users/@me/channels",
                headers=headers,
                json={"recipient_id": str(discord_id)}
            ) as resp:
                if resp.status not in (200, 201):
                    error_text = await resp.text()
                    print(f"  ❌ Failed to create DM channel: {resp.status} - {error_text}")
                    return False
                channel_data = await resp.json()
                channel_id = channel_data["id"]
                print(f"  ✓ DM channel created: {channel_id}")
            
            # Step 2: Send the message to the DM channel
            print("  → Sending message...")
            async with session.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                json={"content": content}
            ) as resp:
                if resp.status == 200:
                    print(f"  ✅ DM sent successfully to {discord_id}")
                    return True
                else:
                    error_text = await resp.text()
                    print(f"  ❌ Failed to send DM: {resp.status} - {error_text}")
                    return False
    except Exception as e:
        print(f"  ❌ DM send exception: {e}")
        return False
    
templates_dir = "web/templates"

# Global reference to the bot instance (set by bot/main.py on startup)
bot_instance = None

def set_bot_instance(bot):
    """Called by bot/main.py to give web access to the Discord bot"""
    global bot_instance
    bot_instance = bot

def format_date(date_string):
    """Convert ISO date string to readable format"""
    if not date_string:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(date_string)
        return dt.strftime('%B %d, %Y')
    except:
        return date_string

async def home(request):
    template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("index.html")
    html = template.render(title="Station 404")
    return web.Response(text=html, content_type="text/html")

async def profile(request):
    discord_id = request.match_info["discord_id"]
    player = PlayerRepository.get_by_discord_id(discord_id)
    
    if not player:
        template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("404.html")
        html = template.render()
        return web.Response(text=html, content_type="text/html", status=404)
    
    player_dict = dict(player)
    player_dict['registered_at_formatted'] = format_date(player_dict.get('registered_at'))
    player_dict['is_on_duty_text'] = '🟢 On Duty' if player_dict.get('is_on_duty') else '🔴 Off Duty'
    
    template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("profile.html")
    html = template.render(player=player_dict, web_url=settings.WEB_URL)
    return web.Response(text=html, content_type="text/html")

async def admin_panel(request):
    secret = request.query.get("secret")
    if secret != settings.WEB_ADMIN_SECRET:
        return web.Response(text="❌ Invalid admin secret", status=403)
    
    template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("admin.html")
    html = template.render()
    return web.Response(text=html, content_type="text/html")

async def health_check(request):
    return web.json_response({"status": "healthy", "service": "station-404-api"})


# ============ NEW: ROUND STATUS ENDPOINT ============
async def round_status(request):
    """Returns current round state for the web timer."""
    state = GameStateRepository.get_all()
    
    if not state or state.get("status") == "idle":
        return web.json_response({
            "status": "idle",
            "phase_number": None,
            "round_end_time": None,
            "next_rotation_time": None,
            "prep_end_time": None,
            "final_phase": False,
            "participants": 0,
            "stop_votes": 0
        })
    
    def safe_float(val):
        try:
            return float(val)
        except (TypeError, ValueError):
            return None
    
    def safe_int(val, default=0):
        try:
            return int(val)
        except (TypeError, ValueError):
            return default
    
    return web.json_response({
        "status": state.get("status"),
        "phase_number": safe_int(state.get("phase_number")),
        "round_end_time": safe_float(state.get("round_end_time")),
        "next_rotation_time": safe_float(state.get("next_rotation_time")),
        "prep_end_time": safe_float(state.get("prep_end_time")),
        "final_phase": state.get("final_phase") == "true",
        "participants": safe_int(state.get("participants")),
        "stop_votes": safe_int(state.get("stop_votes"))
    })
# ==================================================
async def player_status(request):
    """Returns player-specific status (dead/jailed timers)"""
    discord_id = request.match_info["discord_id"]
    player = PlayerRepository.get_by_discord_id(discord_id)
    
    if not player:
        return web.json_response({"error": "Player not found"}, status=404)
    
    # Check if dead
    is_dead = not player['is_alive']
    respawn_time = None
    if is_dead and player['respawn_at']:
        try:
            respawn_time = datetime.fromisoformat(player['respawn_at']).timestamp()
        except:
            pass
    
    # Check if jailed
    is_jailed = False
    jail_release_time = None
    if player['jail_release_at']:
        try:
            release_dt = datetime.fromisoformat(player['jail_release_at'])
            if release_dt > datetime.now():
                is_jailed = True
                jail_release_time = release_dt.timestamp()
        except:
            pass
    
    return web.json_response({
        "is_alive": player['is_alive'],
        "is_dead": is_dead,
        "respawn_time": respawn_time,
        "is_jailed": is_jailed,
        "jail_release_time": jail_release_time,
        "current_room": player['current_room']
    })

async def shop_page(request):
    """Public shop page"""
    items = ShopRepository.get_all_items()
    
    # Read the ?user= parameter from the URL
    discord_id = request.query.get("user")
    player = None
    if discord_id:
        player = PlayerRepository.get_by_discord_id(discord_id)
        if player:
            # Convert to dict so template can access it
            player = dict(player)
    
    template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("shop.html")
    html = template.render(items=items, player=player)
    return web.Response(text=html, content_type="text/html")

async def player_inventory_page(request):
    """View a player's inventory"""
    discord_id = request.match_info["discord_id"]
    player = PlayerRepository.get_by_discord_id(discord_id)
    
    if not player:
        template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("404.html")
        html = template.render()
        return web.Response(text=html, content_type="text/html", status=404)
    
    items = InventoryRepository.get_player_inventory(player['id'])
    template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("inventory.html")
    html = template.render(player=player, items=items)
    return web.Response(text=html, content_type="text/html")

async def admin_shop(request):
    """Admin shop management"""
    secret = request.query.get("secret")
    if secret != settings.WEB_ADMIN_SECRET:
        return web.Response(text="❌ Invalid admin secret", status=403)
    
    items = ShopRepository.get_all_items()
    template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("admin_shop.html")
    html = template.render(items=items, secret=secret)
    return web.Response(text=html, content_type="text/html")

async def admin_approvals(request):
    """Admin approvals page"""
    secret = request.query.get("secret")
    if secret != settings.WEB_ADMIN_SECRET:
        return web.Response(text="❌ Invalid admin secret", status=403)
    
    pending = ApprovalRepository.get_pending()
    all_requests = ApprovalRepository.get_all()
    template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("admin_approvals.html")
    html = template.render(pending=pending, all_requests=all_requests, secret=secret)
    return web.Response(text=html, content_type="text/html")

async def buy_item_api(request):
    """API endpoint for buying items from web"""
    try:
        data = await request.json()
        item_id = data.get('item_id')
        quantity = data.get('quantity', 1)
        discord_id = data.get('discord_id')
        is_pass = data.get('is_pass', False)
        
        if not discord_id:
            return web.json_response({"success": False, "message": "Not authenticated"}, status=401)
        
        player = PlayerRepository.get_by_discord_id(discord_id)
        if not player:
            return web.json_response({"success": False, "message": "Player not found"}, status=404)
        
        item = ShopRepository.get_item_by_id(item_id)
        if not item or not item['is_available']:
            return web.json_response({"success": False, "message": "Item not available"}, status=400)
        
        # ============ PASS-SPECIFIC CHECKS ============
        if is_pass:
            if quantity < 1:
                return web.json_response({"success": False, "message": "Usage must be at least 1"}, status=400)
            
            # Check minimum credits
            min_credits_key = f"{item_id}_min_credits"
            min_credits = ConfigRepository.get_int(min_credits_key, 0)
            if player['pocket_credits'] < min_credits:
                return web.json_response(
                    {"success": False, "message": f"You need at least {min_credits} credits to buy this pass"},
                    status=400
                )
            
            # Check max accounts
            max_accounts_key = f"{item_id}_max_accounts"
            max_accounts = ConfigRepository.get_int(max_accounts_key, 0)
            if max_accounts > 0:
                active_accounts = ApprovalRepository.count_active_accounts(item_id)
                player_has_active = db.fetch_one(
                    """SELECT id FROM approval_requests
                       WHERE item_id = ? AND player_id = ? 
                       AND status = 'approved' AND usage_remaining > 0""",
                    (item_id, player['id'])
                )
                if not player_has_active and active_accounts >= max_accounts:
                    return web.json_response(
                        {"success": False, "message": f"This pass has reached its account limit ({max_accounts})"},
                        status=400
                    )
            
            # Passes consume 1 stock unit regardless of uses
            stock_needed = 1
        else:
            if quantity < 1:
                return web.json_response({"success": False, "message": "Quantity must be at least 1"}, status=400)
            stock_needed = quantity
        
        # Check stock
        if item['stock_limit'] is not None:
            available = item['current_stock'] or 0
            if available < stock_needed:
                return web.json_response(
                    {"success": False, "message": f"Only {available} in stock"},
                    status=400
                )
        
        total_cost = item['price'] * quantity
        
        # Check balance
        if player['pocket_credits'] < total_cost:
            return web.json_response(
                {"success": False, "message": f"Not enough credits. Need {total_cost}, have {player['pocket_credits']}"},
                status=400
            )
        
        # ============ PROCESS PURCHASE ============
        new_balance = player['pocket_credits'] - total_cost
        PlayerRepository.update_balance(player['id'], pocket_credits=new_balance)
        
        # Decrease stock
        for _ in range(stock_needed):
            ShopRepository.buy_item(item_id)
        
        # Handle approval items
        if item['requires_approval']:
            if is_pass:
                # ONE code with multiple uses
                code = ApprovalRepository.create_request(
                    player['id'], discord_id, item_id, usage_limit=quantity
                )
                codes = [f"{code} ({quantity} uses)"]
            else:
                # Multiple codes, 1 use each
                codes = []
                for _ in range(quantity):
                    code = ApprovalRepository.create_request(player['id'], discord_id, item_id)
                    codes.append(code)
            
            EventLogger.item_purchased(
                player_id=discord_id,
                player_name=player['username'],
                item_id=item_id,
                item_name=item['name'],
                quantity=quantity,
                total_cost=total_cost
            )
            
            return web.json_response({
                "success": True,
                "message": f"Purchased {item['name']}!\nAwaiting admin approval.",
                "codes": codes
            })
        else:
            InventoryRepository.add_item(player['id'], item_id, quantity)
            
            EventLogger.item_purchased(
                player_id=discord_id,
                player_name=player['username'],
                item_id=item_id,
                item_name=item['name'],
                quantity=quantity,
                total_cost=total_cost
            )
            
            return web.json_response({
                "success": True,
                "message": f"Purchased {item['name']} x{quantity}!"
            })
    
    except Exception as e:
        print(f"Buy error: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({"success": False, "message": str(e)}, status=500)

# ============ ADMIN AUTH HELPERS ============

def get_admin_token(request):
    """Extract admin token from cookies"""
    return request.cookies.get("admin_token")

def require_admin(handler):
    """Decorator to require admin auth on routes"""
    async def wrapper(request):
        token = get_admin_token(request)
        if not AdminAuth.validate_session(token):
            raise web.HTTPFound("/admin/login")
        return await handler(request)
    return wrapper

# ============ ADMIN ROUTES ============

async def admin_login_page(request):
    """Admin login page"""
    template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("admin_login.html")
    html = template.render(error=None)
    return web.Response(text=html, content_type="text/html")

async def admin_login_submit(request):
    """Handle admin login form submission"""
    data = await request.post()
    secret = data.get("secret", "")
    
    if AdminAuth.validate_secret(secret):
        token = AdminAuth.create_session(ip_address=request.remote)
        response = web.HTTPFound("/admin/dashboard")
        # Set cookie for 8 hours
        response.set_cookie(
            "admin_token", 
            token, 
            max_age=SESSION_DURATION_HOURS * 3600,
            httponly=True,
            samesite="Lax"
        )
        return response
    else:
        template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("admin_login.html")
        html = template.render(error="Invalid admin secret")
        return web.Response(text=html, content_type="text/html", status=401)

async def admin_logout(request):
    """Log out admin"""
    token = get_admin_token(request)
    if token:
        AdminAuth.destroy_session(token)
    response = web.HTTPFound("/admin/login")
    response.del_cookie("admin_token")
    return response

@require_admin
async def admin_dashboard(request):
    """Main admin dashboard"""
    template = jinja2.Environment(loader=jinja2.FileSystemLoader(templates_dir)).get_template("admin_dashboard.html")
    html = template.render()
    return web.Response(text=html, content_type="text/html")

# ============ ADMIN API ENDPOINTS ============

@require_admin
async def api_admin_overview(request):
    """Get current game state overview"""
    state = GameStateRepository.get_all()
    current_round = RoundRepository.get_current()
    latest_round = RoundRepository.get_latest()
    
    # Get player counts
    from database.repositories.player_repo import PlayerRepository
    total_players = len(PlayerRepository.get_all())
    on_duty = len(PlayerRepository.get_all_on_duty())
    
    # Get recent events
    recent_events = db.fetch_all(
        "SELECT * FROM event_log ORDER BY timestamp DESC LIMIT 10"
    )
    
    return web.json_response({
        "game_state": state,
        "current_round": dict(current_round) if current_round else None,
        "latest_round": dict(latest_round) if latest_round else None,
        "total_players": total_players,
        "on_duty": on_duty,
        "recent_events": [dict(e) for e in recent_events]
    })

@require_admin
async def api_admin_players(request):
    """Get all players with optional search"""
    search = request.query.get("search", "").lower()
    
    from database.repositories.player_repo import PlayerRepository
    players = PlayerRepository.get_all()
    
    result = []
    for p in players:
        player_dict = dict(p)
        if search and search not in player_dict['username'].lower() and search not in player_dict['discord_id']:
            continue
        result.append(player_dict)
    
    return web.json_response({"players": result})

@require_admin
async def api_admin_update_player(request):
    """Update a player's data"""
    data = await request.json()
    player_id = data.get("player_id")
    
    if not player_id:
        return web.json_response({"success": False, "message": "Missing player_id"}, status=400)
    
    from database.repositories.player_repo import PlayerRepository
    player = db.fetch_one("SELECT * FROM players WHERE id = ?", (player_id,))
    if not player:
        return web.json_response({"success": False, "message": "Player not found"}, status=404)
    
    # Handle balance updates
    if "pocket_credits" in data:
        try:
            new_credits = int(data["pocket_credits"])
            PlayerRepository.update_balance(player_id, pocket_credits=new_credits)
        except ValueError:
            return web.json_response({"success": False, "message": "Invalid credits value"}, status=400)
    
    if "vault_bonds" in data:
        try:
            new_bonds = int(data["vault_bonds"])
            PlayerRepository.update_balance(player_id, vault_bonds=new_bonds)
        except ValueError:
            return web.json_response({"success": False, "message": "Invalid bonds value"}, status=400)
    
    # Handle jail
    if data.get("action") == "jail":
        duration = int(data.get("duration", 300))
        release_time = (datetime.now() + timedelta(seconds=duration)).isoformat()
        PlayerRepository.set_jail_release(player_id, release_time)
    
    if data.get("action") == "release":
        PlayerRepository.set_jail_release(player_id, None)
    
    # Handle kill/respawn
    if data.get("action") == "kill":
        PlayerRepository.kill_player(player_id)
    
    if data.get("action") == "respawn":
        PlayerRepository.respawn_player(player_id)
    
    # Handle room move
    if "room" in data:
        PlayerRepository.update_room(player_id, data["room"])
    
    EventLogger.admin_action(
        admin_id="web_admin",
        admin_name="Web Admin",
        action="update_player",
        details={"player_id": player_id, "changes": data}
    )
    
    return web.json_response({"success": True, "message": "Player updated"})

@require_admin
async def api_admin_items(request):
    """Get all shop items"""
    items = ShopRepository.get_all_items()
    return web.json_response({"items": [dict(i) for i in items]})

@require_admin
async def api_admin_create_item(request):
    """Create a new shop item"""
    data = await request.json()
    
    try:
        ShopRepository.create_item(
            item_id=data["item_id"],
            name=data["name"],
            description=data["description"],
            price=int(data["price"]),
            rarity=data.get("rarity", "common"),
            item_type=data.get("item_type", "consumable"),
            stock_limit=int(data["stock_limit"]) if data.get("stock_limit") else None,
            can_drop_in_loot=data.get("can_drop_in_loot", False),
            loot_weight=int(data.get("loot_weight", 1)),
            requires_approval=data.get("requires_approval", False)
        )
        
        EventLogger.admin_action(
            admin_id="web_admin",
            admin_name="Web Admin",
            action="create_item",
            details={"item_id": data["item_id"], "name": data["name"]}
        )
        
        return web.json_response({"success": True})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)}, status=400)

@require_admin
async def api_admin_update_item(request):
    """Update a shop item"""
    try:
        data = await request.json()
        item_id = data.get("item_id")
        
        if not item_id:
            return web.json_response({"success": False, "message": "Missing item_id"}, status=400)
        
        # Convert types properly
        updates = {}
        for key in ["name", "description", "rarity"]:
            if key in data:
                updates[key] = str(data[key])
        
        for key in ["price", "stock_limit", "current_stock", "loot_weight"]:
            if key in data and data[key] is not None:
                try:
                    updates[key] = int(data[key])
                except (ValueError, TypeError):
                    pass
        
        for key in ["can_drop_in_loot", "requires_approval", "is_approved", "is_available"]:
            if key in data:
                updates[key] = 1 if data[key] else 0
        
        if not updates:
            return web.json_response({"success": False, "message": "No valid fields to update"}, status=400)
        
        ShopRepository.update_item(item_id, **updates)
        
        EventLogger.admin_action(
            admin_id="web_admin",
            admin_name="Web Admin",
            action="update_item",
            details={"item_id": item_id, "changes": updates}
        )
        
        return web.json_response({"success": True})
    except Exception as e:
        print(f"Error updating item: {e}")
        return web.json_response({"success": False, "message": str(e)}, status=400)

@require_admin
async def api_admin_delete_item(request):
    """Delete a shop item"""
    data = await request.json()
    item_id = data.get("item_id")
    
    if not item_id:
        return web.json_response({"success": False, "message": "Missing item_id"}, status=400)
    
    db.execute("DELETE FROM shop_items WHERE item_id = ?", (item_id,))
    db.execute("DELETE FROM player_inventory WHERE item_id = ?", (item_id,))
    
    return web.json_response({"success": True})

@require_admin
async def api_admin_events(request):
    """Get event log with filters"""
    event_type = request.query.get("type")
    limit = int(request.query.get("limit", 100))
    
    query = "SELECT * FROM event_log"
    params = []
    
    if event_type:
        query += " WHERE event_type = ?"
        params.append(event_type)
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    events = db.fetch_all(query, tuple(params))
    return web.json_response({"events": [dict(e) for e in events]})

@require_admin
async def api_admin_approvals(request):
    """Get approval requests"""
    pending = ApprovalRepository.get_pending()
    all_requests = ApprovalRepository.get_all()
    return web.json_response({
        "pending": [dict(p) for p in pending],
        "all": [dict(r) for r in all_requests]
    })

@require_admin
async def api_admin_approve(request):
    """Approve an approval request"""
    try:
        data = await request.json()
        code = data.get("code", "").upper()
        
        if not code:
            return web.json_response({"success": False, "message": "Missing code"}, status=400)
        
        req = ApprovalRepository.get_by_code(code)
        if not req:
            return web.json_response({"success": False, "message": "Invalid approval code"}, status=404)
        
        if req['status'] != 'pending':
            return web.json_response({"success": False, "message": f"Already {req['status']}"}, status=400)
        
        item_id = req['item_id']
        item_name = req['item_name']
        player_id = req['player_id']
        discord_id = req['discord_id']
        
        # Fix: sqlite3.Row doesn't have .get(), use direct indexing
        try:
            usage_limit = req['usage_limit'] if req['usage_limit'] is not None else 1
        except (KeyError, IndexError):
            usage_limit = 1
        
        if not item_name:
            item_row = ShopRepository.get_item_by_id(item_id)
            item_name = item_row['name'] if item_row else "Unknown Item"
        
        ApprovalRepository.approve(code, "web_admin")
        ShopRepository.approve_item(item_id)
        
        usage_text = f" ({usage_limit} uses)" if usage_limit > 1 else ""
        message_content = (
            f"✅ **Item Approved!**{usage_text}\n\n"
            f"Your **{item_name}** has been approved by an admin!\n"
            f"Approval code: `{code}`\n"
            f"You can now use it with `/use {item_id}`"
        )
        
        pinned_message_id = await send_discord_dm_and_pin(discord_id, message_content)
        if pinned_message_id:
            ApprovalRepository.set_pinned_message(code, pinned_message_id)
        
        EventLogger.admin_action(
            admin_id="web_admin",
            admin_name="Web Admin",
            action="approve_item",
            details={
                "code": code,
                "item_id": item_id,
                "item_name": item_name,
                "player_id": player_id,
                "discord_id": discord_id,
                "usage_limit": usage_limit,
                "pinned": pinned_message_id is not None
            }
        )
        
        return web.json_response({"success": True, "message": "Approved and pinned!"})
    
    except KeyError as e:
        print(f"❌ KeyError in api_admin_approve: {e}")
        return web.json_response({"success": False, "message": f"Missing data field: {e}"}, status=500)
    except Exception as e:
        print(f"❌ Error in api_admin_approve: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({"success": False, "message": f"Server error: {str(e)}"}, status=500)
       
@require_admin
async def api_admin_reject(request):
    """Reject an approval request"""
    try:
        data = await request.json()
        code = data.get("code", "").upper()
        reason = data.get("reason", "")
        
        if not code:
            return web.json_response({"success": False, "message": "Missing code"}, status=400)
        
        req = ApprovalRepository.get_by_code(code)
        if not req:
            return web.json_response({"success": False, "message": "Invalid approval code"}, status=404)
        
        if req['status'] != 'pending':
            return web.json_response({"success": False, "message": f"Already {req['status']}"}, status=400)
        
        item_id = req['item_id']
        item_name = req['item_name']
        discord_id = req['discord_id']
        
        if not item_name:
            item_row = ShopRepository.get_item_by_id(item_id)
            item_name = item_row['name'] if item_row else "Unknown Item"
        
        ApprovalRepository.reject(code, "web_admin", reason)
        
        reject_msg = f"❌ **Item Rejected**\n\nYour **{item_name}** request was rejected."
        if reason:
            reject_msg += f"\nReason: {reason}"
        
        pinned_message_id = await send_discord_dm_and_pin(discord_id, reject_msg)
        if pinned_message_id:
            ApprovalRepository.set_pinned_message(code, pinned_message_id)
        
        EventLogger.admin_action(
            admin_id="web_admin",
            admin_name="Web Admin",
            action="reject_item",
            details={
                "code": code,
                "item_id": item_id,
                "item_name": item_name,
                "reason": reason,
                "pinned": pinned_message_id is not None
            }
        )
        
        return web.json_response({"success": True, "message": "Rejected and pinned!"})
    
    except KeyError as e:
        print(f"❌ KeyError in api_admin_reject: {e}")
        return web.json_response({"success": False, "message": f"Missing data field: {e}"}, status=500)
    except Exception as e:
        print(f"❌ Error in api_admin_reject: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({"success": False, "message": f"Server error: {str(e)}"}, status=500)

async def send_discord_dm_and_pin(discord_id: str, content: str) -> str:
    """Send a DM and pin it. Returns the message ID if successful, None otherwise."""
    token = settings.DISCORD_TOKEN
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Create DM channel
            async with session.post(
                "https://discord.com/api/v10/users/@me/channels",
                headers=headers,
                json={"recipient_id": str(discord_id)}
            ) as resp:
                if resp.status not in (200, 201):
                    print(f"Failed to create DM channel: {resp.status}")
                    return None
                channel_data = await resp.json()
                channel_id = channel_data["id"]
            
            # Send message
            async with session.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                json={"content": content}
            ) as resp:
                if resp.status != 200:
                    print(f"Failed to send DM: {resp.status}")
                    return None
                message_data = await resp.json()
                message_id = message_data["id"]
            
            # Pin the message
            async with session.put(
                f"https://discord.com/api/v10/channels/{channel_id}/pins/{message_id}",
                headers=headers
            ) as resp:
                if resp.status == 204:
                    print(f"✅ DM sent and pinned to {discord_id}")
                    return message_id
                else:
                    print(f"Failed to pin message: {resp.status}")
                    return message_id  # Return message ID even if pin failed
    except Exception as e:
        print(f"DM send/pin error: {e}")
        return None

@require_admin
async def api_admin_pass_config(request):
    """Get all pass-related configuration"""
    pass_keys = [
        "tot_pass_max_accounts", "daily_pass_max_accounts", "all_pass_max_accounts",
        "tot_pass_min_credits", "daily_pass_min_credits", "all_pass_min_credits"
    ]
    
    config = {}
    for key in pass_keys:
        value = ConfigRepository.get(key, "0" if "min" in key else "1")
        try:
            config[key] = int(value)
        except (ValueError, TypeError):
            config[key] = 0 if "min" in key else 1
    
    # Also get pass prices from shop
    passes = {}
    for pass_id in ["tot_pass", "daily_pass", "all_pass"]:
        item = ShopRepository.get_item_by_id(pass_id)
        if item:
            passes[pass_id] = {
                "name": item['name'],
                "price": item['price'],
                "is_available": bool(item['is_available'])
            }
    
    return web.json_response({"config": config, "passes": passes})

@require_admin
async def api_admin_pass_config_update(request):
    """Update pass configuration"""
    try:
        data = await request.json()
        
        allowed_keys = [
            "tot_pass_max_accounts", "daily_pass_max_accounts", "all_pass_max_accounts",
            "tot_pass_min_credits", "daily_pass_min_credits", "all_pass_min_credits"
        ]
        
        updated = []
        for key, value in data.items():
            if key in allowed_keys:
                try:
                    int_value = int(value)
                    if int_value < 0:
                        return web.json_response(
                            {"success": False, "message": f"{key} cannot be negative"},
                            status=400
                        )
                    ConfigRepository.set(key, str(int_value))
                    updated.append(key)
                except (ValueError, TypeError):
                    return web.json_response(
                        {"success": False, "message": f"Invalid value for {key}"},
                        status=400
                    )
        
        # Handle pass availability toggles
        for pass_id in ["tot_pass", "daily_pass", "all_pass"]:
            availability_key = f"{pass_id}_available"
            if availability_key in data:
                ShopRepository.update_item(pass_id, is_available=1 if data[availability_key] else 0)
                updated.append(availability_key)
        
        EventLogger.admin_action(
            admin_id="web_admin",
            admin_name="Web Admin",
            action="update_pass_config",
            details={"updated": updated, "values": data}
        )
        
        return web.json_response({"success": True, "updated": updated})
    
    except Exception as e:
        print(f"Error updating pass config: {e}")
        return web.json_response({"success": False, "message": str(e)}, status=500)

def create_app():
    app = web.Application()
    
    # Public routes
    app.router.add_get("/", home)
    app.router.add_get("/profile/{discord_id}", profile)
    app.router.add_get("/shop", shop_page)
    app.router.add_get("/inventory/{discord_id}", player_inventory_page)
    app.router.add_get("/api/health", health_check)
    app.router.add_get("/api/round-status", round_status)
    app.router.add_get("/api/player-status/{discord_id}", player_status)
    app.router.add_post("/api/buy", buy_item_api)
    
    # Admin auth routes (no auth required)
    app.router.add_get("/admin/login", admin_login_page)
    app.router.add_post("/admin/login", admin_login_submit)
    app.router.add_get("/admin/logout", admin_logout)
    
    # Admin dashboard (requires auth)
    app.router.add_get("/admin/dashboard", admin_dashboard)
    
    # Admin API endpoints (require auth)
    app.router.add_get("/api/admin/overview", api_admin_overview)
    app.router.add_get("/api/admin/players", api_admin_players)
    app.router.add_post("/api/admin/players/update", api_admin_update_player)
    app.router.add_get("/api/admin/items", api_admin_items)
    app.router.add_post("/api/admin/items/create", api_admin_create_item)
    app.router.add_post("/api/admin/items/update", api_admin_update_item)
    app.router.add_post("/api/admin/items/delete", api_admin_delete_item)
    app.router.add_get("/api/admin/events", api_admin_events)
    app.router.add_get("/api/admin/approvals", api_admin_approvals)
    app.router.add_post("/api/admin/approvals/approve", api_admin_approve)
    app.router.add_post("/api/admin/approvals/reject", api_admin_reject)

    app.router.add_get("/api/admin/pass-config", api_admin_pass_config)
    app.router.add_post("/api/admin/pass-config/update", api_admin_pass_config_update)
    
    return app

if __name__ == "__main__":
    app = create_app()
    print(f"🌐 Web server starting on http://{settings.API_HOST}:{settings.API_PORT}")
    web.run_app(app, host=settings.API_HOST, port=settings.API_PORT)