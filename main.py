import discord
from discord.ext import commands

import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

bot.version = "v1.0"

@bot.event
async def on_ready():
    print(f"{bot.user} is ready!")
    
    # Load cogs
    await bot.load_extension("cogs.auto-thread")
    await bot.load_extension("cogs.keywords")
    await bot.load_extension("cogs.mod")

    await bot.tree.sync()
    
    print("All cogs loaded!")

if __name__ == "__main__":
    bot.run(os.getenv("TOKEN"))
