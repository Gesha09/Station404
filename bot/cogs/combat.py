import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from database.repositories.effects_repo import EffectsRepository
from database.repositories.player_repo import PlayerRepository
from database.repositories.config_repo import ConfigRepository
from database.repositories.earnings_repo import EarningsRepository

class CombatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="kill", description="Eliminate a player (Imposter only)")
    @app_commands.describe(target="The player to kill")
    async def kill(self, interaction: discord.Interaction, target: discord.Member):
        await interaction.response.defer(ephemeral=True)
        
        gm = self.bot.game_manager
        if gm.state.status != "active":
            await interaction.followup.send("❌ No active round!", ephemeral=True)
            return
        
        # Check if user is imposter
        if not gm.is_imposter(str(interaction.user.id)):
            await interaction.followup.send(
                "❌ Only the Imposter can use this command!",
                ephemeral=True
            )
            return
        
        killer = PlayerRepository.get_by_discord_id(str(interaction.user.id))
        if not killer or not killer['is_on_duty']:
            await interaction.followup.send("❌ You're not on duty!", ephemeral=True)
            return
        
        if PlayerRepository.is_in_jail(killer):
            await interaction.followup.send("❌ You're in jail!", ephemeral=True)
            return
        
        # Check cooldown
        last_kill = killer['last_kill_at']
        if last_kill and last_kill != "1970-01-01T00:00:00":
            try:
                last_ts = datetime.fromisoformat(last_kill).timestamp()
                if gm.state.final_phase:
                    cd = ConfigRepository.get_int("kill_cooldown_final", 30)
                else:
                    cd = ConfigRepository.get_int("kill_cooldown", 120)
                
                elapsed = datetime.now().timestamp() - last_ts
                remaining = cd - elapsed
                
                if remaining > 0:
                    await interaction.followup.send(
                        f"❌ Kill on cooldown! Ready in {int(remaining)}s.",
                        ephemeral=True
                    )
                    return
            except:
                pass
        
        # Check Final Phase steps
        if gm.state.final_phase and killer['action_steps_used'] >= 5:
            await interaction.followup.send(
                "❌ You've used all 5 action steps in Final Phase!",
                ephemeral=True
            )
            return
        
        victim = PlayerRepository.get_by_discord_id(str(target.id))
        if not victim or not victim['is_on_duty']:
            await interaction.followup.send("❌ Target is not on duty!", ephemeral=True)
            return
        
        if victim['id'] == killer['id']:
            await interaction.followup.send("❌ You can't kill yourself!", ephemeral=True)
            return
        
        if not victim['is_alive']:
            await interaction.followup.send("❌ Target is already dead!", ephemeral=True)
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
                "❌ Target is in jail! They can't be killed.",
                ephemeral=True
            )
            return
        
        if victim['current_room'] != killer['current_room']:
            await interaction.followup.send("❌ Target is not in the same room!", ephemeral=True)
            return
        
        # ============ EXECUTE KILL ============
        
        # NEW: Check if victim has shield
        if EffectsRepository.has_effect(victim['id'], "shield"):
            EffectsRepository.consume_effect(victim['id'], "shield")
            
            # Notify killer
            await interaction.followup.send(
                "🛡️ **KILL BLOCKED!**\n\n"
                f"<@{target.id}> had a **Shield Boost** that absorbed the blow!\n"
                "The shield shattered, but they survived.",
                ephemeral=True
            )
            
            # Notify victim
            try:
                victim_user = await self.bot.fetch_user(int(victim['discord_id']))
                await gm.send_tracked_dm(victim_user,
                    "🛡️ **SHIELD SAVED YOU!**\n\n"
                    f"<@{interaction.user.id}> tried to kill you in {room_name}, "
                    f"but your Shield Boost absorbed the blow!\n"
                    "The shield is now shattered."
                )
            except:
                pass
            
            # Still consume killer's action step and cooldown
            gm._use_action(killer, "kill")
            return
        # Steal 100% of victim's Pocket Credits
        steal_amount = victim['pocket_credits']
        new_killer_balance = killer['pocket_credits'] + steal_amount
        PlayerRepository.update_balance(killer['id'], pocket_credits=new_killer_balance)
        PlayerRepository.update_balance(victim['id'], pocket_credits=0)
        EarningsRepository.add_stolen(gm.state.round_id, killer['id'], steal_amount)
        
        # Kill victim
        PlayerRepository.kill_player(victim['id'])
        
        # Set respawn time
        respawn_cooldown = ConfigRepository.get_int("respawn_cooldown", 180)
        respawn_time = datetime.now() + timedelta(seconds=respawn_cooldown)
        PlayerRepository.set_respawn_time(victim['id'], respawn_time.isoformat())
        
        # Set kill cooldown
        PlayerRepository.update_cooldown(killer['id'], "kill", datetime.now().isoformat())
        if gm.state.final_phase:
            PlayerRepository.increment_action_steps(killer['id'])
        
        # Find witnesses (unless killer has stealth rob)
        if EffectsRepository.has_effect(killer['id'], "stealth_rob"):
            # Stealth mode - no witnesses!
            EffectsRepository.consume_effect(killer['id'], "stealth_rob")
            witness_ids = []
        else:
            witnesses = [
                p for p in gm.get_players_in_room(killer['current_room'], exclude_jailed=True)
                if p['discord_id'] not in [str(interaction.user.id), str(target.id)]
                and p['is_alive']
            ]
            witness_ids = [w['discord_id'] for w in witnesses]
        
        room_name = gm.get_room_name(killer['current_room'])
        
        # Public announcement (anonymous)
        await gm.announce(
            f"💀 **BODY FOUND IN {room_name.upper()}!**\n\n"
            f"{target.mention} has been eliminated!\n"
            f"Their Pocket Credits were stolen."
        )
        
        # Notify victim (anonymously)
        try:
            victim_user = await self.bot.fetch_user(int(victim['discord_id']))
            await gm.send_tracked_dm(victim_user,
                f"💀 **YOU WERE ELIMINATED!**\n\n"
                f"You were killed in {room_name}.\n"
                f"You lost all your Pocket Credits.\n"
                f"You will respawn in {respawn_cooldown // 60} minutes.\n\n"
                f"*The identity of your killer remains a mystery...*"
            )
        except:
            pass
        
        # Notify witnesses with buttons
        if witness_ids:
            await self.bot.game_manager.witness_system.notify_witnesses(
                str(interaction.user.id),
                str(target.id),
                killer['current_room'],
                witness_ids
            )
        
        await interaction.followup.send(
            f"🔪 You eliminated **{target.name}**!\n"
            f"You stole **{steal_amount} Pocket Credits**.\n"
            f"Your new balance: {new_killer_balance}",
            ephemeral=True
        )
        PlayerRepository.mark_first_action(killer['id'])
    

async def setup(bot):
    await bot.add_cog(CombatCog(bot))