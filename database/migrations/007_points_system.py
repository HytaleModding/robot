from database.migration import Migration

class PointsSystem(Migration):
    def __init__(self):
        super().__init__(7, "Create points system for helpful users")
    
    async def apply(self, connection) -> bool:
        """Create points table"""
        async with connection.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_points (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    points INT NOT NULL DEFAULT 0,
                    last_updated DATETIME NOT NULL,
                    PRIMARY KEY (guild_id, user_id),
                    INDEX idx_points (points DESC),
                    INDEX idx_last_updated (last_updated)
                ) ENGINE=InnoDB
            """)
            
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS point_transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    awarded_by BIGINT NOT NULL,
                    points INT NOT NULL,
                    reason VARCHAR(255) NOT NULL,
                    thread_id BIGINT,
                    timestamp DATETIME NOT NULL,
                    INDEX idx_guild_user (guild_id, user_id),
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_thread (thread_id)
                ) ENGINE=InnoDB
            """)
        return True
    
    async def rollback(self, connection) -> bool:
        """Drop points tables"""
        async with connection.cursor() as cursor:
            await cursor.execute("DROP TABLE IF EXISTS point_transactions")
            await cursor.execute("DROP TABLE IF EXISTS user_points")
        return True