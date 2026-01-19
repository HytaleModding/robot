import logging
import os
import sys

import discord
from discord.ext import commands
from discord.ext.commands import ExtensionError
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

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                log.info(f"Loaded cog: {filename}")
            except ExtensionError as cogErr:
                log.exception(f"Failed to load cog {filename}: {cogErr}")

@bot.event
async def on_connect():
    await load_cogs()
    log.info("All cogs loaded.")

@bot.event
async def on_ready():
    # I just left it here like this for now, can be cleaned up later
    config = Config.get()
    bot.staff_role = bot.get_guild(config.core.guild_id).get_role(config.cogs.tickets.staff_role_id) # TODO: optimize

    try:
        await bot.database.init_db()
    except Exception as databaseErr:
        log.critical(f"A critical error occurred while initializing the database: {databaseErr}")
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

    settings = Settings.get()

    bot.database = Database(
        settings.DB_HOST,
        settings.DB_PORT,
        settings.DB_USER,
        settings.DB_PASSWORD,
        settings.DB_NAME
    )

    bot.upload_token = settings.UPLOAD_TOKEN

    bot.config = Config.get()

    bot.run(token=settings.TOKEN, log_handler=None)
