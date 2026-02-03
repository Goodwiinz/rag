"""
Modern migration runner for the Multimodal Enterprise RAG System database
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import asyncpg
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()


class MigrationRunner:
    """Database migration runner with support for rollback and status tracking"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.migrations_dir = Path(__file__).parent
        self.connection_pool = None

    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.connection_pool = await asyncpg.create_pool(
                self.database_url, min_size=2, max_size=10, command_timeout=60
            )
            console.print("✅ Database connection pool initialized", style="green")
        except Exception as e:
            console.print(f"❌ Failed to initialize database pool: {e}", style="red")
            raise

    async def close(self):
        """Close database connection pool"""
        if self.connection_pool:
            await self.connection_pool.close()
            console.print("✅ Database connection pool closed", style="green")

    async def create_migration_table(self):
        """Create migrations tracking table if it doesn't exist"""
        async with self.connection_pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    executed_at TIMESTAMPTZ DEFAULT NOW(),
                    execution_time_ms INTEGER,
                    checksum VARCHAR(64),
                    rollback_version VARCHAR(255)
                )
            """
            )
            console.print("✅ Migration tracking table ready", style="green")

    async def get_executed_migrations(self) -> Dict[str, Dict]:
        """Get list of already executed migrations"""
        async with self.connection_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT version, name, executed_at, execution_time_ms, checksum, rollback_version
                FROM schema_migrations
                ORDER BY executed_at
            """
            )
            return {
                row["version"]: {
                    "name": row["name"],
                    "executed_at": row["executed_at"],
                    "execution_time_ms": row["execution_time_ms"],
                    "checksum": row["checksum"],
                    "rollback_version": row["rollback_version"],
                }
                for row in rows
            }

    def discover_migrations(self) -> List[Dict]:
        """Discover migration files in the migrations directory"""
        migrations = []
        for file_path in sorted(self.migrations_dir.glob("*.sql")):
            if file_path.name in ["migration_runner.py", "new_migration_runner.py"]:
                continue

            version = file_path.stem.split("_", 1)[0]
            name = (
                "_".join(file_path.stem.split("_", 1)[1:])
                if "_" in file_path.stem
                else file_path.stem
            )

            with open(file_path, "r") as f:
                content = f.read()

            migrations.append(
                {
                    "version": version,
                    "name": name,
                    "file_path": file_path,
                    "content": content,
                    "checksum": self.calculate_checksum(content),
                }
            )

        return migrations

    def calculate_checksum(self, content: str) -> str:
        """Calculate SHA-256 checksum of migration content"""
        import hashlib

        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def execute_migration(self, migration: Dict) -> bool:
        """Execute a single migration"""
        start_time = datetime.now()

        try:
            async with self.connection_pool.acquire() as conn:
                async with conn.transaction():
                    # Execute migration SQL
                    await conn.execute(migration["content"])

                    # Record migration
                    execution_time = int(
                        (datetime.now() - start_time).total_seconds() * 1000
                    )
                    await conn.execute(
                        """
                        INSERT INTO schema_migrations (version, name, execution_time_ms, checksum)
                        VALUES ($1, $2, $3, $4)
                    """,
                        migration["version"],
                        migration["name"],
                        execution_time,
                        migration["checksum"],
                    )

            console.print(
                f"✅ Migration {migration['version']} executed successfully ({execution_time}ms)",
                style="green",
            )
            return True

        except Exception as e:
            console.print(
                f"❌ Migration {migration['version']} failed: {e}", style="red"
            )
            logger.error(f"Migration {migration['version']} failed", exc_info=True)
            return False

    async def rollback_migration(self, version: str) -> bool:
        """Rollback a specific migration (if rollback file exists)"""
        rollback_file = self.migrations_dir / f"{version}_rollback.sql"
        if not rollback_file.exists():
            console.print(
                f"❌ No rollback file found for migration {version}", style="red"
            )
            return False

        try:
            with open(rollback_file, "r") as f:
                rollback_content = f.read()

            async with self.connection_pool.acquire() as conn:
                async with conn.transaction():
                    # Execute rollback SQL
                    await conn.execute(rollback_content)

                    # Remove migration record
                    await conn.execute(
                        "DELETE FROM schema_migrations WHERE version = $1", version
                    )

            console.print(
                f"✅ Migration {version} rolled back successfully", style="green"
            )
            return True

        except Exception as e:
            console.print(f"❌ Rollback of migration {version} failed: {e}", style="red")
            logger.error(f"Rollback of migration {version} failed", exc_info=True)
            return False

    async def show_status(self):
        """Show migration status"""
        console.print("\n📊 Migration Status", style="bold blue")

        executed_migrations = await self.get_executed_migrations()
        available_migrations = self.discover_migrations()

        table = Table(title="Migration Status")
        table.add_column("Version", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Executed At", style="yellow")
        table.add_column("Execution Time", style="blue")

        for migration in available_migrations:
            version = migration["version"]
            if version in executed_migrations:
                exec_info = executed_migrations[version]
                status = "✅ Applied"
                executed_at = exec_info["executed_at"].strftime("%Y-%m-%d %H:%M:%S")
                exec_time = f"{exec_info['execution_time_ms']}ms"
            else:
                status = "⏳ Pending"
                executed_at = "-"
                exec_time = "-"

            table.add_row(version, migration["name"], status, executed_at, exec_time)

        console.print(table)

        # Summary
        applied_count = len(executed_migrations)
        pending_count = len(available_migrations) - applied_count

        console.print(
            f"\n📈 Summary: {applied_count} applied, {pending_count} pending",
            style="bold",
        )

    async def migrate(self, target_version: Optional[str] = None):
        """Run migrations up to target version (or all if not specified)"""
        console.print("🚀 Starting database migration", style="bold blue")

        await self.create_migration_table()
        executed_migrations = await self.get_executed_migrations()
        available_migrations = self.discover_migrations()

        # Filter migrations to execute
        migrations_to_run = []
        for migration in available_migrations:
            if migration["version"] not in executed_migrations:
                if target_version is None or migration["version"] <= target_version:
                    # Check if migration content has changed
                    if migration["version"] in executed_migrations:
                        exec_info = executed_migrations[migration["version"]]
                        if exec_info["checksum"] != migration["checksum"]:
                            console.print(
                                f"⚠️  Migration {migration['version']} has changed - manual intervention required",
                                style="yellow",
                            )
                            continue
                    migrations_to_run.append(migration)

        if not migrations_to_run:
            console.print("✅ No migrations to run", style="green")
            return

        # Execute migrations with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Running migrations...", total=len(migrations_to_run)
            )

            for migration in migrations_to_run:
                progress.update(task, description=f"Running {migration['version']}...")

                success = await self.execute_migration(migration)
                if not success:
                    console.print(
                        f"❌ Migration stopped at {migration['version']}", style="red"
                    )
                    return

                progress.advance(task)

        console.print("✅ All migrations completed successfully", style="bold green")

    async def rollback(self, version: str):
        """Rollback to a specific version"""
        console.print(f"🔄 Rolling back to version {version}", style="bold blue")

        executed_migrations = await self.get_executed_migrations()

        # Get migrations to rollback (in reverse order)
        versions_to_rollback = [
            v for v in sorted(executed_migrations.keys(), reverse=True) if v > version
        ]

        if not versions_to_rollback:
            console.print("✅ No migrations to rollback", style="green")
            return

        for rollback_version in versions_to_rollback:
            success = await self.rollback_migration(rollback_version)
            if not success:
                console.print(f"❌ Rollback stopped at {rollback_version}", style="red")
                return

        console.print("✅ Rollback completed successfully", style="bold green")

    async def validate_schema(self):
        """Validate current database schema against expected state"""
        console.print("🔍 Validating database schema", style="bold blue")

        async with self.connection_pool.acquire() as conn:
            # Check if all expected tables exist
            expected_tables = {
                "organizations",
                "users",
                "user_sessions",
                "documents",
                "document_processing_jobs",
                "search_queries",
                "search_results",
                "entities",
                "entity_relationships",
                "concepts",
                "rag_evaluations",
                "performance_metrics",
                "system_health",
                "error_logs",
                "schema_migrations",
            }

            existing_tables = set(
                await conn.fetchval(
                    """
                SELECT array_agg(table_name)
                FROM information_schema.tables
                WHERE table_schema = 'current_schema()'
            """
                )
                or []
            )

            missing_tables = expected_tables - existing_tables
            extra_tables = existing_tables - expected_tables

            if missing_tables:
                console.print(
                    f"❌ Missing tables: {', '.join(missing_tables)}", style="red"
                )
                return False

            if extra_tables:
                console.print(
                    f"⚠️  Extra tables: {', '.join(extra_tables)}", style="yellow"
                )

            # Check if RLS is enabled on sensitive tables
            rls_required_tables = {
                "organizations",
                "users",
                "documents",
                "search_queries",
                "entities",
                "rag_evaluations",
                "error_logs",
            }

            rls_status = await conn.fetch(
                """
                SELECT schemaname, tablename, rowsecurity
                FROM pg_tables
                WHERE tablename = ANY($1)
                  AND schemaname = 'public'
            """,
                list(rls_required_tables),
            )

            for table_info in rls_status:
                if not table_info["rowsecurity"]:
                    console.print(
                        f"⚠️  RLS not enabled on table: {table_info['tablename']}",
                        style="yellow",
                    )

        console.print("✅ Schema validation completed", style="green")
        return True


async def main():
    """Main migration runner entry point"""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Database Migration Runner")
    parser.add_argument(
        "command",
        choices=["migrate", "rollback", "status", "validate"],
        help="Migration command to execute",
    )
    parser.add_argument("--version", help="Target version for migrate/rollback")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="Database connection URL",
    )

    args = parser.parse_args()

    if not args.database_url:
        console.print(
            "❌ DATABASE_URL environment variable or --database-url argument required",
            style="red",
        )
        return

    runner = MigrationRunner(args.database_url)

    try:
        await runner.initialize()

        if args.command == "migrate":
            await runner.migrate(args.version)
        elif args.command == "rollback":
            if not args.version:
                console.print("❌ --version required for rollback", style="red")
                return
            await runner.rollback(args.version)
        elif args.command == "status":
            await runner.show_status()
        elif args.command == "validate":
            await runner.validate_schema()

    except KeyboardInterrupt:
        console.print("\n❌ Migration interrupted by user", style="red")
    except Exception as e:
        console.print(f"❌ Migration failed: {e}", style="red")
        logger.error("Migration failed", exc_info=True)
    finally:
        await runner.close()


if __name__ == "__main__":
    asyncio.run(main())
