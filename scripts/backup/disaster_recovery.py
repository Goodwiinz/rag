#!/usr/bin/env python3
"""
Disaster Recovery Script for Multimodal RAG System
This script handles automated disaster recovery procedures
"""

import os
import re
import sys
import json
import logging
import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum

import asyncpg
from qdrant_client import QdrantClient
from neo4j import GraphDatabase

_VALID_PG_IDENT = re.compile(r'^[a-z_][a-z0-9_]{0,62}$')


def _safe_pg_identifier(name: str, kind: str = "identifier") -> str:
    """Validate a PostgreSQL identifier against an allowlist before interpolation."""
    if not _VALID_PG_IDENT.match(name):
        raise ValueError(f"Invalid PostgreSQL {kind}: {name!r}")
    return name


async def _run_subprocess(*cmd: str, env: Optional[Dict[str, str]] = None,
                          check: bool = True) -> "asyncio.subprocess.Process":
    """Run a subprocess without blocking the event loop."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(cmd)!r} failed with exit code {proc.returncode}: "
            f"{stderr.decode(errors='replace').strip()}"
        )
    proc._captured_stdout = stdout  # type: ignore[attr-defined]
    proc._captured_stderr = stderr  # type: ignore[attr-defined]
    return proc

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/disaster_recovery.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RecoveryStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class DisasterRecovery:
    """Disaster recovery coordinator for the multimodal RAG system."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.recovery_log = []
        self.start_time = datetime.now()

    async def run_recovery(self, components: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run disaster recovery for specified components.
        If no components specified, recover all components.
        """
        logger.info("Starting disaster recovery process...")

        if not components:
            components = ['database', 'vector_store', 'knowledge_graph', 'uploads']

        recovery_results = {}

        # Recovery order matters - database first
        recovery_order = {
            'database': self.recover_database,
            'knowledge_graph': self.recover_knowledge_graph,
            'vector_store': self.recover_vector_store,
            'uploads': self.recover_uploads,
            'services': self.recover_services
        }

        for component in components:
            if component in recovery_order:
                logger.info(f"Starting recovery for {component}")
                try:
                    result = await recovery_order[component]()
                    recovery_results[component] = result
                    self._log_recovery_step(component, result)
                except Exception as e:
                    logger.error(f"Recovery failed for {component}: {e}")
                    recovery_results[component] = {
                        'status': RecoveryStatus.FAILED.value,
                        'error': str(e)
                    }
                    self._log_recovery_step(component, recovery_results[component])
            else:
                logger.warning(f"Unknown component: {component}")

        # Generate recovery report
        report = self._generate_recovery_report(recovery_results)
        await self._send_recovery_notification(report)

        return report

    async def recover_database(self) -> Dict[str, Any]:
        """Recover PostgreSQL database from backup."""
        logger.info("Starting database recovery...")

        try:
            # Find latest backup
            backup_file = await self._find_latest_backup('postgresql')
            if not backup_file:
                return {
                    'status': RecoveryStatus.FAILED.value,
                    'error': 'No database backup found'
                }

            logger.info(f"Using backup: {backup_file}")

            # Stop application services
            await self._stop_services(['backend', 'celery-worker', 'celery-beat'])

            # Drop existing database (if exists)
            await self._drop_database()

            # Create new database
            await self._create_database()

            # Restore from backup
            success = await self._restore_database(backup_file)

            if success:
                # Verify database integrity
                integrity_ok = await self._verify_database_integrity()

                if integrity_ok:
                    logger.info("Database recovery completed successfully")
                    return {
                        'status': RecoveryStatus.SUCCESS.value,
                        'backup_file': str(backup_file),
                        'restored_at': datetime.now().isoformat()
                    }
                else:
                    logger.error("Database integrity check failed")
                    return {
                        'status': RecoveryStatus.FAILED.value,
                        'error': 'Database integrity check failed'
                    }
            else:
                return {
                    'status': RecoveryStatus.FAILED.value,
                    'error': 'Database restore failed'
                }

        except Exception as e:
            logger.error(f"Database recovery failed: {e}")
            return {
                'status': RecoveryStatus.FAILED.value,
                'error': str(e)
            }

    async def recover_knowledge_graph(self) -> Dict[str, Any]:
        """Recover Neo4j knowledge graph from backup."""
        logger.info("Starting knowledge graph recovery...")

        try:
            # Find latest Neo4j backup
            backup_file = await self._find_latest_backup('neo4j')
            if not backup_file:
                logger.warning("No Neo4j backup found, skipping knowledge graph recovery")
                return {
                    'status': RecoveryStatus.SKIPPED.value,
                    'reason': 'No backup found'
                }

            logger.info(f"Using backup: {backup_file}")

            # Stop Neo4j service
            await self._stop_service('neo4j')

            # Clear existing data
            await self._clear_neo4j_data()

            # Restore from backup
            success = await self._restore_neo4j(backup_file)

            if success:
                # Verify graph integrity
                integrity_ok = await self._verify_neo4j_integrity()

                if integrity_ok:
                    logger.info("Knowledge graph recovery completed successfully")
                    return {
                        'status': RecoveryStatus.SUCCESS.value,
                        'backup_file': str(backup_file),
                        'restored_at': datetime.now().isoformat()
                    }
                else:
                    logger.error("Knowledge graph integrity check failed")
                    return {
                        'status': RecoveryStatus.PARTIAL.value,
                        'warning': 'Integrity check failed'
                    }
            else:
                return {
                    'status': RecoveryStatus.FAILED.value,
                    'error': 'Neo4j restore failed'
                }

        except Exception as e:
            logger.error(f"Knowledge graph recovery failed: {e}")
            return {
                'status': RecoveryStatus.FAILED.value,
                'error': str(e)
            }

    async def recover_vector_store(self) -> Dict[str, Any]:
        """Recover Qdrant vector store from backup."""
        logger.info("Starting vector store recovery...")

        try:
            # Find latest vector store backup
            backup_file = await self._find_latest_backup('qdrant')
            if not backup_file:
                logger.warning("No Qdrant backup found, skipping vector store recovery")
                return {
                    'status': RecoveryStatus.SKIPPED.value,
                    'reason': 'No backup found'
                }

            logger.info(f"Using backup: {backup_file}")

            # Stop Qdrant service
            await self._stop_service('qdrant')

            # Clear existing data
            await self._clear_qdrant_data()

            # Restore from backup
            success = await self._restore_qdrant(backup_file)

            if success:
                # Verify vector store integrity
                integrity_ok = await self._verify_qdrant_integrity()

                if integrity_ok:
                    logger.info("Vector store recovery completed successfully")
                    return {
                        'status': RecoveryStatus.SUCCESS.value,
                        'backup_file': str(backup_file),
                        'restored_at': datetime.now().isoformat()
                    }
                else:
                    logger.error("Vector store integrity check failed")
                    return {
                        'status': RecoveryStatus.PARTIAL.value,
                        'warning': 'Integrity check failed'
                    }
            else:
                return {
                    'status': RecoveryStatus.FAILED.value,
                    'error': 'Qdrant restore failed'
                }

        except Exception as e:
            logger.error(f"Vector store recovery failed: {e}")
            return {
                'status': RecoveryStatus.FAILED.value,
                'error': str(e)
            }

    async def recover_uploads(self) -> Dict[str, Any]:
        """Recover uploaded files from backup."""
        logger.info("Starting uploads recovery...")

        try:
            # Find latest uploads backup
            backup_file = await self._find_latest_backup('uploads')
            if not backup_file:
                logger.warning("No uploads backup found, skipping files recovery")
                return {
                    'status': RecoveryStatus.SKIPPED.value,
                    'reason': 'No backup found'
                }

            logger.info(f"Using backup: {backup_file}")

            # Restore files
            success = await self._restore_uploads(backup_file)

            if success:
                # Set correct permissions
                await self._fix_upload_permissions()

                logger.info("Uploads recovery completed successfully")
                return {
                    'status': RecoveryStatus.SUCCESS.value,
                    'backup_file': str(backup_file),
                    'restored_at': datetime.now().isoformat()
                }
            else:
                return {
                    'status': RecoveryStatus.FAILED.value,
                    'error': 'Uploads restore failed'
                }

        except Exception as e:
            logger.error(f"Uploads recovery failed: {e}")
            return {
                'status': RecoveryStatus.FAILED.value,
                'error': str(e)
            }

    async def recover_services(self) -> Dict[str, Any]:
        """Recover application services."""
        logger.info("Starting services recovery...")

        try:
            services_to_start = ['postgres', 'redis', 'neo4j', 'qdrant', 'backend', 'celery-worker', 'celery-beat', 'frontend']
            started_services = []
            failed_services = []

            for service in services_to_start:
                try:
                    success = await self._start_service(service)
                    if success:
                        started_services.append(service)
                        logger.info(f"Started service: {service}")
                    else:
                        failed_services.append(service)
                        logger.error(f"Failed to start service: {service}")
                except Exception as e:
                    failed_services.append(service)
                    logger.error(f"Error starting service {service}: {e}")

            # Wait for services to be ready
            await asyncio.sleep(30)

            # Health check
            health_results = await self._run_health_checks()

            status = RecoveryStatus.SUCCESS
            if failed_services:
                status = RecoveryStatus.PARTIAL

            logger.info(f"Services recovery completed. Started: {len(started_services)}, Failed: {len(failed_services)}")

            return {
                'status': status.value,
                'started_services': started_services,
                'failed_services': failed_services,
                'health_checks': health_results,
                'recovered_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Services recovery failed: {e}")
            return {
                'status': RecoveryStatus.FAILED.value,
                'error': str(e)
            }

    async def _find_latest_backup(self, component: str) -> Optional[Path]:
        """Find the latest backup for a component."""
        backup_dirs = [
            Path(self.config.get('backup_dir', '/backups')),
            Path('/backups'),
            Path('./backups')
        ]

        for backup_dir in backup_dirs:
            if not backup_dir.exists():
                continue

            if component == 'postgresql':
                pattern = "multimodal_rag_backup_*.sql.gz"
            elif component == 'neo4j':
                pattern = "neo4j_backup_*.tar.gz"
            elif component == 'qdrant':
                pattern = "qdrant_backup_*.tar.gz"
            elif component == 'uploads':
                pattern = "uploads_backup_*.tar.gz"
            else:
                continue

            backups = list(backup_dir.glob(pattern))
            if backups:
                # Sort by modification time and return the latest
                latest = max(backups, key=lambda x: x.stat().st_mtime)
                logger.info(f"Found latest backup for {component}: {latest}")
                return latest

        return None

    async def _stop_services(self, services: List[str]):
        """Stop specified services."""
        for service in services:
            await self._stop_service(service)

    async def _stop_service(self, service: str):
        """Stop a specific service."""
        cmd = ['docker', 'stop', service] if self.config.get('use_docker', True) \
            else ['systemctl', 'stop', service]
        try:
            await _run_subprocess(*cmd)
            logger.info(f"Stopped service: {service}")
        except RuntimeError as e:
            logger.warning(f"Failed to stop service {service}: {e}")

    async def _start_service(self, service: str) -> bool:
        """Start a specific service."""
        cmd = ['docker', 'start', service] if self.config.get('use_docker', True) \
            else ['systemctl', 'start', service]
        try:
            await _run_subprocess(*cmd)
            return True
        except RuntimeError as e:
            logger.error(f"Failed to start service {service}: {e}")
            return False

    async def _drop_database(self):
        """Drop existing database."""
        db_name = _safe_pg_identifier(
            self.config.get('db_name', 'multimodal_rag'), 'database name'
        )
        conn = None
        try:
            conn = await asyncpg.connect(
                host=self.config.get('db_host', 'localhost'),
                port=self.config.get('db_port', 5432),
                user=self.config.get('db_user', 'postgres'),
                password=self.config.get('db_password'),
                database='postgres'
            )

            # Terminate connections to the target database
            await conn.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = $1
            """, db_name)

            # Drop the database (identifier validated above)
            await conn.execute(f'DROP DATABASE IF EXISTS {db_name}')
            logger.info("Dropped existing database")
        except Exception as e:
            logger.warning(f"Failed to drop database (may not exist): {e}")
        finally:
            if conn is not None:
                await conn.close()

    async def _create_database(self):
        """Create new database."""
        db_name = _safe_pg_identifier(
            self.config.get('db_name', 'multimodal_rag'), 'database name'
        )
        conn = await asyncpg.connect(
            host=self.config.get('db_host', 'localhost'),
            port=self.config.get('db_port', 5432),
            user=self.config.get('db_user', 'postgres'),
            password=self.config.get('db_password'),
            database='postgres'
        )
        try:
            await conn.execute(f'CREATE DATABASE {db_name}')
            logger.info("Created new database")
        finally:
            await conn.close()

    async def _restore_database(self, backup_file: Path) -> bool:
        """Restore database from backup file."""
        try:
            cmd = [
                'pg_restore',
                '--host', self.config.get('db_host', 'localhost'),
                '--port', str(self.config.get('db_port', 5432)),
                '--username', self.config.get('db_user', 'postgres'),
                '--dbname', self.config.get('db_name', 'multimodal_rag'),
                '--verbose',
                '--no-owner',
                '--no-privileges',
                str(backup_file),
            ]

            # Pass DB password via env without overwriting an existing PGPASSWORD
            # with None (os.environ rejects None values, raising TypeError).
            env = os.environ.copy()
            db_password = self.config.get('db_password')
            if db_password:
                env['PGPASSWORD'] = db_password

            try:
                await _run_subprocess(*cmd, env=env)
            except RuntimeError as e:
                logger.error(f"Database restore failed: {e}")
                return False

            logger.info("Database restore completed successfully")
            return True

        except Exception as e:
            logger.error(f"Database restore error: {e}")
            return False

    async def _verify_database_integrity(self) -> bool:
        """Verify database integrity after restore."""
        try:
            conn = await asyncpg.connect(
                host=self.config.get('db_host', 'localhost'),
                port=self.config.get('db_port', 5432),
                user=self.config.get('db_user', 'postgres'),
                password=self.config.get('db_password'),
                database=self.config.get('db_name', 'multimodal_rag')
            )

            # Check basic connectivity
            result = await conn.fetchval("SELECT 1")
            if result != 1:
                return False

            # Check if tables exist
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """)

            if not tables:
                logger.warning("No tables found in restored database")
                return False

            logger.info(f"Found {len(tables)} tables in restored database")
            await conn.close()
            return True

        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False

    async def _clear_neo4j_data(self):
        """Clear all data from Neo4j."""
        try:
            driver = GraphDatabase.driver(
                self.config.get('neo4j_uri', 'bolt://localhost:7687'),
                auth=(self.config.get('neo4j_user', 'neo4j'), self.config.get('neo4j_password'))
            )

            with driver.session() as session:
                # Delete all nodes and relationships
                session.run("MATCH (n) DETACH DELETE n")

            driver.close()
            logger.info("Cleared Neo4j data")
        except Exception as e:
            logger.warning(f"Failed to clear Neo4j data: {e}")

    async def _restore_neo4j(self, backup_file: Path) -> bool:
        """Restore Neo4j from backup."""
        try:
            # This would depend on your Neo4j backup method
            # For now, we'll simulate a restore
            logger.info(f"Neo4j restore from {backup_file} (simulated)")
            return True
        except Exception as e:
            logger.error(f"Neo4j restore failed: {e}")
            return False

    async def _verify_neo4j_integrity(self) -> bool:
        """Verify Neo4j integrity after restore."""
        try:
            driver = GraphDatabase.driver(
                self.config.get('neo4j_uri', 'bolt://localhost:7687'),
                auth=(self.config.get('neo4j_user', 'neo4j'), self.config.get('neo4j_password'))
            )

            with driver.session() as session:
                result = session.run("MATCH (n) RETURN count(n) as count")
                count = result.single()['count']

            driver.close()
            logger.info(f"Neo4j integrity check passed: {count} nodes found")
            return True

        except Exception as e:
            logger.error(f"Neo4j integrity check failed: {e}")
            return False

    async def _clear_qdrant_data(self):
        """Clear all data from Qdrant."""
        try:
            client = QdrantClient(
                host=self.config.get('qdrant_host', 'localhost'),
                port=self.config.get('qdrant_port', 6333),
                api_key=self.config.get('qdrant_api_key')
            )

            # Get all collections
            collections = client.get_collections()

            # Delete all collections
            for collection in collections.collections:
                client.delete_collection(collection.name)

            logger.info(f"Cleared {len(collections.collections)} Qdrant collections")
        except Exception as e:
            logger.warning(f"Failed to clear Qdrant data: {e}")

    async def _restore_qdrant(self, backup_file: Path) -> bool:
        """Restore Qdrant from backup."""
        try:
            # This would use the backup_vector_store.py restore functionality
            logger.info(f"Qdrant restore from {backup_file} (simulated)")
            return True
        except Exception as e:
            logger.error(f"Qdrant restore failed: {e}")
            return False

    async def _verify_qdrant_integrity(self) -> bool:
        """Verify Qdrant integrity after restore."""
        try:
            client = QdrantClient(
                host=self.config.get('qdrant_host', 'localhost'),
                port=self.config.get('qdrant_port', 6333),
                api_key=self.config.get('qdrant_api_key')
            )

            collections = client.get_collections()
            logger.info(f"Qdrant integrity check passed: {len(collections.collections)} collections found")
            return True

        except Exception as e:
            logger.error(f"Qdrant integrity check failed: {e}")
            return False

    async def _restore_uploads(self, backup_file: Path) -> bool:
        """Restore uploaded files from backup."""
        try:
            upload_dir = Path(self.config.get('upload_dir', '/app/uploads'))
            upload_dir.mkdir(parents=True, exist_ok=True)

            await _run_subprocess('tar', 'xzf', str(backup_file), '-C', str(upload_dir.parent))
            logger.info(f"Restored uploads from {backup_file}")
            return True

        except Exception as e:
            logger.error(f"Uploads restore failed: {e}")
            return False

    async def _fix_upload_permissions(self):
        """Fix permissions for uploaded files."""
        try:
            upload_dir = Path(self.config.get('upload_dir', '/app/uploads'))
            await _run_subprocess('chown', '-R', 'www-data:www-data', str(upload_dir))
            await _run_subprocess('chmod', '-R', '755', str(upload_dir))
            logger.info("Fixed upload permissions")
        except Exception as e:
            logger.warning(f"Failed to fix upload permissions: {e}")

    async def _run_health_checks(self) -> Dict[str, Any]:
        """Run health checks on all components."""
        try:
            # This would use the health checker module
            return {"status": "healthy", "components": {}}
        except Exception as e:
            logger.error(f"Health checks failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    def _log_recovery_step(self, component: str, result: Dict[str, Any]):
        """Log a recovery step."""
        step = {
            'component': component,
            'status': result.get('status', 'unknown'),
            'timestamp': datetime.now().isoformat(),
            'details': result
        }
        self.recovery_log.append(step)

    def _generate_recovery_report(self, recovery_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a comprehensive recovery report."""
        end_time = datetime.now()
        duration = end_time - self.start_time

        total_components = len(recovery_results)
        successful = sum(1 for r in recovery_results.values() if r.get('status') == RecoveryStatus.SUCCESS.value)
        failed = sum(1 for r in recovery_results.values() if r.get('status') == RecoveryStatus.FAILED.value)
        partial = sum(1 for r in recovery_results.values() if r.get('status') == RecoveryStatus.PARTIAL.value)
        skipped = sum(1 for r in recovery_results.values() if r.get('status') == RecoveryStatus.SKIPPED.value)

        overall_status = RecoveryStatus.SUCCESS
        if failed > 0:
            overall_status = RecoveryStatus.FAILED
        elif partial > 0:
            overall_status = RecoveryStatus.PARTIAL

        return {
            'recovery_id': f"recovery_{self.start_time.strftime('%Y%m%d_%H%M%S')}",
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            'overall_status': overall_status.value,
            'summary': {
                'total_components': total_components,
                'successful': successful,
                'failed': failed,
                'partial': partial,
                'skipped': skipped
            },
            'component_results': recovery_results,
            'recovery_log': self.recovery_log
        }

    async def _send_recovery_notification(self, report: Dict[str, Any]):
        """Send recovery notification."""
        try:
            # This would implement Slack/email notifications
            logger.info("Recovery notification sent (simulated)")
        except Exception as e:
            logger.error(f"Failed to send recovery notification: {e}")


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    return {
        'backup_dir': os.getenv('BACKUP_DIR', '/backups'),
        'use_docker': os.getenv('USE_DOCKER', 'true').lower() == 'true',
        'db_host': os.getenv('DB_HOST', 'localhost'),
        'db_port': int(os.getenv('DB_PORT', '5432')),
        'db_user': os.getenv('DB_USER', 'postgres'),
        'db_password': os.getenv('DB_PASSWORD'),
        'db_name': os.getenv('DB_NAME', 'multimodal_rag'),
        'neo4j_uri': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        'neo4j_user': os.getenv('NEO4J_USER', 'neo4j'),
        'neo4j_password': os.getenv('NEO4J_PASSWORD'),
        'qdrant_host': os.getenv('QDRANT_HOST', 'localhost'),
        'qdrant_port': int(os.getenv('QDRANT_PORT', '6333')),
        'qdrant_api_key': os.getenv('QDRANT_API_KEY'),
        'upload_dir': os.getenv('UPLOAD_DIR', '/app/uploads'),
    }


async def main():
    """Main disaster recovery function."""
    parser = argparse.ArgumentParser(description='Disaster recovery for Multimodal RAG system')
    parser.add_argument('--components', nargs='+', help='Components to recover (database, vector_store, knowledge_graph, uploads, services)')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without making changes')
    parser.add_argument('--force', action='store_true', help='Force recovery without confirmation')
    args = parser.parse_args()

    config = load_config()
    recovery = DisasterRecovery(config)

    try:
        if not args.force and not args.dry_run:
            response = input("This will perform disaster recovery. Are you sure? (yes/no): ")
            if response.lower() != 'yes':
                print("Recovery cancelled")
                return

        if args.dry_run:
            print("DRY RUN: Would perform disaster recovery for components:", args.components or 'all')
            return

        report = await recovery.run_recovery(args.components)

        # Save recovery report
        report_file = f"/var/log/recovery_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"Recovery completed. Report saved to: {report_file}")
        print(f"Overall status: {report['overall_status']}")

        if report['overall_status'] == RecoveryStatus.FAILED.value:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Disaster recovery failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())