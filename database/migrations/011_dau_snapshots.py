from database.migration import Migration


class DauSnapshots(Migration):
    def __init__(self):
        super().__init__(11, "Create DAU snapshots table")

    async def apply(self, connection) -> bool:
        """Create a table for persisted daily active user snapshots"""
        async with connection.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS dau_snapshots (
                    guild_id BIGINT NOT NULL,
                    snapshot_at DATETIME NOT NULL,
                    dau_24h INT NOT NULL,
                    computed_at DATETIME NOT NULL,
                    PRIMARY KEY (guild_id, snapshot_at),
                    INDEX idx_snapshot_at (snapshot_at),
                    INDEX idx_guild_computed_at (guild_id, computed_at)
                ) ENGINE=InnoDB
            """)
        return True

    async def rollback(self, connection) -> bool:
        """Drop DAU snapshots table"""
        async with connection.cursor() as cursor:
            await cursor.execute("DROP TABLE IF EXISTS dau_snapshots")
        return True