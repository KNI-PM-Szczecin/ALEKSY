import aiohttp
import nextcord
from nextcord.ext import commands


class MentionTriggerCog(commands.Cog):
    """Fires an n8n webhook whenever the bot is mentioned in a guild message."""

    def __init__(self, client, config):
        self.client = client
        self.config = config

    @commands.Cog.listener()
    async def on_message(self, message: nextcord.Message):
        # Ignore bots (including ourselves) to avoid feedback loops.
        if message.author.bot:
            return

        # Only guild messages carry channel/guild context for the webhook.
        if not message.guild:
            return

        # Only react when the bot is actually mentioned.
        if not self.client.user or self.client.user not in message.mentions:
            return

        payload = {
            "channel_id": str(message.channel.id),
            "channel_name": getattr(message.channel, "name", None),
            "guild_id": str(message.guild.id),
            "user_id": str(message.author.id),
            "user_name": message.author.name,
            "content": message.content,
        }

        async with aiohttp.ClientSession() as session:
            for env in ("test", "production"):
                url = self.config.get_n8n_mention_webhook_url(env)
                try:
                    async with session.post(url, json=payload) as resp:
                        if resp.status < 300:
                            print(f"[mention_trigger] webhook ok ({env}): HTTP {resp.status}")
                        else:
                            print(f"[mention_trigger] webhook error ({env}): HTTP {resp.status}")
                except Exception as e:
                    print(f"[mention_trigger] webhook failed ({env}): {e}")
