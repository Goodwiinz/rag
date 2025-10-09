"""
Database initialization and setup utilities
"""

import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from src.core.config import settings
from src.core.database import Base, get_db
from src.models import *
from src.models.organization import Organization, StorageTier
from src.models.user import User, UserRole
import logging

logger = logging.getLogger(__name__)

def create_database():
    """Create all database tables"""
    try:
        engine = create_engine(settings.DATABASE_URL)

        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        return True
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        return False

def create_default_organization():
    """Create default organization if it doesn't exist"""
    from sqlalchemy.orm import SessionLocal

    db = SessionLocal()
    try:
        # Check if default organization exists
        default_org = db.query(Organization).filter(Organization.name == "Default Organization").first()

        if not default_org:
            default_org = Organization(
                name="Default Organization",
                storage_tier=StorageTier.FREE,
                storage_limit_bytes=Organization.get_default_storage_limit(StorageTier.FREE),
                is_active=True
            )
            db.add(default_org)
            db.commit()
            db.refresh(default_org)
            logger.info(f"Created default organization: {default_org.name}")
        else:
            logger.info(f"Default organization already exists: {default_org.name}")

        return default_org
    except Exception as e:
        logger.error(f"Failed to create default organization: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def create_admin_user(organization_id):
    """Create admin user if it doesn't exist"""
    from sqlalchemy.orm import SessionLocal

    db = SessionLocal()
    try:
        # Check if admin user exists
        admin_user = db.query(User).filter(User.email == "admin@example.com").first()

        if not admin_user:
            admin_user = User(
                email="admin@example.com",
                first_name="System",
                last_name="Administrator",
                role=UserRole.ADMIN,
                organization_id=organization_id,
                is_active=True
            )
            admin_user.set_password("admin123")  # Change this in production!
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            logger.info(f"Created admin user: {admin_user.email}")
        else:
            logger.info(f"Admin user already exists: {admin_user.email}")

        return admin_user
    except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def initialize_database():
    """Initialize the database with default data"""
    logger.info("Starting database initialization...")

    # Create tables
    if not create_database():
        return False

    # Create default organization
    default_org = create_default_organization()
    if not default_org:
        return False

    # Create admin user
    admin_user = create_admin_user(default_org.id)
    if not admin_user:
        return False

    logger.info("Database initialization completed successfully!")
    return True

def reset_database():
    """Reset database by dropping and recreating all tables"""
    logger.warning("Resetting database - all data will be lost!")

    try:
        engine = create_engine(settings.DATABASE_URL)

        # Drop all tables
        Base.metadata.drop_all(bind=engine)
        logger.info("All database tables dropped")

        # Recreate tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables recreated")

        # Initialize with default data
        return initialize_database()

    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        return False

def check_database_health():
    """Check database connection and health"""
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            logger.info("Database health check: OK")
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database management utility")
    parser.add_argument("action", choices=["init", "reset", "health"],
                       help="Action to perform")

    args = parser.parse_args()

    if args.action == "init":
        success = initialize_database()
        sys.exit(0 if success else 1)
    elif args.action == "reset":
        success = reset_database()
        sys.exit(0 if success else 1)
    elif args.action == "health":
        success = check_database_health()
        sys.exit(0 if success else 1)