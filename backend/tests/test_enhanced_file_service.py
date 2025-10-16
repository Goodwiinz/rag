"""
Unit tests for Enhanced File Service
"""

import pytest
import tempfile
import os
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from src.services.enhanced_file_service import (
    EnhancedFileService,
    EnhancedFileValidationError,
    SecurityScanError,
    FileStorageError,
    SecurityThreat
)
from src.models.user import User, UserRole
from src.models.organization import Organization
from src.models.document import DocumentType

class TestEnhancedFileService:
    """Test suite for EnhancedFileService"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def file_service(self, mock_db):
        """Create EnhancedFileService instance with mocked database"""
        with patch('src.services.enhanced_file_service.settings'):
            service = EnhancedFileService(mock_db)
            service.upload_dir = Path(tempfile.mkdtemp())
            service.upload_dir.mkdir(parents=True, exist_ok=True)
            service.create_subdirectories()
            yield service
            # Cleanup
            import shutil
            try:
                shutil.rmtree(service.upload_dir)
            except OSError:
                pass  # Ignore cleanup errors

    @pytest.fixture
    def mock_user(self):
        """Mock user"""
        user = Mock(spec=User)
        user.id = "test-user-id"
        user.has_permission.return_value = True
        return user

    @pytest.fixture
    def mock_organization(self):
        """Mock organization"""
        org = Mock(spec=Organization)
        org.id = "test-org-id"
        org.max_file_size_bytes = 10 * 1024 * 1024  # 10MB
        org.can_upload_file.return_value = True
        org.storage_available_gb = 100.0
        return org

    @pytest.fixture
    def mock_upload_file(self):
        """Mock upload file"""
        file = Mock()
        file.filename = "test_document.pdf"
        file.size = 1024 * 1024  # 1MB
        file.file = Mock()
        file.file.read = AsyncMock(return_value=b"mock file content")
        file.file.seek = Mock()
        return file

    class TestFileValidation:
        """Test file validation methods"""

        @pytest.mark.asyncio
        async def test_perform_basic_validation_success(self, file_service, mock_upload_file, mock_user, mock_organization):
            """Test successful basic file validation"""
            result = await file_service.perform_basic_validation(
                mock_upload_file, mock_user, mock_organization
            )

            assert result["file_size"] == 1024 * 1024
            assert result["detected_mime_type"] is not None
            assert result["document_type"] in DocumentType
            assert result["filename_validation"] == "passed"
            assert result["size_validation"] == "passed"

        @pytest.mark.asyncio
        async def test_basic_validation_file_too_large(self, file_service, mock_upload_file, mock_user, mock_organization):
            """Test validation with file exceeding size limit"""
            mock_organization.max_file_size_bytes = 500 * 1024  # 500KB
            mock_upload_file.size = 1024 * 1024  # 1MB

            with pytest.raises(EnhancedFileValidationError, match="File size .* exceeds maximum"):
                await file_service.perform_basic_validation(mock_upload_file, mock_user, mock_organization)

        @pytest.mark.asyncio
        async def test_basic_validation_insufficient_quota(self, file_service, mock_upload_file, mock_user, mock_organization):
            """Test validation with insufficient storage quota"""
            mock_organization.can_upload_file.return_value = False

            with pytest.raises(EnhancedFileValidationError, match="Insufficient storage quota"):
                await file_service.perform_basic_validation(mock_upload_file, mock_user, mock_organization)

        @pytest.mark.asyncio
        async def test_basic_validation_suspicious_filename(self, file_service, mock_user, mock_organization):
            """Test validation with suspicious filename"""
            malicious_file = Mock()
            malicious_file.filename = "../../../etc/passwd"
            malicious_file.size = 1024
            malicious_file.file = Mock()
            malicious_file.file.read = AsyncMock(return_value=b"content")
            malicious_file.file.seek = Mock()

            with pytest.raises(EnhancedFileValidationError, match="suspicious characters or patterns"):
                await file_service.perform_basic_validation(malicious_file, mock_user, mock_organization)

        def test_get_document_type(self, file_service):
            """Test document type detection"""
            # Test PDF
            assert file_service.get_document_type("document.pdf", "application/pdf") == DocumentType.PDF

            # Test Image
            assert file_service.get_document_type("image.jpg", "image/jpeg") == DocumentType.IMAGE

            # Test Text
            assert file_service.get_document_type("document.txt", "text/plain") == DocumentType.TEXT

            # Test fallback
            assert file_service.get_document_type("unknown.xyz", "application/octet-stream") == DocumentType.MULTIMODAL

        def test_is_suspicious_filename(self, file_service):
            """Test suspicious filename detection"""
            # Path traversal attempts
            assert file_service.is_suspicious_filename("../../../etc/passwd")
            assert file_service.is_suspicious_filename("..\\..\\windows\\system32\\config\\sam")

            # Reserved names
            assert file_service.is_suspicious_filename("con.txt")
            assert file_service.is_suspicious_filename("prn.jpg")

            # Normal filenames should not be suspicious
            assert not file_service.is_suspicious_filename("normal_document.pdf")
            assert not file_service.is_suspicious_filename("My File (1).txt")

    class TestSecurityScanning:
        """Test security scanning methods"""

        @pytest.mark.asyncio
        async def test_perform_security_scan_success(self, file_service, mock_upload_file):
            """Test successful security scanning"""
            validation_result = {
                "detected_mime_type": "application/pdf",
                "document_type": DocumentType.PDF
            }

            with patch.object(file_service, 'save_temp_file') as mock_save_temp, \
                 patch.object(file_service, 'scan_with_clamav') as mock_clamav, \
                 patch.object(file_service, 'analyze_content_for_threats') as mock_content, \
                 patch.object(file_service, 'analyze_archive_safety') as mock_archive, \
                 patch.object(file_service, 'analyze_metadata_for_threats') as mock_metadata:

                mock_save_temp.return_value = "/tmp/test_file"
                mock_clamav.return_value = {"infected": False, "threats": []}
                mock_content.return_value = {"threats": [], "warnings": []}
                mock_archive.return_value = {"is_bomb": False}
                mock_metadata.return_value = {"warnings": []}

                result = await file_service.perform_security_scan(mock_upload_file, validation_result)

                assert result["virus_detected"] is False
                assert len(result["threats"]) == 0
                assert result["scan_status"] == "completed"
                assert "scan_timestamp" in result

        @pytest.mark.asyncio
        async def test_security_scan_virus_detected(self, file_service, mock_upload_file):
            """Test security scanning with virus detected"""
            validation_result = {
                "detected_mime_type": "application/pdf",
                "document_type": DocumentType.PDF
            }

            with patch.object(file_service, 'save_temp_file') as mock_save_temp, \
                 patch.object(file_service, 'scan_with_clamav') as mock_clamav, \
                 patch.object(file_service, 'analyze_content_for_threats') as mock_content:

                mock_save_temp.return_value = "/tmp/test_file"
                mock_clamav.return_value = {
                    "infected": True,
                    "threats": [SecurityThreat("virus", "Test virus", "critical")]
                }
                mock_content.return_value = {"threats": [], "warnings": []}

                result = await file_service.perform_security_scan(mock_upload_file, validation_result)

                assert result["virus_detected"] is True
                assert len(result["threats"]) == 1
                assert result["threats"][0]["type"] == "virus"
                assert result["threats"][0]["severity"] == "critical"

        @pytest.mark.asyncio
        async def test_scan_with_clamav_success(self, file_service):
            """Test ClamAV scanning with clean file"""
            with patch('src.services.enhanced_file_service.CLAMD_AVAILABLE', True), \
                 patch('src.services.enhanced_file_service.pyclamd') as mock_pyclamd:

                mock_cd = Mock()
                mock_cd.ping.return_value = True
                mock_cd.scan_file.return_value = None  # No threats
                mock_pyclamd.ClamdUnixSocket.return_value = mock_cd

                result = await file_service.scan_with_clamav("/tmp/test_file")

                assert result["infected"] is False
                assert len(result["threats"]) == 0

        @pytest.mark.asyncio
        async def test_scan_with_clamav_unavailable(self, file_service):
            """Test ClamAV scanning when service is unavailable"""
            with patch('src.services.enhanced_file_service.CLAMD_AVAILABLE', False):
                result = await file_service.scan_with_clamav("/tmp/test_file")

                assert result["infected"] is False
                assert len(result["threats"]) == 0
                assert "error" in result
                assert result["error"] == "ClamAV not available"

        @pytest.mark.asyncio
        async def test_analyze_content_for_threats_suspicious_code(self, file_service):
            """Test content analysis for suspicious code patterns"""
            validation_result = {"document_type": DocumentType.TEXT}

            # Create temporary file with suspicious content
            temp_file = file_service.upload_dir / "temp" / "test_malicious.txt"
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file.write_bytes(b"This file contains eval(base64_decode('malicious_code')) and shell_exec('rm -rf /')")

            try:
                result = await file_service.analyze_content_for_threats(str(temp_file), validation_result)

                assert len(result["threats"]) >= 2  # Should detect both patterns
                threat_types = [threat["type"] for threat in result["threats"]]
                assert "suspicious_code" in threat_types

            finally:
                temp_file.unlink(missing_ok=True)

        @pytest.mark.asyncio
        async def test_analyze_zip_safety_zip_bomb(self, file_service):
            """Test ZIP archive safety analysis for zip bomb"""
            # Create a temporary ZIP file that simulates a zip bomb
            import zipfile
            temp_zip = file_service.upload_dir / "temp" / "test_bomb.zip"
            temp_zip.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(temp_zip, 'w') as zf:
                # Create a file with very high compression ratio
                large_content = "A" * 10000  # 10KB of 'A's
                zf.writestr("large_file.txt", large_content)

            try:
                # Mock the file size to simulate compression
                with patch('os.path.getsize', return_value=100):  # Very small compressed size
                    result = await file_service.analyze_zip_safety(str(temp_zip))

                    assert result["is_bomb"] is True
                    assert result["compression_ratio"] > 1000

            finally:
                temp_zip.unlink(missing_ok=True)

    class TestFileIntegrity:
        """Test file integrity verification methods"""

        @pytest.mark.asyncio
        async def test_verify_file_integrity_success(self, file_service, mock_upload_file):
            """Test successful file integrity verification"""
            validation_result = {
                "document_type": DocumentType.TEXT,
                "detected_mime_type": "text/plain"
            }

            with patch.object(file_service, 'save_temp_file') as mock_save_temp, \
                 patch.object(file_service, 'calculate_file_hash') as mock_hash, \
                 patch.object(file_service, 'verify_file_structure') as mock_structure, \
                 patch.object(file_service, 'check_file_corruption') as mock_corruption:

                mock_save_temp.return_value = "/tmp/test_file"
                mock_hash.return_value = "abc123hash"
                mock_structure.return_value = True
                mock_corruption.return_value = False

                result = await file_service.verify_file_integrity(mock_upload_file, validation_result)

                assert result["file_hash"] == "abc123hash"
                assert result["structure_valid"] is True
                assert result["corruption_check"] is False
                assert result["integrity_status"] == "passed"

        def test_calculate_file_hash(self, file_service):
            """Test file hash calculation"""
            # Create temporary file
            temp_file = file_service.upload_dir / "temp" / "test_hash.txt"
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file.write_text("test content for hashing")

            try:
                hash_value = file_service.calculate_file_hash(str(temp_file))

                assert isinstance(hash_value, str)
                assert len(hash_value) == 64  # SHA-256 hash length
                assert hash_value.isalnum()  # Should contain only alphanumeric characters

            finally:
                temp_file.unlink(missing_ok=True)

        def test_verify_pdf_structure_valid(self, file_service):
            """Test PDF structure verification for valid PDF"""
            # Create a minimal valid PDF
            pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000010 00000 n\n0000000079 00000 n\n0000000173 00000 n\n0000000301 00000 n\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n398\n%%EOF"

            temp_pdf = file_service.upload_dir / "temp" / "test_valid.pdf"
            temp_pdf.parent.mkdir(parents=True, exist_ok=True)
            temp_pdf.write_bytes(pdf_content)

            try:
                result = file_service.verify_pdf_structure(str(temp_pdf))
                assert result is True

            finally:
                temp_pdf.unlink(missing_ok=True)

        def test_verify_pdf_structure_invalid(self, file_service):
            """Test PDF structure verification for invalid PDF"""
            # Create an invalid PDF (missing PDF header)
            invalid_content = b"This is not a PDF file"

            temp_file = file_service.upload_dir / "temp" / "test_invalid.pdf"
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file.write_bytes(invalid_content)

            try:
                result = file_service.verify_pdf_structure(str(temp_file))
                assert result is False

            finally:
                temp_file.unlink(missing_ok=True)

        def test_calculate_entropy(self, file_service):
            """Test entropy calculation"""
            # Low entropy data (repetitive)
            low_entropy_data = b"A" * 1000
            low_entropy = file_service.calculate_entropy(low_entropy_data)
            assert low_entropy < 1.0

            # High entropy data (random-looking)
            import os
            high_entropy_data = os.urandom(1000)
            high_entropy = file_service.calculate_entropy(high_entropy_data)
            assert high_entropy > 6.0

            # Empty data
            empty_entropy = file_service.calculate_entropy(b"")
            assert empty_entropy == 0.0

    class TestFileOperations:
        """Test file operations"""

        @pytest.mark.asyncio
        async def test_save_temp_file(self, file_service, mock_upload_file):
            """Test temporary file saving"""
            temp_path = await file_service.save_temp_file(mock_upload_file)

            assert os.path.exists(temp_path)
            assert os.path.getsize(temp_path) > 0
            assert temp_path.startswith(str(file_service.upload_dir / "temp"))

            # Cleanup
            os.remove(temp_path)

        @pytest.mark.asyncio
        async def test_save_file_permanently(self, file_service, mock_upload_file):
            """Test permanent file saving"""
            file_path = str(file_service.upload_dir / "documents" / "test_save.pdf")

            saved_path = await file_service.save_file_permanently(mock_upload_file, file_path)

            assert saved_path == file_path
            assert os.path.exists(file_path)
            assert os.path.getsize(file_path) > 0

            # Cleanup
            os.remove(file_path)

        def test_generate_file_path(self, file_service):
            """Test file path generation"""
            org_id = "test-org-id"

            # Test different document types
            pdf_path = file_service.generate_file_path(DocumentType.PDF, org_id)
            assert "documents" in pdf_path
            assert org_id in pdf_path

            image_path = file_service.generate_file_path(DocumentType.IMAGE, org_id)
            assert "images" in image_path
            assert org_id in image_path

            # Verify uniqueness
            pdf_path_2 = file_service.generate_file_path(DocumentType.PDF, org_id)
            assert pdf_path != pdf_path_2

    class TestIntegration:
        """Integration tests combining multiple methods"""

        @pytest.mark.asyncio
        async def test_validate_and_scan_file_complete_flow(self, file_service, mock_upload_file, mock_user, mock_organization):
            """Test complete validation and scanning flow"""
            with patch.object(file_service, 'save_temp_file') as mock_save_temp, \
                 patch.object(file_service, 'scan_with_clamav') as mock_clamav, \
                 patch.object(file_service, 'analyze_content_for_threats') as mock_content, \
                 patch.object(file_service, 'analyze_archive_safety') as mock_archive, \
                 patch.object(file_service, 'analyze_metadata_for_threats') as mock_metadata, \
                 patch.object(file_service, 'calculate_file_hash') as mock_hash, \
                 patch.object(file_service, 'verify_file_structure') as mock_structure, \
                 patch.object(file_service, 'check_file_corruption') as mock_corruption:

                # Setup mocks
                mock_save_temp.return_value = "/tmp/test_file"
                mock_clamav.return_value = {"infected": False, "threats": []}
                mock_content.return_value = {"threats": [], "warnings": []}
                mock_archive.return_value = {"is_bomb": False}
                mock_metadata.return_value = {"warnings": []}
                mock_hash.return_value = "test_hash"
                mock_structure.return_value = True
                mock_corruption.return_value = False

                result = await file_service.validate_and_scan_file(mock_upload_file, mock_user, mock_organization)

                assert result["validation_status"] == "passed"
                assert "basic_validation" in result
                assert "security_scan" in result
                assert "integrity_check" in result
                assert result["security_scan"]["virus_detected"] is False
                assert result["integrity_check"]["integrity_status"] == "passed"

        @pytest.mark.asyncio
        async def test_upload_file_complete_flow(self, file_service, mock_upload_file, mock_user, mock_organization):
            """Test complete file upload flow"""
            validation_result = {
                "basic_validation": {
                    "file_size": 1024,
                    "document_type": DocumentType.PDF,
                    "detected_mime_type": "application/pdf"
                },
                "security_scan": {
                    "virus_detected": False,
                    "threats": [],
                    "warnings": []
                },
                "integrity_check": {
                    "file_hash": "test_hash",
                    "integrity_status": "passed"
                }
            }

            with patch.object(file_service, 'generate_file_path') as mock_generate_path, \
                 patch.object(file_service, 'save_file_permanently') as mock_save_permanent, \
                 patch.object(file_service, 'calculate_file_hash') as mock_hash:

                mock_generate_path.return_value = "/tmp/test_file"
                mock_save_permanent.return_value = "/tmp/test_file.pdf"
                mock_hash.return_value = "test_hash"

                # Mock database operations
                mock_document = Mock()
                mock_document.id = "test-doc-id"
                file_service.db.add = Mock()
                file_service.db.commit = Mock()
                file_service.db.refresh = Mock()

                with patch('src.services.enhanced_file_service.Document', return_value=mock_document):
                    result = await file_service.upload_file(
                        mock_upload_file,
                        "Test Document",
                        "Test description",
                        mock_user,
                        mock_organization,
                        ["test", "document"],
                        False,
                        {"custom": "metadata"},
                        validation_result
                    )

                    assert result is mock_document
                    file_service.db.add.assert_called_once()
                    file_service.db.commit.assert_called()

if __name__ == "__main__":
    pytest.main([__file__])