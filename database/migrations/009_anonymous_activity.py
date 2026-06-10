from database.migration import Migration


class AnonymousActivity(Migration):
    def __init__(self):
        super().__init__(9, "Create anonymous activity table for DAU tracking")

    async def apply(self, connection) -> bool:
        """Create an anonymous activity table for privacy-preserving DAU tracking"""
        async with connection.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS anonymous_activity_events (
                    guild_id BIGINT NOT NULL,
                    activity_date DATE NOT NULL,
                    activity_hour TINYINT UNSIGNED NOT NULL,
                    user_hash CHAR(64) NOT NULL,
                    recorded_at DATETIME NOT NULL,
                    PRIMARY KEY (guild_id, activity_date, activity_hour, user_hash),
                    INDEX idx_guild_recorded_at (guild_id, recorded_at),
                    INDEX idx_recorded_at (recorded_at)
                ) ENGINE=InnoDB
            """)
        return True

    async def rollback(self, connection) -> bool:
        """Drop anonymous activity table"""
        async with connection.cursor() as cursor:
            await cursor.execute("DROP TABLE IF EXISTS anonymous_activity_events")
        return True