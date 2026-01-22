"""
Comprehensive tests for encryption service and data protection.

This test suite covers:
- Core encryption functionality
- Field-level encryption
- File encryption
- Key management and rotation
- Encryption service operations
- Integration with database models
"""

import pytest
import json
import base64
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from src.core.encryption import (
    KeyManager,
    AESEncryption,
    FieldEncryption,
    FileEncryption,
    SecureRandomGenerator,
    KeyDerivation,
    HashUtils,
    EncryptionKeyType,
    EncryptionAlgorithm,
    EncryptionError,
    KeyManagementError,
    DataEncryptionError,
    initialize_encryption,
    get_key_manager,
    get_aes_encryption,
    get_field_encryption,
    get_file_encryption
)
from src.models.encrypted_fields import (
    EncryptedString,
    EncryptedText,
    EncryptedEmail,
    EncryptedPhone,
    EncryptedSSN,
    EncryptedCreditCard,
    EncryptedAddress,
    EncryptedJSON
)
from src.models.encrypted_user import (
    EncryptedUserProfile,
    EncryptedOrganizationProfile,
    EncryptionAuditLog
)
from src.services.security import EncryptionService


class TestSecureRandomGenerator:
    """Test secure random number generation"""

    def test_generate_bytes(self):
        """Test secure bytes generation"""
        length = 32
        random_bytes = SecureRandomGenerator.generate_bytes(length)

        assert len(random_bytes) == length
        assert isinstance(random_bytes, bytes)

        # Test that multiple calls generate different values
        random_bytes2 = SecureRandomGenerator.generate_bytes(length)
        assert random_bytes != random_bytes2

    def test_generate_hex(self):
        """Test secure hex string generation"""
        length = 16
        random_hex = SecureRandomGenerator.generate_hex(length)

        assert len(random_hex) == length * 2  # Hex is 2x bytes
        assert all(c in '0123456789abcdef' for c in random_hex)

    def test_generate_url_safe_token(self):
        """Test URL-safe token generation"""
        token = SecureRandomGenerator.generate_url_safe_token(32)

        assert len(token) >= 32
        # URL-safe tokens should only contain safe characters
        assert all(c.isalnum() or c in '-_' for c in token)

    def test_generate_uuid(self):
        """Test UUID generation"""
        uuid_str = SecureRandomGenerator.generate_uuid()

        assert len(uuid_str) == 32  # UUID4 hex string
        assert all(c in '0123456789abcdef' for c in uuid_str)


class TestKeyDerivation:
    """Test key derivation functions"""

    def test_derive_key_from_password(self):
        """Test PBKDF2 key derivation from password"""
        password = "test_password_123"
        key, salt = KeyDerivation.derive_key_from_password(password)

        assert len(key) == 32  # Default key length
        assert len(salt) == 16  # Default salt length
        assert isinstance(key, bytes)
        assert isinstance(salt, bytes)

        # Test with provided salt
        key2, salt2 = KeyDerivation.derive_key_from_password(password, salt)
        assert key == key2
        assert salt2 == salt

    def test_derive_key_hkdf(self):
        """Test HKDF key derivation"""
        input_material = b"input_key_material"
        salt = b"salt_value"
        info = b"context_info"

        derived_key = KeyDerivation.derive_key_hkdf(input_material, salt, info)

        assert len(derived_key) == 32  # Default key length
        assert isinstance(derived_key, bytes)

        # Test with different parameters
        derived_key2 = KeyDerivation.derive_key_hkdf(input_material, b"different_salt", info)
        assert derived_key != derived_key2


class TestHashUtils:
    """Test hashing utilities"""

    def test_hash_password(self):
        """Test password hashing"""
        password = "secure_password_123"
        hashed_password, salt = HashUtils.hash_password(password)

        assert isinstance(hashed_password, str)
        assert isinstance(salt, bytes)
        assert len(salt) == 32

    def test_verify_password(self):
        """Test password verification"""
        password = "secure_password_123"
        hashed_password, salt = HashUtils.hash_password(password)

        # Correct password should verify
        assert HashUtils.verify_password(password, hashed_password, salt) is True

        # Wrong password should not verify
        assert HashUtils.verify_password("wrong_password", hashed_password, salt) is False

    def test_hash_data(self):
        """Test data hashing"""
        data = "test data to hash"
        hash_result = HashUtils.hash_data(data)

        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 hex length

        # Same data should produce same hash
        hash_result2 = HashUtils.hash_data(data)
        assert hash_result == hash_result2

    def test_hmac_sign_and_verify(self):
        """Test HMAC signing and verification"""
        data = "data to sign"
        key = b"secret_key"

        signature = HashUtils.hmac_sign(data, key)

        assert isinstance(signature, str)
        assert len(signature) == 64  # SHA256 HMAC hex length

        # Verify with correct key
        assert HashUtils.hmac_verify(data, signature, key) is True

        # Verify with wrong key
        assert HashUtils.hmac_verify(data, signature, b"wrong_key") is False


class TestKeyManager:
    """Test encryption key management"""

    @pytest.fixture
    def key_manager(self):
        """Create key manager with mocked master key"""
        with patch.dict('os.environ', {'ENCRYPTION_MASTER_KEY': base64.b64encode(b'32_byte_master_key_for_testing!').decode()}):
            return KeyManager()

    def test_initialization(self, key_manager):
        """Test key manager initialization"""
        assert key_manager._master_key is not None
        assert len(key_manager._master_key) == 32

    def test_generate_key(self, key_manager):
        """Test key generation"""
        key = key_manager.generate_key(
            key_type=EncryptionKeyType.DATA,
            algorithm=EncryptionAlgorithm.AES256_GCM
        )

        assert key.key_type == EncryptionKeyType.DATA
        assert key.algorithm == EncryptionAlgorithm.AES256_GCM
        assert key.key_id is not None
        assert key.key_data is not None
        assert key.is_active is True
        assert key.created_at is not None

    def test_get_key(self, key_manager):
        """Test key retrieval"""
        generated_key = key_manager.generate_key(EncryptionKeyType.DATA)

        retrieved_key = key_manager.get_key(generated_key.key_id)
        assert retrieved_key is not None
        assert retrieved_key.key_id == generated_key.key_id

        # Test non-existent key
        assert key_manager.get_key("non_existent_key") is None

    def test_get_active_key(self, key_manager):
        """Test active key retrieval"""
        # Generate multiple keys
        key1 = key_manager.generate_key(EncryptionKeyType.DATA)
        key2 = key_manager.generate_key(EncryptionKeyType.DATA)

        # Deactivate first key
        key1.is_active = False

        # Should return the active key
        active_key = key_manager.get_active_key(EncryptionKeyType.DATA)
        assert active_key.key_id == key2.key_id

    def test_rotate_key(self, key_manager):
        """Test key rotation"""
        original_key = key_manager.generate_key(EncryptionKeyType.DATA)

        # Rotate the key
        new_key = key_manager.rotate_key(original_key.key_id)

        assert new_key.key_type == original_key.key_type
        assert new_key.algorithm == original_key.algorithm
        assert new_key.key_id != original_key.key_id
        assert original_key.is_active is False
        assert new_key.is_active is True

    def test_encrypt_decrypt_key_data(self, key_manager):
        """Test key data encryption and decryption"""
        key_data = b"sensitive_key_data_to_encrypt"

        encrypted_data = key_manager.encrypt_key_data(key_data)
        assert encrypted_data != key_data
        assert len(encrypted_data) > len(key_data)  # Should include nonce

        decrypted_data = key_manager.decrypt_key_data(encrypted_data)
        assert decrypted_data == key_data


class TestAESEncryption:
    """Test AES encryption functionality"""

    @pytest.fixture
    def aes_encryption(self):
        """Create AES encryption instance with mocked key manager"""
        mock_key_manager = Mock()
        mock_key = Mock()
        mock_key.key_id = "test_key_id"
        mock_key.key_data = b'32_byte_encryption_key_for_tests!!'
        mock_key.algorithm = EncryptionAlgorithm.AES256_GCM
        mock_key_manager.get_key.return_value = mock_key
        mock_key_manager.get_active_key.return_value = mock_key

        return AESEncryption(mock_key_manager)

    def test_encrypt_decrypt_string(self, aes_encryption):
        """Test string encryption and decryption"""
        data = "Sensitive data to encrypt"
        key_id = "test_key_id"

        encrypted_payload = aes_encryption.encrypt(data, key_id)
        assert encrypted_payload["encrypted_data"] is not None
        assert encrypted_payload["nonce"] is not None
        assert encrypted_payload["key_id"] == key_id

        decrypted_data = aes_encryption.decrypt(encrypted_payload)
        assert decrypted_data.decode('utf-8') == data

    def test_encrypt_decrypt_bytes(self, aes_encryption):
        """Test bytes encryption and decryption"""
        data = b"Binary data to encrypt"
        key_id = "test_key_id"

        encrypted_payload = aes_encryption.encrypt(data, key_id)
        decrypted_data = aes_encryption.decrypt(encrypted_payload)
        assert decrypted_data == data

    def test_encrypt_with_associated_data(self, aes_encryption):
        """Test encryption with associated data"""
        data = "Sensitive data"
        associated_data = b"additional authenticated data"
        key_id = "test_key_id"

        encrypted_payload = aes_encryption.encrypt(data, key_id, associated_data)
        decrypted_data = aes_encryption.decrypt(encrypted_payload)

        assert decrypted_data.decode('utf-8') == data

    def test_encrypt_without_key_id(self, aes_encryption):
        """Test encryption without specifying key ID"""
        data = "Test data"

        encrypted_payload = aes_encryption.encrypt(data)
        assert encrypted_payload["key_id"] is not None

        decrypted_data = aes_encryption.decrypt(encrypted_payload)
        assert decrypted_data.decode('utf-8') == data


class TestFieldEncryption:
    """Test field-level encryption"""

    @pytest.fixture
    def field_encryption(self):
        """Create field encryption instance"""
        mock_aes_encryption = Mock()
        mock_aes_encryption.encrypt.return_value = {
            "encrypted_data": base64.b64encode(b"encrypted_data").decode(),
            "nonce": base64.b64encode(b"nonce123456789").decode(),
            "key_id": "test_key_id"
        }
        mock_aes_encryption.decrypt.return_value = b"decrypted_value"

        return FieldEncryption(mock_aes_encryption)

    def test_encrypt_field_string(self, field_encryption):
        """Test string field encryption"""
        value = "sensitive_value"
        field_name = "test_field"

        encrypted_value = field_encryption.encrypt_field(value, field_name)
        assert encrypted_value is not None
        assert isinstance(encrypted_value, str)

    def test_encrypt_field_none(self, field_encryption):
        """Test None value encryption"""
        encrypted_value = field_encryption.encrypt_field(None, "test_field")
        assert encrypted_value is None

    def test_encrypt_field_number(self, field_encryption):
        """Test number field encryption"""
        value = 12345
        field_name = "test_field"

        encrypted_value = field_encryption.encrypt_field(value, field_name)
        assert encrypted_value is not None

    def test_decrypt_field(self, field_encryption):
        """Test field decryption"""
        encrypted_payload = {
            "encrypted_data": base64.b64encode(b"encrypted_data").decode(),
            "nonce": base64.b64encode(b"nonce123456789").decode(),
            "key_id": "test_key_id"
        }

        encrypted_value = json.dumps(encrypted_payload)
        decrypted_value = field_encryption.decrypt_field(encrypted_value, "test_field")

        assert decrypted_value == "decrypted_value"

    def test_decrypt_field_none(self, field_encryption):
        """Test None value decryption"""
        decrypted_value = field_encryption.decrypt_field(None, "test_field")
        assert decrypted_value is None


class TestFileEncryption:
    """Test file encryption functionality"""

    @pytest.fixture
    def file_encryption(self):
        """Create file encryption instance"""
        mock_key_manager = Mock()
        mock_key = Mock()
        mock_key.key_id = "test_file_key"
        mock_key_manager.get_key.return_value = mock_key
        mock_key_manager.get_active_key.return_value = mock_key

        mock_aes_encryption = Mock()
        mock_aes_encryption.encrypt.return_value = {
            "encrypted_data": base64.b64encode(b"encrypted_file_data").decode(),
            "nonce": base64.b64encode(b"nonce123456789").decode(),
            "key_id": "test_file_key"
        }
        mock_aes_encryption.decrypt.return_value = b"original_file_data"

        return FileEncryption(mock_key_manager)

    def test_encrypt_file(self, file_encryption):
        """Test file encryption"""
        file_data = b"This is file content to encrypt"
        filename = "test_document.pdf"

        encrypted_payload = file_encryption.encrypt_file(file_data, filename)

        assert encrypted_payload["encrypted_data"] is not None
        assert encrypted_payload["original_filename"] == filename
        assert encrypted_payload["file_size_bytes"] == len(file_data)
        assert encrypted_payload["encryption_timestamp"] is not None

    def test_decrypt_file(self, file_encryption):
        """Test file decryption"""
        encrypted_payload = {
            "encrypted_data": base64.b64encode(b"encrypted_file_data").decode(),
            "nonce": base64.b64encode(b"nonce123456789").decode(),
            "key_id": "test_file_key"
        }

        decrypted_data = file_encryption.decrypt_file(encrypted_payload)
        assert decrypted_data == b"original_file_data"


class TestEncryptedFieldTypes:
    """Test encrypted SQLAlchemy field types"""

    def test_encrypted_string_process(self):
        """Test EncryptedString field processing"""
        field = EncryptedString()
        field._field_name = "test_field"

        # Test bind (encrypt) - requires actual encryption for this test
        with patch('src.models.encrypted_fields.encrypt_sensitive_field') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_value"

            result = field.process_bind_param("test_value", None)
            assert result == "encrypted_value"
            mock_encrypt.assert_called_once_with("test_value", "test_field")

    def test_encrypted_string_result(self):
        """Test EncryptedString result processing"""
        field = EncryptedString()
        field._field_name = "test_field"

        # Test result (decrypt)
        with patch('src.models.encrypted_fields.decrypt_sensitive_field') as mock_decrypt:
            mock_decrypt.return_value = "decrypted_value"

            result = field.process_result_value("encrypted_value", None)
            assert result == "decrypted_value"
            mock_decrypt.assert_called_once_with("encrypted_value", "test_field")

    def test_encrypted_email_validation(self):
        """Test EncryptedEmail field validation"""
        field = EncryptedEmail()
        field._field_name = "email_field"

        # Valid email should work
        with patch('src.models.encrypted_fields.encrypt_sensitive_field') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_email"
            result = field.process_bind_param("test@example.com", None)
            assert result == "encrypted_email"

        # Invalid email should raise exception
        with pytest.raises(ValueError):
            field.process_bind_param("invalid_email", None)

    def test_encrypted_phone_validation(self):
        """Test EncryptedPhone field validation"""
        field = EncryptedPhone()
        field._field_name = "phone_field"

        # Valid phone should work
        with patch('src.models.encrypted_fields.encrypt_sensitive_field') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_phone"
            result = field.process_bind_param("123-456-7890", None)
            assert result == "encrypted_phone"

        # Invalid phone should raise exception
        with pytest.raises(ValueError):
            field.process_bind_param("123", None)

    def test_encrypted_ssn_validation(self):
        """Test EncryptedSSN field validation"""
        field = EncryptedSSN()
        field._field_name = "ssn_field"

        # Valid SSN should work
        with patch('src.models.encrypted_fields.encrypt_sensitive_field') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_ssn"
            result = field.process_bind_param("123-45-6789", None)
            assert result == "encrypted_ssn"

        # Invalid SSN should raise exception
        with pytest.raises(ValueError):
            field.process_bind_param("123", None)

    def test_encrypted_credit_card_validation(self):
        """Test EncryptedCreditCard field validation"""
        field = EncryptedCreditCard()
        field._field_name = "card_field"

        # Valid credit card should work
        with patch('src.models.encrypted_fields.encrypt_sensitive_field') as mock_encrypt:
            mock_encrypt.return_value = "encrypted_card"
            # Using a test Visa number that passes Luhn check
            result = field.process_bind_param("4111111111111111", None)
            assert result == "encrypted_card"

        # Invalid credit card should raise exception
        with pytest.raises(ValueError):
            field.process_bind_param("123456789012", None)


class TestEncryptionService:
    """Test encryption service operations"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session"""
        return Mock()

    @pytest.fixture
    def encryption_service(self, mock_db):
        """Create encryption service with mocked dependencies"""
        with patch('src.services.encryption_service.get_key_manager') as mock_km, \
             patch('src.services.encryption_service.get_aes_encryption') as mock_aes, \
             patch('src.services.encryption_service.get_field_encryption') as mock_field, \
             patch('src.services.encryption_service.get_file_encryption') as mock_file:

            return EncryptionService(mock_db)

    def test_encrypt_user_profile(self, encryption_service, mock_db):
        """Test user profile encryption"""
        user_id = uuid4()
        profile_data = {
            "first_name": "John",
            "last_name": "Doe",
            "email_personal": "john@example.com"
        }
        performed_by = uuid4()

        # Mock the database operations
        mock_profile = Mock()
        mock_profile.user_id = user_id
        mock_db.query.return_value.filter.return_value.first.return_value = mock_profile
        mock_db.commit.return_value = None

        with patch.object(encryption_service, 'log_encryption_operation') as mock_log:
            result = encryption_service.encrypt_user_profile(
                user_id=user_id,
                profile_data=profile_data,
                performed_by=performed_by
            )

            assert result is not None
            mock_log.assert_called_once()

    def test_decrypt_user_profile(self, encryption_service, mock_db):
        """Test user profile decryption"""
        user_id = uuid4()
        requested_by = uuid4()

        # Mock encrypted profile
        mock_profile = Mock()
        mock_profile.get_decrypted_data.return_value = {
            "first_name": "John",
            "last_name": "Doe"
        }
        mock_db.query.return_value.filter.return_value.first.return_value = mock_profile

        with patch.object(encryption_service, 'log_encryption_operation') as mock_log:
            result = encryption_service.decrypt_user_profile(
                user_id=user_id,
                requested_by=requested_by
            )

            assert result["first_name"] == "John"
            assert result["last_name"] == "Doe"
            mock_log.assert_called_once()

    def test_get_encryption_status(self, encryption_service, mock_db):
        """Test encryption status retrieval"""
        # Mock key manager
        mock_key = Mock()
        mock_key.key_id = "test_key_id"
        mock_key.algorithm = "aes256_gcm"
        mock_key.created_at = datetime.utcnow()
        mock_key.expires_at = None
        mock_key.is_expired.return_value = False

        encryption_service.key_manager.get_active_key.side_effect = lambda key_type: mock_key

        # Mock database queries
        mock_db.query.return_value.count.return_value = 5
        mock_db.query.return_value.order_by.return_value.limit.return_value.all.return_value = []

        status = encryption_service.get_encryption_status()

        assert "key_management" in status
        assert "encrypted_resources" in status
        assert "recent_operations" in status

    def test_validate_encryption_integrity(self, encryption_service, mock_db):
        """Test encryption integrity validation"""
        # Mock profiles
        mock_user_profile = Mock()
        mock_user_profile.get_decrypted_data.return_value = {"test": "data"}

        mock_org_profile = Mock()
        mock_org_profile.get_decrypted_data.return_value = {"test": "data"}

        mock_db.query.return_value.limit.return_value.all.return_value = [mock_user_profile, mock_org_profile]

        results = encryption_service.validate_encryption_integrity()

        assert results["user_profiles_tested"] == 1
        assert results["user_profiles_passed"] == 1
        assert results["organization_profiles_tested"] == 1
        assert results["organization_profiles_passed"] == 1
        assert results["overall_success_rate"] == 1.0


class TestEncryptionIntegration:
    """Integration tests for encryption system"""

    def test_end_to_end_encryption_flow(self):
        """Test complete encryption/decryption flow"""
        # Initialize encryption with test master key
        test_master_key = base64.b64encode(b'32_byte_master_key_for_testing!!').decode()

        with patch.dict('os.environ', {'ENCRYPTION_MASTER_KEY': test_master_key}):
            initialize_encryption()

            # Get encryption components
            key_manager = get_key_manager()
            aes_encryption = get_aes_encryption()
            field_encryption = get_field_encryption()

            # Generate a test key
            test_key = key_manager.generate_key(EncryptionKeyType.DATA)

            # Test data encryption
            original_data = "Sensitive personal information"
            encrypted_payload = aes_encryption.encrypt(original_data, test_key.key_id)

            # Verify encryption changed the data
            assert encrypted_payload["encrypted_data"] != original_data
            assert encrypted_payload["key_id"] == test_key.key_id

            # Test data decryption
            decrypted_data = aes_encryption.decrypt(encrypted_payload)
            assert decrypted_data.decode('utf-8') == original_data

            # Test field encryption
            field_value = "john.doe@example.com"
            encrypted_field = field_encryption.encrypt_field(field_value, "email")
            decrypted_field = field_encryption.decrypt_field(encrypted_field, "email")

            assert decrypted_field == field_value

    def test_key_rotation_simulation(self):
        """Test key rotation process simulation"""
        test_master_key = base64.b64encode(b'32_byte_master_key_for_testing!!').decode()

        with patch.dict('os.environ', {'ENCRYPTION_MASTER_KEY': test_master_key}):
            initialize_encryption()
            key_manager = get_key_manager()

            # Generate original key
            original_key = key_manager.generate_key(EncryptionKeyType.DATA)
            original_key_id = original_key.key_id

            # Rotate key
            new_key = key_manager.rotate_key(original_key_id)

            # Verify rotation
            assert new_key.key_id != original_key_id
            assert original_key.is_active is False
            assert new_key.is_active is True
            assert new_key.key_type == original_key.key_type
            assert new_key.algorithm == original_key.algorithm


if __name__ == "__main__":
    pytest.main([__file__, "-v"])