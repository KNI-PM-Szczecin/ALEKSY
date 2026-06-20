import nextcord
from nextcord.ext import commands, tasks
import random
from utilities.probability import DynamicProbability

class RandomMessageCog(commands.Cog):
    def __init__(self, client, config):
        self.client = client
        self.config = config
        
        # Słownik przechowujący instancje prawdopodobieństwa dla każdego serwera (guild_id -> DynamicProbability)
        self.probabilities = {}
        
        self.forbidden_keywords = [
            "info", "ogłoszenia", "ogloszenia", "announcements", 
            "informacje", "news", "update", "regulamin", "rules", "zasady", "github"
        ]
        
        # Śledzenie ilości wiadomości na poszczególnych kanałach w ciągu ostatniej godziny (channel_id -> count)
        self.hourly_message_counts = {}
        
        self.random_message_task.start()

    def get_probability(self, guild_id):
        if guild_id not in self.probabilities:
            # Inicjalizacja modułu prawdopodobieństwa dla nowego serwera
            self.probabilities[guild_id] = DynamicProbability(
                base_sequence=[10, 8, 5, 3, 2], 
                premium_hours=[18, 19, 20, 21, 22],
                premium_multiplier=1.5
            )
        return self.probabilities[guild_id]

    def cog_unload(self):
        self.random_message_task.cancel()

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignoruj wiadomości od botów
        if message.author.bot:
            return
        
        # Zwiększ licznik wiadomości dla danego kanału
        channel_id = message.channel.id
        self.hourly_message_counts[channel_id] = self.hourly_message_counts.get(channel_id, 0) + 1

    @tasks.loop(hours=1)
    async def random_message_task(self):
        # Wait for the bot to be ready before executing
        await self.client.wait_until_ready()
        
        for guild in self.client.guilds:
            valid_channels = []
            
            # Filtrowanie kanałów po uprawnieniach i nazwach
            for channel in guild.text_channels:
                if not channel.permissions_for(guild.me).send_messages or not channel.permissions_for(guild.me).read_message_history:
                    continue
                
                channel_name = channel.name.lower()
                if any(kw in channel_name for kw in self.forbidden_keywords):
                    continue
                
                valid_channels.append(channel)

            active_channels = []
            total_activity = 0
            
            # Weryfikacja aktywności w ciągu ostatniej godziny i w historii bota
            for channel in valid_channels:
                count = self.hourly_message_counts.get(channel.id, 0)
                
                if count > 0:
                    # Sprawdź, czy bot miał kiedykolwiek aktywność na tym kanale
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

            # Ustal mnożnik szansy na podstawie całkowitej aktywności na serwerze w ciągu godziny
            # Jeśli 0 wiadomości -> mnożnik 0.1 (bardzo niska szansa)
            # Jeśli 20 wiadomości -> mnożnik 1.0 (normalna szansa)
            # Jeśli 100+ wiadomości -> mnożnik 5.0 (bardzo wysoka szansa)
            multiplier = max(0.1, min(5.0, total_activity / 20.0))
            
            prob = self.get_probability(guild.id)
            
            # Jeśli funkcja prawdopodobieństwa uzna, że nie wysyłamy wiadomości, to pomijamy
            if not prob.should_trigger(extra_multiplier=multiplier):
                continue

            # Jeśli pomimo wylosowania nie mamy żadnych aktywnych kanałów z aktywnością bota, pomijamy
            if not active_channels:
                continue

            # Sortowanie i losowanie z uwzględnieniem wagi (aktywności na kanale)
            channels = [item[0] for item in active_channels]
            weights = [item[1] for item in active_channels]
            
            chosen_channel = random.choices(channels, weights=weights, k=1)[0]
            
            try:
                # Tutaj mockup do wywołania webhooka
                await chosen_channel.send("MOCKUP: Webhook trigger")
            except Exception as e:
                print(f"Failed to send random message in {chosen_channel.name}: {e}")

        # Po przejściu wszystkich serwerów, resetujemy liczniki wiadomości na kolejną godzinę
        self.hourly_message_counts.clear()

    @random_message_task.before_loop
    async def before_random_message_task(self):
        await self.client.wait_until_ready()

def setup(client, config):
    client.add_cog(RandomMessageCog(client, config))
