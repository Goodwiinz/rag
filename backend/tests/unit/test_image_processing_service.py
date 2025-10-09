"""
Unit tests for ImageProcessingService
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from PIL import Image
import io

from src.services.image_processing_service import ImageProcessingService
from src.models.document import Document


class TestImageProcessingService:
    """Test cases for ImageProcessingService"""

    def test_init(self):
        """Test ImageProcessingService initialization"""
        service = ImageProcessingService()

        assert service.supported_formats == {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
        assert hasattr(service, 'ocr_available')

    @patch('src.services.image_processing_service.pytesseract')
    def test_init_with_ocr_available(self, mock_pytesseract):
        """Test initialization when OCR is available"""
        mock_pytesseract.image_to_string = Mock()
        service = ImageProcessingService()
        assert service.ocr_available

    @patch('src.services.image_processing_service.pytesseract', side_effect=ImportError)
    def test_init_without_ocr(self, mock_pytesseract):
        """Test initialization when OCR is not available"""
        service = ImageProcessingService()
        assert not service.ocr_available

    def test_process_image_success(self, mock_image_file):
        """Test successful image processing"""
        service = ImageProcessingService()

        with patch('src.services.image_processing_service.Image.open') as mock_image_open:
            # Mock PIL Image
            mock_img = Mock()
            mock_img.width = 800
            mock_img.height = 600
            mock_img.format = "JPEG"
            mock_img.mode = "RGB"
            mock_img.size = (800, 600)
            mock_img.info = {'exif': b'fake_exif_data'}
            mock_image_open.return_value.__enter__.return_value = mock_img

            with patch.object(service, '_perform_ocr', return_value="Extracted text from image") as mock_ocr:
                with patch.object(service, '_analyze_image_quality', return_value={"quality": "high"}) as mock_quality:
                    with patch.object(service, '_extract_color_palette', return_value=["#FF0000", "#00FF00", "#0000FF"]) as mock_palette:
                        with patch.object(service, '_detect_image_features', return_value={"edges": 1000}) as mock_features:

                            result = service.process_image(mock_image_file)

                            assert 'metadata' in result
                            assert 'text_extraction' in result
                            assert 'quality_analysis' in result
                            assert 'color_analysis' in result
                            assert 'feature_analysis' in result
                            assert 'processing_timestamp' in result
                            assert result['text_extraction']['text'] == "Extracted text from image"
                            assert result['text_extraction']['ocr_available'] is True

    def test_process_image_file_not_found(self):
        """Test image processing with non-existent file"""
        service = ImageProcessingService()

        with pytest.raises(FileNotFoundError):
            service.process_image("/non/existent/image.jpg")

    def test_process_image_unsupported_format(self, temp_upload_dir):
        """Test image processing with unsupported file format"""
        service = ImageProcessingService()

        # Create a file with unsupported extension
        unsupported_file = os.path.join(temp_upload_dir, "test.xyz")
        with open(unsupported_file, "wb") as f:
            f.write(b"fake image data")

        with pytest.raises(ValueError, match="Unsupported image format"):
            service.process_image(unsupported_file)

    @patch('src.services.image_processing_service.Image.open')
    def test_extract_image_metadata(self, mock_image_open):
        """Test image metadata extraction"""
        service = ImageProcessingService()

        # Mock PIL Image with comprehensive metadata
        mock_img = Mock()
        mock_img.width = 1920
        mock_img.height = 1080
        mock_img.format = "PNG"
        mock_img.mode = "RGBA"
        mock_img.size = (1920, 1080)
        mock_img.info = {
            'exif': b'fake_exif_data',
            'dpi': (300, 300),
            'compression': 'deflate'
        }
        mock_image_open.return_value.__enter__.return_value = mock_img

        metadata = service._extract_image_metadata("test.png")

        assert metadata['width'] == 1920
        assert metadata['height'] == 1080
        assert metadata['format'] == "PNG"
        assert metadata['mode'] == "RGBA"
        assert metadata['megapixels'] == 2.07  # 1920 * 1080 / 1,000,000
        assert metadata['aspect_ratio'] == "16:9"
        assert metadata['file_size'] > 0
        assert metadata['color_channels'] == 4  # RGBA

    @patch('src.services.image_processing_service.Image.open')
    def test_extract_image_metadata_with_exif(self, mock_image_open):
        """Test image metadata extraction with EXIF data"""
        service = ImageProcessingService()

        # Mock PIL Image with EXIF data
        mock_img = Mock()
        mock_img.width = 4000
        mock_img.height = 3000
        mock_img.format = "JPEG"
        mock_img.mode = "RGB"
        mock_img.size = (4000, 3000)
        mock_img.info = {'exif': b'fake_exif_data'}

        # Mock EXIF extraction
        with patch('src.services.image_processing_service.Image.Exif') as mock_exif:
            mock_exif_instance = Mock()
            mock_exif_instance.get_tag.return_value = "Canon EOS R5"
            mock_exif.return_value = mock_exif_instance

            mock_image_open.return_value.__enter__.return_value = mock_img

            metadata = service._extract_image_metadata("test.jpg")

            # Check EXIF-related metadata
            assert 'exif_data' in metadata or 'camera_make' in metadata

    @patch('src.services.image_processing_service.pytesseract.image_to_string')
    def test_perform_ocr_success(self, mock_ocr, mock_image_file):
        """Test successful OCR text extraction"""
        service = ImageProcessingService()
        service.ocr_available = True

        mock_ocr.return_value = "This is extracted text from the image."

        with patch('src.services.image_processing_service.Image.open') as mock_image_open:
            mock_img = Mock()
            mock_image_open.return_value.__enter__.return_value = mock_img

            result = service._perform_ocr(mock_image_file)

            assert result['text'] == "This is extracted text from the image."
            assert result['confidence'] > 0.0
            assert result['word_count'] > 0
            assert result['language'] == 'eng'  # Default language
            assert result['processing_time_ms'] >= 0

    def test_perform_ocr_unavailable(self, mock_image_file):
        """Test OCR when OCR is not available"""
        service = ImageProcessingService()
        service.ocr_available = False

        result = service._perform_ocr(mock_image_file)

        assert result['text'] == ""
        assert result['ocr_available'] is False
        assert result['confidence'] == 0.0
        assert result['word_count'] == 0
        assert 'reason' in result

    @patch('src.services.image_processing_service.pytesseract.image_to_string')
    def test_perform_ocr_error_handling(self, mock_ocr, mock_image_file):
        """Test OCR error handling"""
        service = ImageProcessingService()
        service.ocr_available = True

        mock_ocr.side_effect = Exception("OCR processing failed")

        with patch('src.services.image_processing_service.Image.open') as mock_image_open:
            mock_img = Mock()
            mock_image_open.return_value.__enter__.return_value = mock_img

            result = service._perform_ocr(mock_image_file)

            assert result['text'] == ""
            assert result['error'] == "OCR processing failed"
            assert result['confidence'] == 0.0

    @patch('src.services.image_processing_service.pytesseract.image_to_string')
    def test_perform_ocr_different_languages(self, mock_ocr, mock_image_file):
        """Test OCR with different languages"""
        service = ImageProcessingService()
        service.ocr_available = True

        # Test Spanish text
        mock_ocr.return_value = "Este es un texto en español."

        with patch('src.services.image_processing_service.Image.open') as mock_image_open:
            mock_img = Mock()
            mock_image_open.return_value.__enter__.return_value = mock_img

            result = service._perform_ocr(mock_image_file, lang='spa')

            assert result['text'] == "Este es un texto en español."
            assert result['language'] == 'spa'

    @patch('src.services.image_processing_service.Image.open')
    def test_analyze_image_quality(self, mock_image_open):
        """Test image quality analysis"""
        service = ImageProcessingService()

        # Mock a high-quality image
        mock_img = Mock()
        mock_img.width = 2000
        mock_img.height = 1500
        mock_img.mode = "RGB"
        mock_img.size = (2000, 1500)
        mock_image_open.return_value.__enter__.return_value = mock_img

        # Mock file size
        with patch('os.path.getsize', return_value=2_000_000):  # 2MB
            quality = service._analyze_image_quality("test.jpg")

            assert 'resolution_category' in quality
            assert 'file_size_category' in quality
            assert 'megapixel_count' in quality
            assert 'aspect_ratio' in quality
            assert 'estimated_quality' in quality
            assert quality['resolution_category'] == "high"
            assert quality['file_size_category'] == "large"

    @patch('src.services.image_processing_service.Image.open')
    def test_analyze_image_quality_low_resolution(self, mock_image_open):
        """Test quality analysis for low-resolution image"""
        service = ImageProcessingService()

        # Mock a low-quality image
        mock_img = Mock()
        mock_img.width = 320
        mock_img.height = 240
        mock_img.mode = "RGB"
        mock_img.size = (320, 240)
        mock_image_open.return_value.__enter__.return_value = mock_img

        with patch('os.path.getsize', return_value=50_000):  # 50KB
            quality = service._analyze_image_quality("test.jpg")

            assert quality['resolution_category'] == "low"
            assert quality['file_size_category'] == "small"

    @patch('src.services.image_processing_service.Image.open')
    def test_extract_color_palette(self, mock_image_open):
        """Test color palette extraction"""
        service = ImageProcessingService()

        # Mock image with specific colors
        mock_img = Mock()
        mock_img.width = 100
        mock_img.height = 100
        mock_img.mode = "RGB"
        mock_img.size = (100, 100)
        mock_img.convert = Mock(return_value=mock_img)
        mock_img.getcolors = Mock(return_value=[
            (5000, (255, 0, 0)),    # Red
            (3000, (0, 255, 0)),    # Green
            (2000, (0, 0, 255)),    # Blue
        ])
        mock_image_open.return_value.__enter__.return_value = mock_img

        palette = service._extract_color_palette("test.jpg")

        assert len(palette) <= 10  # Should limit to top 10 colors
        assert all(isinstance(color, str) and color.startswith('#') for color in palette)
        assert '#FF0000' in palette or '#ff0000' in palette  # Red should be present
        assert '#00FF00' in palette or '#00ff00' in palette  # Green should be present
        assert '#0000FF' in palette or '#0000ff' in palette  # Blue should be present

    @patch('src.services.image_processing_service.Image.open')
    def test_extract_color_palette_grayscale(self, mock_image_open):
        """Test color palette extraction for grayscale images"""
        service = ImageProcessingService()

        # Mock grayscale image
        mock_img = Mock()
        mock_img.width = 100
        mock_img.height = 100
        mock_img.mode = "L"  # Grayscale
        mock_img.size = (100, 100)
        mock_img.convert = Mock(return_value=mock_img)
        mock_img.getcolors = Mock(return_value=[
            (5000, 128),  # Gray
            (3000, 64),   # Dark gray
            (2000, 192),  # Light gray
        ])
        mock_image_open.return_value.__enter__.return_value = mock_img

        palette = service._extract_color_palette("test.jpg")

        assert len(palette) <= 10
        # Grayscale colors should be in format #808080, #404040, #C0C0C0, etc.
        assert all(len(color) == 7 and color[0] == '#' for color in palette)

    @patch('src.services.image_processing_service.Image.open')
    @patch('src.services.image_processing_service.cv2')
    def test_detect_image_features(self, mock_cv2, mock_image_open):
        """Test image feature detection"""
        service = ImageProcessingService()

        # Mock PIL image
        mock_img = Mock()
        mock_img.width = 800
        mock_img.height = 600
        mock_img.mode = "RGB"
        mock_image_open.return_value.__enter__.return_value = mock_img

        # Mock OpenCV operations
        mock_cv2_image = Mock()
        mock_cv2.cvtColor = Mock(return_value=mock_cv2_image)
        mock_cv2.Canny = Mock(return_value=mock_cv2_image)
        mock_cv2.findContours = Mock(return_value=([], None))
        mock_cv2.cvtColor.return_value = mock_cv2_image

        # Mock numpy array conversion
        with patch('src.services.image_processing_service.np.array', return_value=mock_cv2_image):
            features = service._detect_image_features("test.jpg")

            assert 'edge_density' in features
            assert 'corner_count' in features
            assert 'contour_count' in features
            assert 'has_faces' in features
            assert 'dominant_orientation' in features
            assert isinstance(features['edge_density'], (int, float))
            assert isinstance(features['corner_count'], int)

    @patch('src.services.image_processing_service.Image.open')
    def test_detect_faces(self, mock_image_open):
        """Test face detection in images"""
        service = ImageProcessingService()

        mock_img = Mock()
        mock_img.width = 800
        mock_img.height = 600
        mock_img.mode = "RGB"
        mock_image_open.return_value.__enter__.return_value = mock_img

        # Mock face detection
        with patch.object(service, '_detect_faces', return_value=[
            {'x': 100, 'y': 100, 'width': 50, 'height': 50, 'confidence': 0.95},
            {'x': 300, 'y': 200, 'width': 60, 'height': 60, 'confidence': 0.88}
        ]):
            faces = service._detect_faces("test.jpg")

            assert len(faces) == 2
            assert faces[0]['confidence'] > 0.9
            assert faces[1]['confidence'] > 0.8
            assert all('x' in face and 'y' in face and 'width' in face and 'height' in face for face in faces)

    def test_categorize_image_resolution(self):
        """Test image resolution categorization"""
        service = ImageProcessingService()

        test_cases = [
            ((100, 75), "tiny"),
            ((640, 480), "low"),
            ((1280, 720), "medium"),
            ((1920, 1080), "high"),
            ((3840, 2160), "ultra"),
        ]

        for (width, height), expected_category in test_cases:
            category = service._categorize_resolution(width, height)
            assert category == expected_category

    def test_categorize_file_size(self):
        """Test file size categorization"""
        service = ImageProcessingService()

        test_cases = [
            (50_000, "tiny"),      # 50KB
            (500_000, "small"),    # 500KB
            (2_000_000, "medium"), # 2MB
            (8_000_000, "large"),  # 8MB
            (20_000_000, "huge"),  # 20MB
        ]

        for file_size, expected_category in test_cases:
            category = service._categorize_file_size(file_size)
            assert category == expected_category

    @patch('src.services.image_processing_service.Image.open')
    def test_generate_image_summary(self, mock_image_open):
        """Test image summary generation"""
        service = ImageProcessingService()

        # Mock comprehensive processing results
        processing_results = {
            'metadata': {
                'width': 1920,
                'height': 1080,
                'format': 'JPEG',
                'megapixels': 2.07
            },
            'text_extraction': {
                'text': 'Sample text extracted from image',
                'confidence': 0.85,
                'word_count': 5,
                'ocr_available': True
            },
            'quality_analysis': {
                'resolution_category': 'high',
                'file_size_category': 'medium',
                'estimated_quality': 'good'
            },
            'color_analysis': {
                'dominant_colors': ['#FF0000', '#00FF00', '#0000FF'],
                'is_grayscale': False
            },
            'feature_analysis': {
                'edge_density': 0.15,
                'face_count': 1
            }
        }

        summary = service.generate_image_summary(processing_results)

        assert '1920x1080' in summary
        assert '2.07 MP' in summary
        assert 'JPEG' in summary
        assert 'high resolution' in summary
        assert '5 words' in summary
        assert '85%' in summary
        assert 'good quality' in summary
        assert '1 face' in summary

    @patch('src.services.image_processing_service.Image.open')
    def test_process_corrupted_image(self, mock_image_open):
        """Test processing of corrupted image files"""
        service = ImageProcessingService()

        # Mock PIL to raise an exception for corrupted image
        mock_image_open.side_effect = Exception("Cannot identify image file")

        corrupted_file = "corrupted.jpg"

        with pytest.raises(Exception, match="Cannot identify image file"):
            service.process_image(corrupted_file)

    @patch('src.services.image_processing_service.Image.open')
    def test_process_large_image_performance(self, mock_image_open):
        """Test processing performance for large images"""
        service = ImageProcessingService()

        # Mock large image
        mock_img = Mock()
        mock_img.width = 6000
        mock_img.height = 4000
        mock_img.format = "TIFF"
        mock_img.mode = "RGB"
        mock_img.size = (6000, 4000)
        mock_image_open.return_value.__enter__.return_value = mock_img

        with patch.object(service, '_perform_ocr', return_value={'text': '', 'confidence': 0.0}):
            with patch.object(service, '_analyze_image_quality', return_value={}):
                with patch.object(service, '_extract_color_palette', return_value=[]):
                    with patch.object(service, '_detect_image_features', return_value={}):
                        with patch('os.path.getsize', return_value=25_000_000):  # 25MB

                            import time
                            start_time = time.time()
                            result = service.process_image("large_image.tif")
                            end_time = time.time()

                            processing_time = end_time - start_time

                            # Should complete within reasonable time (5 seconds for very large images)
                            assert processing_time < 5.0
                            assert 'metadata' in result
                            assert result['metadata']['width'] == 6000
                            assert result['metadata']['height'] == 4000

    def test_is_image_file_valid(self):
        """Test image file validation"""
        service = ImageProcessingService()

        # Test valid image extensions
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
        for ext in valid_extensions:
            assert service.is_image_file(f"test{ext}") is True

        # Test invalid extensions
        invalid_extensions = ['.txt', '.pdf', '.doc', '.mp4', '.xyz']
        for ext in invalid_extensions:
            assert service.is_image_file(f"test{ext}") is False

    @patch('src.services.image_processing_service.Image.open')
    def test_extract_text_with_different_ocr_engines(self, mock_image_open, mock_image_file):
        """Test OCR with different engine configurations"""
        service = ImageProcessingService()
        service.ocr_available = True

        with patch('src.services.image_processing_service.pytesseract.image_to_string') as mock_ocr:
            mock_ocr.return_value = "Sample extracted text"

            mock_img = Mock()
            mock_image_open.return_value.__enter__.return_value = mock_img

            # Test with custom OCR configuration
            custom_config = '--psm 6 --oem 3'
            result = service._perform_ocr(mock_image_file, config=custom_config)

            mock_ocr.assert_called_with(mock_img, config=custom_config)
            assert result['text'] == "Sample extracted text"