import asyncio
import json
import random
from datetime import datetime, timedelta
from bot.core.witness_system import WitnessSystem

import discord
from database.repositories.effects_repo import EffectsRepository
from database.repositories.round_repo import RoundRepository
from database.repositories.config_repo import ConfigRepository
from database.repositories.player_repo import PlayerRepository
from database.repositories.earnings_repo import EarningsRepository
from database.repositories.game_state_repo import GameStateRepository
from database.repositories.vault_repo import VaultRepository

# The 10 rooms in the station
ROOMS = [
    "cafeteria", "medbay", "electrical", "reactor", "security",
    "admin", "navigation", "weapons", "shields", "comms"
]

# Tasks available in each room
ROOM_TASKS = {
    "cafeteria": ["Empty Trash", "Wipe Tables"],
    "medbay": ["Scan Patients", "Restock Medkits"],
    "electrical": ["Fix Wiring", "Calibrate Breakers"],
    "reactor": ["Align Engine", "Start Reactor"],
    "security": ["Review Cameras", "Clear Logs"],
    "admin": ["Swipe Card", "Upload Data"],
    "navigation": ["Chart Course", "Stabilize Steering"],
    "weapons": ["Clear Asteroids", "Load Weapons"],
    "shields": ["Prime Shields", "Calibrate Shield"],
    "comms": ["Fix Comms", "Download Data"],
}
def format_timestamp(unix_time: float, style: str = "R") -> str:
    """
    Format a Unix timestamp as a Discord timestamp markdown.
    Styles: t, T, d, D, f, F, R (R = relative, best for countdowns)
    """
    return f"<t:{int(unix_time)}:{style}>"

def ts(unix_time: float) -> str:
    """Format a Unix timestamp as a Discord relative countdown.
    Updates automatically on the client side with zero API calls."""
    return f"<t:{int(unix_time)}:R>"
class GameState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.round_id = None
        self.status = "idle"
        self.started_at = None
        self.current_imposter_id = None
        self.participants = []
        self.stop_votes = set()
        self.prep_end_time = None
        self.round_end_time = None
        self.next_rotation_time = None
        self.prep_task = None
        self.round_task = None
        self.rotation_task = None
        self.loot_task = None
        self.cooldown_task = None
        self.respawn_task = None
        self.jail_task = None
        self.final_phase = False
        self.crew_killed = 0
        self.active_loot = {}
        self.phase_number = 0  # NEW: Tracks imposter rotation phases

class GameManager:
    def __init__(self, bot):
        self.bot = bot
        self.state = GameState()
        self._announcement_channel_id = None
        self.witness_system = WitnessSystem(bot)
        self.respawn_task = None
        self.jail_task = None
        self._player_dm_messages = {}  # {discord_id: [message_ids]}
    
    def set_announcement_channel(self, channel_id: int):
        self._announcement_channel_id = channel_id
    
    async def _get_announcement_channel(self):
        if self._announcement_channel_id:
            return self.bot.get_channel(self._announcement_channel_id)
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                return channel
        return None
    
    async def announce(self, message: str, embed=None):
        channel = await self._get_announcement_channel()
        if channel:
            await channel.send(message, embed=embed)

    async def send_tracked_dm(self, user: discord.User, content: str, pin: bool = False) -> discord.Message:
        """Send a DM and track it for cleanup. Returns the message object."""
        try:
            message = await user.send(content)
            
            # Track the message ID for cleanup
            discord_id = str(user.id)
            if discord_id not in self._player_dm_messages:
                self._player_dm_messages[discord_id] = []
            self._player_dm_messages[discord_id].append(message.id)
            
            # Pin if requested
            if pin:
                try:
                    await message.pin()
                except Exception as e:
                    print(f"Failed to pin DM: {e}")
            
            return message
        except Exception as e:
            print(f"Failed to send DM to {user.id}: {e}")
            return None
    async def clear_channel(self, channel):
        """
        Clears all messages in a channel except pinned ones.
        Returns the number of messages deleted, or -1 if no permission.
        """
        if channel is None:
            return 0
        
        try:
            deleted = await channel.purge(
                limit=None,
                check=lambda m: not m.pinned,
                bulk=True
            )
            
            # NEW: Wait for Discord to fully process the deletion
            # before allowing new messages to be sent
            await asyncio.sleep(1.5)
            
            return len(deleted)
        except discord.Forbidden:
            return -1
        except discord.HTTPException as e:
            print(f"⚠️ Channel clear failed: {e}")
            return 0
    # ============ ROOM HELPERS ============
    
    def get_players_in_room(self, room: str, exclude_jailed: bool = False):
        """Get all on-duty participants in a specific room"""
        result = []
        for discord_id in self.state.participants:
            player = PlayerRepository.get_by_discord_id(discord_id)
            if not player or not player['is_on_duty']:
                continue
            if player['current_room'] != room:
                continue
            if exclude_jailed and PlayerRepository.is_in_jail(player):
                continue
            result.append(player)
        return result
    
    def get_room_name(self, room: str) -> str:
        """Pretty room names"""
        names = {
            "cafeteria": "Cafeteria",
            "medbay": "Medbay",
            "electrical": "Electrical",
            "reactor": "Reactor",
            "security": "Security",
            "admin": "Admin",
            "navigation": "Navigation",
            "weapons": "Weapons",
            "shields": "Shields",
            "comms": "Communications",
        }
        return names.get(room, room.title())
    
    # ============ START GAME ============
    
    async def start_game(self):
        if self.state.status != "idle":
            return {"success": False, "message": "❌ A round is already in progress!"}
        
        # Clear channel
        channel = await self._get_announcement_channel()
        cleared_count = 0
        if channel:
            cleared_count = await self.clear_channel(channel)
            if cleared_count == -1:
                await channel.send(
                    "⚠️ **Warning:** Bot lacks `MANAGE_MESSAGES` permission."
                )
            elif cleared_count > 0:
                print(f"🧹 Cleared {cleared_count} messages from channel.")
        
        round_data = RoundRepository.create_new()
        
        self.state.round_id = round_data['id']
        self.state.status = "prep"
        self.state.started_at = round_data['started_at']
        self.state.current_imposter_id = None
        self.state.participants = []
        self.state.stop_votes = set()
        self.state.final_phase = False
        self.state.crew_killed = 0
        self.state.active_loot = {}
        self.state.phase_number = 0  # Reset phase counter
        
        for player in PlayerRepository.get_all_on_duty():
            PlayerRepository.update_room(player['id'], "cafeteria")
            PlayerRepository.reset_action_steps(player['id'])
        
        prep_duration = ConfigRepository.get_int("prep_phase_duration", 60)
        self.state.prep_end_time = datetime.now().timestamp() + prep_duration
        
        # NEW: Write live state for web
        GameStateRepository.clear()
        GameStateRepository.set("status", "prep")
        GameStateRepository.set("prep_end_time", self.state.prep_end_time)
        GameStateRepository.set("participants", len(self.state.participants))
        
        self.state.prep_task = asyncio.create_task(self._prep_countdown())
        
        return {
            "success": True,
            "prep_duration": prep_duration,
            "cleared_messages": cleared_count
        }
    
    async def _prep_countdown(self):
        try:
            while True:
                remaining = self.state.prep_end_time - datetime.now().timestamp()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(remaining, 10))
            await self._transition_to_active()
        except asyncio.CancelledError:
            pass
    
    async def _transition_to_active(self):
        if self.state.status != "prep":
            return
        
        players = PlayerRepository.get_all_on_duty()
        self.state.participants = [p['discord_id'] for p in players]
        
        # ... existing code ...
        
        # Set spawn protection for all players (20 seconds from round start)
        from datetime import datetime, timedelta
        protection_until = (datetime.now() + timedelta(seconds=20)).isoformat()
        for player in players:
            PlayerRepository.update_spawn_protection(player['id'], protection_until)
            PlayerRepository.reset_first_action(player['id'])
        
        imposter_count = ConfigRepository.get_int("imposters_count", 1)
        min_players = imposter_count + 2
        
        if len(self.state.participants) < min_players:
            await self.announce(
                f"⚠️ **ROUND CANCELLED**\n"
                f"Not enough players! Need at least {min_players}.\n"
                f"Only {len(self.state.participants)} were on duty."
            )
            await self._force_end("cancelled")
            return
        
        self.state.status = "active"
        RoundRepository.update_status(self.state.round_id, "active")
        
        for discord_id in self.state.participants:
            player = PlayerRepository.get_by_discord_id(discord_id)
            if player:
                EarningsRepository.ensure_entry(
                    self.state.round_id, player['id'], discord_id, player['username']
                )
        
        round_duration = ConfigRepository.get_int("round_duration", 600)
        self.state.round_end_time = datetime.now().timestamp() + round_duration
        
        self.state.phase_number = 1
        await self._rotate_imposter(first_rotation=True)
        
        rotation_interval = ConfigRepository.get_int("imposter_rotation_interval", 180)
        self.state.next_rotation_time = datetime.now().timestamp() + rotation_interval
        
        # NEW: Write live state for web
        GameStateRepository.set("status", "active")
        GameStateRepository.set("round_end_time", self.state.round_end_time)
        GameStateRepository.set("next_rotation_time", self.state.next_rotation_time)
        GameStateRepository.set("phase_number", self.state.phase_number)
        GameStateRepository.set("final_phase", "false")
        GameStateRepository.set("participants", len(self.state.participants))
        GameStateRepository.set("stop_votes", "0")
        
        # First phase
        self.state.phase_number = 1
        await self._rotate_imposter(first_rotation=True)
        
        rotation_interval = ConfigRepository.get_int("imposter_rotation_interval", 180)
        self.state.next_rotation_time = datetime.now().timestamp() + rotation_interval
        
        self.state.round_task = asyncio.create_task(self._round_countdown())
        self.state.rotation_task = asyncio.create_task(self._rotation_countdown())
        self.state.loot_task = asyncio.create_task(self._loot_spawner())
        self.state.cooldown_task = asyncio.create_task(self._cooldown_monitor())
        self.respawn_task = asyncio.create_task(self._respawn_monitor())
        self.jail_task = asyncio.create_task(self._jail_monitor())
        
        # Announcement with live timer
        await self.announce(
            f"🚀 **ROUND STARTED!**\n\n"
            f"👥 {len(self.state.participants)} players on duty\n"
            f"⏱️ Round ends {ts(self.state.round_end_time)}\n"
            f"🔪 The first Imposter has been chosen...\n\n"
            f"The bank is now **LOCKED**. Good luck!"
        )
    
    # ============ COOLDOWN MONITOR ============
    
    async def _cooldown_monitor(self):
        """Background task that pings publicly when cooldowns expire"""
        try:
            while self.state.status == "active":
                players = PlayerRepository.get_all_on_duty()
                now = datetime.now().timestamp()
                channel = await self._get_announcement_channel()
                
                # Public actions - everyone sees these pings
                public_actions = [
                    ("move", "move_cooldown", 90),
                    ("search", "search_cooldown", 30),
                    ("rob", "rob_cooldown", 60),
                    ("task", "task_cooldown", 45),
                ]
                
                # Private action - only imposter sees this (via DM)
                private_actions = [
                    ("kill", "kill_cooldown", 120),
                ]
                
                for player in players:
                    # ============ PUBLIC COOLDOWNS ============
                    for action, config_key, default_cd in public_actions:
                        column = f"last_{action}_at"
                        last_used = player[column]
                        
                        if not last_used or last_used == "1970-01-01T00:00:00":
                            continue
                        
                        try:
                            last_ts = datetime.fromisoformat(last_used).timestamp()
                        except:
                            continue
                        
                        cd = ConfigRepository.get_int(config_key, default_cd)
                        
                        if now - last_ts >= cd:
                            PlayerRepository.update_cooldown(player['id'], action, "1970-01-01T00:00:00")
                            if channel:
                                await channel.send(
                                    f"✅ <@{player['discord_id']}>, your `/{action}` cooldown is ready!"
                                )
                    
                    # ============ PRIVATE COOLDOWNS (IMPOSTER ONLY) ============
                    for action, config_key, default_cd in private_actions:
                        # Only check if this player is the current imposter
                        if player['discord_id'] != self.state.current_imposter_id:
                            continue
                        
                        column = f"last_{action}_at"
                        last_used = player[column]
                        
                        if not last_used or last_used == "1970-01-01T00:00:00":
                            continue
                        
                        try:
                            last_ts = datetime.fromisoformat(last_used).timestamp()
                        except:
                            continue
                        
                        # Use reduced cooldown during Final Phase
                        if self.state.final_phase:
                            cd = ConfigRepository.get_int("kill_cooldown_final", 30)
                        else:
                            cd = ConfigRepository.get_int(config_key, default_cd)
                        
                        if now - last_ts >= cd:
                            PlayerRepository.update_cooldown(player['id'], action, "1970-01-01T00:00:00")
                            
                            # Send PRIVATE DM instead of public ping
                            try:
                                user = await self.bot.fetch_user(int(player['discord_id']))
                                await self.send_tracked_dm(user,
                                    f"🔪 **Your `/kill` cooldown is ready!**\n\n"
                                    f"You can eliminate another crewmate.\n"
                                    f"*This message is private — your secret is safe.*"
                                )
                            except Exception:
                                pass
                
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass
    
    # ============ LOOT SPAWNER ============
    
    async def _loot_spawner(self):
        """Background task that spawns loot in random rooms"""
        try:
            while self.state.status == "active":
                interval = ConfigRepository.get_int("loot_spawn_interval", 180)
                await asyncio.sleep(interval)
                
                if self.state.status != "active":
                    break
                
                # Pick a random room that doesn't already have loot
                available_rooms = [r for r in ROOMS if r not in self.state.active_loot]
                if not available_rooms:
                    continue
                
                room = random.choice(available_rooms)
                min_amt = ConfigRepository.get_int("loot_amount_min", 50)
                max_amt = ConfigRepository.get_int("loot_amount_max", 200)
                amount = random.randint(min_amt, max_amt)
                
                self.state.active_loot[room] = {
                    "amount": amount,
                    "spawned_at": datetime.now().timestamp()
                }
                
                room_name = self.get_room_name(room)
                await self.announce(
                    f"💰 **LOOT SPOTTED!**\n"
                    f"A cache of **{amount} Pocket Credits** has been discovered in **{room_name}**!\n"
                    f"Get there before someone else does!"
                )
                
                # Despawn check task
                asyncio.create_task(self._loot_despawn(room))
        except asyncio.CancelledError:
            pass
    
    async def _loot_despawn(self, room: str):
        """Despawn loot after configured time"""
        try:
            despawn_time = ConfigRepository.get_int("loot_despawn_time", 300)
            await asyncio.sleep(despawn_time)
            if room in self.state.active_loot:
                del self.state.active_loot[room]
                room_name = self.get_room_name(room)
                await self.announce(
                    f"💨 The loot cache in **{room_name}** has vanished into thin air..."
                )
        except asyncio.CancelledError:
            pass
    
    # ============ LOOT CLAIMING ============
    
    async def claim_loot(self, discord_id: str):
        """Player claims loot in their current room"""
        player = PlayerRepository.get_by_discord_id(discord_id)
        if not player:
            return {"success": False, "message": "❌ Not registered."}
        
        room = player['current_room']
        if room not in self.state.active_loot:
            return {"success": False, "message": "❌ No loot in this room."}
        
        loot = self.state.active_loot[room]
        amount = loot["amount"]
        
        # Give credits
        new_balance = player['pocket_credits'] + amount
        PlayerRepository.update_balance(player['id'], pocket_credits=new_balance)
        
        # Track earnings
        EarningsRepository.add_earned(self.state.round_id, player['id'], amount)
        
        # Remove loot
        del self.state.active_loot[room]
        
        room_name = self.get_room_name(room)
        return {
            "success": True,
            "message": f"💰 You looted **{amount} Pocket Credits** from {room_name}!",
            "amount": amount
        }
    
    # ============ IMPOSTER ROTATION ============
    
    async def _rotate_imposter(self, first_rotation=False, due_to_jail=False):
        available = []
        for discord_id in self.state.participants:
            player = PlayerRepository.get_by_discord_id(discord_id)
            if player and not PlayerRepository.is_in_jail(player):
                available.append(discord_id)
        
        if not available:
            await self.announce("⚠️ All players are jailed! Round ending.")
            await self._force_end("all_jailed")
            return
        
        candidates = [p for p in available if p != self.state.current_imposter_id]
        if not candidates:
            candidates = available
        
        new_imposter_id = random.choice(candidates)
        old_imposter_id = self.state.current_imposter_id
        self.state.current_imposter_id = new_imposter_id
        
        RoundRepository.set_imposters(self.state.round_id, [new_imposter_id])
        
        # DM new imposter
        try:
            user = await self.bot.fetch_user(int(new_imposter_id))
            if first_rotation:
                await self.send_tracked_dm(user,
                    f"🔪 **YOU ARE THE IMPOSTER!**\n\n"
                    f"Phase {self.state.phase_number} has begun.\n"
                    f"Eliminate the crew and steal their Pocket Credits!\n\n"
                    f"*This message is secret — don't share it!*"
                )
            elif due_to_jail:
                await self.send_tracked_dm(user,
                    f"🔪 **EMERGENCY SHIFT — YOU ARE NOW THE IMPOSTER!**\n\n"
                    f"The previous Imposter was jailed. You've been chosen to take their place.\n"
                    f"Phase {self.state.phase_number} continues.\n\n"
                    f"*This message is secret — don't share it!*"
                )
            else:
                await self.send_tracked_dm(user,
                    f"🔪 **PHASE {self.state.phase_number} — YOU ARE NOW THE IMPOSTER!**\n\n"
                    f"The mantle has passed to you.\n"
                    f"Use your powers wisely before the next phase.\n\n"
                    f"*This message is secret — don't share it!*"
                )
        except Exception:
            pass
        
        # DM old imposter
        if old_imposter_id and old_imposter_id != new_imposter_id:
            try:
                old_user = await self.bot.fetch_user(int(old_imposter_id))
                await self.send_tracked_dm(old_user,
                    f"👷 **You are no longer the Imposter.**\n\n"
                    f"You're now a regular crewmate. Any loot you stole is yours to keep!"
                )
            except Exception:
                pass
        
        return new_imposter_id
        
        # DM old imposter
        if old_imposter_id and old_imposter_id != new_imposter_id:
            try:
                old_user = await self.bot.fetch_user(int(old_imposter_id))
                await old_user.send(
                    f"👷 **Phase {self.state.phase_number} — You are no longer the Imposter.**\n\n"
                    f"You're now a regular crewmate. Any loot you stole is yours to keep!"
                )
            except Exception:
                pass
        
        return new_imposter_id
    
    async def _rotation_countdown(self):
        try:
            while self.state.status == "active":
                remaining = self.state.next_rotation_time - datetime.now().timestamp()
                if remaining <= 0:
                    # Increment phase number
                    self.state.phase_number += 1
                    
                    await self.announce(
                        f"🔄 **PHASE {self.state.phase_number} — SHIFT CHANGE!**\n\n"
                        "The Imposter role has been reassigned...\n"
                        "Check your DMs if you've been chosen."
                    )
                    await self._rotate_imposter()
                    rotation_interval = ConfigRepository.get_int("imposter_rotation_interval", 180)
                    self.state.next_rotation_time = datetime.now().timestamp() + rotation_interval
                    
                    # Update web state
                    GameStateRepository.set("next_rotation_time", self.state.next_rotation_time)
                    GameStateRepository.set("phase_number", self.state.phase_number)
                else:
                    await asyncio.sleep(min(remaining, 10))
        except asyncio.CancelledError:
            pass
    
    # ============ ROUND COUNTDOWN ============
    
    async def _round_countdown(self):
        try:
            while True:
                remaining = self.state.round_end_time - datetime.now().timestamp()
                if remaining <= 0:
                    await self._end_round_by_timer()
                    return
                
                # Trigger Final Phase at 60 seconds remaining
                if remaining <= 120 and not self.state.final_phase:
                    await self._trigger_final_phase("time_running_out")
                
                if 55 <= remaining <= 65 and not self.state.final_phase:
                    await self.announce("⏰ **1 MINUTE REMAINING!**")
                elif 25 <= remaining <= 35 and not self.state.final_phase:
                    await self.announce("⏰ **30 SECONDS REMAINING!**")
                
                await asyncio.sleep(min(remaining, 10))
        except asyncio.CancelledError:
            pass
    
    async def _trigger_final_phase(self, reason=""):
        if self.state.final_phase:
            return
        self.state.final_phase = True
        
        # Update web state
        GameStateRepository.set("final_phase", "true")
        
        # Reset action steps for all participants
        for discord_id in self.state.participants:
            player = PlayerRepository.get_by_discord_id(discord_id)
            if player:
                PlayerRepository.reset_action_steps(player['id'])
        
        await self.announce(
            "🚨 **FINAL PHASE — LAST 2 MINUTES!**\n\n"
            "Time is running out!\n"
            "Everyone gets **5 action steps** to survive or escape!\n"
            "The Imposter's kill cooldown is reduced drastically!"
        )
    
    async def _end_round_by_timer(self):
        if self.state.status != "active":
            return
        
        winner = EarningsRepository.get_winner(self.state.round_id)
        top_3 = EarningsRepository.get_top_3(self.state.round_id)
        
        if winner:
            RoundRepository.set_winner(self.state.round_id, winner['discord_id'], "timer")
        
        medals = ["🥇", "🥈", "🥉"]
        leaderboard_lines = []
        for i, entry in enumerate(top_3):
            medal = medals[i] if i < 3 else f"{i+1}."
            leaderboard_lines.append(
                f"{medal} **{entry['username']}** — {entry['total']:,} credits earned"
            )
        
        leaderboard_text = "\n".join(leaderboard_lines) if leaderboard_lines else "No earnings recorded."
        
        bond_rewards = [500, 300, 150]
        reward_lines = []
        for i, entry in enumerate(top_3):
            if i < len(bond_rewards):
                player = PlayerRepository.get_by_discord_id(entry['discord_id'])
                if player:
                    new_total = player['vault_bonds'] + bond_rewards[i]
                    PlayerRepository.update_balance(player['id'], vault_bonds=new_total)
                    reward_lines.append(
                        f"• {medals[i]} {entry['username']} receives **+{bond_rewards[i]} Vault Bonds**"
                    )
        
        rewards_text = "\n".join(reward_lines) if reward_lines else "No rewards distributed."
        
        winner_name = winner['username'] if winner else "No one"
        await self.announce(
            f"🏆 **ROUND COMPLETE!**\n\n"
            f"**🏅 Winner: {winner_name}**\n\n"
            f"**📊 Top 3:**\n{leaderboard_text}\n\n"
            f"**💎 Rewards:**\n{rewards_text}"
        )
        # Apply vault interest
        beneficiaries = VaultRepository.apply_interest(self.state.round_id)
        if beneficiaries:
            interest_lines = []
            for b in beneficiaries[:5]:  # Top 5
                interest_lines.append(f"• {b['username']}: +{b['interest']} 💎")
            
            await self.announce(
                f"💎 **VAULT INTEREST APPLIED!**\n\n"
                f"Interest rate: {ConfigRepository.get_int('vault_interest_rate', 5)}%\n\n"
                + "\n".join(interest_lines)
            )
        await self._force_end("timer")
    
    # ============ STOP GAME ============
    
    async def force_stop(self, reason="admin"):
        if self.state.status == "idle":
            return {"success": False, "message": "❌ No round is in progress!"}
        
        await self._force_end(reason)
        return {"success": True, "message": f"✅ Round has been stopped."}
    
    async def _force_end(self, reason="ended"):
        # Cancel all tasks
        for task in [self.state.prep_task, self.state.round_task, 
                     self.state.rotation_task, self.state.loot_task, 
                     self.state.cooldown_task, self.respawn_task, self.jail_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        if self.state.round_id:
            RoundRepository.update_status(self.state.round_id, "ended")
        
        # Reset all players
        for discord_id in self.state.participants:
            player = PlayerRepository.get_by_discord_id(discord_id)
            if player:
                PlayerRepository.set_on_duty(player['id'], False)
                PlayerRepository.reset_action_steps(player['id'])
                if not player['is_alive']:
                    PlayerRepository.respawn_player(player['id'])

        # Clear all active effects
        for discord_id in self.state.participants:
            player = PlayerRepository.get_by_discord_id(discord_id)
            if player:
                EffectsRepository.clear_all_effects(player['id'])
        
        # NEW: Clean up tracked DMs (preserves pinned messages)
        await self.cleanup_player_dms()
        
        # Clear live state
        GameStateRepository.clear()
        GameStateRepository.set("status", "idle")
        
        self.state.reset()
        
        await self.announce(f"🛑 **Round ended.** ({reason})")
    
    # ============ DM CLEANUP ============
    
    async def cleanup_player_dms(self):
        """Clean up tracked DMs, preserving pinned messages"""
        if not self._player_dm_messages:
            return
        
        cleaned_count = 0
        preserved_count = 0
        
        for discord_id, message_ids in self._player_dm_messages.items():
            try:
                user = await self.bot.fetch_user(int(discord_id))
                for message_id in message_ids:
                    try:
                        message = await user.fetch_message(message_id)
                        
                        # Skip pinned messages (approval/rejection notices)
                        if message.pinned:
                            preserved_count += 1
                            continue
                        
                        await message.delete()
                        cleaned_count += 1
                    except discord.NotFound:
                        # Message already deleted
                        pass
                    except discord.Forbidden:
                        # Can't delete this message
                        pass
                    except Exception as e:
                        print(f"Failed to delete DM {message_id}: {e}")
            except Exception as e:
                print(f"Failed to clean DMs for {discord_id}: {e}")
        
        print(f"✅ DM cleanup: {cleaned_count} deleted, {preserved_count} preserved (pinned)")
        self._player_dm_messages.clear()
    
    # ============ CLOCK IN / OUT ============
    
    async def clock_in(self, discord_id: str, username: str):
        if self.state.status == "active":
            return {"success": False, "message": "❌ Can't clock in during an active round!"}
        
        player = PlayerRepository.get_by_discord_id(discord_id)
        if not player:
            return {"success": False, "message": "❌ You're not registered! Use `/register` first."}
        
        if player['is_on_duty']:
            return {"success": False, "message": "❌ You're already on duty!"}
        
        PlayerRepository.set_on_duty(player['id'], True)
        PlayerRepository.update_room(player['id'], "cafeteria")
        
        if self.state.status == "prep":
            if discord_id not in self.state.participants:
                self.state.participants.append(discord_id)
        
        return {
            "success": True,
            "message": f"✅ You are now **On Duty** in the Cafeteria!"
        }
    
    async def clock_out(self, discord_id: str):
        player = PlayerRepository.get_by_discord_id(discord_id)
        if not player:
            return {"success": False, "message": "❌ You're not registered!"}
        
        if not player['is_on_duty']:
            return {"success": False, "message": "❌ You're not on duty!"}
        
        if self.state.status == "active" and discord_id in self.state.participants:
            return {
                "success": False,
                "message": "❌ You can't clock out during an active round!"
            }
        
        PlayerRepository.set_on_duty(player['id'], False)
        
        if self.state.status == "prep" and discord_id in self.state.participants:
            self.state.participants.remove(discord_id)
        
        return {"success": True, "message": "✅ You are now **Off Duty**."}
    
    # ============ VOTE TO STOP ============
    
    async def vote_stop(self, discord_id: str):
        if self.state.status != "active":
            return {"success": False, "message": "❌ Can only vote during an active round!"}
        
        if discord_id not in self.state.participants:
            return {"success": False, "message": "❌ You're not in this round!"}
        
        if discord_id in self.state.stop_votes:
            return {"success": False, "message": "❌ You've already voted!"}
        
        self.state.stop_votes.add(discord_id)
        
        # NEW: Update web state
        GameStateRepository.set("stop_votes", str(len(self.state.stop_votes)))
        
        total = len(self.state.participants)
        votes = len(self.state.stop_votes)
        needed = (total // 2) + 1
        
        if votes >= needed:
            await self.announce(
                f"🗳️ **MAJORITY VOTED TO STOP**\n{votes}/{total} players voted."
            )
            await self._force_end("majority vote")
            return {"success": True, "message": "✅ Your vote ended the round.", "ended": True}
        
        return {
            "success": True,
            "message": f"✅ Vote counted. ({votes}/{needed} needed)",
            "votes": votes, "total": total, "needed": needed, "ended": False
        }
    
    # ============ STATUS QUERIES ============
    
    def get_status(self):
        if self.state.status == "idle":
            return {
                "status": "idle",
                "message": "🔵 **No round in progress.**\nAdmins can use `/startgame` to begin."
            }
        
        elif self.state.status == "prep":
            return {
                "status": "prep",
                "players": len(self.state.participants),
                "message": (
                    f"🟡 **PREPARATION PHASE**\n"
                    f"⏱️ Starts {ts(self.state.prep_end_time)}\n"
                    f"👥 Players on duty: {len(self.state.participants)}\n\n"
                    f"Use `/clockin` to join or `/offduty` to leave."
                )
            }
        
        elif self.state.status == "active":
            votes = len(self.state.stop_votes)
            total = len(self.state.participants)
            needed = (total // 2) + 1
            
            final_text = "\n🚨 **FINAL PHASE ACTIVE**" if self.state.final_phase else ""
            
            return {
                "status": "active",
                "phase": self.state.phase_number,
                "players": total,
                "message": (
                    f"🔴 **ROUND ACTIVE — Phase {self.state.phase_number}**{final_text}\n"
                    f"⏱️ Round ends {ts(self.state.round_end_time)}\n"
                    f"🔄 Next shift change {ts(self.state.next_rotation_time)}\n"
                    f"👥 Players: {total}\n"
                    f"🗳️ Stop votes: {votes}/{needed}\n\n"
                    f"The bank is **LOCKED**. Good luck!"
                )
            }
        
        return {"status": "unknown", "message": "Unknown state"}

    async def _respawn_monitor(self):
        """Background task that respawns dead players"""
        try:
            while self.state.status == "active":
                dead_players = PlayerRepository.get_all_dead()
                now = datetime.now()
                
                for player in dead_players:
                    if player['respawn_at']:
                        try:
                            respawn_time = datetime.fromisoformat(player['respawn_at'])
                            if now >= respawn_time:
                                # Respawn player
                                PlayerRepository.respawn_player(player['id'])
                                
                                # Send tracked DM
                                try:
                                    user = await self.bot.fetch_user(int(player['discord_id']))
                                    await self.send_tracked_dm(user,
                                        "✅ **YOU HAVE RESPAWNED!**\n\n"
                                        "You're back in the Cafeteria.\n"
                                        "You lost all your Pocket Credits, but your Vault Bonds are safe.\n"
                                        "Good luck!"
                                    )
                                except Exception as e:
                                    print(f"Failed to DM respawned player: {e}")
                        except:
                            pass
                
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            pass
    
    async def _jail_monitor(self):
        """Background task that releases jailed players"""
        try:
            while self.state.status == "active":
                jailed_players = PlayerRepository.get_all_jailed()
                now = datetime.now()
                
                for player in jailed_players:
                    if player['jail_release_at']:
                        try:
                            release_time = datetime.fromisoformat(player['jail_release_at'])
                            if now >= release_time:
                                # Release from jail
                                PlayerRepository.set_jail_release(player['id'], None)
                                
                                # Notify player
                                try:
                                    user = await self.bot.fetch_user(int(player['discord_id']))
                                    await user.send(
                                        "✅ **YOU'VE BEEN RELEASED FROM JAIL!**\n\n"
                                        "You're free to play again."
                                    )
                                except:
                                    pass
                        except:
                            pass
                
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
    
    def is_imposter(self, discord_id: str) -> bool:
        return discord_id == self.state.current_imposter_id
    
    def is_participant(self, discord_id: str) -> bool:
        return discord_id in self.state.participants
    
    def get_current_imposter(self) -> str:
        return self.state.current_imposter_id