import discord
from discord.ext import commands

import os
from dotenv import load_dotenv
from database import Database
load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

bot.version = "v1.0"
bot.upload_token = os.getenv("UPLOAD_TOKEN")

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            print(f"Loaded cog: {filename}")

@bot.event
async def on_load():
    bot.database = Database()
    await bot.database.init_db()

@bot.event
async def on_ready():
    await load_cogs()
    print(f"{bot.user} is ready!")

    await bot.tree.sync()

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        pass 

if __name__ == "__main__":
    bot.run(os.getenv("TOKEN"))
