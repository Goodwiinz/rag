"""
Database configuration and connection management
"""

import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import logging

# Import base model from models
from ..models.base import Base
from ..models.user import User, UserRole
from ..models.organization import Organization, StorageTier

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/multimodal_rag")
ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL", DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"))

# Create engine with appropriate settings
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=os.getenv("ENVIRONMENT") == "development"
)

# Create async engine for async operations
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=os.getenv("ENVIRONMENT") == "development"
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

def get_db() -> Session:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_session() -> AsyncSession:
    """Get async database session"""
    async with AsyncSessionLocal() as session:
        yield session

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

async def create_tables_async():
    """Create all database tables using async engine"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully (async)")

def drop_tables():
    """Drop all database tables (use with caution)"""
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")

def init_database():
    """Initialize database with seed data"""
    db = SessionLocal()
    try:
        # Check if already initialized
        if db.query(Organization).first():
            print("Database already initialized")
            return

        # Create default organization
        default_org = Organization(
            name="Default Organization",
            storage_tier=StorageTier.FREE,
            storage_limit_bytes=Organization.get_default_storage_limit(StorageTier.FREE),
            is_active=True
        )
        db.add(default_org)
        db.flush()
        print(f"Created default organization: {default_org.name}")

        # Create admin user
        admin_user = User(
            email="admin@multimodal-rag.com",
            first_name="System",
            last_name="Administrator",
            role=UserRole.ADMIN,
            organization_id=default_org.id,
            is_active=True
        )
        admin_user.set_password("REDACTED")  # Change this in production!
        db.add(admin_user)
        db.flush()
        print(f"Created admin user: {admin_user.email}")

        # Create demo user
        demo_user = User(
            email="demo@multimodal-rag.com",
            first_name="Demo",
            last_name="User",
            role=UserRole.USER,
            organization_id=default_org.id,
            is_active=True
        )
        demo_user.set_password("demo123")
        db.add(demo_user)
        db.flush()
        print(f"Created demo user: {demo_user.email}")

        # Create additional demo organization
        demo_org = Organization(
            name="Demo Research Lab",
            storage_tier=StorageTier.PROFESSIONAL,
            storage_limit_bytes=Organization.get_default_storage_limit(StorageTier.PROFESSIONAL),
            is_active=True
        )
        db.add(demo_org)
        db.flush()
        print(f"Created demo organization: {demo_org.name}")

        # Create demo organization admin
        lab_admin = User(
            email="lab-admin@multimodal-rag.com",
            first_name="Lab",
            last_name="Administrator",
            role=UserRole.CONTENT_MANAGER,  # Using available role instead of ORG_ADMIN
            organization_id=demo_org.id,
            is_active=True
        )
        lab_admin.set_password("lab123")
        db.add(lab_admin)
        db.flush()
        print(f"Created lab admin user: {lab_admin.email}")

        # Commit all changes
        db.commit()
        print("\n✅ Database initialized successfully!")
        print("\n📋 Default Users Created:")
        print("   Admin User:")
        print("   ├── Email: admin@multimodal-rag.com")
        print("   ├── Password: REDACTED")
        print("   └── Role: System Administrator")
        print()
        print("   Demo User:")
        print("   ├── Email: demo@multimodal-rag.com")
        print("   ├── Password: demo123")
        print("   └── Role: Regular User")
        print()
        print("   Lab Admin:")
        print("   ├── Email: lab-admin@multimodal-rag.com")
        print("   ├── Password: lab123")
        print("   └── Role: Organization Admin")
        print()
        print("⚠️  IMPORTANT: Change default passwords in production!")

    except SQLAlchemyError as e:
        db.rollback()
        print(f"❌ Error initializing database: {e}")
        raise
    finally:
        db.close()


def get_database_info():
    """Get information about database state"""
    db = SessionLocal()
    try:
        info = {}

        # Get table counts
        info['users_count'] = db.query(User).count()
        info['organizations_count'] = db.query(Organization).count()

        # Get database size (PostgreSQL specific)
        try:
            result = db.execute(text("SELECT pg_size_pretty(pg_database_size('multimodal_rag'))"))
            info['database_size'] = result.scalar()
        except (Exception,) as e:
            logger.debug(f"Could not get database size: {e}")
            info['database_size'] = 'Unknown'

        return info
    except Exception as e:
        print(f"Error getting database info: {e}")
        return {}
    finally:
        db.close()


# Database health check
def check_database_health() -> bool:
    """Check if database is healthy"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False