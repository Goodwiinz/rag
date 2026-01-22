"""
Enhanced Security Service
Provides advanced security controls including:
- Field-level encryption for sensitive data
- Data masking for PII
- Tokenization for secure data storage
- Key rotation management
- Secure key derivation
"""

import os
import base64
import secrets
import hashlib
import json
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from cryptography.hazmat.backends import default_backend
import redis
import logging

from src.core.config import settings

logger = logging.getLogger(__name__)

class DataClassification(Enum):
    """Data classification levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class EncryptionAlgorithm(Enum):
    """Supported encryption algorithms"""
    AES_256_GCM = "aes_256_gcm"
    FERNET = "fernet"
    CHACHA20_POLY1305 = "chacha20_poly1305"

class EnhancedSecurityService:
    """Enhanced security service for advanced data protection"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.backend = default_backend()

        # Initialize encryption keys
        self.master_key = self._get_or_create_master_key()
        self.data_encryption_key = self._derive_key(
            self.master_key,
            b"data_encryption",
            32
        )
        self.masking_key = self._derive_key(
            self.master_key,
            b"data_masking",
            32
        )
        self.tokenization_key = self._derive_key(
            self.master_key,
            b"tokenization",
            32
        )

        # Initialize encryption ciphers
        self.fernet_cipher = Fernet(
            base64.urlsafe_b64encode(self.data_encryption_key)
        )

        # PII field patterns for detection
        self.pii_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',
            'ssn': r'\b\d{3}-?\d{2}-?\d{4}\b',
            'credit_card': r'\b(?:\d[ -]*?){13,16}\b',
            'passport': r'\b[A-Z][0-9]{8}\b',
            'driver_license': r'\b[A-Z]{1,2}[0-9]{6,8}\b',
            'bank_account': r'\b\d{8,17}\b',
            'routing_number': r'\b\d{9}\b',
            'ip_address': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            'mac_address': r'\b[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'
        }

        # Token store (in production, use secure database)
        self.token_store = {} if not self.redis_client else self.redis_client

    def _get_or_create_master_key(self) -> bytes:
        """Get or create master encryption key"""
        # In production, load from secure key management system
        key_file = os.path.join(settings.SECURITY_DIR, 'master.key')

        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new master key
            key = os.urandom(32)
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
            return key

    def _derive_key(self, secret: bytes, salt: bytes, length: int) -> bytes:
        """Derive encryption key using PBKDF2"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            iterations=100000,
            backend=self.backend
        )
        return kdf.derive(secret)

    def encrypt_field(
        self,
        data: Union[str, Dict, List],
        classification: DataClassification = DataClassification.CONFIDENTIAL,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.FERNET,
        additional_data: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Encrypt a field with metadata
        """
        try:
            # Serialize data
            if isinstance(data, (dict, list)):
                data_str = json.dumps(data)
            else:
                data_str = str(data)

            data_bytes = data_str.encode('utf-8')

            # Encrypt based on algorithm
            if algorithm == EncryptionAlgorithm.FERNET:
                encrypted_data = self.fernet_cipher.encrypt(data_bytes)
                nonce = None
                tag = None

            elif algorithm == EncryptionAlgorithm.AES_256_GCM:
                # Generate random nonce
                nonce = os.urandom(12)
                cipher = Cipher(
                    algorithms.AES(self.data_encryption_key),
                    modes.GCM(nonce),
                    backend=self.backend
                )
                encryptor = cipher.encryptor()

                # Add additional authenticated data if provided
                if additional_data:
                    encryptor.authenticate_additional_data(additional_data)

                encrypted_data = encryptor.update(data_bytes) + encryptor.finalize()
                tag = encryptor.tag

            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

            # Create encrypted package
            encrypted_package = {
                'data': base64.b64encode(encrypted_data).decode('utf-8'),
                'algorithm': algorithm.value,
                'classification': classification.value,
                'timestamp': datetime.utcnow().isoformat(),
                'version': '1.0',
                'nonce': base64.b64encode(nonce).decode('utf-8') if nonce else None,
                'tag': base64.b64encode(tag).decode('utf-8') if tag else None,
                'key_id': hashlib.sha256(self.data_encryption_key).hexdigest()[:16]
            }

            return encrypted_package

        except Exception as e:
            logger.error(f"Field encryption failed: {e}")
            raise

    def decrypt_field(self, encrypted_package: Dict[str, Any]) -> Union[str, Dict, List]:
        """
        Decrypt an encrypted field
        """
        try:
            # Extract data
            encrypted_data = base64.b64decode(encrypted_package['data'])
            algorithm = EncryptionAlgorithm(encrypted_package['algorithm'])

            # Decrypt based on algorithm
            if algorithm == EncryptionAlgorithm.FERNET:
                decrypted_data = self.fernet_cipher.decrypt(encrypted_data)

            elif algorithm == EncryptionAlgorithm.AES_256_GCM:
                nonce = base64.b64decode(encrypted_package['nonce'])
                tag = base64.b64decode(encrypted_package['tag'])

                cipher = Cipher(
                    algorithms.AES(self.data_encryption_key),
                    modes.GCM(nonce, tag),
                    backend=self.backend
                )
                decryptor = cipher.decryptor()
                decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")

            # Deserialize data
            data_str = decrypted_data.decode('utf-8')
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                return data_str

        except Exception as e:
            logger.error(f"Field decryption failed: {e}")
            raise

    def mask_pii_data(
        self,
        data: str,
        preserve_length: bool = True,
        mask_char: str = '*',
        show_last: int = 4
    ) -> str:
        """
        Mask PII data while preserving format
        """
        import re

        for pii_type, pattern in self.pii_patterns.items():
            def mask_match(match):
                original = match.group()
                length = len(original)

                if pii_type == 'email':
                    # Mask email: user@domain -> u***@domain
                    local, domain = original.split('@', 1)
                    masked_local = local[0] + mask_char * (len(local) - 2) + local[-1] if len(local) > 2 else mask_char * len(local)
                    return f"{masked_local}@{domain}"

                elif pii_type == 'phone':
                    # Mask phone: (555) 123-4567 -> (555) ***-4567
                    if length > show_last:
                        return original[:-show_last] + mask_char * show_last
                    return mask_char * length

                elif pii_type == 'credit_card':
                    # Mask credit card: 1234567890123456 -> ****-****-****-3456
                    groups = [original[i:i+4] for i in range(0, length, 4)]
                    masked_groups = [mask_char * 4 if i < len(groups) - 1 else groups[i] for i in range(len(groups))]
                    return '-'.join(masked_groups)

                else:
                    # Default masking
                    if preserve_length and length > show_last:
                        return mask_char * (length - show_last) + original[-show_last:]
                    return mask_char * length

            data = re.sub(pattern, mask_match, data, flags=re.IGNORECASE)

        return data

    def tokenize_data(
        self,
        data: str,
        context: Optional[str] = None,
        preserve_format: bool = False
    ) -> str:
        """
        Tokenize sensitive data for secure storage
        """
        # Create token
        token_data = {
            'data': data,
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        }
        token_bytes = json.dumps(token_data).encode('utf-8')

        # Generate token using HMAC
        h = hashes.HMAC(self.tokenization_key, hashes.SHA256(), backend=self.backend)
        h.update(token_bytes)
        digest = h.finalize()

        # Create readable token
        token = base64.urlsafe_b64encode(digest).decode('utf-8')[:32]

        # Store mapping in secure store
        if self.redis_client:
            self.redis_client.setex(
                f"token:{token}",
                timedelta(days=365),  # 1 year expiry
                json.dumps(token_data)
            )
        else:
            self.token_store[token] = token_data

        if preserve_format:
            # Create format-preserving token (simplified)
            return self._format_preserving_token(data, token)
        else:
            return f"TKN-{token}"

    def _format_preserving_token(self, original: str, token: str) -> str:
        """
        Create format-preserving token (simplified implementation)
        """
        if len(original) == 16 and original.isdigit():  # Credit card
            return f"4111{token[:12]}"
        elif '@' in original:  # Email
            local, domain = original.split('@', 1)
            return f"{token[:8].lower()}@{domain}"
        else:
            return token[:len(original)]

    def detokenize_data(self, token: str) -> Optional[str]:
        """
        Retrieve original data from token
        """
        # Clean token format
        if token.startswith('TKN-'):
            token = token[4:]

        # Retrieve from store
        if self.redis_client:
            token_data = self.redis_client.get(f"token:{token}")
            if token_data:
                data = json.loads(token_data)
                return data.get('data')
        else:
            return self.token_store.get(token, {}).get('data')

        return None

    def rotate_encryption_keys(self, new_master_key: Optional[bytes] = None):
        """
        Rotate encryption keys
        """
        try:
            # Generate new master key if not provided
            if not new_master_key:
                new_master_key = os.urandom(32)

            # Derive new keys
            new_data_key = self._derive_key(new_master_key, b"data_encryption", 32)
            new_masking_key = self._derive_key(new_master_key, b"data_masking", 32)
            new_token_key = self._derive_key(new_master_key, b"tokenization", 32)

            # Re-encrypt data with new keys (would need to iterate through all encrypted data)
            # This is a simplified version

            # Update current keys
            self.master_key = new_master_key
            self.data_encryption_key = new_data_key
            self.masking_key = new_masking_key
            self.tokenization_key = new_token_key

            # Save new master key
            key_file = os.path.join(settings.SECURITY_DIR, 'master.key')
            with open(key_file, 'wb') as f:
                f.write(new_master_key)

            logger.info("Encryption keys rotated successfully")

        except Exception as e:
            logger.error(f"Key rotation failed: {e}")
            raise

    def verify_data_integrity(
        self,
        data: bytes,
        signature: Optional[bytes] = None,
        hash_algorithm: str = 'sha256'
    ) -> Dict[str, Any]:
        """
        Verify data integrity using HMAC
        """
        try:
            # Calculate hash
            if hash_algorithm == 'sha256':
                digest = hashes.Hash(hashes.SHA256(), backend=self.backend)
            elif hash_algorithm == 'sha512':
                digest = hashes.Hash(hashes.SHA512(), backend=self.backend)
            else:
                raise ValueError(f"Unsupported hash algorithm: {hash_algorithm}")

            digest.update(data)
            data_hash = digest.finalize()

            result = {
                'hash': base64.b64encode(data_hash).decode('utf-8'),
                'algorithm': hash_algorithm,
                'timestamp': datetime.utcnow().isoformat()
            }

            # Verify signature if provided
            if signature:
                h = hashes.HMAC(self.data_encryption_key, hashes.SHA256(), backend=self.backend)
                h.update(data)
                expected_signature = h.finalize()

                result['signature_valid'] = secrets.compare_digest(
                    signature,
                    expected_signature
                )

            return result

        except Exception as e:
            logger.error(f"Data integrity verification failed: {e}")
            raise

    def generate_secure_token(
        self,
        length: int = 32,
        prefix: Optional[str] = None,
        suffix: Optional[str] = None,
        url_safe: bool = True
    ) -> str:
        """
        Generate secure random token
        """
        if url_safe:
            token = secrets.token_urlsafe(length)
        else:
            token = secrets.token_hex(length)

        # Add prefix and suffix
        if prefix:
            token = f"{prefix}-{token}"
        if suffix:
            token = f"{token}-{suffix}"

        return token

    def audit_encryption_usage(self, days: int = 30) -> Dict[str, Any]:
        """
        Audit encryption usage for compliance
        """
        # This would query audit logs for encryption events
        # Simplified version
        return {
            'total_encrypted_fields': 0,
            'fields_by_classification': {
                'public': 0,
                'internal': 0,
                'confidential': 0,
                'restricted': 0
            },
            'algorithms_used': {
                'fernet': 0,
                'aes_256_gcm': 0,
                'chacha20_poly1305': 0
            },
            'key_rotation_last_performed': None,
            'keys_pending_rotation': 0
        }

# Create global instance
enhanced_security_service = EnhancedSecurityService()