import asyncio
import discord
from discord.ext import commands, tasks

from config import ConfigSchema
from database import Database
from datetime import datetime

import logging

log = logging.getLogger(__name__)

class StatisticsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database
        self.config: ConfigSchema = bot.config

        self.collect_stats.start()
    
    def cog_unload(self):
        """Stop the background task when cog is unloaded"""
        self.collect_stats.cancel()
    
    @tasks.loop(minutes=5) 
    async def collect_stats(self):
        """Background task to collect server statistics"""
        guild = self.bot.get_guild(self.config.core.guild_id)
        try:
            await self._collect_guild_stats(guild)
        except Exception as e:
            log.error(f"Error in stats collection: {e}")
    
    @collect_stats.before_loop
    async def before_collect_stats(self):
        """Wait for bot to be ready before starting stats collection"""
        await self.bot.wait_until_ready()
    
    async def _collect_guild_stats(self, guild):
        """Collect statistics for a single guild"""
        try:
            online = 0
            idle = 0
            dnd = 0
            offline = 0
            
            for member in guild.members:
                if member.bot:
                    continue
                    
                if member.status == discord.Status.online:
                    online += 1
                elif member.status == discord.Status.idle:
                    idle += 1
                elif member.status == discord.Status.dnd:
                    dnd += 1
                else:  # offline
                    offline += 1
            
            total_members = guild.member_count
            await self.db.log_server_stats(
                guild_id=guild.id,
                total_members=total_members,
                online_members=online,
                idle_members=idle,
                dnd_members=dnd,
                offline_members=offline
            )

            log.info(f"[{datetime.now().strftime('%H:%M:%S')}] Logged stats for {guild.name}: "
                      f"{total_members} total, {online} online, {idle} idle, {dnd} dnd, {offline} offline")

        except Exception as e:
            log.error(f"Error collecting stats for guild {guild.name} ({guild.id}): {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Track user activity when they send messages"""
        if not message.author.bot and message.guild:
            try:
                await self.db.update_user_activity(message.guild.id, message.author.id)
            except Exception as e:
                log.error(f"Error updating user activity: {e}")

async def setup(bot):
    await bot.add_cog(StatisticsCog(bot))