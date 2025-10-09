"""
Automated test data generation utilities for comprehensive testing
"""

import os
import tempfile
import random
import json
import string
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from src.models.document import DocumentType
from src.models.entity import EntityType
from src.models.user import UserRole
from src.models.processing import JobType, JobStatus


class TestDataGenerator:
    """Utility class for generating comprehensive test data"""

    def __init__(self, temp_dir: Optional[str] = None):
        """Initialize test data generator

        Args:
            temp_dir: Temporary directory for generated files. If None, uses system temp.
        """
        self.temp_dir = temp_dir or tempfile.mkdtemp()
        os.makedirs(self.temp_dir, exist_ok=True)

        # Sample data pools for realistic content generation
        self.names = [
            "John Smith", "Jane Doe", "Michael Johnson", "Emily Brown", "David Wilson",
            "Sarah Davis", "Robert Miller", "Lisa Anderson", "James Taylor", "Mary Thomas"
        ]

        self.organizations = [
            "Acme Corporation", "TechGlobal Inc.", "Innovation Solutions", "Digital Dynamics",
            "Future Systems", "Smart Technologies", "Cloud Services Co.", "Data Analytics Ltd.",
            "Software Solutions Inc.", "Cybersecurity Dynamics"
        ]

        self.locations = [
            "New York", "San Francisco", "Los Angeles", "Chicago", "Boston",
            "Seattle", "Austin", "Denver", "Portland", "Miami"
        ]

        self.email_domains = [
            "gmail.com", "yahoo.com", "outlook.com", "company.com", "business.org"
        ]

    def generate_text_document(
        self,
        filename: Optional[str] = None,
        size_kb: int = 10,
        include_entities: bool = True,
        language: str = "en"
    ) -> str:
        """Generate a text document with realistic content

        Args:
            filename: Output filename. If None, generates automatically.
            size_kb: Target file size in kilobytes
            include_entities: Whether to include named entities
            language: Language code (en, es, fr)

        Returns:
            Path to generated file
        """
        if filename is None:
            filename = f"test_doc_{random.randint(1000, 9999)}.txt"

        file_path = os.path.join(self.temp_dir, filename)

        # Generate content based on language
        if language == "en":
            content = self._generate_english_content(size_kb, include_entities)
        elif language == "es":
            content = self._generate_spanish_content(size_kb, include_entities)
        elif language == "fr":
            content = self._generate_french_content(size_kb, include_entities)
        else:
            content = self._generate_english_content(size_kb, include_entities)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return file_path

    def _generate_english_content(self, size_kb: int, include_entities: bool) -> str:
        """Generate English language content"""
        paragraphs = []
        target_chars = size_kb * 1024

        if include_entities:
            # Include entity-rich content
            entity_templates = [
                "{name} from {organization} contacted us at {email} regarding the project in {location}.",
                "The meeting was scheduled with {name} from {organization} to discuss business opportunities in {location}.",
                "Please contact {name} at {email} or call {phone} for more information about our services in {location}.",
                "{organization} announced new initiatives in {location}, according to {name} who can be reached at {email}.",
                "Visit {website} to learn more about {organization}'s operations in {location}, or contact {name} at {email}."
            ]

            while len("".join(paragraphs)) < target_chars:
                template = random.choice(entity_templates)

                # Replace placeholders with sample data
                content = template.format(
                    name=random.choice(self.names),
                    organization=random.choice(self.organizations),
                    location=random.choice(self.locations),
                    email=self._generate_email(),
                    phone=self._generate_phone(),
                    website=self._generate_url()
                )

                paragraphs.append(content)
        else:
            # Generate generic content
            base_sentences = [
                "This document contains sample text for testing purposes.",
                "The content includes various paragraphs and sentence structures.",
                "Testing ensures the quality and reliability of document processing systems.",
                "Automated testing helps maintain consistency and accuracy over time.",
                "Different types of content are used to verify processing capabilities."
            ]

            while len("".join(paragraphs)) < target_chars:
                paragraph = " ".join(random.choices(base_sentences, k=3))
                paragraphs.append(paragraph)

        return "\n\n".join(paragraphs)

    def _generate_spanish_content(self, size_kb: int, include_entities: bool) -> str:
        """Generate Spanish language content"""
        # Basic Spanish content for testing
        content = """
        Este es un documento de prueba en español para fines de testing.

        El contenido incluye varios párrafos con estructuras diferentes.
        La prueba asegura la calidad y fiabilidad de los sistemas de procesamiento.

        Contacto: Juan García de Tecnología Global puede ser contactado en juan.garcia@tecnoglobal.com.
        La empresa está ubicada en Madrid, España. El número de teléfono es (34) 91-123-4567.
        """

        # Repeat content to reach target size
        target_chars = size_kb * 1024
        while len(content) < target_chars:
            content += "\n\n" + content

        return content[:target_chars]

    def _generate_french_content(self, size_kb: int, include_entities: bool) -> str:
        """Generate French language content"""
        # Basic French content for testing
        content = """
        Ceci est un document de test en français à des fins de testing.

        Le contenu inclut divers paragraphes avec des structures différentes.
        Le test assure la qualité et la fiabilité des systèmes de traitement.

        Contact: Marie Martin de Solutions Innovantes peut être contactée à marie.martin@solutions.fr.
        L'entreprise est située à Paris, France. Le numéro de téléphone est (33) 01-23-45-67-89.
        """

        # Repeat content to reach target size
        target_chars = size_kb * 1024
        while len(content) < target_chars:
            content += "\n\n" + content

        return content[:target_chars]

    def _generate_email(self) -> str:
        """Generate a realistic email address"""
        names = ["john", "jane", "michael", "emily", "david", "sarah", "robert", "lisa"]
        domains = self.email_domains
        return f"{random.choice(names)}.{random.randint(10, 99)}@{random.choice(domains)}"

    def _generate_phone(self) -> str:
        """Generate a realistic phone number"""
        formats = [
            "(555) {num1}-{num2}",
            "+1-555-{num1}-{num2}",
            "555-{num1}-{num2}"
        ]

        num1 = f"{random.randint(100, 999)}"
        num2 = f"{random.randint(1000, 9999)}"

        return random.choice(formats).format(num1=num1, num2=num2)

    def _generate_url(self) -> str:
        """Generate a realistic URL"""
        companies = ["acme", "techglobal", "innovations", "digital", "future", "smart"]
        return f"https://www.{random.choice(companies)}.com"

    def generate_image_file(
        self,
        filename: Optional[str] = None,
        width: int = 800,
        height: int = 600,
        format: str = "PNG",
        include_text: bool = False,
        text_content: Optional[str] = None
    ) -> str:
        """Generate an image file with various characteristics

        Args:
            filename: Output filename. If None, generates automatically.
            width: Image width in pixels
            height: Image height in pixels
            format: Image format (PNG, JPEG, etc.)
            include_text: Whether to include text in the image
            text_content: Text to include in image

        Returns:
            Path to generated file
        """
        if filename is None:
            filename = f"test_img_{random.randint(1000, 9999)}.{format.lower()}"

        file_path = os.path.join(self.temp_dir, filename)

        # Create image with random colors
        img_array = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        img = Image.fromarray(img_array, 'RGB')

        if include_text:
            # Add text to image
            draw = ImageDraw.Draw(img)

            try:
                # Try to use a default font
                font = ImageFont.load_default()
            except:
                font = None

            if text_content is None:
                text_content = "Test Image for OCR Processing"

            # Add text at multiple positions
            text_positions = [(50, 50), (50, 150), (50, 250)]

            for x, y in text_positions:
                if font:
                    draw.text((x, y), text_content, fill='white', font=font)
                else:
                    draw.text((x, y), text_content, fill='white')

        img.save(file_path, format)
        return file_path

    def generate_audio_file_mock(
        self,
        filename: Optional[str] = None,
        duration_seconds: int = 10,
        sample_rate: int = 44100
    ) -> str:
        """Generate a mock audio file (for testing without actual audio)

        Args:
            filename: Output filename. If None, generates automatically.
            duration_seconds: Duration in seconds
            sample_rate: Sample rate in Hz

        Returns:
            Path to generated file
        """
        if filename is None:
            filename = f"test_audio_{random.randint(1000, 9999)}.mp3"

        file_path = os.path.join(self.temp_dir, filename)

        # Generate mock audio data (binary pattern that looks like audio)
        audio_data = np.random.randint(0, 256, duration_seconds * sample_rate * 2, dtype=np.uint8)

        with open(file_path, "wb") as f:
            f.write(audio_data.tobytes())

        return file_path

    def generate_video_file_mock(
        self,
        filename: Optional[str] = None,
        duration_seconds: int = 30,
        width: int = 1920,
        height: int = 1080
    ) -> str:
        """Generate a mock video file (for testing without actual video)

        Args:
            filename: Output filename. If None, generates automatically.
            duration_seconds: Duration in seconds
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            Path to generated file
        """
        if filename is None:
            filename = f"test_video_{random.randint(1000, 9999)}.mp4"

        file_path = os.path.join(self.temp_dir, filename)

        # Generate mock video data (binary pattern that looks like video)
        frame_size = width * height * 3  # RGB
        total_frames = duration_seconds * 30  # Assuming 30 fps

        video_data = np.random.randint(0, 256, frame_size * total_frames, dtype=np.uint8)

        with open(file_path, "wb") as f:
            f.write(video_data.tobytes())

        return file_path

    def generate_corrupted_file(
        self,
        filename: Optional[str] = None,
        extension: str = "txt",
        size_bytes: int = 1024
    ) -> str:
        """Generate a corrupted file for error testing

        Args:
            filename: Output filename. If None, generates automatically.
            extension: File extension
            size_bytes: File size in bytes

        Returns:
            Path to generated file
        """
        if filename is None:
            filename = f"corrupted_{random.randint(1000, 9999)}.{extension}"

        file_path = os.path.join(self.temp_dir, filename)

        # Generate random binary data that's likely to be corrupted for the file type
        if extension.lower() in ['jpg', 'jpeg', 'png', 'gif']:
            # Generate data that's not valid image format
            corrupted_data = b"This is not valid image data at all!" * (size_bytes // 50)
        elif extension.lower() in ['mp3', 'wav', 'ogg']:
            # Generate data that's not valid audio format
            corrupted_data = b"This is not valid audio data at all!" * (size_bytes // 50)
        elif extension.lower() in ['mp4', 'avi', 'mov']:
            # Generate data that's not valid video format
            corrupted_data = b"This is not valid video data at all!" * (size_bytes // 50)
        else:
            # Generic corrupted data
            corrupted_data = np.random.bytes(size_bytes)

        with open(file_path, "wb") as f:
            f.write(corrupted_data[:size_bytes])

        return file_path

    def generate_large_file(
        self,
        filename: Optional[str] = None,
        extension: str = "txt",
        size_mb: int = 100
    ) -> str:
        """Generate a large file for performance testing

        Args:
            filename: Output filename. If None, generates automatically.
            extension: File extension
            size_mb: File size in megabytes

        Returns:
            Path to generated file
        """
        if filename is None:
            filename = f"large_{random.randint(1000, 9999)}.{extension}"

        file_path = os.path.join(self.temp_dir, filename)

        # Generate large content
        if extension.lower() == 'txt':
            # Text content
            content = "This is a large test file for performance testing. " * 100
            target_size = size_mb * 1024 * 1024

            with open(file_path, "w", encoding="utf-8") as f:
                while f.tell() < target_size:
                    f.write(content)
        else:
            # Binary content
            target_size = size_mb * 1024 * 1024
            chunk_size = 1024 * 1024  # 1MB chunks
            chunk = b"A" * chunk_size

            with open(file_path, "wb") as f:
                while f.tell() < target_size:
                    remaining = target_size - f.tell()
                    f.write(chunk[:min(chunk_size, remaining)])

        return file_path

    def generate_test_document_metadata(
        self,
        document_type: DocumentType,
        user_id: int,
        organization_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate test document metadata

        Args:
            document_type: Type of document
            user_id: User ID
            organization_id: Organization ID
            **kwargs: Additional metadata fields

        Returns:
            Dictionary with document metadata
        """
        base_metadata = {
            "title": kwargs.get("title", f"Test Document {random.randint(1000, 9999)}"),
            "filename": kwargs.get("filename", f"test_doc_{random.randint(1000, 9999)}.{self._get_extension_for_type(document_type)}"),
            "file_path": kwargs.get("file_path", f"/test/path/test_{random.randint(1000, 9999)}"),
            "file_size": kwargs.get("file_size", random.randint(1024, 1024 * 1024)),
            "mime_type": kwargs.get("mime_type", self._get_mime_type_for_type(document_type)),
            "document_type": document_type,
            "description": kwargs.get("description", f"Test document for {document_type.value} processing"),
            "user_id": user_id,
            "organization_id": organization_id,
        }

        # Add type-specific metadata
        if document_type == DocumentType.IMAGE:
            base_metadata.update({
                "width": kwargs.get("width", random.randint(800, 4000)),
                "height": kwargs.get("height", random.randint(600, 3000)),
                "format": kwargs.get("format", random.choice(["JPEG", "PNG", "TIFF"]))
            })
        elif document_type == DocumentType.AUDIO:
            base_metadata.update({
                "duration": kwargs.get("duration", random.randint(30, 600)),
                "sample_rate": kwargs.get("sample_rate", random.choice([22050, 44100, 48000])),
                "format": kwargs.get("format", random.choice(["MP3", "WAV", "OGG"]))
            })
        elif document_type == DocumentType.VIDEO:
            base_metadata.update({
                "duration": kwargs.get("duration", random.randint(60, 3600)),
                "width": kwargs.get("width", random.choice([1280, 1920, 3840])),
                "height": kwargs.get("height", random.choice([720, 1080, 2160])),
                "fps": kwargs.get("fps", random.choice([24, 30, 60])),
                "format": kwargs.get("format", random.choice(["MP4", "AVI", "MOV"]))
            })

        return base_metadata

    def generate_test_processing_job_metadata(
        self,
        document_id: int,
        job_type: JobType = JobType.DOCUMENT_PROCESSING,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate test processing job metadata

        Args:
            document_id: Document ID
            job_type: Type of job
            **kwargs: Additional job metadata

        Returns:
            Dictionary with job metadata
        """
        return {
            "document_id": document_id,
            "job_type": job_type,
            "status": kwargs.get("status", JobStatus.PENDING),
            "progress_percentage": kwargs.get("progress_percentage", 0),
            "current_step": kwargs.get("current_step", "Initializing"),
            "error_message": kwargs.get("error_message"),
            "retry_count": kwargs.get("retry_count", 0),
            "max_retries": kwargs.get("max_retries", 3),
            "result": kwargs.get("result"),
            "metadata": kwargs.get("metadata", {}),
        }

    def generate_test_user_metadata(
        self,
        organization_id: int,
        role: UserRole = UserRole.USER,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate test user metadata

        Args:
            organization_id: Organization ID
            role: User role
            **kwargs: Additional user metadata

        Returns:
            Dictionary with user metadata
        """
        first_names = ["John", "Jane", "Michael", "Emily", "David", "Sarah", "Robert", "Lisa"]
        last_names = ["Smith", "Doe", "Johnson", "Brown", "Wilson", "Davis", "Miller", "Anderson"]

        first_name = random.choice(first_names)
        last_name = random.choice(last_names)

        return {
            "email": kwargs.get("email", f"{first_name.lower()}.{last_name.lower()}@example.com"),
            "username": kwargs.get("username", f"{first_name.lower()}{last_name.lower()}{random.randint(10, 99)}"),
            "hashed_password": kwargs.get("hashed_password", "hashed_password_placeholder"),
            "role": role,
            "organization_id": organization_id,
            "is_active": kwargs.get("is_active", True),
            "full_name": kwargs.get("full_name", f"{first_name} {last_name}"),
        }

    def generate_test_organization_metadata(self, **kwargs) -> Dict[str, Any]:
        """Generate test organization metadata

        Args:
            **kwargs: Additional organization metadata

        Returns:
            Dictionary with organization metadata
        """
        return {
            "name": kwargs.get("name", random.choice(self.organizations)),
            "domain": kwargs.get("domain", f"company{random.randint(1000, 9999)}.com"),
            "is_active": kwargs.get("is_active", True),
            "settings": kwargs.get("settings", {
                "max_file_size": 100 * 1024 * 1024,  # 100MB
                "allowed_file_types": ["txt", "pdf", "jpg", "png", "mp3", "mp4"],
                "processing_timeout": 3600,  # 1 hour
            }),
        }

    def generate_batch_test_files(
        self,
        count: int = 10,
        file_types: Optional[List[DocumentType]] = None,
        size_range_kb: tuple = (10, 100)
    ) -> List[str]:
        """Generate a batch of test files

        Args:
            count: Number of files to generate
            file_types: List of file types to generate. If None, uses random types.
            size_range_kb: Tuple of (min_size_kb, max_size_kb)

        Returns:
            List of file paths
        """
        if file_types is None:
            file_types = list(DocumentType)

        files = []

        for i in range(count):
            doc_type = random.choice(file_types)
            size_kb = random.randint(size_range_kb[0], size_range_kb[1])

            if doc_type == DocumentType.TEXT:
                file_path = self.generate_text_document(size_kb=size_kb)
            elif doc_type == DocumentType.IMAGE:
                file_path = self.generate_image_file(
                    width=random.randint(400, 2000),
                    height=random.randint(300, 1500)
                )
            elif doc_type == DocumentType.AUDIO:
                file_path = self.generate_audio_file_mock(
                    duration_seconds=random.randint(10, 60)
                )
            elif doc_type == DocumentType.VIDEO:
                file_path = self.generate_video_file_mock(
                    duration_seconds=random.randint(30, 120)
                )
            else:
                file_path = self.generate_text_document(size_kb=size_kb)

            files.append(file_path)

        return files

    def _get_extension_for_type(self, document_type: DocumentType) -> str:
        """Get file extension for document type"""
        extensions = {
            DocumentType.TEXT: "txt",
            DocumentType.IMAGE: "png",
            DocumentType.AUDIO: "mp3",
            DocumentType.VIDEO: "mp4",
            DocumentType.PDF: "pdf",
            DocumentType.OTHER: "bin"
        }
        return extensions.get(document_type, "txt")

    def _get_mime_type_for_type(self, document_type: DocumentType) -> str:
        """Get MIME type for document type"""
        mime_types = {
            DocumentType.TEXT: "text/plain",
            DocumentType.IMAGE: "image/png",
            DocumentType.AUDIO: "audio/mpeg",
            DocumentType.VIDEO: "video/mp4",
            DocumentType.PDF: "application/pdf",
            DocumentType.OTHER: "application/octet-stream"
        }
        return mime_types.get(document_type, "application/octet-stream")

    def cleanup(self):
        """Clean up generated test files"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)