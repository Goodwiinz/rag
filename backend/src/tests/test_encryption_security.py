import pytest
import secrets
from src.core.encryption import HashUtils
from src.core.security import verify_sensitive_data_hash

def test_verify_sensitive_data_hash_success():
    data = "my-secret-data"
    import hashlib
    hashed = hashlib.sha256(data.encode()).hexdigest()
    assert verify_sensitive_data_hash(data, hashed) is True

def test_verify_sensitive_data_hash_failure():
    data = "my-secret-data"
    import hashlib
    hashed = hashlib.sha256(b"wrong").hexdigest()
    assert verify_sensitive_data_hash(data, hashed) is False

def test_verify_password_success():
    password = "password123"
    salt = b"somesalt"
    hashed_password, _ = HashUtils.hash_password(password, salt)
    assert HashUtils.verify_password(password, hashed_password, salt) is True

def test_verify_password_failure():
    password = "password123"
    salt = b"somesalt"
    hashed_password, _ = HashUtils.hash_password("wrong", salt)
    assert HashUtils.verify_password(password, hashed_password, salt) is False
