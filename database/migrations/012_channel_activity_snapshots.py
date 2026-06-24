from database.migration import Migration


class ChannelActivitySnapshots(Migration):
    def __init__(self):
        super().__init__(12, "Create channel activity snapshots table")

    async def apply(self, connection) -> bool:
        """Create a table for persisted hourly channel message counts"""
        async with connection.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS channel_activity_snapshots (
                    guild_id BIGINT NOT NULL,
                    snapshot_at DATETIME NOT NULL,
                    channel_id BIGINT NOT NULL,
                    message_count INT NOT NULL,
                    computed_at DATETIME NOT NULL,
                    PRIMARY KEY (guild_id, snapshot_at, channel_id),
                    INDEX idx_snapshot_at (snapshot_at),
                    INDEX idx_guild_message_count (guild_id, message_count),
                    INDEX idx_channel_computed_at (channel_id, computed_at)
                ) ENGINE=InnoDB
            """)
        return True

    async def rollback(self, connection) -> bool:
        """Drop channel activity snapshots table"""
        async with connection.cursor() as cursor:
            await cursor.execute("DROP TABLE IF EXISTS channel_activity_snapshots")
        return True