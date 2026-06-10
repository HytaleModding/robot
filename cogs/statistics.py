import asyncio
import hashlib
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

from config import ConfigSchema
from database import Database

log = logging.getLogger(__name__)

class StatisticsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database
        self.config: ConfigSchema = bot.config
        self._pending_activity: dict[int, set[str]] = defaultdict(set)
        self._dau_cache: dict[int, tuple[int, datetime]] = {}

        self.collect_stats.start()
        self.refresh_activity_cache.start()
    
    def cog_unload(self):
        """Stop the background task when cog is unloaded"""
        self.collect_stats.cancel()
        self.refresh_activity_cache.cancel()
        if self._pending_activity:
            asyncio.create_task(self._flush_pending_activity())
    
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

    @tasks.loop(hours=1)
    async def refresh_activity_cache(self):
        """Persist unique activity for the last hour and refresh cached DAU values"""
        try:
            await self._refresh_activity_cache()
        except Exception as e:
            log.error(f"Error refreshing activity cache: {e}")

    @refresh_activity_cache.before_loop
    async def before_refresh_activity_cache(self):
        await self.bot.wait_until_ready()
        await self._refresh_activity_cache()

    async def _refresh_activity_cache(self):
        """Persist pending activity, remove expired rows, and refresh the cached DAU"""
        await self._flush_pending_activity()
        await self.db.cleanup_old_anonymous_activity(hours=24)
        await self.db.cleanup_old_dau_snapshots(days=30)

        guild = self.bot.get_guild(self.config.core.guild_id)
        if guild is None:
            return

        dau = await self.db.get_active_users_24h(guild.id)
        await self.db.record_dau_snapshot(guild.id, dau, snapshot_at=datetime.utcnow())
        self._dau_cache[guild.id] = (dau, datetime.utcnow())
        log.info(f"Refreshed cached DAU for {guild.name}: {dau}")

    async def _flush_pending_activity(self):
        """Write pending activity buckets to the database in one batch per guild"""
        if not self._pending_activity:
            return

        flushed_at = datetime.utcnow()
        for guild_id, user_hashes in list(self._pending_activity.items()):
            if not user_hashes:
                continue

            await self.db.record_anonymous_activity(
                guild_id=guild_id,
                user_hashes=user_hashes,
                recorded_at=flushed_at
            )
            self._pending_activity[guild_id].clear()

    def _hash_user_id(self, guild_id: int, user_id: int) -> str:
        """Create a one-way hash so raw user identifiers never reach the database"""
        payload = f"{guild_id}:{user_id}:{self.bot.user.id if self.bot.user else 0}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    
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
        """Track user activity in memory so DAU can be updated in hourly batches"""
        if not message.author.bot and message.guild:
            try:
                user_hash = self._hash_user_id(message.guild.id, message.author.id)
                self._pending_activity[message.guild.id].add(user_hash)
            except Exception as e:
                log.error(f"Error updating user activity: {e}")

    async def get_cached_dau(self, guild_id: int) -> int | None:
        """Return the cached DAU value if it is still fresh"""
        cached = self._dau_cache.get(guild_id)
        if cached is None:
            return None

        dau, computed_at = cached
        if datetime.utcnow() - computed_at > timedelta(hours=1, minutes=5):
            return None

        return dau

async def setup(bot):
    await bot.add_cog(StatisticsCog(bot))