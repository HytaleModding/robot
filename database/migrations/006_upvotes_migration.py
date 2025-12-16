from database.migration import Migration

class UpvotesMigration(Migration):
    def __init__(self):
        super().__init__(6, "Migrate upvotes table from user-showcase schema to showcase with count schema", [2])
    
    async def apply(self, connection) -> bool:
        """Migrate upvotes table structure if needed"""
        async with connection.cursor() as cursor:
            await cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 'upvotes'
                ORDER BY ORDINAL_POSITION
            """)
            columns = {row[0] for row in await cursor.fetchall()}
            is_old_schema = columns == {'user_id', 'showcase_id'}

            if not is_old_schema:
                return False

            await cursor.execute("DROP TABLE IF EXISTS upvotes_new")
            await cursor.execute("""
                CREATE TABLE upvotes_new (
                    showcase_id BIGINT NOT NULL PRIMARY KEY,
                    count INT NOT NULL DEFAULT 0
                ) ENGINE=InnoDB
            """)
            
            await cursor.execute("""
                INSERT INTO upvotes_new (showcase_id, count)
                SELECT showcase_id, COUNT(*) AS count
                FROM upvotes
                GROUP BY showcase_id
            """)

            await cursor.execute("""
                RENAME TABLE
                    upvotes TO upvotes_backup,
                    upvotes_new TO upvotes
            """)

            return True
    
    async def rollback(self, connection) -> bool:
        """Rollback upvotes migration"""
        async with connection.cursor() as cursor:
            await cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = DATABASE() AND table_name = 'upvotes_backup'
            """)
            backup_exists = (await cursor.fetchone())[0] > 0
            
            if backup_exists:
                await cursor.execute("""
                    RENAME TABLE
                        upvotes TO upvotes_migrated,
                        upvotes_backup TO upvotes
                """)
                await cursor.execute("DROP TABLE IF EXISTS upvotes_migrated")
                return True
            
            return False