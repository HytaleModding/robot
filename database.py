import aiomysql
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import json

class Database:
    def __init__(self, host: str = "localhost", port: int = 3306, 
                 user: str = "root", password: str = "", database: str = "moderation"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
    
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
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                # Warnings table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS warnings (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        moderator_id BIGINT NOT NULL,
                        reason TEXT,
                        timestamp DATETIME NOT NULL,
                        INDEX idx_guild_user (guild_id, user_id),
                        INDEX idx_timestamp (timestamp)
                    ) ENGINE=InnoDB
                """)
                
                # Mod actions log table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS mod_actions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        action_type VARCHAR(50) NOT NULL,
                        user_id BIGINT NOT NULL,
                        moderator_id BIGINT NOT NULL,
                        reason TEXT,
                        duration INT,
                        timestamp DATETIME NOT NULL,
                        INDEX idx_guild_user (guild_id, user_id),
                        INDEX idx_timestamp (timestamp)
                    ) ENGINE=InnoDB
                """)
                
                # Mod log channel settings
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS mod_config (
                        guild_id BIGINT PRIMARY KEY,
                        log_channel_id BIGINT
                    ) ENGINE=InnoDB
                """)
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS upvotes (
                        user_id BIGINT NOT NULL,
                        showcase_id BIGINT NOT NULL,
                        PRIMARY KEY (user_id, showcase_id)
                    ) ENGINE=InnoDB
                """)

                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS thread_followers (
                        thread_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        PRIMARY KEY (thread_id, user_id)
                    ) ENGINE=InnoDB
                """)

                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tickets (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        channel_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        username VARCHAR(255) NOT NULL,
                        created_at DATETIME NOT NULL,
                        closed_at DATETIME NULL,
                        closed_by BIGINT NULL,
                        status VARCHAR(20) DEFAULT 'open',
                        transcript_url TEXT,
                        INDEX idx_guild (guild_id),
                        INDEX idx_status (status),
                        INDEX idx_user (user_id)
                    ) ENGINE=InnoDB
                """)
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ticket_participants (
                        ticket_id INT NOT NULL,
                        user_id BIGINT NOT NULL,
                        added_by BIGINT NOT NULL,
                        added_at DATETIME NOT NULL,
                        PRIMARY KEY (ticket_id, user_id),
                        FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
                    ) ENGINE=InnoDB
                """)

                # Server statistics tables for Grafana
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS server_stats (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        guild_id BIGINT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        total_members INT NOT NULL,
                        online_members INT NOT NULL,
                        idle_members INT NOT NULL,
                        dnd_members INT NOT NULL,
                        offline_members INT NOT NULL,
                        INDEX idx_guild_time (guild_id, timestamp)
                    ) ENGINE=InnoDB
                """)

                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_activity (
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL,
                        last_message DATETIME NOT NULL,
                        PRIMARY KEY (guild_id, user_id),
                        INDEX idx_last_message (last_message)
                    ) ENGINE=InnoDB
                """)

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
    
    async def clear_warnings(self, guild_id: int, user_id: int) -> int:
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM warnings WHERE guild_id = %s AND user_id = %s",
                    (guild_id, user_id)
                )
                return cursor.rowcount
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
        
    async def log_upvote(self, user_id: int, showcase_id: int):
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT IGNORE INTO upvotes (user_id, showcase_id) VALUES (%s, %s)",
                    (user_id, showcase_id)
                )
        finally:
            conn.close()

    async def get_upvotes(self, showcase_id: int) -> int:
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT COUNT(*) FROM upvotes WHERE showcase_id = %s",
                    (showcase_id,)
                )
                row = await cursor.fetchone()
                return row[0] if row else 0
        finally:
            conn.close()
        
    async def has_user_upvoted(self, user_id: int, showcase_id: int) -> bool:
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT 1 FROM upvotes WHERE user_id = %s AND showcase_id = %s",
                    (user_id, showcase_id)
                )
                row = await cursor.fetchone()
                return row is not None
        finally:
            conn.close()
    
    async def remove_upvote(self, user_id: int, showcase_id: int) -> bool:
        conn = await self.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM upvotes WHERE user_id = %s AND showcase_id = %s",
                    (user_id, showcase_id)
                )
                return cursor.rowcount > 0
        finally:
            conn.close()
        
    async def get_top_5_showcases(self) -> List[Dict]:
        conn = await self.get_connection()
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT showcase_id, COUNT(*) as upvote_count
                    FROM upvotes
                    GROUP BY showcase_id
                    ORDER BY upvote_count DESC
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