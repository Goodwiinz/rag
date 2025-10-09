"""
Test fixtures for different file types and processing scenarios
"""

import pytest
import os
import tempfile
import json
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from typing import Dict, Any, List, Optional
from unittest.mock import Mock

from src.models.document import DocumentType
from src.models.entity import EntityType


@pytest.fixture
def temp_upload_dir():
    """Create temporary directory for test files"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_text_file(temp_upload_dir):
    """Create a sample text file for testing"""
    file_path = os.path.join(temp_upload_dir, "sample.txt")
    content = """This is a sample text document for testing purposes.

It contains multiple paragraphs and various content types including:
- Regular text content
- Some numbers like 123 and 4567
- Email addresses: test@example.com, admin@company.org
- URLs: https://www.example.com, http://test.org
- Company names: Acme Corporation, Global Tech Inc
- Person names: John Smith, Jane Doe
- Locations: New York, San Francisco, London

This document should be suitable for testing text extraction,
entity recognition, and quality assessment features.

Contact Information:
- Phone: (555) 123-4567, +1-555-987-6543
- Email: contact@example.com
- Website: https://www.example.com

Financial Information:
- Budget: $1,000,000
- Revenue: $5,500,000
- Date: December 15, 2023

The content should provide good test coverage for various
processing components including NLP, entity extraction, and
metadata analysis.
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    yield file_path


@pytest.fixture
def sample_multilingual_text_file(temp_upload_dir):
    """Create a multilingual text file for testing"""
    file_path = os.path.join(temp_upload_dir, "multilingual.txt")
    content = """English Section:
This is English content for testing language detection.
The system should identify this as English text.

Spanish Section:
Este es contenido en español para probar la detección de idiomas.
El sistema debería identificar esto como texto en español.

French Section:
Ceci est un contenu français pour tester la détection de langue.
Le système devrait identifier ceci comme du texte français.

Mixed Content:
John Smith works at Global Corporation.
Él está en Nueva York.
Il visite Paris souvent.
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    yield file_path


@pytest.fixture
def sample_entity_rich_text_file(temp_upload_dir):
    """Create a text file rich in entities for extraction testing"""
    file_path = os.path.join(temp_upload_dir, "entities.txt")
    content = """Entity Extraction Test Document

People:
- John Smith (CEO) can be reached at john.smith@techcorp.com
- Jane Doe (CTO) works at Innovation Labs Inc.
- Dr. Michael Johnson from Medical Research Center
- Professor Emily Brown from University of Technology

Organizations:
- Microsoft Corporation based in Redmond, Washington
- Google Inc. located in Mountain View, California
- Apple Inc. headquartered in Cupertino, California
- Amazon.com Inc. in Seattle, Washington
- Tesla Inc. in Austin, Texas

Locations:
- New York City, New York
- San Francisco Bay Area, California
- Boston, Massachusetts
- Chicago, Illinois
- Miami, Florida

Contact Information:
- Sales: sales@company.com, (555) 123-4567
- Support: support@help.org, (555) 987-6543
- International: +1-555-555-5555

Websites:
- Corporate: https://www.corporate.com
- Products: https://products.company.org
- Support: https://help.company.net

Financial Data:
- Q1 Revenue: $2,500,000
- Q2 Profit: $1,200,000
- Annual Budget: $10,000,000
- Stock Price: $156.75

Dates and Events:
- Annual Meeting: March 15, 2024
- Product Launch: June 30, 2024
- Conference: September 10-12, 2024
- Deadline: December 31, 2024

Additional Entities:
- Product Name: SmartAnalytics Pro 2.0
- Project Code: ALPHA-2024-X1
- Reference ID: DOC-2024-001
- Patent Number: US10,123,456B2
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    yield file_path


@pytest.fixture
def sample_large_text_file(temp_upload_dir):
    """Create a large text file for performance testing"""
    file_path = os.path.join(temp_upload_dir, "large.txt")

    # Generate repetitive content to create a large file
    base_content = """
This is a large text document for performance testing purposes.

The document contains business-related content including:
- Company information: Acme Corporation, Global Tech Inc, Innovation Solutions
- Person references: John Smith, Jane Doe, Michael Johnson
- Location data: New York, San Francisco, Chicago
- Contact details: contact@company.com, (555) 123-4567
- Financial figures: $1,000,000 in revenue, $500,000 in expenses
- Website references: https://www.company.com

Such large documents are used to test the performance and scalability
of text processing components including extraction, parsing, and analysis.
"""

    # Repeat content to create approximately 1MB file
    target_size = 1024 * 1024  # 1MB
    content = ""
    while len(content.encode('utf-8')) < target_size:
        content += base_content

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    yield file_path


@pytest.fixture
def sample_image_file(temp_upload_dir):
    """Create a sample image file for testing"""
    file_path = os.path.join(temp_upload_dir, "test_image.png")

    # Create a simple test image
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)

    # Add some visual elements
    draw.rectangle([50, 50, 750, 550], outline='black', width=2)
    draw.ellipse([100, 100, 700, 500], fill='lightgray', outline='black')

    # Add text if possible
    try:
        font = ImageFont.load_default()
        draw.text((400, 300), "Test Image", fill='black', font=font, anchor='mm')
    except:
        pass  # Skip text if font not available

    img.save(file_path, 'PNG')
    yield file_path


@pytest.fixture
def sample_image_with_text(temp_upload_dir):
    """Create an image file with text for OCR testing"""
    file_path = os.path.join(temp_upload_dir, "text_image.png")

    # Create image with readable text
    img = Image.new('RGB', (1200, 800), color='white')
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.load_default()

        # Add various text samples
        text_samples = [
            "OCR Test Document",
            "This image contains text for OCR testing",
            "Company: Acme Corporation",
            "Contact: info@acme.com",
            "Phone: (555) 123-4567",
            "Address: 123 Business St, City, State 12345",
            "Date: December 15, 2023"
        ]

        y_pos = 50
        for text in text_samples:
            draw.text((50, y_pos), text, fill='black', font=font)
            y_pos += 60

    except:
        # If font not available, create simple pattern
        for i in range(10):
            y = i * 80
            draw.rectangle([50, y, 1150, y + 40], fill='gray' if i % 2 == 0 else 'white')

    img.save(file_path, 'PNG')
    yield file_path


@pytest.fixture
def sample_high_resolution_image(temp_upload_dir):
    """Create a high-resolution image for testing"""
    file_path = os.path.join(temp_upload_dir, "high_res.jpg")

    # Create high-resolution image with complex content
    width, height = 4000, 3000
    img_array = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    img = Image.fromarray(img_array, 'RGB')

    # Add some structured content
    draw = ImageDraw.Draw(img)

    # Draw a grid pattern
    for i in range(0, width, 200):
        draw.line([i, 0, i, height], fill='black', width=1)
    for i in range(0, height, 200):
        draw.line([0, i, width, i], fill='black', width=1)

    # Add some rectangles
    for i in range(10):
        x1 = np.random.randint(0, width - 200)
        y1 = np.random.randint(0, height - 200)
        x2 = x1 + np.random.randint(100, 200)
        y2 = y1 + np.random.randint(100, 200)
        color = (np.random.randint(0, 256), np.random.randint(0, 256), np.random.randint(0, 256))
        draw.rectangle([x1, y1, x2, y2], fill=color, outline='black')

    img.save(file_path, 'JPEG', quality=95)
    yield file_path


@pytest.fixture
def sample_corrupted_image(temp_upload_dir):
    """Create a corrupted image file for error testing"""
    file_path = os.path.join(temp_upload_dir, "corrupted.png")

    # Write data that looks like image but isn't valid
    with open(file_path, "wb") as f:
        f.write(b"This is not a valid PNG image file at all!")
        f.write(b"Fake image data that should cause processing errors.")
        f.write(b"Not a real PNG header or image data structure.")

    yield file_path


@pytest.fixture
def sample_audio_file(temp_upload_dir):
    """Create a mock audio file for testing"""
    file_path = os.path.join(temp_upload_dir, "test_audio.mp3")

    # Generate mock audio data (binary pattern)
    sample_rate = 44100
    duration_seconds = 10
    samples = sample_rate * duration_seconds * 2  # Stereo

    # Create sine wave-like pattern
    audio_data = np.zeros(samples, dtype=np.uint8)
    for i in range(0, samples, 100):
        audio_data[i] = int(128 + 127 * np.sin(i * 0.01))

    with open(file_path, "wb") as f:
        f.write(audio_data.tobytes())

    yield file_path


@pytest.fixture
def sample_long_audio_file(temp_upload_dir):
    """Create a longer mock audio file for performance testing"""
    file_path = os.path.join(temp_upload_dir, "long_audio.mp3")

    # Generate longer mock audio data
    sample_rate = 44100
    duration_seconds = 300  # 5 minutes
    samples = sample_rate * duration_seconds * 2  # Stereo

    # Create varied audio patterns
    audio_data = np.random.randint(0, 256, samples, dtype=np.uint8)

    with open(file_path, "wb") as f:
        f.write(audio_data.tobytes())

    yield file_path


@pytest.fixture
def sample_corrupted_audio(temp_upload_dir):
    """Create a corrupted audio file for error testing"""
    file_path = os.path.join(temp_upload_dir, "corrupted.mp3")

    # Write invalid audio data
    with open(file_path, "wb") as f:
        f.write(b"This is not a valid MP3 audio file!")
        f.write(b"Fake audio data that should cause processing errors.")

    yield file_path


@pytest.fixture
def sample_video_file(temp_upload_dir):
    """Create a mock video file for testing"""
    file_path = os.path.join(temp_upload_dir, "test_video.mp4")

    # Generate mock video data
    width, height = 1920, 1080
    fps = 30
    duration_seconds = 60
    total_frames = fps * duration_seconds

    # Create mock video frames
    frame_size = width * height * 3  # RGB
    video_data = np.random.randint(0, 256, frame_size * total_frames, dtype=np.uint8)

    with open(file_path, "wb") as f:
        f.write(video_data.tobytes())

    yield file_path


@pytest.fixture
def sample_high_resolution_video(temp_upload_dir):
    """Create a high-resolution mock video file for testing"""
    file_path = os.path.join(temp_upload_dir, "high_res_video.mp4")

    # Generate 4K video mock data
    width, height = 3840, 2160
    fps = 30
    duration_seconds = 120  # 2 minutes
    total_frames = fps * duration_seconds

    frame_size = width * height * 3  # RGB
    video_data = np.random.randint(0, 256, frame_size * total_frames, dtype=np.uint8)

    with open(file_path, "wb") as f:
        f.write(video_data.tobytes())

    yield file_path


@pytest.fixture
def sample_corrupted_video(temp_upload_dir):
    """Create a corrupted video file for error testing"""
    file_path = os.path.join(temp_upload_dir, "corrupted.mp4")

    # Write invalid video data
    with open(file_path, "wb") as f:
        f.write(b"This is not a valid MP4 video file!")
        f.write(b"Fake video data that should cause processing errors.")

    yield file_path


@pytest.fixture
def sample_pdf_file(temp_upload_dir):
    """Create a mock PDF file for testing"""
    file_path = os.path.join(temp_upload_dir, "test.pdf")

    # Create minimal PDF-like structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Sample PDF Content) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f
0000000010 00000 n
0000000079 00000 n
0000000173 00000 n
0000000301 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
396
%%EOF
"""

    with open(file_path, "wb") as f:
        f.write(pdf_content)

    yield file_path


@pytest.fixture
def sample_empty_file(temp_upload_dir):
    """Create an empty file for edge case testing"""
    file_path = os.path.join(temp_upload_dir, "empty.txt")
    with open(file_path, "w") as f:
        pass  # Create empty file
    yield file_path


@pytest.fixture
def sample_whitespace_only_file(temp_upload_dir):
    """Create a file with only whitespace for edge case testing"""
    file_path = os.path.join(temp_upload_dir, "whitespace.txt")
    with open(file_path, "w") as f:
        f.write("   \n\t   \n\n   \t\n")  # Only whitespace
    yield file_path


@pytest.fixture
def sample_special_characters_file(temp_upload_dir):
    """Create a file with special characters and unicode"""
    file_path = os.path.join(temp_upload_dir, "special_chars.txt")
    content = """Special Characters Test Document

Unicode Characters:
- Accents: José Martínez, Søren Andersen, François Dubois
- Asian: 北京, 東京, 서울, मुंबई
- Symbols: ©, ®, ™, €, ¥, £, §, ¶
- Math: ∑, ∏, ∫, √, ∞, ±, ≠, ≤, ≥
- Arrows: →, ←, ↑, ↓, ↔, ↕

Special Characters:
- Quotes: "Hello", 'World', «French», »German«
- Dashes: – (en dash), — (em dash)
- Ellipsis: …
- Bullets: •, ‣, ⁃

Control Characters:
- Tab:	Tabbed content
- Newline: Multiple
lines

Programming:
- JSON: {"key": "value", "number": 123}
- XML: <tag attribute="value">content</tag>
- URL: https://example.com/path?param=value&other=data

Email and Contact:
- Emails: user+tag@example.com, admin@sub.domain.org
- Phone: +1-555-123-4567, (555) 987-6543

This file tests handling of various character encodings
and special characters in text processing.
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    yield file_path


@pytest.fixture
def sample_mixed_content_file(temp_upload_dir):
    """Create a file with mixed content types"""
    file_path = os.path.join(temp_upload_dir, "mixed_content.txt")
    content = """Mixed Content Document

Structured Data:
[JSON]
{
  "company": "Acme Corporation",
  "employees": [
    {"name": "John Smith", "role": "CEO", "email": "john@acme.com"},
    {"name": "Jane Doe", "role": "CTO", "email": "jane@acme.com"}
  ],
  "revenue": 5000000,
  "locations": ["New York", "San Francisco", "London"]
}
[/JSON]

[XML]
<company>
  <name>Global Tech Inc</name>
  <contact>
    <phone>(555) 123-4567</phone>
    <email>info@globaltech.com</email>
  </contact>
  <address>
    <street>123 Tech Street</street>
    <city>Innovation City</city>
    <state>CA</state>
  </address>
</company>
[/XML]

Tables:
Name | Role | Department | Email
John Smith | Manager | Sales | john.smith@company.com
Jane Doe | Developer | Engineering | jane.doe@company.com
Mike Johnson | Analyst | Marketing | mike.johnson@company.com

Lists:
- High priority items:
  1. Complete Q4 report
  2. Prepare budget presentation
  3. Schedule team meetings

- Contact information:
  * Office: (555) 123-4567
  * Mobile: (555) 987-6543
  * Email: contact@company.com

Code snippets:
function processDocument(content) {
    const entities = extractEntities(content);
    return {
        people: entities.filter(e => e.type === 'PERSON'),
        organizations: entities.filter(e => e.type === 'ORG'),
        locations: entities.filter(e => e.type === 'LOCATION')
    };
}

Regular expressions:
- Email: \b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b
- Phone: \b\d{3}[-.]?\d{3}[-.]?\d{4}\b
- URL: https?://[^\s]+

This document tests processing of various structured and
unstructured content formats that might be encountered in real
business documents.
"""
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    yield file_path


@pytest.fixture
def sample_files_collection(temp_upload_dir):
    """Create a collection of various sample files for comprehensive testing"""
    files = {}

    # Text files
    files['text_basic'] = os.path.join(temp_upload_dir, "basic.txt")
    with open(files['text_basic'], "w") as f:
        f.write("Basic text document for testing.\nSecond line of text.")

    files['text_medium'] = os.path.join(temp_upload_dir, "medium.txt")
    with open(files['text_medium'], "w") as f:
        f.write("Medium sized text document.\n" * 100)

    files['text_large'] = os.path.join(temp_upload_dir, "large.txt")
    with open(files['text_large'], "w") as f:
        f.write("Large text document for performance testing.\n" * 1000)

    # Create simple images
    for name, size in [('small', (200, 150)), ('medium', (800, 600)), ('large', (1600, 1200))]:
        files[f'image_{name}'] = os.path.join(temp_upload_dir, f"image_{name}.png")
        img = Image.new('RGB', size, color='white')
        ImageDraw.Draw(img).rectangle([10, 10, size[0]-10, size[1]-10], outline='black')
        img.save(files[f'image_{name}'], 'PNG')

    # Create mock audio files
    for name, duration in [('short', 5), ('medium', 30), ('long', 120)]:
        files[f'audio_{name}'] = os.path.join(temp_upload_dir, f"audio_{name}.mp3")
        samples = duration * 44100 * 2  # duration * sample_rate * channels
        audio_data = np.random.randint(0, 256, samples, dtype=np.uint8)
        with open(files[f'audio_{name}'], "wb") as f:
            f.write(audio_data.tobytes())

    # Create mock video files
    for name, duration in [('short', 10), ('medium', 60), ('long', 300)]:
        files[f'video_{name}'] = os.path.join(temp_upload_dir, f"video_{name}.mp4")
        frame_size = 1920 * 1080 * 3  # width * height * channels
        total_frames = duration * 30  # duration * fps
        video_data = np.random.randint(0, 256, frame_size * total_frames, dtype=np.uint8)
        with open(files[f'video_{name}'], "wb") as f:
            f.write(video_data.tobytes())

    yield files


@pytest.fixture
def file_processing_test_cases():
    """Define standard test cases for file processing"""
    return [
        {
            'name': 'basic_text',
            'type': DocumentType.TEXT,
            'description': 'Basic text file processing',
            'expected_entities': [EntityType.PERSON, EntityType.ORGANIZATION, EntityType.EMAIL],
            'expected_processing_time': 2.0  # seconds
        },
        {
            'name': 'entity_rich_text',
            'type': DocumentType.TEXT,
            'description': 'Text file rich in entities',
            'expected_entities': [EntityType.PERSON, EntityType.ORGANIZATION, EntityType.LOCATION,
                                 EntityType.EMAIL, EntityType.PHONE, EntityType.URL],
            'expected_processing_time': 5.0
        },
        {
            'name': 'large_text',
            'type': DocumentType.TEXT,
            'description': 'Large text file for performance testing',
            'expected_entities': [EntityType.PERSON, EntityType.ORGANIZATION],
            'expected_processing_time': 30.0
        },
        {
            'name': 'basic_image',
            'type': DocumentType.IMAGE,
            'description': 'Basic image processing',
            'expected_metadata': ['width', 'height', 'format'],
            'expected_processing_time': 3.0
        },
        {
            'name': 'ocr_image',
            'type': DocumentType.IMAGE,
            'description': 'Image with text for OCR',
            'expected_metadata': ['width', 'height', 'format', 'ocr_text'],
            'expected_processing_time': 10.0
        },
        {
            'name': 'high_res_image',
            'type': DocumentType.IMAGE,
            'description': 'High-resolution image processing',
            'expected_metadata': ['width', 'height', 'format', 'quality_score'],
            'expected_processing_time': 15.0
        },
        {
            'name': 'basic_audio',
            'type': DocumentType.AUDIO,
            'description': 'Basic audio processing',
            'expected_metadata': ['duration', 'format', 'sample_rate'],
            'expected_processing_time': 20.0
        },
        {
            'name': 'long_audio',
            'type': DocumentType.AUDIO,
            'description': 'Long audio file for performance testing',
            'expected_metadata': ['duration', 'format', 'transcription'],
            'expected_processing_time': 120.0
        },
        {
            'name': 'basic_video',
            'type': DocumentType.VIDEO,
            'description': 'Basic video processing',
            'expected_metadata': ['duration', 'width', 'height', 'format'],
            'expected_processing_time': 45.0
        },
        {
            'name': 'high_res_video',
            'type': DocumentType.VIDEO,
            'description': 'High-resolution video processing',
            'expected_metadata': ['duration', 'width', 'height', 'format', 'fps'],
            'expected_processing_time': 180.0
        }
    ]


@pytest.fixture
def error_test_scenarios():
    """Define error scenarios for testing"""
    return [
        {
            'name': 'corrupted_text',
            'type': DocumentType.TEXT,
            'description': 'Corrupted text file',
            'expected_error': 'FileProcessingError'
        },
        {
            'name': 'corrupted_image',
            'type': DocumentType.IMAGE,
            'description': 'Corrupted image file',
            'expected_error': 'FileProcessingError'
        },
        {
            'name': 'corrupted_audio',
            'type': DocumentType.AUDIO,
            'description': 'Corrupted audio file',
            'expected_error': 'FileProcessingError'
        },
        {
            'name': 'corrupted_video',
            'type': DocumentType.VIDEO,
            'description': 'Corrupted video file',
            'expected_error': 'FileProcessingError'
        },
        {
            'name': 'nonexistent_file',
            'type': DocumentType.OTHER,
            'description': 'Nonexistent file path',
            'expected_error': 'ResourceNotFoundError'
        },
        {
            'name': 'empty_file',
            'type': DocumentType.TEXT,
            'description': 'Empty file',
            'expected_error': None  # Should handle gracefully
        },
        {
            'name': 'permission_denied',
            'type': DocumentType.TEXT,
            'description': 'File with no read permissions',
            'expected_error': 'PermissionError'
        },
        {
            'name': 'too_large_file',
            'type': DocumentType.TEXT,
            'description': 'File exceeding size limits',
            'expected_error': 'ValidationError'
        }
    ]