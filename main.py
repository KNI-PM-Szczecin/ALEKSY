import nextcord
from nextcord.ext import commands
from utilities import baseUtils
import os

def main():
    config = baseUtils.ConfigReader()

    intents = nextcord.Intents.default()
    intents.message_content = True
    intents.members = True

    client = commands.Bot(command_prefix="!", intents=intents)

    payload = {
        'client': client,
        'config': config
    }

    baseUtils.Loader(payload)

    @client.event
    async def on_ready():
        print(f'Logged in as {client.user} (ID: {client.user.id})')
        print('------')

    bot_token = config.get_bot_token()
    if not bot_token:
        print("Błąd: Nie znaleziono tokenu bota w pliku .env!")
        return

    client.run(bot_token)

if __name__ == "__main__":
    main()
