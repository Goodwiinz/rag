#!/usr/bin/env python3
"""
Vector Store Backup Script for Qdrant
This script creates automated backups of the Qdrant vector database
"""

import os
import sys
import json
import gzip
import shutil
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List

import asyncio
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Configuration
DEFAULT_BACKUP_DIR = "/backups/qdrant"
DEFAULT_RETENTION_DAYS = 30
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 6333

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VectorStoreBackup:
    """Backup manager for Qdrant vector database."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.backup_dir = Path(config['backup_dir'])
        self.client = QdrantClient(
            host=config['host'],
            port=config['port'],
            api_key=config.get('api_key')
        )
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    async def create_backup(self) -> str:
        """Create a complete backup of the vector store."""
        logger.info("Starting vector store backup...")

        # Create backup directory
        backup_path = self.backup_dir / f"qdrant_backup_{self.timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            # Get all collections
            collections = self.client.get_collections()
            logger.info(f"Found {len(collections.collections)} collections")

            backup_data = {
                "backup_info": {
                    "timestamp": self.timestamp,
                    "version": "1.0",
                    "collections": [],
                    "total_points": 0
                },
                "collections": {}
            }

            total_points = 0

            # Backup each collection
            for collection in collections.collections:
                logger.info(f"Backing up collection: {collection.name}")

                collection_data = await self._backup_collection(collection.name, backup_path)
                backup_data["collections"][collection.name] = collection_data
                backup_data["backup_info"]["collections"].append(collection.name)
                backup_data["backup_info"]["total_points"] += collection_data["points_count"]
                total_points += collection_data["points_count"]

            # Save backup metadata
            metadata_file = backup_path / "backup_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(backup_data, f, indent=2)

            # Create compressed archive
            archive_path = await self._create_archive(backup_path)

            logger.info(f"Backup completed successfully: {archive_path}")
            logger.info(f"Total collections: {len(collections.collections)}")
            logger.info(f"Total points: {total_points}")

            return str(archive_path)

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            # Cleanup on failure
            if backup_path.exists():
                shutil.rmtree(backup_path)
            raise

    async def _backup_collection(self, collection_name: str, backup_path: Path) -> Dict[str, Any]:
        """Backup a single collection."""
        collection_info = self.client.get_collection(collection_name)
        # points_count is Optional[int] in qdrant-client and is None for empty
        # collections; passing None to scroll(limit=...) raises TypeError.
        points_count: int = collection_info.points_count or 0

        # Create collection directory
        collection_dir = backup_path / "collections" / collection_name
        collection_dir.mkdir(parents=True, exist_ok=True)

        # Save collection configuration
        config_file = collection_dir / "collection_config.json"
        config_data = {
            "name": collection_name,
            "vectors_config": collection_info.config.vectors_config.to_dict(),
            "points_count": points_count
        }
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)

        # Export points in batches
        points_file = collection_dir / "points.jsonl.gz"
        exported_points = 0

        if points_count == 0:
            logger.info(f"Collection {collection_name} is empty, skipping point export")
            # Still create an empty points file so downstream consumers can rely on its presence
            with gzip.open(points_file, 'wt', encoding='utf-8') as f:
                pass
            return {
                "name": collection_name,
                "points_count": 0,
                "config": config_data,
                "backup_file": f"collections/{collection_name}/points.jsonl.gz",
            }

        with gzip.open(points_file, 'wt', encoding='utf-8') as f:
            all_points = self.client.scroll(
                collection_name=collection_name,
                limit=points_count,
                with_payload=True,
                with_vectors=True
            )[0]

            for point in all_points:
                point_dict = {
                    "id": point.id,
                    "payload": point.payload,
                    "vector": point.vector
                }
                f.write(json.dumps(point_dict) + '\n')
                exported_points += 1

                if exported_points % 1000 == 0:
                    logger.info(f"Exported {exported_points}/{points_count} points for {collection_name}")

        logger.info(f"Exported {exported_points} points for collection {collection_name}")

        return {
            "name": collection_name,
            "points_count": exported_points,
            "config": config_data,
            "backup_file": f"collections/{collection_name}/points.jsonl.gz"
        }

    async def _create_archive(self, backup_path: Path) -> Path:
        """Create a compressed archive of the backup."""
        archive_path = backup_path.parent / f"{backup_path.name}.tar.gz"

        logger.info(f"Creating archive: {archive_path}")

        # Create tar.gz archive
        shutil.make_archive(
            str(backup_path),
            'gztar',
            root_dir=backup_path.parent,
            base_dir=backup_path.name
        )

        # Get archive size
        archive_size = archive_path.stat().st_size
        archive_size_mb = archive_size / (1024 * 1024)
        logger.info(f"Archive size: {archive_size_mb:.2f} MB")

        # Remove uncompressed backup directory
        shutil.rmtree(backup_path)

        return archive_path

    def cleanup_old_backups(self):
        """Remove old backup files based on retention policy."""
        logger.info(f"Cleaning up backups older than {self.config['retention_days']} days")

        cutoff_date = datetime.now() - timedelta(days=self.config['retention_days'])
        deleted_count = 0

        for backup_file in self.backup_dir.glob("qdrant_backup_*.tar.gz"):
            try:
                # backup_file.stem on a .tar.gz only strips the outer .gz, leaving
                # qdrant_backup_YYYYMMDD_HHMMSS.tar — and split('_')[-1] would yield
                # "HHMMSS.tar". Strip the full compound suffix and re-join the two
                # timestamp segments instead.
                bare = backup_file.name.removesuffix('.tar.gz')
                parts = bare.split('_')
                if len(parts) < 2:
                    raise ValueError(f"Unexpected backup filename layout: {backup_file.name}")
                timestamp_str = '_'.join(parts[-2:])  # "YYYYMMDD_HHMMSS"
                backup_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                if backup_date < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old backup: {backup_file}")

                    # Also delete metadata file if exists
                    metadata_file = backup_file.with_suffix('.json')
                    if metadata_file.exists():
                        metadata_file.unlink()

            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse timestamp from {backup_file}: {e}")

        logger.info(f"Deleted {deleted_count} old backup files")

    def upload_to_cloud(self, archive_path: Path):
        """Upload backup to cloud storage if configured."""
        if self.config.get('cloud_storage_enabled', False):
            provider = self.config.get('cloud_storage_provider', '').lower()

            if provider == 'aws':
                self._upload_to_s3(archive_path)
            elif provider == 'gcp':
                self._upload_to_gcs(archive_path)
            elif provider == 'azure':
                self._upload_to_azure(archive_path)
            else:
                logger.warning(f"Unknown cloud storage provider: {provider}")

    def _upload_to_s3(self, archive_path: Path):
        """Upload backup to AWS S3."""
        try:
            import boto3

            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.config.get('aws_access_key_id'),
                aws_secret_access_key=self.config.get('aws_secret_access_key')
            )

            bucket = self.config['aws_s3_bucket']
            key = f"vector-backups/{archive_path.name}"

            s3_client.upload_file(str(archive_path), bucket, key)
            logger.info(f"Uploaded backup to S3: s3://{bucket}/{key}")

        except ImportError:
            logger.warning("boto3 not installed, skipping S3 upload")
        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")

    def _upload_to_gcs(self, archive_path: Path):
        """Upload backup to Google Cloud Storage."""
        try:
            from google.cloud import storage

            client = storage.Client()
            bucket = client.bucket(self.config['gcs_bucket'])
            blob = bucket.blob(f"vector-backups/{archive_path.name}")

            blob.upload_from_filename(str(archive_path))
            logger.info(f"Uploaded backup to GCS: gs://{self.config['gcs_bucket']}/vector-backups/{archive_path.name}")

        except ImportError:
            logger.warning("google-cloud-storage not installed, skipping GCS upload")
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")

    def _upload_to_azure(self, archive_path: Path):
        """Upload backup to Azure Blob Storage."""
        try:
            from azure.storage.blob import BlobServiceClient

            blob_service = BlobServiceClient(
                account_url=f"https://{self.config['azure_storage_account']}.blob.core.windows.net",
                credential=self.config.get('azure_storage_key')
            )

            blob_client = blob_service.get_blob_client(
                container=self.config['azure_container'],
                blob=f"vector-backups/{archive_path.name}"
            )

            with open(archive_path, 'rb') as data:
                blob_client.upload_blob(data, overwrite=True)

            logger.info(f"Uploaded backup to Azure: {self.config['azure_container']}/vector-backups/{archive_path.name}")

        except ImportError:
            logger.warning("azure-storage-blob not installed, skipping Azure upload")
        except Exception as e:
            logger.error(f"Failed to upload to Azure: {e}")

    def send_notification(self, archive_path: Path, success: bool = True):
        """Send backup notification if configured."""
        if self.config.get('notification_enabled', False):
            notification_type = self.config.get('notification_type', '').lower()

            if notification_type == 'slack':
                self._send_slack_notification(archive_path, success)
            elif notification_type == 'email':
                self._send_email_notification(archive_path, success)

    def _send_slack_notification(self, archive_path: Path, success: bool):
        """Send Slack notification."""
        try:
            import requests

            webhook_url = self.config.get('slack_webhook_url')
            if not webhook_url:
                return

            status_emoji = "✅" if success else "❌"
            status_text = "completed successfully" if success else "failed"

            # Get file size
            size_mb = archive_path.stat().st_size / (1024 * 1024)

            message = f"{status_emoji} Vector store backup {status_text}\n" \
                     f"• File: {archive_path.name}\n" \
                     f"• Size: {size_mb:.2f} MB\n" \
                     f"• Timestamp: {datetime.now().isoformat()}"

            requests.post(webhook_url, json={"text": message})
            logger.info("Slack notification sent")

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")

    def _send_email_notification(self, archive_path: Path, success: bool):
        """Send email notification."""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            smtp_server = self.config.get('smtp_server')
            smtp_port = self.config.get('smtp_port', 587)
            smtp_user = self.config.get('smtp_user')
            smtp_password = self.config.get('smtp_password')
            recipient = self.config.get('notification_email')

            if not all([smtp_server, smtp_user, smtp_password, recipient]):
                return

            status_text = "completed successfully" if success else "failed"
            size_mb = archive_path.stat().st_size / (1024 * 1024)

            subject = f"Vector Store Backup {'Success' if success else 'Failed'} - Qdrant"
            body = f"""Vector store backup {status_text}.

            Backup File: {archive_path.name}
            Size: {size_mb:.2f} MB
            Timestamp: {datetime.now().isoformat()}
            Hostname: {os.uname().nodename}

            This is an automated message from the vector store backup system."""

            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            server.quit()

            logger.info("Email notification sent")

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")


def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    return {
        'backup_dir': os.getenv('BACKUP_DIR', DEFAULT_BACKUP_DIR),
        'retention_days': int(os.getenv('RETENTION_DAYS', DEFAULT_RETENTION_DAYS)),
        'host': os.getenv('QDRANT_HOST', DEFAULT_HOST),
        'port': int(os.getenv('QDRANT_PORT', DEFAULT_PORT)),
        'api_key': os.getenv('QDRANT_API_KEY'),
        'cloud_storage_enabled': os.getenv('CLOUD_STORAGE_ENABLED', '').lower() == 'true',
        'cloud_storage_provider': os.getenv('CLOUD_STORAGE_PROVIDER', ''),
        'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'aws_s3_bucket': os.getenv('AWS_S3_BUCKET'),
        'gcs_bucket': os.getenv('GCS_BUCKET'),
        'azure_storage_account': os.getenv('AZURE_STORAGE_ACCOUNT'),
        'azure_storage_key': os.getenv('AZURE_STORAGE_KEY'),
        'azure_container': os.getenv('AZURE_CONTAINER'),
        'notification_enabled': os.getenv('NOTIFICATION_ENABLED', '').lower() == 'true',
        'notification_type': os.getenv('NOTIFICATION_TYPE', ''),
        'slack_webhook_url': os.getenv('SLACK_WEBHOOK_URL'),
        'smtp_server': os.getenv('SMTP_SERVER'),
        'smtp_port': int(os.getenv('SMTP_PORT', '587')),
        'smtp_user': os.getenv('SMTP_USER'),
        'smtp_password': os.getenv('SMTP_PASSWORD'),
        'notification_email': os.getenv('NOTIFICATION_EMAIL'),
    }


async def main():
    """Main backup function."""
    parser = argparse.ArgumentParser(description='Backup Qdrant vector database')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without creating backup')
    parser.add_argument('--cleanup-only', action='store_true', help='Only cleanup old backups')
    args = parser.parse_args()

    config = load_config()
    backup_manager = VectorStoreBackup(config)

    try:
        if args.cleanup_only:
            backup_manager.cleanup_old_backups()
        elif args.dry_run:
            # Test connection and list collections
            collections = backup_manager.client.get_collections()
            logger.info(f"DRY RUN: Found {len(collections.collections)} collections")
            for collection in collections.collections:
                info = backup_manager.client.get_collection(collection.name)
                logger.info(f"  - {collection.name}: {info.points_count} points")
        else:
            # Perform backup
            archive_path = await backup_manager.create_backup()
            backup_manager.cleanup_old_backups()
            backup_manager.upload_to_cloud(Path(archive_path))
            backup_manager.send_notification(Path(archive_path), success=True)

    except Exception as e:
        logger.error(f"Backup process failed: {e}")
        backup_manager.send_notification(Path("failed_backup"), success=False)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())