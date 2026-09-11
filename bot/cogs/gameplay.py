import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from database.repositories.effects_repo import EffectsRepository
from database.repositories.player_repo import PlayerRepository
from database.repositories.config_repo import ConfigRepository
from database.repositories.earnings_repo import EarningsRepository
from bot.core.game_manager import ROOMS, ROOM_TASKS
import random

class GameplayCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def _check_cooldown(self, player: dict, action: str) -> tuple[bool, int]:
        """Returns (is_ready, seconds_remaining)"""
        column = f"last_{action}_at"
        last_used = player[column]
        
        if not last_used or last_used == "1970-01-01T00:00:00":
            return True, 0
        
        try:
            last_ts = datetime.fromisoformat(last_used).timestamp()
        except:
            return True, 0
        
        config_key = f"{action}_cooldown"
        defaults = {"move": 90, "search": 30, "rob": 60, "task": 45, "kill": 120}
        
        # During Final Phase, use reduced kill cooldown
        if action == "kill" and self.bot.game_manager.state.final_phase:
            cd = ConfigRepository.get_int("kill_cooldown_final", 30)
        else:
            cd = ConfigRepository.get_int(config_key, defaults.get(action, 60))
        
        elapsed = datetime.now().timestamp() - last_ts
        remaining = cd - elapsed
        
        if remaining <= 0:
            return True, 0
        return False, int(remaining)
    
    def _use_action(self, player: dict, action: str):
        """Mark action as used and increment steps if in Final Phase"""
        PlayerRepository.update_cooldown(player['id'], action, datetime.now().isoformat())
        if self.bot.game_manager.state.final_phase:
            PlayerRepository.increment_action_steps(player['id'])
    
    def _check_final_phase_steps(self, player: dict) -> bool:
        """Returns True if player has steps remaining"""
        if not self.bot.game_manager.state.final_phase:
            return True
        return player['action_steps_used'] < 5
    
    @app_commands.command(name="move", description="Move to another room")
    @app_commands.describe(room="The room to move to")
    @app_commands.choices(room=[
        app_commands.Choice(name=r.title(), value=r) for r in ROOMS
    ])
    async def move(self, interaction: discord.Interaction, room: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player or not player['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        # NEW: Mark first action (removes spawn protection)
        PlayerRepository.mark_first_action(player['id'])
        
        gm = self.bot.game_manager
        if gm.state.status != "active":
            await interaction.followup.send("❌ No active round!", ephemeral=True)
            return
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player or not player['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        if PlayerRepository.is_in_jail(player):
            await interaction.followup.send("❌ You're in jail!", ephemeral=True)
            return
        
        if not self._check_final_phase_steps(player):
            await interaction.followup.send("❌ You've used all 5 action steps in Final Phase!", ephemeral=True)
            return
        
        ready, remaining = self._check_cooldown(player, "move")
        if not ready:
            await interaction.followup.send(
                f"❌ Movement on cooldown! Ready in {remaining}s.",
                ephemeral=True
            )
            return
        
        target_room = room.value
        current_room = player['current_room']
        
        if target_room == current_room:
            await interaction.followup.send(f"❌ You're already in {gm.get_room_name(current_room)}!", ephemeral=True)
            return
        
        # Move player
        PlayerRepository.update_room(player['id'], target_room)
        self._use_action(player, "move")
        
        # Check who's in the new room
        players_in_room = gm.get_players_in_room(target_room)
        other_players = [p for p in players_in_room if p['discord_id'] != str(interaction.user.id)]
        
        if other_players:
            names = ", ".join([f"**{p['username']}**" for p in other_players])
            message = f"🚶 You moved to **{gm.get_room_name(target_room)}**.\n\n👥 You found: {names}"
        else:
            message = f"🚶 You moved to **{gm.get_room_name(target_room)}**.\n\n🏠 The room is empty."
        
        # Check for loot
        if target_room in gm.state.active_loot:
            loot_amount = gm.state.active_loot[target_room]["amount"]
            message += f"\n\n💰 You spot a loot cache worth **{loot_amount} Pocket Credits**! Use `/loot` to claim it."
        
        await interaction.followup.send(message, ephemeral=True)
    
    @app_commands.command(name="search", description="Search your current room")
    async def search(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player or not player['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        # NEW: Mark first action (removes spawn protection)
        PlayerRepository.mark_first_action(player['id'])
        
        gm = self.bot.game_manager
        if gm.state.status != "active":
            await interaction.followup.send("❌ No active round!", ephemeral=True)
            return
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player or not player['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        ready, remaining = self._check_cooldown(player, "search")
        if not ready:
            await interaction.followup.send(f"❌ Search on cooldown! Ready in {remaining}s.", ephemeral=True)
            return
        
        self._use_action(player, "search")
        
        room = player['current_room']
        # Include jailed players in search (they're physically there, just incapacitated)
        players_in_room = gm.get_players_in_room(room, exclude_jailed=False)
        other_players = [p for p in players_in_room if p['discord_id'] != str(interaction.user.id)]
        
        embed = discord.Embed(
            title=f"🔍 Searching {gm.get_room_name(room)}",
            color=discord.Color.blue()
        )
        
        if other_players:
            # NEW: Show jailed status next to names
            lines = []
            for p in other_players:
                name = p['username']
                if PlayerRepository.is_in_jail(p):
                    lines.append(f"• {name} ⚖️ *(jailed)*")
                elif not p['is_alive']:
                    lines.append(f"• {name} 💀 *(dead)*")
                else:
                    lines.append(f"• {name}")
            embed.add_field(name="👥 People in this room", value="\n".join(lines), inline=False)
        else:
            embed.description = "🏠 The room is empty."
        
        # Show available tasks (only if not jailed)
        if not PlayerRepository.is_in_jail(player):
            tasks = ROOM_TASKS.get(room, [])
            if tasks:
                embed.add_field(name="📋 Available Tasks", value="\n".join([f"• {t}" for t in tasks]), inline=False)
        
        # Show loot
        if room in gm.state.active_loot:
            loot_amount = gm.state.active_loot[room]["amount"]
            embed.add_field(name="💰 Loot Cache", value=f"{loot_amount} Pocket Credits\nUse `/loot` to claim.", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="tasks", description="View tasks in your current room")
    async def tasks(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player or not player['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        # NEW: Mark first action (removes spawn protection)
        PlayerRepository.mark_first_action(player['id'])
        
        gm = self.bot.game_manager
        if gm.state.status != "active":
            await interaction.followup.send("❌ No active round!", ephemeral=True)
            return
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player or not player['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        room = player['current_room']
        tasks = ROOM_TASKS.get(room, [])
        
        if not tasks:
            await interaction.followup.send("❌ No tasks in this room.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"📋 Tasks in {gm.get_room_name(room)}",
            description="\n".join([f"• `/complete task:{t}`" for t in tasks]),
            color=discord.Color.green()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="complete", description="Complete a task for credits")
    @app_commands.describe(task="The task to complete")
    async def complete(self, interaction: discord.Interaction, task: str):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player or not player['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        # NEW: Mark first action (removes spawn protection)
        PlayerRepository.mark_first_action(player['id'])
        
        gm = self.bot.game_manager
        if gm.state.status != "active":
            await interaction.followup.send("❌ No active round!", ephemeral=True)
            return
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player or not player['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        if PlayerRepository.is_in_jail(player):
            await interaction.followup.send("❌ You're in jail!", ephemeral=True)
            return
        
        if not self._check_final_phase_steps(player):
            await interaction.followup.send("❌ You've used all 5 action steps in Final Phase!", ephemeral=True)
            return
        
        ready, remaining = self._check_cooldown(player, "task")
        if not ready:
            await interaction.followup.send(f"❌ Task on cooldown! Ready in {remaining}s.", ephemeral=True)
            return
        
        room = player['current_room']
        available_tasks = ROOM_TASKS.get(room, [])
        
        if task not in available_tasks:
            await interaction.followup.send(
                f"❌ Task '{task}' not available in {gm.get_room_name(room)}.\n"
                f"Available: {', '.join(available_tasks)}",
                ephemeral=True
            )
            return
        
        # Calculate reward
        min_reward = ConfigRepository.get_int("task_reward_min", 50)
        max_reward = ConfigRepository.get_int("task_reward_max", 200)
        reward = random.randint(min_reward, max_reward)
        
        # Give credits
        new_balance = player['pocket_credits'] + reward
        PlayerRepository.update_balance(player['id'], pocket_credits=new_balance)
        EarningsRepository.add_earned(gm.state.round_id, player['id'], reward)
        
        self._use_action(player, "task")
        
        await interaction.followup.send(
            f"✅ **Task Complete: {task}**\n\n"
            f"You earned **{reward} Pocket Credits**!\n"
            f"New balance: {new_balance} Pocket Credits",
            ephemeral=True
        )
    
    @app_commands.command(name="loot", description="Claim loot in your current room")
    async def loot(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        gm = self.bot.game_manager
        if gm.state.status != "active":
            await interaction.followup.send("❌ No active round!", ephemeral=True)
            return
        
        result = await gm.claim_loot(str(interaction.user.id))
        await interaction.followup.send(result["message"], ephemeral=True)
    
    @app_commands.command(name="rob", description="Rob another player in your room")
    @app_commands.describe(target="The player to rob")
    async def rob(self, interaction: discord.Interaction, target: discord.Member):
        await interaction.response.defer(ephemeral=True)
        
        player = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not player or not player['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        # NEW: Mark first action (removes spawn protection)
        PlayerRepository.mark_first_action(player['id'])
        
        gm = self.bot.game_manager
        if gm.state.status != "active":
            await interaction.followup.send("❌ No active round!", ephemeral=True)
            return
        
        robber = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not robber or not robber['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        if PlayerRepository.is_in_jail(robber):
            await interaction.followup.send("❌ You're in jail!", ephemeral=True)
            return
        
        if not self._check_final_phase_steps(robber):
            await interaction.followup.send("❌ You've used all 5 action steps in Final Phase!", ephemeral=True)
            return
        
        ready, remaining = self._check_cooldown(robber, "rob")
        if not ready:
            await interaction.followup.send(f"❌ Rob on cooldown! Ready in {remaining}s.", ephemeral=True)
            return
        
        victim = PlayerRepository.get_by_discord_id(str(target.id))
        if not victim or not victim['is_on_duty']:
            await interaction.followup.send("❌ Target is not on duty!", ephemeral=True)
            return
        
        if victim['id'] == robber['id']:
            await interaction.followup.send("❌ You can't rob yourself!", ephemeral=True)
            return
        
        # NEW: Check spawn protection
        if PlayerRepository.is_spawn_protected(victim):
            await interaction.followup.send(
                "❌ Target has spawn protection! They're immune for 20 seconds or until their first action.",
                ephemeral=True
            )
            return
        
        if PlayerRepository.is_in_jail(victim):
            await interaction.followup.send(
                "❌ Target is in jail! They can't be robbed.",
                ephemeral=True
            )
            return
        
        if victim['current_room'] != robber['current_room']:
            await interaction.followup.send("❌ Target is not in the same room!", ephemeral=True)
            return

        # NEW: Check if victim has rob proof
        if EffectsRepository.has_effect(victim['id'], "rob_proof"):
            EffectsRepository.consume_effect(victim['id'], "rob_proof")
            
            await interaction.followup.send(
                "🛡️ **ROB BLOCKED!**\n\n"
                f"<@{target.id}> was wearing a **Rob Proof Vest**!\n"
                "Your robbery attempt failed and the vest is now used up.",
                ephemeral=True
            )
            
            # Notify victim
            try:
                victim_user = await self.bot.fetch_user(int(victim['discord_id']))
                await gm.send_tracked_dm(victim_user,
                    f"🛡️ **ROBBERY ATTEMPT BLOCKED!**\n\n"
                    f"<@{interaction.user.id}> tried to rob you in {room_name}, "
                    f"but your Rob Proof Vest blocked it!"
                )
            except:
                pass
            
            return
        # Calculate steal amount
        cut_pct = ConfigRepository.get_int("robbery_cut", 30) / 100
        steal_amount = int(victim['pocket_credits'] * cut_pct)
        
        if steal_amount <= 0:
            await interaction.followup.send("❌ Target has no Pocket Credits to steal!", ephemeral=True)
            return
        
        # Transfer credits
        new_victim_balance = victim['pocket_credits'] - steal_amount
        new_robber_balance = robber['pocket_credits'] + steal_amount
        PlayerRepository.update_balance(victim['id'], pocket_credits=new_victim_balance)
        PlayerRepository.update_balance(robber['id'], pocket_credits=new_robber_balance)
        EarningsRepository.add_stolen(gm.state.round_id, robber['id'], steal_amount)
        
        self._use_action(robber, "rob")
        
        # Find witnesses (unless robber has stealth)
        if EffectsRepository.has_effect(robber['id'], "stealth_rob"):
            EffectsRepository.consume_effect(robber['id'], "stealth_rob")
            witness_ids = []
        else:
            witnesses = [
                p for p in gm.get_players_in_room(robber['current_room'], exclude_jailed=True)
                if p['discord_id'] not in [str(interaction.user.id), str(target.id)]
                and p['is_alive']
            ]
            witness_ids = [w['discord_id'] for w in witnesses]
        
        room_name = gm.get_room_name(robber['current_room'])
        
        # Public announcement (no robber name)
        await gm.announce(
            f"🚨 **ROBBERY IN {room_name.upper()}!**\n"
            f"{target.mention} was just robbed of **{steal_amount} Pocket Credits**!\n"
            f"The thief has escaped into the shadows..."
        )
        
       # DM to victim (anonymously)
        try:
            victim_user = await self.bot.fetch_user(int(victim['discord_id']))
            await gm.send_tracked_dm(victim_user,
                f"💸 **YOU WERE ROBBED!**\n\n"
                f"Someone stole **{steal_amount} Pocket Credits** from you in {room_name}.\n\n"
                f"*The identity of the robber remains unknown...*"
            )
        except Exception as e:
            print(f"Failed to DM victim: {e}")
        
        # Notify witnesses with 3-minute timer
        witness_timer = ConfigRepository.get_int("witness_timer", 180)
        for witness in witnesses:
            try:
                witness_user = await self.bot.fetch_user(int(witness['discord_id']))
                await witness_user.send(
                    f"👁️ **YOU SAW THE CRIME!**\n\n"
                    f"You watched **{interaction.user.name}** rob **{target.name}** in {room_name}.\n"
                    f"You have **{witness_timer // 60} minutes** to decide.\n\n"
                    f"Use `/report @user` to report, or stay silent."
                )
            except:
                pass
        
        await interaction.followup.send(
            f"🥷 You robbed **{target.name}** of **{steal_amount} Pocket Credits**!\n"
            f"Your new balance: {new_robber_balance}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(GameplayCog(bot))