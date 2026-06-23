import aiohttp
import nextcord
from nextcord.ext import commands, tasks
import random
from utilities.probability import DynamicProbability

class RandomMessageCog(commands.Cog):
    def __init__(self, client, config):
        self.client = client
        self.config = config
        
        # Dictionary storing probability instances for each guild (guild_id -> DynamicProbability)
        self.probabilities = {}
        
        self.forbidden_keywords = [
            "info", "ogłoszenia", "ogloszenia", "announcements", 
            "informacje", "news", "update", "regulamin", "rules", "zasady", "github"
        ]
        
        # Tracking the number of messages per channel in the last hour (channel_id -> count)
        self.hourly_message_counts = {}
        
        self.random_message_task.start()

    def get_probability(self, guild_id):
        if guild_id not in self.probabilities:
            # Initialize probability module for a new guild
            self.probabilities[guild_id] = DynamicProbability(
                base_sequence=[10, 8, 5, 3, 2], 
                premium_hours=[7, 8, 9,10, 18, 19, 20, 21, 22],
                premium_multiplier=1.5
            )
        return self.probabilities[guild_id]

    def cog_unload(self):
        self.random_message_task.cancel()

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from bots
        if message.author.bot:
            return
        
        # Increment message counter for the given channel
        channel_id = message.channel.id
        self.hourly_message_counts[channel_id] = self.hourly_message_counts.get(channel_id, 0) + 1

    async def _select_active_channels(self, guild):
        """Filters the guild's channels and returns (active_channels, total_activity).

        active_channels is a list of (channel, hourly_count) for channels that are
        writable, not forbidden by name, had activity this hour, and where the bot
        has prior history.
        """
        valid_channels = []

        # Filter channels by permissions and names
        for channel in guild.text_channels:
            if not channel.permissions_for(guild.me).send_messages or not channel.permissions_for(guild.me).read_message_history:
                continue

            channel_name = channel.name.lower()
            if any(kw in channel_name for kw in self.forbidden_keywords):
                continue

            valid_channels.append(channel)

        active_channels = []
        total_activity = 0

        # Verify activity in the last hour and in the bot's history
        for channel in valid_channels:
            count = self.hourly_message_counts.get(channel.id, 0)

            if count > 0:
                # Check if the bot has ever had activity in this channel
                has_bot_activity = False
                try:
                    async_history = channel.history(limit=50)
                except Exception:
                    async_history = None

                if async_history is not None:
                    try:
                        async for msg in async_history:
                            if msg.author == self.client.user:
                                has_bot_activity = True
                                break
                    except Exception:
                        pass

                if has_bot_activity:
                    active_channels.append((channel, count))
                    total_activity += count

        return active_channels, total_activity

    async def _fire_webhook(self, guild, channel):
        """Fire-and-forget: notify n8n that a random trigger happened.

        Returns a list of short per-environment result strings (for logging / the
        test command) so failures are never silent.
        """
        payload = {
            "guild_id": str(guild.id),
            "channel_id": str(channel.id),
            "channel_name": getattr(channel, "name", None),
        }

        results = []
        async with aiohttp.ClientSession() as session:
            for env in ("test", "production"):
                url = self.config.get_n8n_mention_webhook_url(env)
                try:
                    async with session.post(url, json=payload) as resp:
                        status = "ok" if resp.status < 300 else "error"
                        line = f"{env}: HTTP {resp.status}"
                        print(f"[random_message] webhook {status} ({env}): HTTP {resp.status}")
                except Exception as e:
                    line = f"{env}: FAILED ({e})"
                    print(f"[random_message] webhook failed ({env}): {e}")
                results.append(line)
        return results

    async def _run_cycle_for_guild(self, guild, force=False):
        """Runs one random-message cycle for a single guild.

        With force=True the probability gate is skipped. Returns a human-readable
        report string describing what happened (used by the test command).
        """
        active_channels, total_activity = await self._select_active_channels(guild)

        # Determine chance multiplier based on total server activity in the last hour
        # If 0 messages -> multiplier 0.1 (very low chance)
        # If 20 messages -> multiplier 1.0 (normal chance)
        # If 100+ messages -> multiplier 5.0 (very high chance)
        multiplier = max(0.1, min(5.0, total_activity / 20.0))

        prob = self.get_probability(guild.id)

        # If the probability function decides not to trigger, we skip
        if not force and not prob.should_trigger(extra_multiplier=multiplier):
            return f"{guild.name}: not triggered (multiplier={multiplier:.2f})"

        # If it triggers but there are no active channels with bot history, we skip
        if not active_channels:
            return f"{guild.name}: triggered, but no active channels with bot history"

        # Sorting and randomly selecting a channel considering weights (channel activity)
        channels = [item[0] for item in active_channels]
        weights = [item[1] for item in active_channels]

        chosen_channel = random.choices(channels, weights=weights, k=1)[0]

        results = await self._fire_webhook(guild, chosen_channel)
        return f"{guild.name}: fired for #{chosen_channel.name} -> " + " | ".join(results)

    @tasks.loop(hours=1)
    async def random_message_task(self):
        # Wait for the bot to be ready before executing
        await self.client.wait_until_ready()

        for guild in self.client.guilds:
            await self._run_cycle_for_guild(guild)

        # After iterating through all guilds, reset the message counters for the next hour
        self.hourly_message_counts.clear()

    @nextcord.slash_command(
        name="testrandom",
        description="Manually fire the random-message webhook for this server",
        guild_ids=[1357420845970100335],
    )
    async def test_random(self, interaction: nextcord.Interaction):
        """Manually trigger the random-message webhook for this guild.

        Skips the probability gate so it always fires when there is an eligible
        channel, and reports the HTTP result back so nothing fails silently. If no
        channel qualifies (no recent activity + bot history), it falls back to
        firing for the current channel.
        """
        if interaction.guild is None:
            await interaction.response.send_message("This command only works inside a server.")
            return

        # History scan + two webhook POSTs can exceed Discord's 3s window, so defer.
        await interaction.response.defer()

        active_channels, _ = await self._select_active_channels(interaction.guild)
        if active_channels:
            report = await self._run_cycle_for_guild(interaction.guild, force=True)
        else:
            channel = interaction.channel
            results = await self._fire_webhook(interaction.guild, channel)
            report = (
                f"{interaction.guild.name}: no eligible channel (no recent activity + bot "
                f"history), fired fallback for #{getattr(channel, 'name', '?')} -> "
                + " | ".join(results)
            )

        await interaction.followup.send(f"```{report}```")

    @random_message_task.before_loop
    async def before_random_message_task(self):
        await self.client.wait_until_ready()

def setup(client, config):
    client.add_cog(RandomMessageCog(client, config))
