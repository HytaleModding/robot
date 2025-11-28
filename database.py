import sqlite3
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict

class Database:
    def __init__(self, db_path: str = "moderation.db"):
        self.db_path = db_path
    
    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            # Warnings table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    reason TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            
            # Mod actions log table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mod_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    moderator_id INTEGER NOT NULL,
                    reason TEXT,
                    duration INTEGER,
                    timestamp TEXT NOT NULL
                )
            """)
            
            # Mod log channel settings
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mod_config (
                    guild_id INTEGER PRIMARY KEY,
                    log_channel_id INTEGER
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS upvotes (
                    user_id INTEGER NOT NULL,
                    showcase_id INTEGER NOT NULL
                )
                """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS thread_followers (
                    thread_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    PRIMARY KEY (thread_id, user_id)
                )
            """)

            await db.commit()
    
    # Warning methods
    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
        timestamp = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                (guild_id, user_id, moderator_id, reason, timestamp)
            )
            await db.commit()
            return cursor.lastrowid
    
    async def get_warnings(self, guild_id: int, user_id: int) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
                (guild_id, user_id)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def remove_warning(self, warning_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM warnings WHERE id = ?", (warning_id,))
            await db.commit()
            return cursor.rowcount > 0
    
    async def clear_warnings(self, guild_id: int, user_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            await db.commit()
            return cursor.rowcount
    
    # Mod actions log
    async def log_action(self, guild_id: int, action_type: str, user_id: int, 
                        moderator_id: int, reason: str = None, duration: int = None):
        timestamp = datetime.utcnow().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO mod_actions (guild_id, action_type, user_id, moderator_id, reason, duration, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (guild_id, action_type, user_id, moderator_id, reason, duration, timestamp)
            )
            await db.commit()
    
    async def get_user_history(self, guild_id: int, user_id: int) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM mod_actions WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT 50",
                (guild_id, user_id)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # Config methods
    async def set_log_channel(self, guild_id: int, channel_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO mod_config (guild_id, log_channel_id) VALUES (?, ?)",
                (guild_id, channel_id)
            )
            await db.commit()
    
    async def get_log_channel(self, guild_id: int) -> Optional[int]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT log_channel_id FROM mod_config WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None
        
    async def log_upvote(self, user_id: int, showcase_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO upvotes (user_id, showcase_id) VALUES (?, ?)",
                (user_id, showcase_id)
            )
            await db.commit()

    async def get_upvotes(self, showcase_id: int) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM upvotes WHERE showcase_id = ?",
                (showcase_id,)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
        
    async def has_user_upvoted(self, user_id: int, showcase_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM upvotes WHERE user_id = ? AND showcase_id = ?",
                (user_id, showcase_id)
            )
            row = await cursor.fetchone()
            return row is not None
    
    async def remove_upvote(self, user_id: int, showcase_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM upvotes WHERE user_id = ? AND showcase_id = ?",
                (user_id, showcase_id)
            )
            await db.commit()
            return cursor.rowcount > 0
        
    async def get_top_5_showcases(self) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT showcase_id, COUNT(*) as upvote_count
                FROM upvotes
                GROUP BY showcase_id
                ORDER BY upvote_count DESC
                LIMIT 5
                """
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    # Thread follower methods
    async def add_thread_follower(self, thread_id: int, user_id: int) -> bool:
        """Add a user as a follower of a thread. Returns True if added, False if already following."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    "INSERT INTO thread_followers (thread_id, user_id) VALUES (?, ?)",
                    (thread_id, user_id)
                )
                await db.commit()
                return True
            except sqlite3.IntegrityError:
                return False
    
    async def remove_thread_follower(self, thread_id: int, user_id: int) -> bool:
        """Remove a user as a follower of a thread. Returns True if removed, False if not following."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM thread_followers WHERE thread_id = ? AND user_id = ?",
                (thread_id, user_id)
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def get_thread_followers(self, thread_id: int) -> List[int]:
        """Get all followers of a thread."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT user_id FROM thread_followers WHERE thread_id = ?",
                (thread_id,)
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def is_following_thread(self, thread_id: int, user_id: int) -> bool:
        """Check if a user is following a thread."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM thread_followers WHERE thread_id = ? AND user_id = ?",
                (thread_id, user_id)
            )
            row = await cursor.fetchone()
            return row is not None