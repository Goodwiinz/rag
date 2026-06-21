"""Regression tests: EncryptedType never returns ciphertext on decrypt failure.

Previously EncryptedType.process_result_value caught every exception and
returned the raw stored value — so a value that was stored as an encryption
envelope but could not be decrypted (no/changed key, corruption) was silently
served back to the caller as ciphertext (and EncryptedJSON handed back the
envelope metadata dict). These tests pin the corrected behavior:

* genuine decrypt failure of an envelope -> None (or raise under strict), never
  the raw ciphertext;
* plaintext / legacy rows still round-trip raw.
"""

import base64
import json
import os
from unittest.mock import patch

import pytest

from src.core.encryption import EncryptionError, is_encrypted_payload
from src.models import encrypted_fields as ef
from src.models.encrypted_fields import EncryptedString

# EncryptedJSON is wrapped by Mutable.as_mutable() at import, so the module
# attribute is an instance — grab the class to construct fresh field instances.
EncryptedJSONType = type(ef.EncryptedJSON)


@pytest.fixture
def encryption():
    """Initialize field encryption with a deterministic test key + DATA key."""
    from src.core.encryption import (
        EncryptionKeyType,
        get_key_manager,
        initialize_encryption,
    )

    test_key = base64.urlsafe_b64encode(b"test-encryption-key-32-bytes!!!!").decode()
    with patch.dict(os.environ, {"ENCRYPTION_MASTER_KEY": test_key}):
        initialize_encryption()
        km = get_key_manager()
        if not km.get_active_key(EncryptionKeyType.DATA):
            km.generate_key(EncryptionKeyType.DATA)
        yield


def _field(cls=EncryptedString, name="last_name"):
    t = cls()
    t._field_name = name
    return t


# --- is_encrypted_payload ----------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "value,expected",
    [
        ("LegacyBob", False),
        ("plain@example.com", False),
        ('{"foo": 1}', False),  # JSON, but not an envelope
        ('{"encrypted_data": "x", "nonce": "y"}', False),  # missing key_id
        ('{"encrypted_data": "x", "nonce": "y", "key_id": "z"}', True),
        ("not json {", False),
        (None, False),
        (123, False),
    ],
)
def test_is_encrypted_payload(value, expected):
    assert is_encrypted_payload(value) is expected


# --- decrypt-failure handling ------------------------------------------------


@pytest.mark.unit
def test_encrypted_value_roundtrips(encryption):
    f = _field()
    stored = f.process_bind_param("Smith", None)
    assert is_encrypted_payload(stored)  # stored as an envelope
    assert f.process_result_value(stored, None) == "Smith"


@pytest.mark.unit
def test_corrupt_envelope_returns_none_not_ciphertext(encryption):
    f = _field()
    stored = f.process_bind_param("Smith", None)
    payload = json.loads(stored)
    payload["encrypted_data"] = base64.b64encode(b"corrupted").decode()
    corrupt = json.dumps(payload)

    result = f.process_result_value(corrupt, None)

    assert result is None
    assert result != corrupt
    assert "encrypted_data" not in (result or "")


@pytest.mark.unit
def test_corrupt_envelope_raises_under_strict(encryption):
    f = _field()
    stored = f.process_bind_param("Smith", None)
    payload = json.loads(stored)
    payload["encrypted_data"] = base64.b64encode(b"corrupted").decode()
    corrupt = json.dumps(payload)

    with patch.dict(os.environ, {"ENCRYPTION_STRICT": "true"}):
        with pytest.raises(EncryptionError):
            f.process_result_value(corrupt, None)


@pytest.mark.unit
def test_plaintext_value_returns_raw_on_failure(encryption):
    """Legacy/plaintext rows (not envelopes) still read back raw."""
    f = _field()
    assert f.process_result_value("LegacyBob", None) == "LegacyBob"


@pytest.mark.unit
def test_encrypted_json_corrupt_does_not_leak_payload_dict(encryption):
    f = _field(EncryptedJSONType, name="preferences")
    stored = f.process_bind_param({"theme": "dark"}, None)
    payload = json.loads(stored)
    payload["encrypted_data"] = base64.b64encode(b"corrupted").decode()
    corrupt = json.dumps(payload)

    result = f.process_result_value(corrupt, None)

    assert result is None
    assert not isinstance(result, dict)
