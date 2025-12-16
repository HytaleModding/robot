import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

log = logging.getLogger(__name__)

class Migration(ABC):
    """Base class for database migrations"""

    def __init__(self, migration_number: int, description: str, depends: list[int] = []):
        self.migration_number = migration_number
        self.description = description
        self.applied_at: Optional[datetime] = None
        self.depends: list[int] = depends

    @abstractmethod
    async def apply(self, connection) -> bool:
        """Apply the migration. Return True if applied, False if already applied."""
        pass
    
    @abstractmethod
    async def rollback(self, connection) -> bool:
        """Rollback the migration. Return True if rolled back successfully."""
        pass
    
    @property
    def name(self) -> str:
        """Get the migration name"""
        return f"{self.migration_number:03d}_{self.__class__.__name__.lower()}"

class MigrationManager:
    """Manages database migrations"""
    
    def __init__(self, database):
        self.database = database
        self.migrations: Dict[int, Migration] = {}
        self.dependencies: Dict[int, list[int]] = {}
    
    def register_migration(self, migration: Migration):
        """Register a migration"""
        if migration.migration_number in self.migrations:
            raise ValueError(f"Migration {migration.migration_number} already registered")
        self.migrations[migration.migration_number] = migration
        self.dependencies[migration.migration_number] = migration.depends

    async def init_migrations_table(self):
        """Create the migrations tracking table if it doesn't exist"""
        conn = await self.database.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS migrations (
                        migration_number INT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        applied_at DATETIME NOT NULL,
                        INDEX idx_applied_at (applied_at)
                    ) ENGINE=InnoDB
                """)
        finally:
            conn.close()
    
    async def get_applied_migrations(self) -> Dict[int, Dict[str, Any]]:
        """Get all applied migrations"""
        conn = await self.database.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    SELECT migration_number, name, description, applied_at
                    FROM migrations
                    ORDER BY migration_number
                """)
                rows = await cursor.fetchall()
                return {
                    row[0]: {
                        'name': row[1],
                        'description': row[2],
                        'applied_at': row[3]
                    }
                    for row in rows
                }
        finally:
            conn.close()
    
    async def mark_migration_applied(self, migration: Migration):
        """Mark a migration as applied"""
        conn = await self.database.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO migrations (migration_number, name, description, applied_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE applied_at = VALUES(applied_at)
                """, (
                    migration.migration_number,
                    migration.name,
                    migration.description,
                    datetime.utcnow()
                ))
        finally:
            conn.close()
    
    async def mark_migration_rolled_back(self, migration_number: int):
        """Remove migration from applied migrations"""
        conn = await self.database.get_connection()
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    "DELETE FROM migrations WHERE migration_number = %s",
                    (migration_number,)
                )
        finally:
            conn.close()
    
    async def run_migrations(self):
        """Run all pending migrations"""
        await self.init_migrations_table()
        applied_migrations = await self.get_applied_migrations()
        
        # Sort migrations by number
        sorted_migrations = sorted(self.migrations.items())
        
        for migration_number, migration in sorted_migrations:
            if migration_number not in applied_migrations:
                log.info(f"Applying migration {migration.name}: {migration.description}")
                
                if migration.depends:
                    log.info(f"Migration {migration.name} depends on {migration.depends}, checking dependencies")
                    for dep_mig_num in migration.depends:
                        if dep_mig_num not in applied_migrations:
                            log.info(f"Dependency migration {dep_mig_num} not applied, applying it first")
                            await self.run_migrations()  
                            break 
                try:
                    was_applied = await migration.apply(await self.database.get_connection())
                    if was_applied:
                        await self.mark_migration_applied(migration)
                        log.info(f"Successfully applied migration {migration.name}")
                    else:
                        log.info(f"Migration {migration.name} was already applied")
                        await self.mark_migration_applied(migration)
                except Exception as e:
                    log.error(f"Failed to apply migration {migration.name}: {e}")
                    raise
            else:
                log.debug(f"Migration {migration.name} already applied")
    
    async def rollback_migration(self, migration_number: int) -> bool:
        """Rollback a specific migration"""
        if migration_number not in self.migrations:
            log.error(f"Migration {migration_number} not found")
            return False
        
        applied_migrations = await self.get_applied_migrations()
        if migration_number not in applied_migrations:
            log.info(f"Migration {migration_number} is not applied")
            return False
        
        migration = self.migrations[migration_number]
        log.info(f"Rolling back migration {migration.name}")
        
        dependants = self.get_dependants(migration_number)
        if dependants:
            log.info("Dependent migrations found, rolling them back first")
            for dep_mig_num in dependants:
                await self.rollback_migration(dep_mig_num)
                log.info(f"Successfully rolled back dependent migration {dep_mig_num}")

        try:
            success = await migration.rollback(await self.database.get_connection())
            if success:
                await self.mark_migration_rolled_back(migration_number)
                log.info(f"Successfully rolled back migration {migration.name}")
            return success
        except Exception as e:
            log.error(f"Failed to rollback migration {migration.name}: {e}")
            raise

    def get_dependants(self, migration_number: int) -> list[int]:
        """Get a list of migrations that depend on the given migration"""
        dependants = []
        for mig_num, deps in self.dependencies.items():
            if migration_number in deps:
                dependants.append(mig_num)
        return dependants
    
    def get_dependencies(self, migration_number: int) -> list[int]:
        """Get a list of migrations that the given migration depends on"""
        return self.dependencies.get(migration_number, [])