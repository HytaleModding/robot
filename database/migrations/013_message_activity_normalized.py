from database.migration import Migration


class MessageActivityNormalized(Migration):
    def __init__(self):
        super().__init__(13, "Create normalized message activity table")

    async def apply(self, connection) -> bool:
        """Replace the old snapshot tables with one row per message"""
        async with connection.cursor() as cursor:
            await cursor.execute("DROP TABLE IF EXISTS anonymous_activity_events")
            await cursor.execute("DROP TABLE IF EXISTS dau_snapshots")
            await cursor.execute("DROP TABLE IF EXISTS channel_activity_snapshots")
            await cursor.execute("DROP TABLE IF EXISTS user_activity")
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_activity (
                    message_id BIGINT NOT NULL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    recorded_at DATETIME NOT NULL,
                    INDEX idx_guild_recorded_at (guild_id, recorded_at),
                    INDEX idx_guild_channel_recorded_at (guild_id, channel_id, recorded_at),
                    INDEX idx_guild_user_recorded_at (guild_id, user_id, recorded_at)
                ) ENGINE=InnoDB
            """)
        return True

    async def rollback(self, connection) -> bool:
        """Drop the normalized message activity table"""
        async with connection.cursor() as cursor:
            await cursor.execute("DROP TABLE IF EXISTS message_activity")
        return True