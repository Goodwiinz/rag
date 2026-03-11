import os
import base64
import pytest
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.models.user import User, UserRole
from src.models.base import Base
from src.models.organization import Organization, StorageTier
from src.core.encryption import decrypt_sensitive_field, initialize_encryption, get_key_manager, EncryptionKeyType

# Use SQLite in-memory database for testing
DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="module")
def engine():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture(scope="function")
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def test_user_encryption(db_session):
    # Initialize encryption explicitly with a valid base64 encoded 32-byte key
    master_key = base64.b64encode(b"0" * 32).decode("utf-8")
    os.environ["ENCRYPTION_MASTER_KEY"] = master_key
    initialize_encryption()

    # Generate a data encryption key so AESEncryption works
    key_manager = get_key_manager()
    key_manager.generate_key(key_type=EncryptionKeyType.DATA)

    # Create organization
    org = Organization(
        name=f"Test Org {uuid.uuid4()}",
        storage_tier=StorageTier.FREE,
        storage_limit_bytes=1000,
        is_active=True
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)

    # Create user with sensitive PII
    plain_first_name = "Alice"
    plain_last_name = "Smith"

    user = User(
        email=f"alice_{uuid.uuid4()}@example.com",
        first_name=plain_first_name,
        last_name=plain_last_name,
        role=UserRole.USER,
        organization_id=org.id,
        is_active=True
    )
    user.set_password("SecurePass123!")

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # 1. Verify ORM returns decrypted value (transparent decryption)
    assert user.first_name == plain_first_name
    assert user.last_name == plain_last_name

    # 2. Verify Database stores encrypted value
    # Execute raw SQL to fetch the stored value
    result = db_session.execute(
        text("SELECT first_name, last_name FROM users WHERE id = :id"),
        {"id": str(user.id)}
    ).fetchone()

    stored_first_name = result[0]
    stored_last_name = result[1]

    # Stored value should NOT be the plaintext
    assert stored_first_name != plain_first_name
    assert stored_last_name != plain_last_name

    # Stored value should be decryptable to the plaintext
    # We use 'first_name' and 'last_name' as the field keys based on the model definition
    decrypted_first = decrypt_sensitive_field(stored_first_name, "first_name")
    decrypted_last = decrypt_sensitive_field(stored_last_name, "last_name")

    assert decrypted_first == plain_first_name
    assert decrypted_last == plain_last_name

def test_legacy_plaintext_fallback(db_session):
    """
    Verify that existing plaintext data in the database is read correctly
    without crashing, simulating a scenario where migration hasn't happened yet.
    """
    # Create organization
    org = Organization(
        name=f"Legacy Org {uuid.uuid4()}",
        storage_tier=StorageTier.FREE,
        storage_limit_bytes=1000,
        is_active=True
    )
    db_session.add(org)
    db_session.commit()

    legacy_user_id = str(uuid.uuid4())
    legacy_email = f"legacy_{uuid.uuid4()}@example.com"
    legacy_first = "LegacyBob"
    legacy_last = "LegacyJones"

    # Manually insert plaintext data (simulating pre-existing data)
    # We use raw SQL to bypass the ORM encryption logic on insert
    # Note: SQLite DEFAULT CURRENT_TIMESTAMP is UTC
    # Added login_count=0 to satisfy NOT NULL constraint
    db_session.execute(
        text("""
            INSERT INTO users (id, email, password_hash, first_name, last_name, role, is_active, organization_id, created_at, updated_at, is_deleted, login_count)
            VALUES (:id, :email, 'hash', :first, :last, 'USER', 1, :org_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 0)
        """),
        {
            "id": legacy_user_id,
            "email": legacy_email,
            "first": legacy_first,
            "last": legacy_last,
            "org_id": str(org.id)
        }
    )
    db_session.commit()

    # Now try to read it back using the ORM
    user = db_session.query(User).filter(User.id == legacy_user_id).first()

    assert user is not None
    # The encryption type should fail to decrypt "LegacyBob" and return it as-is (due to our fallback fix)
    assert user.first_name == legacy_first
    assert user.last_name == legacy_last

if __name__ == "__main__":
    # Allow running directly
    import sys
    sys.exit(pytest.main([__file__]))
