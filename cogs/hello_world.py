import nextcord
from nextcord.ext import commands

class HelloWorldCog(commands.Cog):
    def __init__(self, client, config):
        self.client = client
        self.config = config

    @commands.command(name="hello")
    async def hello(self, ctx):
        await ctx.send("Hello world!")
        
    @nextcord.slash_command(name="hello", description="Mówi hello world")
    async def hello_slash(self, interaction: nextcord.Interaction):
        await interaction.response.send_message("Hello world!")
