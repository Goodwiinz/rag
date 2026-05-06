"""
Enhanced Database Security Implementation
Addresses database security vulnerabilities and implements encryption
"""

import base64
import hashlib
import json
import logging
import os
import re
import secrets
import ssl
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import engine

logger = logging.getLogger(__name__)


class DatabaseConnectionSecurity:
    """Enhanced database connection security"""

    def __init__(self):
        self.ssl_context = self._create_ssl_context()
        self.connection_timeout = 30
        self.max_connections = 20
        self.connection_validation_interval = 30

    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for database connections"""
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        # Enforce strong SSL/TLS versions
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3

        # Verify server certificate
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True

        # Load custom CA certificate if provided
        if hasattr(settings, "DB_SSL_CA_CERT"):
            try:
                context.load_verify_locations(settings.DB_SSL_CA_CERT)
                logger.info("Custom CA certificate loaded for database SSL")
            except Exception as e:
                logger.error(f"Failed to load CA certificate: {e}")

        # Set strong cipher suites
        context.set_ciphers(
            "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
        )

        return context

    def create_secure_connection_string(self) -> str:
        """Create secure database connection string"""
        base_url = settings.DATABASE_URL

        # Add SSL parameters
        ssl_params = {
            "sslmode": "require",
            "sslcert": getattr(settings, "DB_SSL_CERT", ""),
            "sslkey": getattr(settings, "DB_SSL_KEY", ""),
            "sslrootcert": getattr(settings, "DB_SSL_CA_CERT", ""),
            "sslcrldir": getattr(settings, "DB_SSL_CRL_DIR", ""),
        }

        # Remove empty parameters
        ssl_params = {k: v for k, v in ssl_params.items() if v}

        # Build connection string with SSL
        if "?" in base_url:
            connection_string = (
                base_url + "&" + "&".join([f"{k}={v}" for k, v in ssl_params.items()])
            )
        else:
            connection_string = (
                base_url + "?" + "&".join([f"{k}={v}" for k, v in ssl_params.items()])
            )

        return connection_string


class QuerySecurityAnalyzer:
    """Analyzes SQL queries for security vulnerabilities"""

    def __init__(self):
        self.suspicious_patterns = {
            "sql_injection": [
                r"(?i)\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b",
                r"(?i)'\s*(or|and)\s+\w+\s*=\s*\w+",
                r"(?i)(\%27)|(\')\s*((\%6F)|o|(\%4F))((\%72)|r|(\%52))",
                r"(?i)(\%27)|(\')\s*((\%61)|a|(\%41))((\%6E)|n|(\%4E))((\%64)|d|(\%44))",
                r"(?i)(--|#|/\*|\*/)",
                r"(?i)(waitfor\s+delay|benchmark\s*\(|sleep\s*\(|pg_sleep\s*\()",
                r"(?i)(system\s*\(|exec\s*\(|xp_cmdshell)",
                r"(?i)(0x[0-9a-f]+)",
                r"(?i)(;\s*(drop|delete|update|insert|create|alter|exec))",
            ],
            "data_exfiltration": [
                r"(?i)(load_file|into\s+outfile|into\s+dumpfile)",
                r"(?i)(information_schema|mysql\.sys|pg_catalog)",
                r"(?i)(sysobjects|sysdatabases|sysusers)",
            ],
            "privilege_escalation": [
                r"(?i)(grant\s+.*\s+to|revoke\s+.*\s+from)",
                r"(?i)(set\s+role|set\s+session\s+authorization)",
                r"(?i)(create\s+user|alter\s+user|drop\s+user)",
            ],
            "denial_of_service": [
                r"(?i)(waitfor\s+delay|pg_sleep|sleep\s*\()",
                r"(?i)(benchmark\s*\(|\.+\.+)",  # BENCHMARK or repeated dots
                r"(?i)(cartesian|cross\s+join)",
            ],
        }

        self.risk_thresholds = {
            "sql_injection": 3,  # High risk
            "data_exfiltration": 3,  # High risk
            "privilege_escalation": 2,  # Medium risk
            "denial_of_service": 1,  # Low risk
        }

    def analyze_query(
        self, query: str, parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Analyze SQL query for security vulnerabilities"""
        analysis = {
            "is_safe": True,
            "risk_score": 0,
            "vulnerabilities": [],
            "recommendations": [],
            "suspicious_patterns": [],
        }

        query_lower = query.lower()

        # Check for suspicious patterns
        for vulnerability_type, patterns in self.suspicious_patterns.items():
            matches = []
            for pattern in patterns:
                found_matches = re.findall(pattern, query_lower)
                if found_matches:
                    matches.extend(found_matches)

            if matches:
                risk_score = self.risk_thresholds.get(vulnerability_type, 1)
                analysis["risk_score"] += risk_score
                analysis["vulnerabilities"].append(
                    {
                        "type": vulnerability_type,
                        "matches": matches,
                        "risk_score": risk_score,
                    }
                )
                analysis["suspicious_patterns"].extend(matches)

        # Check for parameterized query usage
        if not self._is_parameterized(query) and analysis["risk_score"] > 0:
            analysis["recommendations"].append(
                "Use parameterized queries instead of string concatenation"
            )

        # Check for excessive complexity
        if self._is_excessively_complex(query):
            analysis["risk_score"] += 1
            analysis["vulnerabilities"].append(
                {"type": "query_complexity", "risk_score": 1}
            )
            analysis["recommendations"].append("Simplify query complexity")

        # Determine overall safety
        analysis["is_safe"] = analysis["risk_score"] < 3

        return analysis

    def _is_parameterized(self, query: str) -> bool:
        """Check if query uses parameterization"""
        parameter_patterns = [r"%s", r":\w+", r"\?", r"\$\d+"]
        return any(re.search(pattern, query) for pattern in parameter_patterns)

    def _is_excessively_complex(self, query: str) -> bool:
        """Check if query is excessively complex"""
        # Count joins, subqueries, and unions
        join_count = len(
            re.findall(
                r"\b(join|inner\s+join|left\s+join|right\s+join|full\s+join)\b",
                query,
                re.IGNORECASE,
            )
        )
        subquery_count = len(
            re.findall(
                r"\bselect\b.*\bfrom\b.*\bwhere\b.*\bselect\b", query, re.IGNORECASE
            )
        )
        union_count = len(re.findall(r"\bunion\b", query, re.IGNORECASE))

        # Consider complex if too many joins, subqueries, or unions
        complexity_score = join_count + (subquery_count * 2) + (union_count * 3)
        return complexity_score > 10


class FieldLevelEncryption:
    """Field-level encryption for sensitive data"""

    def __init__(self):
        self.master_key = self._get_or_create_master_key()
        self.cipher = Fernet(self.master_key)
        self.encrypted_fields = {
            "User.email": self.encrypt_email,
            "User.phone": self.encrypt_phone,
            "User.ssn": self.encrypt_ssn,
            "Document.content": self.encrypt_content,
            "Organization.api_key": self.encrypt_api_key,
        }

    def _get_or_create_master_key(self) -> bytes:
        """Get or create master encryption key"""
        key_file = "/etc/rag/field_encryption.key"

        try:
            with open(key_file, "rb") as f:
                return f.read()
        except FileNotFoundError:
            # Generate new master key
            key = Fernet.generate_key()

            try:
                os.makedirs(os.path.dirname(key_file), exist_ok=True)
                with open(key_file, "wb") as f:
                    f.write(key)
                os.chmod(key_file, 0o600)
                logger.info("Generated new field encryption key")
            except Exception as e:
                logger.error(f"Failed to save encryption key: {e}")

            return key

    def encrypt_field(self, model_field: str, value: str) -> str:
        """Encrypt a specific field"""
        if not value:
            return value

        encrypt_func = self.encrypted_fields.get(model_field)
        if encrypt_func:
            return encrypt_func(value)
        else:
            return self.encrypt_generic(value)

    def decrypt_field(self, model_field: str, encrypted_value: str) -> str:
        """Decrypt a specific field"""
        if not encrypted_value:
            return encrypted_value

        try:
            decrypt_func = self.encrypted_fields.get(model_field)
            if decrypt_func:
                # Most fields use the same decryption method
                return self.decrypt_generic(encrypted_value)
            else:
                return self.decrypt_generic(encrypted_value)
        except Exception as e:
            logger.error(f"Failed to decrypt field {model_field}: {e}")
            return encrypted_value

    def encrypt_generic(self, value: str) -> str:
        """Generic encryption for any field"""
        if not value:
            return value

        try:
            # Add field prefix for identification
            value_bytes = f"encrypted:{value}".encode("utf-8")
            encrypted_bytes = self.cipher.encrypt(value_bytes)
            return base64.b64encode(encrypted_bytes).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encrypt value: {e}")
            return value

    def decrypt_generic(self, encrypted_value: str) -> str:
        """Generic decryption for any field"""
        if not encrypted_value or not encrypted_value.startswith("encrypted:"):
            return encrypted_value

        try:
            # Remove prefix if it exists (for legacy compatibility)
            if ":" in encrypted_value and not encrypted_value.startswith("encrypted:"):
                # Legacy format without prefix
                encrypted_bytes = base64.b64decode(encrypted_value)
                decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
                return decrypted_bytes.decode("utf-8")
            else:
                # New format with prefix - remove base64 part first
                if encrypted_value.startswith("encrypted:"):
                    # This shouldn't happen in normal flow
                    return encrypted_value

                encrypted_bytes = base64.b64decode(encrypted_value)
                decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
                decrypted_str = decrypted_bytes.decode("utf-8")

                # Remove prefix if present
                if decrypted_str.startswith("encrypted:"):
                    return decrypted_str[10:]  # Remove 'encrypted:' prefix

                return decrypted_str
        except Exception as e:
            logger.error(f"Failed to decrypt value: {e}")
            return encrypted_value

    def encrypt_email(self, email: str) -> str:
        """Encrypt email field"""
        return self.encrypt_generic(email)

    def encrypt_phone(self, phone: str) -> str:
        """Encrypt phone field"""
        return self.encrypt_generic(phone)

    def encrypt_ssn(self, ssn: str) -> str:
        """Encrypt SSN field"""
        return self.encrypt_generic(ssn)

    def encrypt_content(self, content: str) -> str:
        """Encrypt document content"""
        # For large content, we might want to use chunking
        if len(content) > 1000000:  # 1MB
            return self.encrypt_large_content(content)
        return self.encrypt_generic(content)

    def encrypt_api_key(self, api_key: str) -> str:
        """Encrypt API key"""
        return self.encrypt_generic(api_key)

    def encrypt_large_content(self, content: str) -> str:
        """Encrypt large content using chunking"""
        chunk_size = 1000000  # 1MB chunks
        chunks = [
            content[i : i + chunk_size] for i in range(0, len(content), chunk_size)
        ]

        encrypted_chunks = []
        for chunk in chunks:
            encrypted_chunks.append(self.encrypt_generic(chunk))

        # Combine chunks with delimiter
        return "|||".join(encrypted_chunks)

    def decrypt_large_content(self, encrypted_content: str) -> str:
        """Decrypt large content from chunks"""
        if "|||" in encrypted_content:
            encrypted_chunks = encrypted_content.split("|||")
            decrypted_chunks = []
            for chunk in encrypted_chunks:
                decrypted_chunks.append(self.decrypt_generic(chunk))
            return "".join(decrypted_chunks)
        else:
            return self.decrypt_generic(encrypted_content)


class DatabaseAuditor:
    """Database security auditor"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.field_encryption = FieldLevelEncryption()

    def audit_sensitive_data_access(
        self,
        table_name: str,
        record_id: str = None,
        user_id: str = None,
        action: str = "SELECT",
    ) -> None:
        """Audit access to sensitive data"""
        audit_record = {
            "timestamp": datetime.utcnow(),
            "table_name": table_name,
            "record_id": record_id,
            "user_id": user_id,
            "action": action,
            "ip_address": getattr(self, "_current_ip", "unknown"),
            "user_agent": getattr(self, "_current_user_agent", "unknown"),
        }

        # Store audit record in database
        try:
            self.db.execute(
                text(
                    """
                INSERT INTO audit_log (timestamp, table_name, record_id, user_id, action, ip_address, user_agent)
                VALUES (:timestamp, :table_name, :record_id, :user_id, :action, :ip_address, :user_agent)
                """
                ),
                audit_record,
            )
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to record audit log: {e}")

    def check_data_integrity(self, table_name: str, record_id: str) -> bool:
        """Verify data integrity using checksums"""
        try:
            # Get stored checksum
            result = self.db.execute(
                text(
                    "SELECT checksum FROM data_integrity WHERE table_name = :table AND record_id = :id"
                ),
                {"table": table_name, "id": record_id},
            ).fetchone()

            if not result:
                return True  # No integrity check available

            stored_checksum = result[0]

            # Calculate current checksum - use dynamic SQL with proper validation
            # Validate table name against whitelist
            allowed_tables = ['documents', 'users', 'organizations', 'processing_history']
            if table_name not in allowed_tables:
                raise ValueError(f"Invalid table name: {table_name}")
            
            current_data = self.db.execute(
                text("SELECT * FROM {} WHERE id = :id".format(table_name)),  # nosec: B608 - table/column names validated against whitelist
                {'id': record_id}
            ).fetchone()

            if current_data:
                data_str = json.dumps(dict(current_data), sort_keys=True)
                current_checksum = hashlib.sha256(data_str.encode()).hexdigest()
                return stored_checksum == current_checksum

            return False
        except Exception as e:
            logger.error(f"Data integrity check failed: {e}")
            return False

    def generate_integrity_checksum(
        self, table_name: str, record_id: str, data: Dict[str, Any]
    ) -> str:
        """Generate integrity checksum for data"""
        data_str = json.dumps(data, sort_keys=True)
        checksum = hashlib.sha256(data_str.encode()).hexdigest()

        # Store checksum
        try:
            self.db.execute(
                text(
                    """
                INSERT INTO data_integrity (table_name, record_id, checksum, created_at)
                VALUES (:table, :id, :checksum, :timestamp)
                ON CONFLICT (table_name, record_id)
                DO UPDATE SET checksum = :checksum, updated_at = :timestamp
                """
                ),
                {
                    "table": table_name,
                    "id": record_id,
                    "checksum": checksum,
                    "timestamp": datetime.utcnow(),
                },
            )
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to store integrity checksum: {e}")

        return checksum


class SecureDatabaseEngine:
    """Enhanced database engine with security features"""

    def __init__(self):
        self.connection_security = DatabaseConnectionSecurity()
        self.query_analyzer = QuerySecurityAnalyzer()
        self.field_encryption = FieldLevelEncryption()

    def create_secure_engine(self):
        """Create secure database engine"""
        # Create SSL-enabled connection string
        secure_url = self.connection_security.create_secure_connection_string()

        # Create engine with security settings
        engine = create_engine(
            secure_url,
            pool_size=self.connection_security.max_connections,
            max_overflow=10,
            pool_timeout=self.connection_security.connection_timeout,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_args={
                "sslcontext": self.connection_security.ssl_context,
                "connect_timeout": self.connection_security.connection_timeout,
                "application_name": "rag_system_secure",
            },
        )

        # Add security event listeners
        self._add_security_listeners(engine)

        return engine

    def _add_security_listeners(self, engine: Engine):
        """Add security event listeners to engine"""

        @event.listens_for(engine, "before_execute")
        def before_execute(conn, clauseelement, multiparams, params, execution_options):
            """Analyze queries before execution"""
            query_str = str(clauseelement)

            # Analyze for security vulnerabilities
            analysis = self.query_analyzer.analyze_query(query_str, params)

            if not analysis["is_safe"]:
                logger.warning(
                    f"Potentially unsafe query detected: {query_str}",
                    extra={
                        "vulnerabilities": analysis["vulnerabilities"],
                        "risk_score": analysis["risk_score"],
                    },
                )

                # For high-risk queries, raise exception
                if analysis["risk_score"] >= 3:
                    raise ValueError(
                        f"Query rejected due to security concerns: {analysis['vulnerabilities']}"
                    )

        @event.listens_for(engine, "after_execute")
        def after_execute(
            conn, clauseelement, multiparams, params, result, execution_options
        ):
            """Log query execution for audit"""
            query_str = str(clauseelement)

            # Log sensitive data access
            if any(
                table in query_str.lower()
                for table in ["user", "document", "organization"]
            ):
                logger.info(
                    f"Sensitive data query executed",
                    extra={
                        "query": query_str[:200],  # Truncate for logging
                        "params": str(params)[:100] if params else None,
                    },
                )


# Database security manager
class DatabaseSecurityManager:
    """Main database security manager"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.auditor = DatabaseAuditor(db_session)
        self.field_encryption = FieldLevelEncryption()
        self.query_analyzer = QuerySecurityAnalyzer()

    def secure_insert(self, table_name: str, data: Dict[str, Any]) -> Any:
        """Secure insert with field encryption and integrity checking"""
        # Validate table name against whitelist
        allowed_tables = ['documents', 'users', 'organizations', 'processing_history', 'audit_log', 'data_integrity']
        if table_name not in allowed_tables:
            raise ValueError(f"Invalid table name: {table_name}")
        
        # Encrypt sensitive fields
        encrypted_data = {}
        for field, value in data.items():
            model_field = f"{table_name}.{field}"
            if isinstance(value, str):
                encrypted_data[field] = self.field_encryption.encrypt_field(
                    model_field, value
                )
            else:
                encrypted_data[field] = value

        # Generate integrity checksum
        if "id" in encrypted_data:
            self.auditor.generate_integrity_checksum(
                table_name, str(encrypted_data["id"]), encrypted_data
            )

        # Execute insert
        try:
            # Validate table name and column names to prevent SQL injection.
            # The nosec comment below asserts identifiers are safe to interpolate;
            # isidentifier() enforces that assertion instead of trusting it.
            if not table_name.isidentifier():
                raise ValueError(f"Invalid table name: {table_name!r}")
            for key in encrypted_data.keys():
                if not key.isidentifier():
                    raise ValueError(f"Invalid column name: {key!r}")

            columns = ', '.join(encrypted_data.keys())
            placeholders = ', '.join([f':{key}' for key in encrypted_data.keys()])
            query = text("INSERT INTO {} ({}) VALUES ({})".format(table_name, columns, placeholders))  # nosec: B608 - table and column names validated via isidentifier()

            result = self.db.execute(query, encrypted_data)
            self.db.commit()

            # Audit the operation
            self.auditor.audit_sensitive_data_access(
                table_name,
                str(encrypted_data.get("id", result.lastrowid)),
                getattr(self, "_current_user_id", None),
                "INSERT",
            )

            return result

        except Exception as e:
            self.db.rollback()
            logger.error(f"Secure insert failed: {e}")
            raise

    def secure_select(
        self, table_name: str, filters: Dict[str, Any] = None, columns: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Secure select with access control and audit logging"""
        try:
            # Validate table name against whitelist
            allowed_tables = ['documents', 'users', 'organizations', 'processing_history', 'audit_log', 'data_integrity']
            if table_name not in allowed_tables:
                raise ValueError(f"Invalid table name: {table_name}")
            
            allowed_columns = ['id', 'name', 'created_at', 'updated_at', 'status', 'email', 'phone', 'content']

            # Validate column names if specified
            if columns:
                for col in columns:
                    if col not in allowed_columns:
                        raise ValueError(f"Invalid column name: {col}")
                select_columns = ', '.join(columns)
            else:
                select_columns = '*'
            
            # Build base query using string formatting for table name (after validation)
            query = "SELECT {} FROM {}".format(select_columns, table_name)  # nosec: B608 - table/column names validated against whitelist
            params = {}

            if filters:
                where_clauses = []
                for field, value in filters.items():
                    # Validate field names
                    if field not in allowed_columns:
                        raise ValueError(f"Invalid filter field: {field}")
                    where_clauses.append(f"{field} = :{field}")
                    params[field] = value
                query += " WHERE {}".format(' AND '.join(where_clauses))

            # Analyze query for security
            analysis = self.query_analyzer.analyze_query(query, params)
            if not analysis["is_safe"]:
                raise ValueError(
                    f"Query rejected due to security concerns: {analysis['vulnerabilities']}"
                )

            # Execute query
            result = self.db.execute(text(query), params).fetchall()

            # Decrypt sensitive fields
            decrypted_results = []
            for row in result:
                row_dict = dict(row)
                for field, value in row_dict.items():
                    if isinstance(value, str):
                        model_field = f"{table_name}.{field}"
                        row_dict[field] = self.field_encryption.decrypt_field(
                            model_field, value
                        )
                decrypted_results.append(row_dict)

            # Audit the operation
            if filters and 'id' in filters:
                self.auditor.audit_sensitive_data_access(
                    table_name,
                    str(filters["id"]),
                    getattr(self, "_current_user_id", None),
                    "SELECT",
                )

            return decrypted_results

        except Exception as e:
            logger.error(f"Secure select failed: {e}")
            raise


# Initialize secure database engine
def get_secure_database_engine():
    """Get secure database engine instance"""
    secure_engine = SecureDatabaseEngine()
    return secure_engine.create_secure_engine()


# Database security dependency
def get_database_security_manager(
    db: Session = Depends(get_db),
) -> DatabaseSecurityManager:
    """Get database security manager instance"""
    return DatabaseSecurityManager(db)
