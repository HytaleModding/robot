from database.migration import Migration


class DropLegacyUserActivity(Migration):
    def __init__(self):
        super().__init__(10, "Drop legacy user activity table")

    async def apply(self, connection) -> bool:
        """Drop the old per-user activity table"""
        async with connection.cursor() as cursor:
            await cursor.execute("DROP TABLE IF EXISTS user_activity")
        return True

    async def rollback(self, connection) -> bool:
        """Restore the legacy per-user activity table"""
        async with connection.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_activity (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    last_message DATETIME NOT NULL,
                    PRIMARY KEY (guild_id, user_id),
                    INDEX idx_last_message (last_message)
                ) ENGINE=InnoDB
            """)
        return True