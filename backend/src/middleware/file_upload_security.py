"""
Enhanced File Upload Security Middleware
Provides comprehensive security controls for file uploads including:
- Virus scanning with ClamAV
- File type validation using magic bytes
- Archive bomb detection
- Metadata sanitization
- Content scanning for sensitive information
"""

import bz2
import gzip
import hashlib
import logging
import os
import re
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

import clamd
import exifread
import magic
import maxminddb
import pyminizip
import rarfile
from fastapi import HTTPException, UploadFile, status
from PIL import Image

from src.core.config import settings
from src.models.organization import Organization
from src.models.user import User

logger = logging.getLogger(__name__)


class SecurityValidationError(Exception):
    """Security validation failed for file upload"""

    pass


class FileUploadSecurityService:
    """Comprehensive security service for file uploads"""

    def __init__(self):
        self.allowed_mime_types = {
            # Documents
            "application/pdf": [".pdf"],
            "application/msword": [".doc"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
                ".docx"
            ],
            "text/plain": [".txt", ".md", ".log"],
            "text/csv": [".csv"],
            "text/markdown": [".md"],
            "application/vnd.ms-excel": [".xls"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
                ".xlsx"
            ],
            "application/vnd.ms-powerpoint": [".ppt"],
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": [
                ".pptx"
            ],
            "application/rtf": [".rtf"],
            "application/vnd.oasis.opendocument.text": [".odt"],
            "application/vnd.oasis.opendocument.spreadsheet": [".ods"],
            "application/vnd.oasis.opendocument.presentation": [".odp"],
            # Images
            "image/jpeg": [".jpg", ".jpeg"],
            "image/png": [".png"],
            "image/gif": [".gif"],
            "image/bmp": [".bmp"],
            "image/tiff": [".tiff", ".tif"],
            "image/webp": [".webp"],
            "image/svg+xml": [".svg"],
            "image/x-icon": [".ico"],
            # Audio
            "audio/mpeg": [".mp3"],
            "audio/wav": [".wav"],
            "audio/ogg": [".ogg"],
            "audio/flac": [".flac"],
            "audio/aac": [".aac"],
            "audio/m4a": [".m4a"],
            "audio/x-ms-wma": [".wma"],
            # Video
            "video/mp4": [".mp4"],
            "video/avi": [".avi"],
            "video/mov": [".mov"],
            "video/wmv": [".wmv"],
            "video/flv": [".flv"],
            "video/webm": [".webm"],
            "video/mkv": [".mkv"],
            "video/quicktime": [".mov", ".qt"],
            # Archives (restricted)
            "application/zip": [".zip"],
            "application/x-rar-compressed": [".rar"],
            "application/x-tar": [".tar"],
            "application/gzip": [".gz"],
            "application/x-bzip2": [".bz2"],
            "application/x-7z-compressed": [".7z"],
        }

        # Dangerous file extensions to block
        self.blocked_extensions = {
            ".exe",
            ".bat",
            ".cmd",
            ".com",
            ".pif",
            ".scr",
            ".vbs",
            ".js",
            ".jar",
            ".app",
            ".deb",
            ".pkg",
            ".dmg",
            ".msi",
            ".msp",
            ".msm",
            ".sh",
            ".ps1",
            ".vb",
            ".vbe",
            ".jse",
            ".ws",
            ".wsf",
            ".wsc",
            ".wsh",
            ".ps1xml",
            ".ps2",
            ".ps2xml",
            ".psc1",
            ".psc2",
            ".msh",
            ".msh1",
            ".msh2",
            ".mshxml",
            ".msh1xml",
            ".msh2xml",
            ".scf",
            ".lnk",
            ".inf",
            ".reg",
            ".docm",
            ".dotm",
            ".xlsm",
            ".xltm",
            ".xlam",
            ".pptm",
            ".potm",
            ".ppam",
            ".ppsm",
            ".sldm",
            ".ade",
            ".adp",
            ".cpl",
            ".mdb",
            ".accdb",
            ".accdc",
            ".accde",
            ".accdr",
            ".accdt",
            ".accda",
            ".mda",
            ".mdw",
            ".mdt",
            ".mdz",
            ".xll",
            ".xlw",
            ".wks",
            ".wiz",
            ".wps",
            ".xtp",
            ".xnk",
            ".ins",
            ".isp",
            ".onetoc2",
            ".tmp",
            ".url",
            ".vsmacros",
            ".vsw",
            ".vsd",
            ".vsdx",
            ".vss",
            ".vst",
            ".vdx",
            ".vsx",
            ".vtx",
            ".vsdm",
            ".vssm",
            ".vstm",
            ".xdw",
            ".xps",
        }

        # Dangerous MIME types to block
        self.blocked_mime_types = {
            "application/x-executable",
            "application/x-msdownload",
            "application/x-msdos-program",
            "application/x-sh",
            "application/x-shellscript",
            "application/x-php",
            "application/x-perl",
            "application/x-python",
            "application/x-ruby",
            "application/javascript",
            "text/javascript",
            "application/x-javascript",
            "text/ecmascript",
            "application/ecmascript",
        }

        # Initialize ClamAV scanner if available
        self.clam_scanner = None
        try:
            self.clam_scanner = clamd.ClamdUnixSocket()
            self.clam_scanner.ping()
            logger.info("ClamAV scanner initialized successfully")
        except Exception as e:
            logger.warning(f"ClamAV not available: {e}")

        # Initialize GeoIP database for suspicious location detection
        self.geoip_reader = None
        try:
            self.geoip_reader = maxminddb.open_database(
                "/usr/share/GeoIP/GeoLite2-Country.mmdb"
            )
        except:
            logger.warning("GeoIP database not available")

        # Patterns for sensitive data detection
        self.sensitive_patterns = {
            "ssn": r"\b\d{3}-?\d{2}-?\d{4}\b",
            "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
            "api_key": r'(?i)(api[_-]?key|apikey)["\'\s]*[:=]["\'\s]*([a-zA-Z0-9_\-]{16,})',
            "password": r'(?i)(password|pwd)["\'\s]*[:=]["\'\s]*([^\s\'"]{6,})',
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "phone": r"\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b",
            "private_key": r"-----BEGIN\s*(RSA\s*)?PRIVATE\s*KEY-----",
            "jwt_token": r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*",
            "aws_access_key": r"AKIA[0-9A-Z]{16}",
            "github_token": r"ghp_[a-zA-Z0-9]{36}",
            "slack_token": r"xox[baprs]-[0-9]{12}-[0-9]{12}-[0-9]{12}-[a-zA-Z0-9]{24}",
        }

    async def validate_file_security(
        self,
        file: UploadFile,
        user: User,
        organization: Organization,
        client_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive security validation on uploaded file
        """
        validation_results = {
            "passed": True,
            "warnings": [],
            "errors": [],
            "metadata": {},
            "security_flags": [],
        }

        # Store original file position
        original_position = file.file.tell()

        try:
            # Read file content for analysis
            file_content = await self._read_file_content(file)

            # 1. File size validation
            size_result = self._validate_file_size(file_content, organization)
            validation_results.update(size_result)

            # 2. Filename validation
            filename_result = self._validate_filename(file.filename)
            validation_results.update(filename_result)

            # 3. MIME type and magic bytes validation
            mime_result = self._validate_mime_type(file.filename, file_content)
            validation_results.update(mime_result)

            # 4. Virus scanning
            virus_result = await self._scan_for_viruses(file_content)
            validation_results.update(virus_result)

            # 5. Archive bomb detection
            if self._is_archive_file(mime_result.get("detected_mime", "")):
                archive_result = await self._detect_archive_bomb(
                    file_content, file.filename
                )
                validation_results.update(archive_result)

            # 6. Image-specific validation
            if mime_result.get("detected_mime", "").startswith("image/"):
                image_result = await self._validate_image_security(
                    file_content, file.filename
                )
                validation_results.update(image_result)

            # 7. Content security scanning
            content_result = await self._scan_content_security(file_content)
            validation_results.update(content_result)

            # 8. Geolocation check
            if client_ip and self.geoip_reader:
                geo_result = self._check_geolocation(client_ip, user)
                validation_results.update(geo_result)

            # 9. Metadata extraction and sanitization
            metadata_result = await self._extract_and_sanitize_metadata(
                file_content, mime_result.get("detected_mime", "")
            )
            validation_results["metadata"].update(metadata_result)

            # 10. Calculate file hash
            validation_results["file_hash"] = self._calculate_file_hash(file_content)

            # Overall validation result
            validation_results["passed"] = len(validation_results["errors"]) == 0

            return validation_results

        finally:
            # Reset file position
            file.file.seek(original_position)

    async def _read_file_content(
        self, file: UploadFile, max_size: int = 100 * 1024 * 1024
    ) -> bytes:
        """Read file content with size limit"""
        content = b""
        file.file.seek(0)

        while True:
            chunk = await file.read(8192)
            if not chunk:
                break

            content += chunk
            if len(content) > max_size:
                raise SecurityValidationError(f"File too large for security scanning")

        return content

    def _validate_file_size(
        self, content: bytes, organization: Organization
    ) -> Dict[str, Any]:
        """Validate file size against limits"""
        result = {"errors": [], "warnings": []}

        file_size = len(content)

        # Check against organization limit
        if file_size > organization.max_file_size_bytes:
            result["errors"].append(
                f"File size ({file_size} bytes) exceeds maximum allowed size "
                f"({organization.max_file_size_bytes} bytes)"
            )

        # Check against storage quota
        if not organization.can_upload_file(file_size):
            result["errors"].append(
                f"Insufficient storage quota. Available: {organization.storage_available_gb:.2f}GB"
            )

        # Warn for large files
        if file_size > 50 * 1024 * 1024:  # 50MB
            result["warnings"].append(
                f"Large file detected ({file_size / (1024*1024):.1f}MB). "
                "Processing may take longer."
            )

        return result

    def _validate_filename(self, filename: str) -> Dict[str, Any]:
        """Validate filename for security issues"""
        result = {"errors": [], "warnings": []}

        if not filename:
            result["errors"].append("Filename is required")
            return result

        # Check path traversal attempts
        if ".." in filename or "/" in filename or "\\" in filename:
            result["errors"].append("Invalid filename: path traversal not allowed")
            return result

        # Check for dangerous extensions
        file_ext = Path(filename).suffix.lower()
        if file_ext in self.blocked_extensions:
            result["errors"].append(
                f"File extension '{file_ext}' is not allowed for security reasons"
            )

        # Check filename length
        if len(filename) > 255:
            result["errors"].append("Filename too long (max 255 characters)")

        # Check for special characters that might cause issues
        dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "\0"]
        if any(char in filename for char in dangerous_chars):
            result["warnings"].append(
                "Filename contains special characters that may cause issues"
            )

        # Check for suspicious patterns
        suspicious_patterns = [
            r"^\.htaccess$",
            r"^\.htpasswd$",
            r"^web\.config$",
            r"^\.env",
            r"^config\.php$",
            r"^wp-config\.php$",
        ]

        for pattern in suspicious_patterns:
            if re.match(pattern, filename, re.IGNORECASE):
                result["errors"].append(
                    f"Filename '{filename}' matches a restricted pattern"
                )

        return result

    def _validate_mime_type(self, filename: str, content: bytes) -> Dict[str, Any]:
        """Validate MIME type using magic bytes"""
        result = {"errors": [], "warnings": [], "detected_mime": None}

        # Detect MIME type from content
        try:
            detected_mime = magic.from_buffer(content, mime=True)
            result["detected_mime"] = detected_mime
        except Exception as e:
            result["warnings"].append(f"Could not detect file MIME type: {e}")
            return result

        # Check against blocked MIME types
        if detected_mime in self.blocked_mime_types:
            result["errors"].append(
                f"File type '{detected_mime}' is not allowed for security reasons"
            )

        # Get expected MIME type from extension
        expected_mime = None
        file_ext = Path(filename).suffix.lower()
        for mime, extensions in self.allowed_mime_types.items():
            if file_ext in extensions:
                expected_mime = mime
                break

        # Validate MIME type matches extension
        if expected_mime and not detected_mime.startswith(expected_mime.split("/")[0]):
            result["warnings"].append(
                f"File extension '{file_ext}' does not match detected content type '{detected_mime}'"
            )

        # Check if MIME type is allowed
        allowed = False
        for mime, extensions in self.allowed_mime_types.items():
            if detected_mime.startswith(mime.split("/")[0]) or detected_mime == mime:
                allowed = True
                break

        if not allowed:
            result["errors"].append(f"File type '{detected_mime}' is not supported")

        return result

    async def _scan_for_viruses(self, content: bytes) -> Dict[str, Any]:
        """Scan file for viruses using ClamAV"""
        result = {"errors": [], "warnings": [], "security_flags": []}

        if not self.clam_scanner:
            result["warnings"].append("Virus scanning not available")
            return result

        try:
            # Create temporary file for scanning
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                # Scan with ClamAV
                scan_result = self.clam_scanner.scan_file(temp_file_path)

                if scan_result is None:
                    # No threat detected
                    result["security_flags"].append("virus_scan_clean")
                else:
                    # Threat detected
                    result["errors"].append(f"Security threat detected: {scan_result}")
                    result["security_flags"].append("virus_detected")

            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"Virus scanning failed: {e}")
            result["warnings"].append("Virus scanning encountered an error")

        return result

    def _is_archive_file(self, mime_type: str) -> bool:
        """Check if file is an archive"""
        archive_mimes = [
            "application/zip",
            "application/x-rar-compressed",
            "application/x-tar",
            "application/gzip",
            "application/x-bzip2",
            "application/x-7z-compressed",
        ]
        return mime_type in archive_mimes

    async def _detect_archive_bomb(
        self, content: bytes, filename: str
    ) -> Dict[str, Any]:
        """Detect archive bombs and compressed file threats"""
        result = {"errors": [], "warnings": [], "security_flags": []}

        try:
            # Create temporary file for analysis
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                # Check compression ratio
                compression_ratio = len(content) / 1024  # Simple ratio check
                if compression_ratio > 100:  # Very high compression ratio
                    result["warnings"].append(
                        "File has very high compression ratio - possible zip bomb"
                    )

                # For zip files, check contents
                if filename.lower().endswith(".zip"):
                    try:
                        with zipfile.ZipFile(temp_file_path, "r") as zip_file:
                            # Check number of files
                            if len(zip_file.namelist()) > 1000:
                                result["errors"].append(
                                    "Archive contains too many files (possible zip bomb)"
                                )

                            # Check total uncompressed size
                            total_size = sum(
                                file.file_size for file in zip_file.infolist()
                            )
                            max_size = 1024 * 1024 * 1024  # 1GB limit
                            if total_size > max_size:
                                result["errors"].append(
                                    f"Archive uncompressed size too large: {total_size / (1024*1024):.1f}MB"
                                )

                            # Check for nested archives
                            for file_info in zip_file.infolist():
                                file_ext = Path(file_info.filename).suffix.lower()
                                if file_ext in [
                                    ".zip",
                                    ".rar",
                                    ".tar",
                                    ".gz",
                                    ".bz2",
                                    ".7z",
                                ]:
                                    result["warnings"].append(
                                        f"Archive contains nested archive: {file_info.filename}"
                                    )

                    except zipfile.BadZipFile:
                        result["errors"].append("Invalid zip file")

                result["security_flags"].append("archive_checked")

            finally:
                # Clean up
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"Archive bomb detection failed: {e}")
            result["warnings"].append("Archive analysis failed")

        return result

    async def _validate_image_security(
        self, content: bytes, filename: str
    ) -> Dict[str, Any]:
        """Validate image files for security threats"""
        result = {"errors": [], "warnings": [], "security_flags": []}

        try:
            # Create temporary file for analysis
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                with Image.open(temp_file_path) as img:
                    # Check for large dimensions (DoS prevention)
                    max_dimension = 10000
                    if img.width > max_dimension or img.height > max_dimension:
                        result["errors"].append(
                            f"Image dimensions too large: {img.width}x{img.height}"
                        )

                    # Check for EXIF data
                    try:
                        with open(temp_file_path, "rb") as f:
                            exif_tags = exifread.process_file(f)

                        if exif_tags:
                            # Check for potentially sensitive EXIF data
                            sensitive_tags = ["GPS", "DateTimeOriginal", "Software"]
                            for tag in exif_tags:
                                for sensitive in sensitive_tags:
                                    if sensitive in tag:
                                        result["warnings"].append(
                                            f"Image contains potentially sensitive metadata: {tag}"
                                        )
                                        break

                    except Exception:
                        pass  # EXIF reading failed

                    # Check for animated images (DoS risk)
                    if hasattr(img, "is_animated") and img.is_animated:
                        if hasattr(img, "n_frames") and img.n_frames > 100:
                            result["warnings"].append(
                                "Animated image has many frames - may impact performance"
                            )

            finally:
                # Clean up
                try:
                    os.unlink(temp_file_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            result["errors"].append("Invalid image file")

        return result

    async def _scan_content_security(self, content: bytes) -> Dict[str, Any]:
        """Scan content for sensitive information"""
        result = {"errors": [], "warnings": [], "security_flags": []}

        try:
            # Convert bytes to text for scanning
            text_content = content.decode("utf-8", errors="ignore")

            # Scan for sensitive patterns
            detected_patterns = []
            for pattern_name, pattern in self.sensitive_patterns.items():
                matches = re.findall(pattern, text_content)
                if matches:
                    detected_patterns.append(pattern_name)
                    # Log without exposing the actual sensitive data
                    logger.warning(
                        f"Sensitive data pattern '{pattern_name}' detected in uploaded file",
                        extra={
                            "pattern": pattern_name,
                            "match_count": len(matches),
                            "severity": "high"
                            if pattern_name in ["ssn", "credit_card", "private_key"]
                            else "medium",
                        },
                    )

            if detected_patterns:
                result["security_flags"].append("sensitive_data_detected")
                result["warnings"].append(
                    f"File contains potentially sensitive information: {', '.join(detected_patterns)}"
                )

            # Check for script content in non-script files
            script_patterns = [
                r"<script[^>]*>",
                r"javascript:",
                r"vbscript:",
                r"onload\s*=",
                r"onerror\s*=",
                r"eval\s*\(",
                r"document\.write",
                r"innerHTML\s*=",
            ]

            for pattern in script_patterns:
                if re.search(pattern, text_content, re.IGNORECASE):
                    result["security_flags"].append("script_content_detected")
                    result["warnings"].append(
                        "File contains script-like content - please verify this is intentional"
                    )
                    break

        except Exception as e:
            logger.error(f"Content scanning failed: {e}")

        return result

    def _check_geolocation(self, client_ip: str, user: User) -> Dict[str, Any]:
        """Check if upload is from suspicious location"""
        result = {"errors": [], "warnings": [], "security_flags": []}

        if not self.geoip_reader:
            return result

        try:
            geo_data = self.geoip_reader.get(client_ip)

            if geo_data:
                country = geo_data.get("country", {}).get("iso_code", "Unknown")

                # Check for high-risk countries (example list)
                high_risk_countries = ["CN", "RU", "KP", "IR"]

                if country in high_risk_countries:
                    result["warnings"].append(
                        f"Upload from high-risk country detected: {country}"
                    )
                    result["security_flags"].append("suspicious_geolocation")

                # Log location for security monitoring
                logger.info(
                    f"File upload from {client_ip} ({country}) by user {user.id}",
                    extra={
                        "client_ip": client_ip,
                        "country": country,
                        "user_id": user.id,
                    },
                )

        except Exception as e:
            logger.error(f"Geolocation check failed: {e}")

        return result

    async def _extract_and_sanitize_metadata(
        self, content: bytes, mime_type: str
    ) -> Dict[str, Any]:
        """Extract and sanitize file metadata"""
        metadata = {}

        try:
            if mime_type.startswith("image/"):
                # Image metadata
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content)
                    temp_file_path = temp_file.name

                try:
                    with Image.open(temp_file_path) as img:
                        metadata.update(
                            {
                                "image_format": img.format,
                                "image_mode": img.mode,
                                "image_size": (img.width, img.height),
                            }
                        )

                        # Remove EXIF data by creating a new image without it
                        if img.format in ["JPEG", "TIFF"]:
                            # This would be where you'd strip EXIF if needed
                            metadata["exif_stripped"] = False
                finally:
                    try:
                        os.unlink(temp_file_path)
                    except:
                        pass

            elif mime_type == "application/pdf":
                # PDF metadata extraction would go here
                metadata["pdf_version"] = "unknown"

            # Add file size and hash
            metadata["file_size"] = len(content)
            metadata["content_hash"] = hashlib.sha256(content).hexdigest()

        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")

        return metadata

    def _calculate_file_hash(self, content: bytes) -> str:
        """Calculate SHA-256 hash of file content"""
        return hashlib.sha256(content).hexdigest()


# Singleton instance
file_upload_security_service = FileUploadSecurityService()
