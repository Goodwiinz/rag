"""
Database migration for encryption tables.

This migration creates tables for:
- Encrypted user profiles
- Encrypted organization profiles
- Encryption audit logs
"""

import logging
from datetime import datetime
from uuid import uuid4

from src.core.database import get_db
from src.models.encrypted_user import (
    EncryptedOrganizationProfile,
    EncryptedUserProfile,
    EncryptionAuditLog,
)

logger = logging.getLogger(__name__)


def migrate_encryption_tables():
    """
    Create encryption-related database tables and indexes.

    This migration:
    1. Creates encrypted user profile table
    2. Creates encrypted organization profile table
    3. Creates encryption audit log table
    4. Creates necessary indexes for performance
    5. Sets up foreign key relationships
    """
    logger.info("Starting encryption tables migration")

    try:
        db = next(get_db())

        # Create encrypted user profile table
        create_encrypted_user_profile_table(db)

        # Create encrypted organization profile table
        create_encrypted_organization_profile_table(db)

        # Create encryption audit log table
        create_encryption_audit_log_table(db)

        # Create performance indexes
        create_encryption_indexes(db)

        logger.info("Encryption tables migration completed successfully")
        return True

    except Exception as e:
        logger.error(f"Encryption tables migration failed: {str(e)}")
        raise e


def create_encrypted_user_profile_table(db):
    """Create encrypted user profile table"""
    logger.info("Creating encrypted_user_profiles table")

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS encrypted_user_profiles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

        -- Basic encrypted personal information
        first_name TEXT,
        last_name TEXT,
        middle_name TEXT,

        -- Contact information (encrypted)
        email_personal TEXT,
        phone_mobile TEXT,
        phone_work TEXT,
        address_home TEXT,
        address_work TEXT,

        -- Sensitive identifiers
        ssn TEXT,
        passport_number TEXT,
        driver_license TEXT,

        -- Emergency contact (encrypted)
        emergency_contact_name TEXT,
        emergency_contact_phone TEXT,
        emergency_contact_relationship TEXT,

        -- Additional encrypted personal data
        personal_notes TEXT,
        preferences TEXT,

        -- Employment information (encrypted)
        job_title TEXT,
        department TEXT,
        employee_id TEXT,

        -- Metadata
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE,
        last_encryption_rotation TIMESTAMP WITH TIME ZONE
    );
    """

    db.execute(create_table_sql)
    db.commit()
    logger.info("encrypted_user_profiles table created successfully")


def create_encrypted_organization_profile_table(db):
    """Create encrypted organization profile table"""
    logger.info("Creating encrypted_organization_profiles table")

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS encrypted_organization_profiles (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,

        -- Business information (encrypted)
        legal_business_name TEXT,
        dba_name TEXT,
        tax_id TEXT,
        duns_number TEXT,

        -- Contact information (encrypted)
        billing_address TEXT,
        shipping_address TEXT,
        billing_phone TEXT,
        billing_email TEXT,

        -- Financial information (encrypted)
        bank_account_number TEXT,
        bank_routing_number TEXT,
        payment_method TEXT,

        -- Legal information (encrypted)
        legal_contact_name TEXT,
        legal_contact_email TEXT,
        legal_contact_phone TEXT,

        -- Additional encrypted data
        business_notes TEXT,
        custom_attributes TEXT,

        -- Metadata
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE,
        last_encryption_rotation TIMESTAMP WITH TIME ZONE
    );
    """

    db.execute(create_table_sql)
    db.commit()
    logger.info("encrypted_organization_profiles table created successfully")


def create_encryption_audit_log_table(db):
    """Create encryption audit log table"""
    logger.info("Creating encryption_audit_logs table")

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS encryption_audit_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

        -- Operation details
        operation_type VARCHAR(50) NOT NULL,
        resource_type VARCHAR(50) NOT NULL,
        resource_id UUID NOT NULL,

        -- Key information
        key_id VARCHAR(64),
        key_version INTEGER,

        -- User and context
        performed_by UUID REFERENCES users(id),
        organization_id UUID REFERENCES organizations(id),

        -- Operation details (encrypted)
        operation_details TEXT,

        -- Metadata
        ip_address INET,
        user_agent TEXT,
        success BOOLEAN DEFAULT TRUE,
        error_message TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """

    db.execute(create_table_sql)
    db.commit()
    logger.info("encryption_audit_logs table created successfully")


def create_encryption_indexes(db):
    """Create performance indexes for encryption tables"""
    logger.info("Creating encryption table indexes")

    # Indexes for encrypted_user_profiles
    user_profile_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_encrypted_user_profiles_user_id ON encrypted_user_profiles(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_encrypted_user_profiles_created_at ON encrypted_user_profiles(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_encrypted_user_profiles_updated_at ON encrypted_user_profiles(updated_at);",
    ]

    # Indexes for encrypted_organization_profiles
    org_profile_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_encrypted_org_profiles_organization_id ON encrypted_organization_profiles(organization_id);",
        "CREATE INDEX IF NOT EXISTS idx_encrypted_org_profiles_created_at ON encrypted_organization_profiles(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_encrypted_org_profiles_updated_at ON encrypted_organization_profiles(updated_at);",
    ]

    # Indexes for encryption_audit_logs
    audit_log_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_encryption_audit_logs_operation_type ON encryption_audit_logs(operation_type);",
        "CREATE INDEX IF NOT EXISTS idx_encryption_audit_logs_resource_type ON encryption_audit_logs(resource_type);",
        "CREATE INDEX IF NOT EXISTS idx_encryption_audit_logs_resource_id ON encryption_audit_logs(resource_id);",
        "CREATE INDEX IF NOT EXISTS idx_encryption_audit_logs_performed_by ON encryption_audit_logs(performed_by);",
        "CREATE INDEX IF NOT EXISTS idx_encryption_audit_logs_organization_id ON encryption_audit_logs(organization_id);",
        "CREATE INDEX IF NOT EXISTS idx_encryption_audit_logs_created_at ON encryption_audit_logs(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_encryption_audit_logs_success ON encryption_audit_logs(success);",
        "CREATE INDEX IF NOT EXISTS idx_encryption_audit_logs_key_id ON encryption_audit_logs(key_id);",
        "CREATE INDEX IF NOT EXISTS idx_encryption_audit_logs_composite ON encryption_audit_logs(operation_type, resource_type, created_at);",
    ]

    all_indexes = user_profile_indexes + org_profile_indexes + audit_log_indexes

    for index_sql in all_indexes:
        try:
            db.execute(index_sql)
            logger.debug(f"Created index: {index_sql.split('idx_')[1].split(' ')[0]}")
        except Exception as e:
            logger.warning(f"Failed to create index: {str(e)}")

    db.commit()
    logger.info("Encryption table indexes created successfully")


def create_encryption_triggers(db):
    """Create database triggers for encryption tables"""
    logger.info("Creating encryption table triggers")

    # Update timestamp trigger for encrypted_user_profiles
    user_profile_trigger = """
    CREATE OR REPLACE FUNCTION update_encrypted_user_profile_timestamp()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ language 'plpgsql';

    DROP TRIGGER IF EXISTS trigger_update_encrypted_user_profile_timestamp ON encrypted_user_profiles;
    CREATE TRIGGER trigger_update_encrypted_user_profile_timestamp
        BEFORE UPDATE ON encrypted_user_profiles
        FOR EACH ROW
        EXECUTE FUNCTION update_encrypted_user_profile_timestamp();
    """

    # Update timestamp trigger for encrypted_organization_profiles
    org_profile_trigger = """
    CREATE OR REPLACE FUNCTION update_encrypted_org_profile_timestamp()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ language 'plpgsql';

    DROP TRIGGER IF EXISTS trigger_update_encrypted_org_profile_timestamp ON encrypted_organization_profiles;
    CREATE TRIGGER trigger_update_encrypted_org_profile_timestamp
        BEFORE UPDATE ON encrypted_organization_profiles
        FOR EACH ROW
        EXECUTE FUNCTION update_encrypted_org_profile_timestamp();
    """

    triggers = [user_profile_trigger, org_profile_trigger]

    for trigger_sql in triggers:
        try:
            db.execute(trigger_sql)
            logger.debug("Created encryption trigger")
        except Exception as e:
            logger.warning(f"Failed to create trigger: {str(e)}")

    db.commit()
    logger.info("Encryption table triggers created successfully")


def create_encryption_row_level_security(db):
    """Create row-level security policies for encryption tables"""
    logger.info("Creating row-level security for encryption tables")

    # Enable RLS on encryption tables
    rls_statements = [
        "ALTER TABLE encrypted_user_profiles ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE encrypted_organization_profiles ENABLE ROW LEVEL SECURITY;",
        "ALTER TABLE encryption_audit_logs ENABLE ROW LEVEL SECURITY;",
    ]

    # Create RLS policies
    user_profile_rls = """
    CREATE POLICY encrypted_user_profiles_organization_policy ON encrypted_user_profiles
        FOR ALL TO authenticated_user
        USING (
            user_id IN (
                SELECT id FROM users WHERE organization_id = current_setting('app.current_organization_id')::UUID
            )
        );
    """

    org_profile_rls = """
    CREATE POLICY encrypted_organization_profiles_organization_policy ON encrypted_organization_profiles
        FOR ALL TO authenticated_user
        USING (
            organization_id = current_setting('app.current_organization_id')::UUID
        );
    """

    audit_log_rls = """
    CREATE POLICY encryption_audit_logs_organization_policy ON encryption_audit_logs
        FOR SELECT TO authenticated_user
        USING (
            organization_id = current_setting('app.current_organization_id')::UUID
            OR performed_by = current_setting('app.current_user_id')::UUID
        );
    """

    all_policies = rls_statements + [user_profile_rls, org_profile_rls, audit_log_rls]

    for policy_sql in all_policies:
        try:
            db.execute(policy_sql)
            logger.debug("Created encryption RLS policy")
        except Exception as e:
            logger.warning(f"Failed to create RLS policy: {str(e)}")

    db.commit()
    logger.info("Encryption row-level security created successfully")


def add_encryption_constraints(db):
    """Add data integrity constraints for encryption tables"""
    logger.info("Adding encryption table constraints")

    # Check constraints for encrypted_user_profiles
    user_profile_constraints = [
        """
        ALTER TABLE encrypted_user_profiles
        ADD CONSTRAINT chk_encrypted_user_profiles_ssn_length
        CHECK (ssn IS NULL OR length(ssn) >= 9);
        """,
        """
        ALTER TABLE encrypted_user_profiles
        ADD CONSTRAINT chk_encrypted_user_profiles_phone_format
        CHECK (phone_mobile IS NULL OR length(phone_mobile) >= 10);
        """,
    ]

    # Check constraints for encrypted_organization_profiles
    org_profile_constraints = [
        """
        ALTER TABLE encrypted_organization_profiles
        ADD CONSTRAINT chk_encrypted_org_profiles_tax_id_length
        CHECK (tax_id IS NULL OR length(tax_id) >= 9);
        """,
    ]

    # Check constraints for encryption_audit_logs
    audit_log_constraints = [
        """
        ALTER TABLE encryption_audit_logs
        ADD CONSTRAINT chk_encryption_audit_logs_operation_type
        CHECK (operation_type IN ('ENCRYPT', 'DECRYPT', 'ROTATE_KEY', 'ENCRYPT_PROFILE', 'DECRYPT_PROFILE', 'VALIDATE'));
        """,
        """
        ALTER TABLE encryption_audit_logs
        ADD CONSTRAINT chk_encryption_audit_logs_resource_type
        CHECK (resource_type IN ('USER_PROFILE', 'ORG_PROFILE', 'ENCRYPTION_KEY', 'DOCUMENT'));
        """,
    ]

    all_constraints = (
        user_profile_constraints + org_profile_constraints + audit_log_constraints
    )

    for constraint_sql in all_constraints:
        try:
            db.execute(constraint_sql)
            logger.debug("Created encryption constraint")
        except Exception as e:
            logger.warning(f"Failed to create constraint: {str(e)}")

    db.commit()
    logger.info("Encryption table constraints added successfully")


def create_encryption_views(db):
    """Create helpful views for encryption data"""
    logger.info("Creating encryption views")

    # View for user encryption status
    user_encryption_view = """
    CREATE OR REPLACE VIEW user_encryption_status AS
    SELECT
        u.id as user_id,
        u.email,
        o.name as organization_name,
        CASE WHEN eup.id IS NOT NULL THEN TRUE ELSE FALSE END as has_encrypted_profile,
        eup.created_at as profile_encrypted_at,
        eup.updated_at as profile_last_updated,
        eup.last_encryption_rotation
    FROM users u
    LEFT JOIN organizations o ON u.organization_id = o.id
    LEFT JOIN encrypted_user_profiles eup ON u.id = eup.user_id;
    """

    # View for organization encryption status
    org_encryption_view = """
    CREATE OR REPLACE VIEW organization_encryption_status AS
    SELECT
        o.id as organization_id,
        o.name as organization_name,
        CASE WHEN eop.id IS NOT NULL THEN TRUE ELSE FALSE END as has_encrypted_profile,
        eop.created_at as profile_encrypted_at,
        eop.updated_at as profile_last_updated,
        eop.last_encryption_rotation,
        COUNT(eup.id) as encrypted_user_profiles
    FROM organizations o
    LEFT JOIN encrypted_organization_profiles eop ON o.id = eop.organization_id
    LEFT JOIN users u ON o.id = u.organization_id
    LEFT JOIN encrypted_user_profiles eup ON u.id = eup.user_id
    GROUP BY o.id, o.name, eop.id, eop.created_at, eop.updated_at, eop.last_encryption_rotation;
    """

    # View for encryption audit summary
    audit_summary_view = """
    CREATE OR REPLACE VIEW encryption_audit_summary AS
    SELECT
        operation_type,
        resource_type,
        COUNT(*) as operation_count,
        COUNT(*) FILTER (WHERE success = TRUE) as success_count,
        COUNT(*) FILTER (WHERE success = FALSE) as failure_count,
        MAX(created_at) as last_operation,
        MIN(created_at) as first_operation
    FROM encryption_audit_logs
    GROUP BY operation_type, resource_type
    ORDER BY operation_count DESC;
    """

    views = [user_encryption_view, org_encryption_view, audit_summary_view]

    for view_sql in views:
        try:
            db.execute(view_sql)
            logger.debug("Created encryption view")
        except Exception as e:
            logger.warning(f"Failed to create view: {str(e)}")

    db.commit()
    logger.info("Encryption views created successfully")


def run_full_migration():
    """Run the complete encryption tables migration"""
    logger.info("Starting full encryption tables migration")

    try:
        # Core tables
        migrate_encryption_tables()

        # Get database session for additional operations
        db = next(get_db())

        # Additional features
        create_encryption_triggers(db)
        create_encryption_row_level_security(db)
        add_encryption_constraints(db)
        create_encryption_views(db)

        logger.info("Full encryption tables migration completed successfully")
        return True

    except Exception as e:
        logger.error(f"Full encryption tables migration failed: {str(e)}")
        raise e


if __name__ == "__main__":
    # Run migration when executed directly
    logging.basicConfig(level=logging.INFO)
    run_full_migration()
    print("Encryption tables migration completed!")
