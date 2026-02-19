import pytest
from src.core.security import verify_sensitive_data_hash
import hashlib

def test_verify_sensitive_data_hash():
    data = "secret_data"
    hashed = hashlib.sha256(data.encode()).hexdigest()

    # Should return True for correct hash
    assert verify_sensitive_data_hash(data, hashed) is True

    # Should return False for incorrect hash
    assert verify_sensitive_data_hash(data, "wrong_hash") is False

    # Should return False for incorrect data
    assert verify_sensitive_data_hash("wrong_data", hashed) is False
