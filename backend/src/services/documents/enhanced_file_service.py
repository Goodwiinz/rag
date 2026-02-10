"""
Enhanced File Service with advanced validation, security scanning, and storage management
"""

import asyncio
import hashlib
import logging
import mimetypes
import os
import struct
import tarfile
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

import aiofiles
import magic
from fastapi import Depends, HTTPException, UploadFile, status
from PIL import Image
from pypdf import PdfReader
from sqlalchemy.orm import Session

# ClamAV integration - only available if properly configured
try:
    import pyclamd

    CLAMD_AVAILABLE = True
except ImportError:
    CLAMD_AVAILABLE = False

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.organization import Organization
from src.models.processing import JobPriority, JobStatus, JobType, ProcessingJob
from src.models.user import User, UserRole

logger = logging.getLogger(__name__)


class EnhancedFileValidationError(Exception):
    """Enhanced file validation related errors"""

    pass


class SecurityScanError(Exception):
    """Security scanning related errors"""

    pass


class FileStorageError(Exception):
    """File storage related errors"""

    pass


class FileIntegrityError(Exception):
    """File integrity related errors"""

    pass


class SecurityThreat:
    """Represents a security threat detected during scanning"""

    def __init__(
        self, threat_type: str, description: str, severity: str, location: str = None
    ):
        self.threat_type = threat_type
        self.description = description
        self.severity = severity  # low, medium, high, critical
        self.location = location
        self.detected_at = datetime.utcnow()


class EnhancedFileService:
    """Enhanced service for handling file uploads, validation, and security scanning"""

    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Security scan configuration
        # Use standard ClamAV socket locations, configurable via settings
        import os
        default_socket = os.environ.get("CLAMD_SOCKET", "/var/run/clamav/clamd.sock")
        self.clamd_socket = getattr(settings, "CLAMD_SOCKET", default_socket)
        self.max_scan_size_mb = getattr(settings, "MAX_VIRUS_SCAN_SIZE_MB", 100)

        # File validation configuration
        self.allowed_mime_types = {
            # Documents
            "text/plain",
            "text/csv",
            "text/markdown",
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            # Images
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/bmp",
            "image/tiff",
            "image/webp",
            # Audio
            "audio/mpeg",
            "audio/wav",
            "audio/ogg",
            "audio/flac",
            "audio/aac",
            # Video
            "video/mp4",
            "video/avi",
            "video/mkv",
            "video/mov",
            "video/wmv",
            "video/webm",
            # Archives
            "application/zip",
            "application/x-tar",
            "application/x-rar-compressed",
        }

        # Create subdirectories
        self.create_subdirectories()

    def create_subdirectories(self):
        """Create subdirectories for different file types and security"""
        subdirs = [
            "documents",
            "images",
            "audio",
            "video",
            "archives",
            "temp",
            "processed",
            "quarantine",
            "scanning",
        ]

        for subdir in subdirs:
            (self.upload_dir / subdir).mkdir(parents=True, exist_ok=True)

    async def validate_and_scan_file(
        self, file: UploadFile, user: User, organization: Organization
    ) -> Dict[str, Any]:
        """
        Comprehensive file validation and security scanning
        """
        try:
            # Step 1: Basic validation
            basic_validation = await self.perform_basic_validation(
                file, user, organization
            )

            # Step 2: Security scanning
            security_scan = await self.perform_security_scan(file, basic_validation)

            # Step 3: File integrity check
            integrity_check = await self.verify_file_integrity(file, basic_validation)

            return {
                "basic_validation": basic_validation,
                "security_scan": security_scan,
                "integrity_check": integrity_check,
                "validation_timestamp": datetime.utcnow(),
                "validation_status": "passed"
                if not security_scan["virus_detected"]
                else "failed",
            }

        except Exception as e:
            logger.error(f"File validation and scanning failed: {str(e)}")
            raise EnhancedFileValidationError(f"Validation failed: {str(e)}")

    async def perform_basic_validation(
        self, file: UploadFile, user: User, organization: Organization
    ) -> Dict[str, Any]:
        """Perform basic file validation"""

        # Get file size
        if hasattr(file, "size") and file.size:
            file_size = file.size
        else:
            # Read content to get size if not available
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset position

        # Check file size limits
        if file_size > organization.max_file_size_bytes:
            raise EnhancedFileValidationError(
                f"File size ({file_size} bytes) exceeds maximum allowed size "
                f"({organization.max_file_size_bytes} bytes)"
            )

        # Check storage quota
        if not organization.can_upload_file(file_size):
            raise EnhancedFileValidationError(
                f"Insufficient storage quota. Available: "
                f"{organization.storage_available_gb:.2f}GB"
            )

        # Read content for type detection
        file_content = file.file.read(min(file_size, 8192))  # Read first 8KB
        file.file.seek(0)  # Reset position

        # Detect MIME type using python-magic
        try:
            detected_mime_type = magic.from_buffer(file_content, mime=True)
        except (OSError, ValueError) as e:
            logger.debug(f"Magic MIME detection failed, falling back to mimetypes: {e}")
            detected_mime_type = mimetypes.guess_type(file.filename)[0]

        # Validate MIME type
        if detected_mime_type not in self.allowed_mime_types:
            raise EnhancedFileValidationError(
                f"File type '{detected_mime_type}' is not allowed"
            )

        # Determine document type
        document_type = self.get_document_type(file.filename, detected_mime_type)

        # Check for suspicious patterns in filename
        if self.is_suspicious_filename(file.filename):
            raise EnhancedFileValidationError(
                "Filename contains suspicious characters or patterns"
            )

        return {
            "file_size": file_size,
            "detected_mime_type": detected_mime_type,
            "document_type": document_type,
            "filename_validation": "passed",
            "size_validation": "passed",
        }

    async def perform_security_scan(
        self, file: UploadFile, validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform comprehensive security scanning"""

        threats = []
        warnings = []
        virus_detected = False

        try:
            # Save temporary file for scanning
            temp_file_path = await self.save_temp_file(file)

            try:
                # Step 1: ClamAV virus scanning (if available)
                if CLAMD_AVAILABLE:
                    clamav_result = await self.scan_with_clamav(temp_file_path)
                    if clamav_result["infected"]:
                        virus_detected = True
                        threats.extend(clamav_result["threats"])
                else:
                    logger.warning("ClamAV not available, skipping virus scan")

                # Step 2: Content analysis for suspicious patterns
                content_analysis = await self.analyze_content_for_threats(
                    temp_file_path, validation_result
                )
                threats.extend(content_analysis["threats"])
                warnings.extend(content_analysis["warnings"])

                # Step 3: Archive bomb detection
                if validation_result["detected_mime_type"] in [
                    "application/zip",
                    "application/x-tar",
                ]:
                    archive_analysis = await self.analyze_archive_safety(temp_file_path)
                    if archive_analysis["is_bomb"]:
                        threats.append(
                            SecurityThreat(
                                threat_type="archive_bomb",
                                description="Potential zip bomb detected",
                                severity="high",
                                location="archive_structure",
                            )
                        )

                # Step 4: Metadata analysis for suspicious content
                metadata_analysis = await self.analyze_metadata_for_threats(
                    temp_file_path, validation_result
                )
                warnings.extend(metadata_analysis["warnings"])

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

            return {
                "virus_detected": virus_detected,
                "threats": [
                    {
                        "type": threat.threat_type,
                        "description": threat.description,
                        "severity": threat.severity,
                        "location": threat.location,
                        "detected_at": threat.detected_at.isoformat(),
                    }
                    for threat in threats
                ],
                "warnings": warnings,
                "scan_timestamp": datetime.utcnow(),
                "scan_status": "completed",
            }

        except Exception as e:
            logger.error(f"Security scan failed: {str(e)}")
            raise SecurityScanError(f"Security scanning failed: {str(e)}")

    async def scan_with_clamav(self, file_path: str) -> Dict[str, Any]:
        """Scan file with ClamAV"""
        try:
            if not CLAMD_AVAILABLE:
                return {
                    "infected": False,
                    "threats": [],
                    "error": "ClamAV not available",
                }

            cd = pyclamd.ClamdUnixSocket()

            # Check if ClamAV is available
            if not cd.ping():
                logger.warning("ClamAV daemon is not running, skipping virus scan")
                return {"infected": False, "threats": []}

            # Perform scan
            scan_result = cd.scan_file(file_path)

            if scan_result is None:
                # No threats found
                return {"infected": False, "threats": []}
            elif scan_result[file_path][0] == "FOUND":
                # Virus found
                threat_name = scan_result[file_path][1]
                return {
                    "infected": True,
                    "threats": [
                        SecurityThreat(
                            threat_type="virus",
                            description=f"Virus detected: {threat_name}",
                            severity="critical",
                            location=file_path,
                        )
                    ],
                }
            else:
                return {"infected": False, "threats": []}

        except Exception as e:
            logger.error(f"ClamAV scan failed: {str(e)}")
            return {"infected": False, "threats": [], "error": str(e)}

    async def analyze_content_for_threats(
        self, file_path: str, validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze file content for suspicious patterns"""
        threats = []
        warnings = []

        try:
            # Read file content for analysis
            with open(file_path, "rb") as f:
                content = f.read(min(1024 * 1024, 10 * 1024 * 1024))  # Read max 10MB

            # Check for common malware signatures
            malware_signatures = [
                b"eval(base64_decode",
                b"shell_exec",
                b"passthru",
                b"system(",
                b"exec(",
                b"<script",
                b"javascript:",
                b"vbscript:",
            ]

            content_lower = content.lower()
            for signature in malware_signatures:
                if signature in content_lower:
                    threats.append(
                        SecurityThreat(
                            threat_type="suspicious_code",
                            description=f"Suspicious code pattern detected: {signature.decode('utf-8', errors='ignore')}",
                            severity="medium",
                            location="content_analysis",
                        )
                    )

            # Check for suspicious file headers
            if self.is_suspicious_file_header(content):
                warnings.append("File header appears suspicious")

            # Check for encrypted/obfuscated content
            high_entropy = self.calculate_entropy(content) > 7.0
            if high_entropy:
                warnings.append(
                    "File has high entropy, possibly encrypted or obfuscated"
                )

        except Exception as e:
            logger.error(f"Content analysis failed: {str(e)}")
            warnings.append(f"Content analysis failed: {str(e)}")

        return {"threats": threats, "warnings": warnings}

    async def analyze_archive_safety(self, file_path: str) -> Dict[str, Any]:
        """Analyze archive for zip bomb or other safety issues"""
        try:
            if file_path.endswith(".zip"):
                return await self.analyze_zip_safety(file_path)
            elif file_path.endswith((".tar", ".tar.gz", ".tgz")):
                return await self.analyze_tar_safety(file_path)
            else:
                return {"is_bomb": False, "compression_ratio": 1.0}

        except Exception as e:
            logger.error(f"Archive analysis failed: {str(e)}")
            return {"is_bomb": False, "error": str(e)}

    async def analyze_zip_safety(self, file_path: str) -> Dict[str, Any]:
        """Analyze ZIP file for zip bomb"""
        try:
            with zipfile.ZipFile(file_path, "r") as zip_file:
                total_size = 0
                max_file_size = 0

                for info in zip_file.infolist():
                    file_size = info.file_size
                    compressed_size = info.compress_size

                    # Check for extremely high compression ratio
                    if file_size > 0:
                        compression_ratio = file_size / compressed_size
                        if compression_ratio > 1000:  # Very high compression ratio
                            return {
                                "is_bomb": True,
                                "compression_ratio": compression_ratio,
                            }

                    total_size += file_size
                    max_file_size = max(max_file_size, file_size)

                    # Check for path traversal attempts
                    if ".." in info.filename or info.filename.startswith("/"):
                        return {"is_bomb": True, "reason": "path_traversal"}

                # Check total uncompressed size
                if total_size > 1024 * 1024 * 1024:  # 1GB
                    return {"is_bomb": True, "reason": "excessive_size"}

                compression_ratio = (
                    total_size / os.path.getsize(file_path)
                    if os.path.getsize(file_path) > 0
                    else 1.0
                )

                return {"is_bomb": False, "compression_ratio": compression_ratio}

        except Exception as e:
            logger.error(f"ZIP analysis failed: {str(e)}")
            return {"is_bomb": False, "error": str(e)}

    async def analyze_tar_safety(self, file_path: str) -> Dict[str, Any]:
        """Analyze TAR file for safety issues"""
        try:
            with tarfile.open(file_path, "r:*") as tar_file:
                total_size = 0

                for member in tar_file:
                    # Check for path traversal attempts
                    if ".." in member.name or member.name.startswith("/"):
                        return {"is_bomb": True, "reason": "path_traversal"}

                    total_size += member.size

                    # Check for excessive size
                    if total_size > 1024 * 1024 * 1024:  # 1GB
                        return {"is_bomb": True, "reason": "excessive_size"}

                return {"is_bomb": False, "total_size": total_size}

        except Exception as e:
            logger.error(f"TAR analysis failed: {str(e)}")
            return {"is_bomb": False, "error": str(e)}

    async def analyze_metadata_for_threats(
        self, file_path: str, validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze file metadata for suspicious content"""
        warnings = []

        try:
            document_type = validation_result["document_type"]

            if document_type == DocumentType.PDF:
                warnings.extend(await self.analyze_pdf_metadata(file_path))
            elif document_type == DocumentType.IMAGE:
                warnings.extend(await self.analyze_image_metadata(file_path))
            elif document_type in [
                DocumentType.TEXT,
                DocumentType.SPREADSHEET,
                DocumentType.PRESENTATION,
            ]:
                warnings.extend(
                    await self.analyze_document_metadata(file_path, document_type)
                )

        except Exception as e:
            logger.error(f"Metadata analysis failed: {str(e)}")
            warnings.append(f"Metadata analysis failed: {str(e)}")

        return {"warnings": warnings}

    async def analyze_pdf_metadata(self, file_path: str) -> List[str]:
        """Analyze PDF metadata for suspicious content"""
        warnings = []

        try:
            with open(file_path, "rb") as file:
                pdf_reader = PdfReader(file)

                if pdf_reader.metadata:
                    # Check for suspicious metadata
                    title = pdf_reader.metadata.get("/Title", "")
                    author = pdf_reader.metadata.get("/Author", "")
                    creator = pdf_reader.metadata.get("/Creator", "")

                    suspicious_strings = [
                        "hack",
                        "exploit",
                        "malware",
                        "virus",
                        "payload",
                    ]

                    for field_value in [title, author, creator]:
                        if any(
                            sus in field_value.lower() for sus in suspicious_strings
                        ):
                            warnings.append(f"Suspicious content found in PDF metadata")
                            break

                # Check for excessive number of pages (potential DoS)
                if len(pdf_reader.pages) > 10000:
                    warnings.append("PDF has excessive number of pages")

        except Exception as e:
            logger.error(f"PDF metadata analysis failed: {str(e)}")

        return warnings

    async def analyze_image_metadata(self, file_path: str) -> List[str]:
        """Analyze image metadata for suspicious content"""
        warnings = []

        try:
            with Image.open(file_path) as img:
                # Check for suspicious dimensions
                if img.width > 50000 or img.height > 50000:
                    warnings.append("Image has extremely large dimensions")

                # Check for excessive file size for the dimensions
                file_size = os.path.getsize(file_path)
                estimated_size = img.width * img.height * 3  # Rough estimate for RGB

                if file_size > estimated_size * 10:  # Much larger than expected
                    warnings.append("Image file size is suspiciously large")

        except Exception as e:
            logger.error(f"Image metadata analysis failed: {str(e)}")

        return warnings

    async def analyze_document_metadata(
        self, file_path: str, document_type: DocumentType
    ) -> List[str]:
        """Analyze document metadata for suspicious content"""
        warnings = []

        try:
            # Basic file analysis
            file_size = os.path.getsize(file_path)

            # Check for suspicious file names or extensions
            suspicious_extensions = [".exe", ".bat", ".cmd", ".scr", ".pif", ".com"]
            filename = os.path.basename(file_path)

            if any(filename.lower().endswith(ext) for ext in suspicious_extensions):
                warnings.append("File has suspicious extension")

            # Check for files that are too small to be valid
            if file_size < 10:
                warnings.append("File is suspiciously small")

        except Exception as e:
            logger.error(f"Document metadata analysis failed: {str(e)}")

        return warnings

    async def verify_file_integrity(
        self, file: UploadFile, validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify file integrity"""
        try:
            # Save temporary file for integrity checks
            temp_file_path = await self.save_temp_file(file)

            try:
                # Calculate file hash
                file_hash = self.calculate_file_hash(temp_file_path)

                # Verify file structure
                structure_valid = await self.verify_file_structure(
                    temp_file_path, validation_result
                )

                # Check for corruption
                corruption_check = await self.check_file_corruption(
                    temp_file_path, validation_result
                )

                return {
                    "file_hash": file_hash,
                    "structure_valid": structure_valid,
                    "corruption_check": corruption_check,
                    "integrity_status": "passed"
                    if structure_valid and not corruption_check
                    else "failed",
                }

            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

        except Exception as e:
            logger.error(f"File integrity verification failed: {str(e)}")
            raise FileIntegrityError(f"Integrity verification failed: {str(e)}")

    async def verify_file_structure(
        self, file_path: str, validation_result: Dict[str, Any]
    ) -> bool:
        """Verify file structure based on type"""
        try:
            document_type = validation_result["document_type"]
            detected_mime_type = validation_result["detected_mime_type"]

            if document_type == DocumentType.PDF:
                return self.verify_pdf_structure(file_path)
            elif document_type == DocumentType.IMAGE:
                return self.verify_image_structure(file_path)
            elif document_type in [
                DocumentType.TEXT,
                DocumentType.SPREADSHEET,
                DocumentType.PRESENTATION,
            ]:
                return self.verify_document_structure(file_path, detected_mime_type)
            else:
                return True  # Default to valid for unknown types

        except Exception as e:
            logger.error(f"File structure verification failed: {str(e)}")
            return False

    def verify_pdf_structure(self, file_path: str) -> bool:
        """Verify PDF file structure"""
        try:
            with open(file_path, "rb") as file:
                # Check PDF header
                header = file.read(4)
                if header != b"%PDF":
                    return False

                # Try to read with PyPDF2
                file.seek(0)
                pdf_reader = PdfReader(file)

                # Check if we can read pages
                if len(pdf_reader.pages) == 0:
                    return False

                return True

        except Exception as e:
            logger.error(f"PDF structure verification failed: {str(e)}")
            return False

    def verify_image_structure(self, file_path: str) -> bool:
        """Verify image file structure"""
        try:
            with Image.open(file_path) as img:
                # Try to load the image
                img.verify()
                return True

        except Exception as e:
            logger.error(f"Image structure verification failed: {str(e)}")
            return False

    def verify_document_structure(self, file_path: str, mime_type: str) -> bool:
        """Verify document file structure"""
        try:
            # Basic structure checks
            file_size = os.path.getsize(file_path)

            if file_size == 0:
                return False

            # Check for common document headers
            with open(file_path, "rb") as file:
                header = file.read(8)

                # Office documents
                if mime_type in [
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ]:
                    return header.startswith(b"PK\x03\x04")  # ZIP header

                # Old Office documents
                elif mime_type in [
                    "application/msword",
                    "application/vnd.ms-excel",
                    "application/vnd.ms-powerpoint",
                ]:
                    return header.startswith(
                        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
                    )  # OLE header

            return True

        except Exception as e:
            logger.error(f"Document structure verification failed: {str(e)}")
            return False

    async def check_file_corruption(
        self, file_path: str, validation_result: Dict[str, Any]
    ) -> bool:
        """Check for file corruption"""
        try:
            document_type = validation_result["document_type"]

            if document_type == DocumentType.PDF:
                return not self.is_pdf_corrupted(file_path)
            elif document_type == DocumentType.IMAGE:
                return not self.is_image_corrupted(file_path)
            else:
                return False  # Assume not corrupted for other types

        except Exception as e:
            logger.error(f"File corruption check failed: {str(e)}")
            return True  # Assume corrupted on error

    def is_pdf_corrupted(self, file_path: str) -> bool:
        """Check if PDF is corrupted"""
        try:
            with open(file_path, "rb") as file:
                pdf_reader = PdfReader(file)
                # Try to extract text from first page
                if len(pdf_reader.pages) > 0:
                    pdf_reader.pages[0].extract_text()
                return False
        except (IOError, OSError, ValueError, Exception) as e:
            logger.warning(f"PDF file appears corrupted: {file_path}, error: {e}")
            return True

    def is_image_corrupted(self, file_path: str) -> bool:
        """Check if image is corrupted"""
        try:
            with Image.open(file_path) as img:
                img.load()  # Load image data
                return False
        except (IOError, OSError, ValueError) as e:
            logger.warning(f"Image file appears corrupted: {file_path}, error: {e}")
            return True

    async def save_temp_file(self, file: UploadFile) -> str:
        """Save file temporarily for scanning"""
        temp_dir = self.upload_dir / "temp"
        temp_file_path = temp_dir / f"temp_{uuid.uuid4().hex}"

        async with aiofiles.open(temp_file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # Reset file position
        file.file.seek(0)

        return str(temp_file_path)

    def get_document_type(self, filename: str, mime_type: str) -> DocumentType:
        """Determine document type based on filename and MIME type"""
        if mime_type.startswith("text/"):
            return DocumentType.TEXT
        elif mime_type.startswith("image/"):
            return DocumentType.IMAGE
        elif mime_type.startswith("audio/"):
            return DocumentType.AUDIO
        elif mime_type.startswith("video/"):
            return DocumentType.VIDEO
        elif mime_type == "application/pdf":
            return DocumentType.PDF
        elif mime_type in [
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        ]:
            return DocumentType.SPREADSHEET
        elif mime_type in [
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        ]:
            return DocumentType.PRESENTATION
        else:
            return DocumentType.MULTIMODAL

    def is_suspicious_filename(self, filename: str) -> bool:
        """Check if filename is suspicious"""
        suspicious_patterns = [
            "..",
            "\\",
            "/",
            ":",
            "*",
            "?",
            '"',
            "<",
            ">",
            "|",
            "con",
            "prn",
            "aux",
            "nul",
            "com1",
            "com2",
            "com3",
            "com4",
            "com5",
            "com6",
            "com7",
            "com8",
            "com9",
            "lpt1",
            "lpt2",
            "lpt3",
            "lpt4",
            "lpt5",
            "lpt6",
            "lpt7",
            "lpt8",
            "lpt9",
        ]

        filename_lower = filename.lower()
        return any(pattern in filename_lower for pattern in suspicious_patterns)

    def is_suspicious_file_header(self, content: bytes) -> bool:
        """Check if file header is suspicious"""
        suspicious_headers = [
            b"MZ",  # Windows executable
            b"\x7fELF",  # Linux executable
            b"\xca\xfe\xba\xbe",  # Java class
            b"#!",  # Script files
        ]

        return any(content.startswith(header) for header in suspicious_headers)

    def calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data"""
        if not data:
            return 0.0

        # Count byte frequencies
        byte_counts = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1

        # Calculate entropy
        entropy = 0.0
        data_len = len(data)

        for count in byte_counts.values():
            probability = count / data_len
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)

        return entropy

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    async def upload_file(
        self,
        file: UploadFile,
        title: str,
        description: Optional[str],
        user: User,
        organization: Organization,
        tags: List[str],
        is_public: bool,
        custom_metadata: Dict[str, Any],
        validation_result: Dict[str, Any],
    ) -> Document:
        """Process and store uploaded file with enhanced validation"""
        try:
            # Generate file path
            file_path = self.generate_file_path(
                validation_result["basic_validation"]["document_type"],
                str(organization.id),
            )

            # Add original extension to file path
            original_ext = Path(file.filename).suffix
            file_path_with_ext = f"{file_path}{original_ext}"

            # Save file
            saved_path = await self.save_file_permanently(file, file_path_with_ext)

            # Calculate file hash
            file_hash = self.calculate_file_hash(saved_path)

            # Create document record
            document = Document(
                title=title,
                filename=file.filename,
                file_path=saved_path,
                file_size_bytes=validation_result["basic_validation"]["file_size"],
                mime_type=validation_result["basic_validation"]["detected_mime_type"],
                document_type=validation_result["basic_validation"]["document_type"],
                processing_status=ProcessingStatus.PENDING,
                is_public=is_public,
                tags=tags,
                organization_id=organization.id,
                uploaded_by_user_id=user.id,
            )

            # Add metadata
            document.add_metadata("file_hash", file_hash)
            document.add_metadata("original_filename", file.filename)
            document.add_metadata("security_scan", validation_result["security_scan"])
            document.add_metadata(
                "integrity_check", validation_result["integrity_check"]
            )
            document.add_metadata("custom_metadata", custom_metadata)

            if description:
                document.add_metadata("description", description)

            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)

            # Update organization storage usage
            organization.update_storage_usage(
                validation_result["basic_validation"]["file_size"]
            )
            self.db.commit()

            return document

        except Exception as e:
            self.db.rollback()
            raise FileStorageError(f"Failed to upload file: {str(e)}")

    def generate_file_path(
        self, document_type: DocumentType, organization_id: str
    ) -> str:
        """Generate unique file path for uploaded file"""
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())

        type_dir = {
            DocumentType.TEXT: "documents",
            DocumentType.PDF: "documents",
            DocumentType.SPREADSHEET: "documents",
            DocumentType.PRESENTATION: "documents",
            DocumentType.IMAGE: "images",
            DocumentType.AUDIO: "audio",
            DocumentType.VIDEO: "video",
            DocumentType.MULTIMODAL: "documents",
        }

        directory = type_dir.get(document_type, "documents")
        filename = f"{timestamp}_{unique_id}"

        return str(self.upload_dir / directory / f"{organization_id}" / filename)

    async def save_file_permanently(self, file: UploadFile, file_path: str) -> str:
        """Save uploaded file to permanent storage"""
        try:
            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

            # Save file asynchronously
            async with aiofiles.open(file_path, "wb") as f:
                content = await file.read()
                await f.write(content)

            return file_path

        except Exception as e:
            # Clean up on failure
            if os.path.exists(file_path):
                os.remove(file_path)
            raise FileStorageError(f"Failed to save file: {str(e)}")

    async def rescan_file_security(self, document: Document) -> Dict[str, Any]:
        """Rescan document for security threats"""
        try:
            # Read file content
            with open(document.file_path, "rb") as f:
                content = f.read()

            # This is a simplified implementation
            # In practice, you'd create a proper UploadFile wrapper
            class TempUploadFile:
                def __init__(self, filename: str, content: bytes):
                    self.filename = filename
                    self.content = content
                    self.size = len(content)

                async def read(self):
                    return self.content

            temp_file = TempUploadFile(document.filename, content)

            # Perform validation and scanning
            validation_result = await self.validate_and_scan_file(
                file=temp_file,
                user=document.uploaded_by_user,
                organization=document.organization,
            )

            # Update document metadata with new scan results
            document.add_metadata(
                "last_security_scan", validation_result["security_scan"]
            )
            document.add_metadata("last_scan_timestamp", datetime.utcnow().isoformat())

            self.db.commit()

            return validation_result["security_scan"]

        except Exception as e:
            logger.error(f"Security rescan failed: {str(e)}")
            raise SecurityScanError(f"Security rescan failed: {str(e)}")


# Dependency injection
def get_enhanced_file_service(db: Session = Depends(get_db)) -> EnhancedFileService:
    """Get enhanced file service instance"""
    return EnhancedFileService(db)
