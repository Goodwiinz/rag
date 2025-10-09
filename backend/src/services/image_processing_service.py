"""
Image processing and analysis service for multimodal documents (Basic Version)
"""

import os
import logging
from typing import Dict, Any
from pathlib import Path
from datetime import datetime

from PIL import Image, ImageStat, ExifTags

logger = logging.getLogger(__name__)

class ImageProcessingService:
    """Service for processing and analyzing images (Basic Version without OCR dependencies)"""

    def __init__(self):
        """Initialize the image processing service"""
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        self.max_image_size = (4096, 4096)  # Maximum dimensions for processing

    def process_image(self, image_path: str) -> Dict[str, Any]:
        """Comprehensive image processing and analysis"""
        try:
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")

            # Validate image format
            file_ext = Path(image_path).suffix.lower()
            if file_ext not in self.supported_formats:
                raise ValueError(f"Unsupported image format: {file_ext}")

            logger.info(f"Processing image: {image_path}")

            # Load and validate image
            image = self._load_image(image_path)

            # Extract basic metadata
            metadata = self._extract_image_metadata(image_path, image)

            # Perform basic image analysis
            analysis_results = self._analyze_image_content(image)

            # Color analysis
            color_analysis = self._analyze_colors(image)

            # Image quality assessment
            quality_score = self._assess_image_quality(image, analysis_results)

            # OCR placeholder (would be implemented with proper dependencies)
            ocr_results = {
                'text': '',
                'confidence': 0.0,
                'regions': [],
                'note': 'OCR not available in this basic version'
            }

            results = {
                'metadata': metadata,
                'ocr_text': ocr_results['text'],
                'ocr_confidence': ocr_results['confidence'],
                'text_regions': ocr_results['regions'],
                'image_analysis': analysis_results,
                'color_analysis': color_analysis,
                'face_analysis': {'face_count': 0, 'faces': [], 'has_faces': False},  # Simplified
                'quality_score': quality_score,
                'processing_timestamp': datetime.now().isoformat(),
                'ocr_available': False
            }

            logger.info(f"Successfully processed image: {image_path}")
            return results

        except Exception as e:
            logger.error(f"Image processing failed for {image_path}: {str(e)}")
            raise

    def _load_image(self, image_path: str) -> Image.Image:
        """Load and validate image using PIL"""
        try:
            image = Image.open(image_path)

            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Resize if too large
            if image.size[0] > self.max_image_size[0] or image.size[1] > self.max_image_size[1]:
                image.thumbnail(self.max_image_size, Image.Resampling.LANCZOS)
                logger.info(f"Resized image to {image.size}")

            return image

        except Exception as e:
            logger.error(f"Failed to load image {image_path}: {str(e)}")
            raise

    def _extract_image_metadata(self, image_path: str, image: Image.Image) -> Dict[str, Any]:
        """Extract comprehensive image metadata"""
        metadata = {
            'file_path': image_path,
            'file_size': os.path.getsize(image_path),
            'dimensions': {
                'width': image.size[0],
                'height': image.size[1],
                'channels': len(image.getbands())
            },
            'aspect_ratio': image.size[0] / image.size[1],
            'file_format': Path(image_path).suffix.lower(),
            'mode': image.mode
        }

        try:
            # Extract EXIF data
            exif_data = image._getexif()
            if exif_data:
                exif_dict = {}
                for tag_id, value in exif_data.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    exif_dict[tag] = value
                metadata['exif'] = exif_dict

        except Exception as e:
            logger.warning(f"Failed to extract EXIF data: {str(e)}")

        return metadata

    def _analyze_image_content(self, image: Image.Image) -> Dict[str, Any]:
        """Analyze image content and characteristics"""
        analysis = {
            'brightness': self._calculate_brightness(image),
            'contrast': self._calculate_contrast(image),
            'image_type': self._classify_image_type(image),
            'size_category': self._categorize_size(image)
        }

        return analysis

    def _calculate_brightness(self, image: Image.Image) -> float:
        """Calculate average image brightness"""
        try:
            # Convert to grayscale if needed
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image

            # Calculate average brightness
            stat = ImageStat.Stat(gray)
            return float(stat.mean[0] / 255.0)
        except Exception as e:
            logger.warning(f"Failed to calculate brightness: {str(e)}")
            return 0.5

    def _calculate_contrast(self, image: Image.Image) -> float:
        """Calculate image contrast (standard deviation)"""
        try:
            # Convert to grayscale if needed
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image

            # Calculate standard deviation
            stat = ImageStat.Stat(gray)
            return float(stat.stddev[0] / 255.0)
        except Exception as e:
            logger.warning(f"Failed to calculate contrast: {str(e)}")
            return 0.0

    def _classify_image_type(self, image: Image.Image) -> str:
        """Classify image type based on characteristics"""
        width, height = image.size
        aspect_ratio = width / height

        # Basic classification heuristics
        if aspect_ratio > 1.5:
            return "panoramic"
        elif aspect_ratio < 0.7:
            return "portrait"
        elif max(width, height) > 2000:
            return "high_resolution"
        elif min(width, height) < 300:
            return "thumbnail"
        else:
            return "standard"

    def _categorize_size(self, image: Image.Image) -> str:
        """Categorize image size"""
        width, height = image.size
        pixels = width * height

        if pixels >= 4000000:  # 4MP+
            return "large"
        elif pixels >= 1000000:  # 1MP+
            return "medium"
        elif pixels >= 100000:  # 0.1MP+
            return "small"
        else:
            return "tiny"

    def _analyze_colors(self, image: Image.Image) -> Dict[str, Any]:
        """Extract dominant colors from image (Simplified)"""
        try:
            # Simple color analysis using PIL
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Sample colors from the image
            colors = []
            width, height = image.size

            # Sample a grid of points
            sample_size = min(100, max(10, min(width, height) // 10))
            for x in range(0, width, max(1, width // sample_size)):
                for y in range(0, height, max(1, height // sample_size)):
                    try:
                        r, g, b = image.getpixel((x, y))
                        colors.append((r, g, b))
                    except Exception:
                        continue

            if colors:
                # Calculate average color
                avg_r = sum(c[0] for c in colors) / len(colors)
                avg_g = sum(c[1] for c in colors) / len(colors)
                avg_b = sum(c[2] for c in colors) / len(colors)

                # Create a dominant color from the average
                dominant_color = (int(avg_r), int(avg_g), int(avg_b))

                # Determine color characteristics
                color_name = self._get_color_name(dominant_color)

                return {
                    'dominant_colors': [{
                        'rgb': dominant_color,
                        'hex': '#{:02x}{:02x}{:02x}'.format(*dominant_color),
                        'percentage': 1.0,
                        'name': color_name
                    }],
                    'color_count': 1,
                    'average_color': {
                        'rgb': dominant_color,
                        'hex': '#{:02x}{:02x}{:02x}'.format(*dominant_color),
                        'name': color_name
                    },
                    'color_distribution': {
                        'warmth': self._calculate_color_warmth(dominant_color),
                        'brightness_level': sum(dominant_color) / (3 * 255)
                    }
                }
            else:
                return {
                    'dominant_colors': [],
                    'color_count': 0,
                    'average_color': {'rgb': [128, 128, 128], 'hex': '#808080', 'name': 'gray'},
                    'color_distribution': {'warmth': 0.0, 'brightness_level': 0.5}
                }

        except Exception as e:
            logger.error(f"Color analysis failed: {str(e)}")
            return {
                'dominant_colors': [],
                'color_count': 0,
                'average_color': {'rgb': [128, 128, 128], 'hex': '#808080', 'name': 'gray'},
                'color_distribution': {'warmth': 0.0, 'brightness_level': 0.5}
            }

    def _get_color_name(self, rgb: tuple) -> str:
        """Get a simple color name from RGB values"""
        r, g, b = rgb

        # Simple color classification
        if r > 200 and g > 200 and b > 200:
            return "white"
        elif r < 50 and g < 50 and b < 50:
            return "black"
        elif r > g and r > b:
            if r > 150 and g < 100 and b < 100:
                return "red"
            elif g > 100:
                return "orange"
            elif b > 100:
                return "purple"
            else:
                return "red"
        elif g > r and g > b:
            if r > 150:
                return "yellow"
            elif b < 100:
                return "green"
            else:
                return "cyan"
        elif b > r and b > g:
            if r < 100 and g < 100:
                return "blue"
            elif r > 150:
                return "purple"
            else:
                return "blue"
        elif r > 100 and g > 100 and b > 100:
            return "light gray"
        elif r < 100 and g < 100 and b < 100:
            return "dark gray"
        else:
            return "mixed"

    def _calculate_color_warmth(self, rgb: tuple) -> float:
        """Calculate color warmth (-1.0 for cool to 1.0 for warm)"""
        r, g, b = rgb
        # Warm colors have more red, cool colors have more blue
        warmth = (r - b) / 255.0
        return max(-1.0, min(1.0, warmth))

    def _assess_image_quality(self, image: Image.Image, analysis: Dict) -> float:
        """Assess overall image quality (0.0 to 1.0)"""
        quality_score = 0.5  # Base score

        # Brightness factor (prefer well-lit images)
        brightness = analysis['brightness']
        if 0.3 <= brightness <= 0.8:
            quality_score += 0.2
        elif brightness < 0.1 or brightness > 0.9:
            quality_score -= 0.2

        # Contrast factor
        contrast = analysis['contrast']
        if contrast >= 0.1:
            quality_score += 0.1
        else:
            quality_score -= 0.1

        # Image size factor
        width, height = image.size
        if min(width, height) >= 500:
            quality_score += 0.1
        elif min(width, height) < 100:
            quality_score -= 0.2

        # Size category factor
        if analysis['size_category'] == 'large':
            quality_score += 0.1
        elif analysis['size_category'] == 'tiny':
            quality_score -= 0.1

        return max(0.0, min(1.0, quality_score))

    def generate_image_summary(self, image_results: Dict[str, Any]) -> str:
        """Generate a natural language summary of image analysis"""
        try:
            summary_parts = []

            # Basic information
            metadata = image_results['metadata']
            dimensions = metadata['dimensions']
            summary_parts.append(f"Image dimensions: {dimensions['width']}x{dimensions['height']} pixels")

            # Image characteristics
            analysis = image_results['image_analysis']
            summary_parts.append(f"Image type: {analysis['image_type']}, size category: {analysis['size_category']}")
            summary_parts.append(f"Brightness: {analysis['brightness']:.1%}, contrast: {analysis['contrast']:.1%}")

            # Color information
            color_analysis = image_results['color_analysis']
            if color_analysis['dominant_colors']:
                top_color = color_analysis['dominant_colors'][0]
                summary_parts.append(f"Primary color: {top_color['name']} ({top_color['hex']})")

            # Quality assessment
            summary_parts.append(f"Overall image quality: {image_results['quality_score']:.1%}")

            # OCR availability
            if not image_results.get('ocr_available', True):
                summary_parts.append("Text extraction via OCR is not available in this configuration")

            return ". ".join(summary_parts) + "."

        except Exception as e:
            logger.error(f"Failed to generate image summary: {str(e)}")
            return "Image analysis completed with limited details."