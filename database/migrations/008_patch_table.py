from database.migration import Migration

class PointsSystem(Migration):
    def __init__(self):
        super().__init__(8, "Create patches table")

    async def apply(self, connection) -> bool:
        """Create patches table"""
        async with connection.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS patches (
                    patch_id INT AUTO_INCREMENT PRIMARY KEY,
                    version TEXT NOT NULL,
                    patchline TEXT NOT NULL,
                    time DATETIME NOT NULL
                ) ENGINE=InnoDB
            """)
        return True
    
    async def rollback(self, connection) -> bool:
        """Drop patches tables"""
        async with connection.cursor() as cursor:
            await cursor.execute("DROP TABLE IF EXISTS patches")
        return True