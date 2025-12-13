import discord
from discord.ext import commands

import os
import logging
from dotenv import load_dotenv
from database import Database
from logging_configuration import setup_logging

load_dotenv()

setup_logging()
log = logging.getLogger(__name__)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=".", intents=intents)

bot.version = "v1.0"
bot.upload_token = os.getenv("UPLOAD_TOKEN")

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")
            log.info(f"Loaded cog: {filename}")

@bot.event
async def on_ready():
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", 3306))
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
    bot.database = Database(host, port, user, password, database)
    await bot.database.init_db()

    await load_cogs()
    log.info(f"{bot.user} is ready!")

    await bot.tree.sync()

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        pass

if __name__ == "__main__":
    bot.run(token=os.getenv("TOKEN"), log_handler=None)
