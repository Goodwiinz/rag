import hashlib
import pytest
from src.core.security import verify_sensitive_data_hash
from src.core.encryption import HashUtils


class TestVerifySensitiveDataHash:
    def test_valid_hash_returns_true(self):
        data = "my-secret-data"
        hashed = hashlib.sha256(data.encode()).hexdigest()
        assert verify_sensitive_data_hash(data, hashed) is True

    def test_invalid_hash_returns_false(self):
        data = "my-secret-data"
        assert verify_sensitive_data_hash(data, "wrong_hash") is False

    def test_wrong_data_returns_false(self):
        hashed = hashlib.sha256(b"original").hexdigest()
        assert verify_sensitive_data_hash("tampered", hashed) is False


class TestHashUtilsVerifyPassword:
    def test_correct_password_returns_true(self):
        password = "password123"
        hashed, salt = HashUtils.hash_password(password)
        assert HashUtils.verify_password(password, hashed, salt) is True

    def test_wrong_password_returns_false(self):
        password = "password123"
        hashed, salt = HashUtils.hash_password(password)
        assert HashUtils.verify_password("wrong", hashed, salt) is False

    def test_wrong_salt_returns_false(self):
        password = "password123"
        hashed, salt = HashUtils.hash_password(password)
        assert HashUtils.verify_password(password, hashed, b"wrong_salt") is False
