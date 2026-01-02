import aiomysql
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
from .migration import MigrationManager
from .migrations import discover_migrations

import warnings
from pymysql import Warning as MySQLWarning

log = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=MySQLWarning)

class Database:
    def __init__(self, host: str, port: int, user: str | None, password: str, database: str | None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        
        self.migration_manager = MigrationManager(self)
        self._register_migrations()
    
    def _register_migrations(self):
        """Register all available migrations"""
        migrations = discover_migrations()
        
        for migration in migrations:
            self.migration_manager.register_migration(migration)
    
    async def get_connection(self):
        return await aiomysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            db=self.database,
            autocommit=True
        )
    
    async def init_db(self):
        """Initialize database by running all migrations"""
        await self.migration_manager.run_migrations()

    async def run_migrations(self):
        migrations = (
            self.migration_001_upvotes_by_count,
        )

        for migration in migrations:
            name = migration.__name__

            try:
                was_applied = await migration()
                if was_applied:
                    log.info(f"Applied migration: {name}")
            except Exception:
                log.error(f"Tried to apply migration {name} but failed. The migration can be safely re-run after the issue is fixed.")
                raise

    async def migration_001_upvotes_by_count(self) -> bool:
        """Migrate upvotes table from a user-showcase schema to a showcase with count schema"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = 'upvotes'
                    ORDER BY ORDINAL_POSITION
                """, (self.database,))
                columns = {row[0] for row in await cursor.fetchall()}
                is_old_schema = columns == {'user_id', 'showcase_id'}

                if not is_old_schema:
                    return False

                await cursor.execute("DROP TABLE IF EXISTS migration_001_upvotes_new")
                await cursor.execute("""
                    CREATE TABLE migration_001_upvotes_new (
                        showcase_id BIGINT NOT NULL PRIMARY KEY,
                        count INT NOT NULL DEFAULT 0
                    ) ENGINE=InnoDB
                """)
                await cursor.execute("""
                    INSERT INTO migration_001_upvotes_new (showcase_id, count)
                    SELECT showcase_id, COUNT(*) AS count
                    FROM upvotes
                    GROUP BY showcase_id
                """)

                await cursor.execute("""
                    RENAME TABLE
                        upvotes TO migration_001_upvotes_backup,
                        migration_001_upvotes_new TO upvotes
                """)

                return True
        finally:
            conn.close()
    
    # Warning methods
    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp) VALUES (%s, %s, %s, %s, %s)",
                    (guild_id, user_id, moderator_id, reason, datetime.utcnow())
                )
                return cursor.lastrowid
        finally:
            conn.close()
    
    async def get_warnings(self, guild_id: int, user_id: int) -> List[Dict]:
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM warnings WHERE guild_id = %s AND user_id = %s ORDER BY timestamp DESC",
                    (guild_id, user_id)
                )
                return await cursor.fetchall()
        finally:
            conn.close()
    
    async def remove_warning(self, warning_id: int) -> bool:
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute("DELETE FROM warnings WHERE id = %s", (warning_id,))
                return cursor.rowcount > 0
        finally:
            conn.close()

    # Points system methods
    async def award_points(self, guild_id: int, user_id: int, awarded_by: int, points: int, reason: str, thread_id: int = None) -> bool:
        """Award points to a user"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                # Insert or update user points
                await cursor.execute("""
                    INSERT INTO user_points (guild_id, user_id, points, last_updated)
                    VALUES (%s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                    points = points + VALUES(points),
                    last_updated = NOW()
                """, (guild_id, user_id, points))
                
                # Record the transaction
                await cursor.execute("""
                    INSERT INTO point_transactions (guild_id, user_id, awarded_by, points, reason, thread_id, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (guild_id, user_id, awarded_by, points, reason, thread_id))
                
                return True
        finally:
            conn.close()

    async def get_user_points(self, guild_id: int, user_id: int) -> int:
        """Get a user's total points"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT points FROM user_points WHERE guild_id = %s AND user_id = %s",
                    (guild_id, user_id)
                )
                result = await cursor.fetchone()
                return result[0] if result else 0
        finally:
            conn.close()

    async def get_points_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict]:
        """Get points leaderboard for a guild"""
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT user_id, points, last_updated 
                    FROM user_points 
                    WHERE guild_id = %s AND points > 0
                    ORDER BY points DESC 
                    LIMIT %s
                """, (guild_id, limit))
                return await cursor.fetchall()
        finally:
            conn.close()

    async def get_user_point_history(self, guild_id: int, user_id: int, limit: int = 10) -> List[Dict]:
        """Get a user's point transaction history"""
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT points, reason, thread_id, timestamp, awarded_by
                    FROM point_transactions 
                    WHERE guild_id = %s AND user_id = %s
                    ORDER BY timestamp DESC 
                    LIMIT %s
                """, (guild_id, user_id, limit))
                return await cursor.fetchall()
        finally:
            conn.close()

    # Mod actions log
    async def log_action(self, guild_id: int, action_type: str, user_id: int, 
                        moderator_id: int, reason: str = None, duration: int = None):
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO mod_actions (guild_id, action_type, user_id, moderator_id, reason, duration, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (guild_id, action_type, user_id, moderator_id, reason, duration, datetime.utcnow())
                )
        finally:
            conn.close()
    
    async def get_user_history(self, guild_id: int, user_id: int) -> List[Dict]:
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM mod_actions WHERE guild_id = %s AND user_id = %s ORDER BY timestamp DESC LIMIT 50",
                    (guild_id, user_id)
                )
                return await cursor.fetchall()
        finally:
            conn.close()
    
    # Config methods
    async def set_log_channel(self, guild_id: int, channel_id: int):
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO mod_config (guild_id, log_channel_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE log_channel_id = VALUES(log_channel_id)",
                    (guild_id, channel_id)
                )
        finally:
            conn.close()
    
    async def get_log_channel(self, guild_id: int) -> Optional[int]:
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT log_channel_id FROM mod_config WHERE guild_id = %s",
                    (guild_id,)
                )
                row = await cursor.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    async def set_upvotes(self, showcase_id: int, count: int):
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO upvotes (showcase_id, count) VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE count = %s
                """, (showcase_id, count, count))
        finally:
            conn.close()

    async def get_upvotes(self, showcase_id: int) -> int:
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT count FROM upvotes WHERE showcase_id = %s",
                    (showcase_id,)
                )
                row = await cursor.fetchone()
                return row[0] if row else 0
        finally:
            conn.close()

    async def get_top_5_showcases(self) -> List[Dict]:
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT showcase_id, count AS upvote_count
                    FROM upvotes
                    ORDER BY count DESC
                    LIMIT 5
                """)
                return await cursor.fetchall()
        finally:
            conn.close()
    
    # Thread follower methods
    async def add_thread_follower(self, thread_id: int, user_id: int) -> bool:
        """Add a user as a follower of a thread. Returns True if added, False if already following."""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT IGNORE INTO thread_followers (thread_id, user_id) VALUES (%s, %s)",
                    (thread_id, user_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()
    
    async def remove_thread_follower(self, thread_id: int, user_id: int) -> bool:
        """Remove a user as a follower of a thread. Returns True if removed, False if not following."""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM thread_followers WHERE thread_id = %s AND user_id = %s",
                    (thread_id, user_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()
    
    async def get_thread_followers(self, thread_id: int) -> List[int]:
        """Get all followers of a thread."""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT user_id FROM thread_followers WHERE thread_id = %s",
                    (thread_id,)
                )
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        finally:
            conn.close()
    
    async def is_following_thread(self, thread_id: int, user_id: int) -> bool:
        """Check if a user is following a thread."""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT 1 FROM thread_followers WHERE thread_id = %s AND user_id = %s",
                    (thread_id, user_id)
                )
                row = await cursor.fetchone()
                return row is not None
        finally:
            conn.close()
    
    # Ticket methods
    async def create_ticket(self, guild_id: int, channel_id: int, user_id: int, username: str) -> int:
        """Create a new ticket record and return the ticket ID"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO tickets (guild_id, channel_id, user_id, username, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (guild_id, channel_id, user_id, username, datetime.utcnow())
                )
                return cursor.lastrowid
        finally:
            conn.close()

    async def close_ticket(self, channel_id: int, closed_by: int, transcript_url: str = None) -> bool:
        """Close a ticket by channel ID"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "UPDATE tickets SET closed_at = %s, closed_by = %s, status = 'closed', transcript_url = %s WHERE channel_id = %s",
                    (datetime.utcnow(), closed_by, transcript_url, channel_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[Dict]:
        """Get ticket info by channel ID"""
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM tickets WHERE channel_id = %s",
                    (channel_id,)
                )
                return await cursor.fetchone()
        finally:
            conn.close()

    async def get_open_tickets(self, guild_id: int) -> List[Dict]:
        """Get all open tickets for a guild"""
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM tickets WHERE guild_id = %s AND status = 'open' ORDER BY created_at DESC",
                    (guild_id,)
                )
                return await cursor.fetchall()
        finally:
            conn.close()

    async def get_user_tickets(self, guild_id: int, user_id: int, limit: int = 10) -> List[Dict]:
        """Get recent tickets for a user"""
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM tickets WHERE guild_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT %s",
                    (guild_id, user_id, limit)
                )
                return await cursor.fetchall()
        finally:
            conn.close()

    async def add_ticket_participant(self, ticket_id: int, user_id: int, added_by: int) -> bool:
        """Add a participant to a ticket"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT IGNORE INTO ticket_participants (ticket_id, user_id, added_by, added_at) VALUES (%s, %s, %s, %s)",
                    (ticket_id, user_id, added_by, datetime.utcnow())
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    async def remove_ticket_participant(self, ticket_id: int, user_id: int) -> bool:
        """Remove a participant from a ticket"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM ticket_participants WHERE ticket_id = %s AND user_id = %s",
                    (ticket_id, user_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()

    async def get_ticket_stats(self, guild_id: int) -> Dict:
        """Get ticket statistics for a guild"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                # Total tickets
                await cursor.execute(
                    "SELECT COUNT(*) FROM tickets WHERE guild_id = %s",
                    (guild_id,)
                )
                total = (await cursor.fetchone())[0]

                # Open tickets
                await cursor.execute(
                    "SELECT COUNT(*) FROM tickets WHERE guild_id = %s AND status = 'open'",
                    (guild_id,)
                )
                open_count = (await cursor.fetchone())[0]

                # Closed tickets
                await cursor.execute(
                    "SELECT COUNT(*) FROM tickets WHERE guild_id = %s AND status = 'closed'",
                    (guild_id,)
                )
                closed_count = (await cursor.fetchone())[0]

                return {
                    'total': total,
                    'open': open_count,
                    'closed': closed_count
                }
        finally:
            conn.close()

    # Server statistics methods for Grafana
    async def update_user_activity(self, guild_id: int, user_id: int):
        """Update the last message time for a user"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO user_activity (guild_id, user_id, last_message) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE last_message = VALUES(last_message)",
                    (guild_id, user_id, datetime.utcnow())
                )
        finally:
            conn.close()

    async def log_server_stats(self, guild_id: int, total_members: int, online_members: int,
                              idle_members: int, dnd_members: int, offline_members: int):
        """Log server statistics"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO server_stats (guild_id, timestamp, total_members, online_members, idle_members, dnd_members, offline_members) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (guild_id, datetime.utcnow(), total_members, online_members, idle_members, dnd_members, offline_members)
                )
        finally:
            conn.close()

    async def get_server_stats(self, guild_id: int, hours: int = 24) -> List[Dict]:
        """Get server statistics for the past N hours"""
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                cutoff_time = datetime.utcnow() - timedelta(hours=hours)
                await cursor.execute(
                    """SELECT * FROM server_stats 
                       WHERE guild_id = %s AND timestamp >= %s 
                       ORDER BY timestamp DESC""",
                    (guild_id, cutoff_time)
                )
                return await cursor.fetchall()
        finally:
            conn.close()

    async def get_active_users_24h(self, guild_id: int) -> int:
        """Get count of users who were active in the past 24 hours"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                cutoff_time = datetime.utcnow() - timedelta(hours=24)
                await cursor.execute(
                    "SELECT COUNT(*) FROM user_activity WHERE guild_id = %s AND last_message >= %s",
                    (guild_id, cutoff_time)
                )
                row = await cursor.fetchone()
                return row[0] if row else 0
        finally:
            conn.close()

    async def cleanup_old_stats(self, days: int = 30):
        """Clean up server stats older than specified days"""
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                cutoff_time = datetime.utcnow() - timedelta(days=days)
                await cursor.execute(
                    "DELETE FROM server_stats WHERE timestamp < %s",
                    (cutoff_time,)
                )
                return cursor.rowcount
        finally:
            conn.close()