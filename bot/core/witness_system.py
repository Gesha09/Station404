import discord
from datetime import datetime, timedelta
from database.repositories.player_repo import PlayerRepository
from database.repositories.config_repo import ConfigRepository
from database.repositories.earnings_repo import EarningsRepository

class WitnessView(discord.ui.View):
    def __init__(self, bot, killer_id: str, victim_id: str, room: str, witness_id: str):
        # Read witness timer from config (default 180 seconds = 3 minutes)
        from database.repositories.config_repo import ConfigRepository
        timeout_seconds = ConfigRepository.get_int("witness_timer", 180)
        
        super().__init__(timeout=timeout_seconds)
        self.bot = bot
        self.killer_id = killer_id
        self.victim_id = victim_id
        self.room = room
        self.witness_id = witness_id
        self.resolved = False
        self._message = None  # Store reference to the DM message
    
    async def on_timeout(self):
        """Called when the witness timer expires"""
        if self.resolved:
            return
        
        self.resolved = True
        
        # Get room name for announcement
        room_name = self.bot.game_manager.get_room_name(self.room)
        
        # Announce that witness window closed
        try:
            await self.bot.game_manager.announce(
                f"👁️ **WITNESS WINDOW CLOSED**\n\n"
                f"The witness in {room_name} did not report the crime.\n"
                f"The incident goes unrecorded."
            )
        except Exception as e:
            print(f"Failed to announce witness timeout: {e}")
        
        # Notify the witness that time ran out
        try:
            user = await self.bot.fetch_user(int(self.witness_id))
            if self._message:
                await self._message.edit(
                    content=(
                        f"⏰ **TIME'S UP!**\n\n"
                        f"You didn't report the crime in time.\n"
                        f"The incident goes unrecorded."
                    ),
                    view=None  # Remove buttons
                )
        except Exception as e:
            print(f"Failed to notify witness of timeout: {e}")
        
        # Disable buttons
        self.stop()
    
    @discord.ui.button(label="🚨 REPORT", style=discord.ButtonStyle.danger)
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Quick checks first
        if str(interaction.user.id) != self.witness_id:
            await interaction.response.send_message(
                "❌ This button is not for you!",
                ephemeral=True
            )
            return
        
        if self.resolved:
            await interaction.response.send_message(
                "❌ This crime has already been resolved.",
                ephemeral=True
            )
            return
        
        # Defer immediately so Discord knows we're working on it
        await interaction.response.defer(ephemeral=True)
        
        self.resolved = True
        
        # Now do all the heavy work
        killer = PlayerRepository.get_by_discord_id(self.killer_id)
        if killer:
            # Increment offense count
            PlayerRepository.increment_jail_offense(killer['id'])
            offense_count = killer['jail_offense_count'] + 1
            
            # Calculate jail time based on offense count
            if offense_count == 1:
                jail_seconds = ConfigRepository.get_int("jail_time_1", 120)
            elif offense_count == 2:
                jail_seconds = ConfigRepository.get_int("jail_time_2", 180)
            else:
                jail_seconds = ConfigRepository.get_int("jail_time_3", 240)
            
            jail_release = datetime.now() + timedelta(seconds=jail_seconds)
            PlayerRepository.set_jail_release(killer['id'], jail_release.isoformat())
            
            # Log the jailing
            from bot.core.event_logger import EventLogger
            EventLogger.player_jailed(
                round_id=self.bot.game_manager.state.round_id,
                player_id=self.killer_id,
                player_name=killer['username'],
                duration=jail_seconds,
                offense_count=offense_count,
                reported_by=self.witness_id
            )
            
            # If killer was imposter, trigger rotation
            gm = self.bot.game_manager
            if gm.is_imposter(self.killer_id):
                await gm.announce(
                    "🔄 **IMPOSTER JAILED!**\n\n"
                    "The Imposter has been sent to jail. A new Imposter will be chosen..."
                )
                await gm._rotate_imposter(due_to_jail=True)
            
            # Public announcement
            room_name = gm.get_room_name(self.room)
            await gm.announce(
                f"⚖️ **JUSTICE SERVED!**\n\n"
                f"<@{self.killer_id}> was reported for murder in {room_name}!\n"
                f"They've been sent to jail for {jail_seconds // 60} minutes."
            )
        
        # Update the original message
        try:
            if self._message:
                await self._message.edit(
                    content="✅ **Crime reported!** The killer has been jailed.",
                    view=None
                )
        except:
            pass
        
        # Use followup since we deferred
        await interaction.followup.send(
            "✅ You reported the crime! The killer has been jailed.",
            ephemeral=True
        )
        
        # Disable buttons
        self.stop()
    
    @discord.ui.button(label="🤐 LOOK AWAY", style=discord.ButtonStyle.secondary)
    async def look_away(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Quick checks first
        if str(interaction.user.id) != self.witness_id:
            await interaction.response.send_message(
                "❌ This button is not for you!",
                ephemeral=True
            )
            return
        
        if self.resolved:
            await interaction.response.send_message(
                "❌ This crime has already been resolved.",
                ephemeral=True
            )
            return
        
        # Defer immediately
        await interaction.response.defer(ephemeral=True)
        
        self.resolved = True
        
        # Update the original message
        try:
            if self._message:
                await self._message.edit(
                    content="🤐 **You chose to look away.** The crime goes unreported.",
                    view=None
                )
        except:
            pass
        
        # Use followup since we deferred
        await interaction.followup.send(
            "🤐 You chose to look away. The crime goes unreported.",
            ephemeral=True
        )
        
        self.stop()


class WitnessSystem:
    """Manages witness timers and reports"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_witnesses = {}  # {witness_id: WitnessView}
    
    async def notify_witnesses(self, killer_id: str, victim_id: str, room: str, witness_ids: list):
        """Notify witnesses of a crime via DM with REPORT/LOOK AWAY buttons"""
        # Convert room ID to room name
        room_name = self.bot.game_manager.get_room_name(room)
        
        # Get witness timer for display
        from database.repositories.config_repo import ConfigRepository
        witness_timer = ConfigRepository.get_int("witness_timer", 180)
        timer_minutes = witness_timer // 60
        
        for witness_id in witness_ids:
            try:
                user = await self.bot.fetch_user(int(witness_id))
                view = WitnessView(self.bot, killer_id, victim_id, room, witness_id)
                
                # Send DM and track it
                message = await user.send(
                    f"👁️ **YOU WITNESSED A CRIME!**\n\n"
                    f"You saw <@{killer_id}> eliminate <@{victim_id}> in {room_name}.\n\n"
                    f"⏱️ You have **{timer_minutes} minutes** to decide.\n\n"
                    f"What do you want to do?",
                    view=view
                )
                
                # Store message reference so timeout handler can edit it
                view._message = message
                
                # Track for cleanup
                if witness_id not in self.bot.game_manager._player_dm_messages:
                    self.bot.game_manager._player_dm_messages[witness_id] = []
                self.bot.game_manager._player_dm_messages[witness_id].append(message.id)
            except Exception as e:
                print(f"Failed to notify witness {witness_id}: {e}")

    async def _witness_timer(self, witness_id: str, seconds: int, message: discord.Message):
        """Auto-resolve witness choice after timer expires"""
        try:
            await discord.utils.sleep_until(
                datetime.now() + timedelta(seconds=seconds)
            )
            
            view = self.active_witnesses.get(witness_id)
            if view and not view.resolved:
                view.resolved = True
                
                # Notify witness
                try:
                    witness_user = await self.bot.fetch_user(int(witness_id))
                    await witness_user.send(
                        "⏰ **Time's up!** You didn't make a choice, so the crime goes unreported."
                    )
                except:
                    pass
                
                # Edit original message to disable buttons
                try:
                    for child in view.children:
                        child.disabled = True
                    await message.edit(view=view)
                except:
                    pass
                
                view.stop()
            
            # Clean up
            if witness_id in self.active_witnesses:
                del self.active_witnesses[witness_id]
        except Exception as e:
            print(f"Witness timer error: {e}")