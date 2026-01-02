import logging
import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv

from config import Config
from database import Database
from logging_configuration import setup_logging
from settings import Settings

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
async def on_connect():
    await load_cogs()
    log.info("All cogs loaded.")

@bot.event
async def on_ready():
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", 3306))
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME")
    bot.database = Database(host, port, user, password, database)
    bot.staff_role = bot.get_guild(1440173445039132724).get_role(1440793371529449614) # TODO: optimize
    try:
        await bot.database.init_db()
    except Exception as e:
        log.critical(f"A critical error occurred while initializing the database: {e}")
        await bot.close()
        return

    log.info(f"{bot.user} is ready!")

    await bot.tree.sync()

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        pass

if __name__ == "__main__":
    try:
        Settings.init()
        Config.init()
    except Exception as e:
        log.critical(e)
        sys.exit(1)

    bot.run(token=os.getenv("TOKEN"), log_handler=None)
