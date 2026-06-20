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

    @tasks.loop(hours=1)
    async def random_message_task(self):
        # Wait for the bot to be ready before executing
        await self.client.wait_until_ready()
        
        for guild in self.client.guilds:
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
                        async for msg in channel.history(limit=50):
                            if msg.author == self.client.user:
                                has_bot_activity = True
                                break
                    except Exception:
                        pass
                    
                    if has_bot_activity:
                        active_channels.append((channel, count))
                        total_activity += count

            # Determine chance multiplier based on total server activity in the last hour
            # If 0 messages -> multiplier 0.1 (very low chance)
            # If 20 messages -> multiplier 1.0 (normal chance)
            # If 100+ messages -> multiplier 5.0 (very high chance)
            multiplier = max(0.1, min(5.0, total_activity / 20.0))
            
            prob = self.get_probability(guild.id)
            
            # If the probability function decides not to trigger, we skip
            if not prob.should_trigger(extra_multiplier=multiplier):
                continue

            # If it triggers but there are no active channels with bot history, we skip
            if not active_channels:
                continue

            # Sorting and randomly selecting a channel considering weights (channel activity)
            channels = [item[0] for item in active_channels]
            weights = [item[1] for item in active_channels]
            
            chosen_channel = random.choices(channels, weights=weights, k=1)[0]
            
            try:
                # Webhook trigger mockup goes here
                await chosen_channel.send("MOCKUP: Webhook trigger")
            except Exception as e:
                print(f"Failed to send random message in {chosen_channel.name}: {e}")

        # After iterating through all guilds, reset the message counters for the next hour
        self.hourly_message_counts.clear()

    @random_message_task.before_loop
    async def before_random_message_task(self):
        await self.client.wait_until_ready()

def setup(client, config):
    client.add_cog(RandomMessageCog(client, config))
