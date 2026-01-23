"""
Unit tests for AudioProcessingService
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import time

from src.services.processing import AudioProcessingService


class TestAudioProcessingService:
    """Test cases for AudioProcessingService"""

    @patch('src.services.audio_processing_service.whisper.load_model')
    def test_init_with_whisper_available(self, mock_whisper_load):
        """Test initialization when Whisper is available"""
        mock_model = Mock()
        mock_whisper_load.return_value = mock_model

        service = AudioProcessingService()

        assert service.whisper_model == mock_model
        mock_whisper_load.assert_called_once_with("base")

    @patch('src.services.audio_processing_service.whisper.load_model', side_effect=Exception("Whisper not available"))
    def test_init_without_whisper(self, mock_whisper_load):
        """Test initialization when Whisper is not available"""
        service = AudioProcessingService()

        assert service.whisper_model is None

    def test_supported_audio_formats(self):
        """Test supported audio formats"""
        service = AudioProcessingService()

        expected_formats = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg', '.wma', '.mp4', '.webm'}
        assert service.supported_formats == expected_formats

    def test_process_audio_success(self, mock_audio_file):
        """Test successful audio processing"""
        service = AudioProcessingService()
        service.whisper_model = Mock()

        with patch.object(service, '_extract_audio_metadata', return_value={
            'file_path': mock_audio_file,
            'file_size': 1024_000,
            'file_format': '.wav',
            'duration_seconds': 30.5,
            'bitrate': 128,
            'sample_rate': 44100,
            'channels': 2
        }) as mock_metadata:
            with patch.object(service, '_transcribe_audio', return_value={
                'text': 'This is transcribed audio content',
                'language': 'en',
                'confidence': 0.92,
                'word_count': 6,
                'segments': []
            }) as mock_transcribe:
                with patch.object(service, '_analyze_audio_quality', return_value={
                    'file_size_category': 'small',
                    'duration_category': 'short',
                    'format_quality': 'medium'
                }) as mock_quality:

                    result = service.process_audio(mock_audio_file)

                    assert 'metadata' in result
                    assert 'transcription' in result
                    assert 'quality_analysis' in result
                    assert 'processing_timestamp' in result
                    assert result['transcription_available'] is True
                    assert result['transcription']['text'] == 'This is transcribed audio content'
                    assert result['transcription']['confidence'] == 0.92

    def test_process_audio_file_not_found(self):
        """Test audio processing with non-existent file"""
        service = AudioProcessingService()

        with pytest.raises(FileNotFoundError):
            service.process_audio("/non/existent/audio.mp3")

    def test_process_audio_unsupported_format(self, temp_upload_dir):
        """Test audio processing with unsupported file format"""
        service = AudioProcessingService()

        # Create a file with unsupported extension
        unsupported_file = os.path.join(temp_upload_dir, "test.xyz")
        with open(unsupported_file, "wb") as f:
            f.write(b"fake audio data")

        with pytest.raises(ValueError, match="Unsupported audio format"):
            service.process_audio(unsupported_file)

    def test_extract_audio_metadata_with_ffprobe(self, mock_audio_file):
        """Test audio metadata extraction using ffprobe"""
        service = AudioProcessingService()

        # Mock ffprobe subprocess call
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '''{
            "streams": [{
                "codec_name": "pcm_s16le",
                "sample_rate": "44100",
                "channels": 2,
                "channel_layout": "stereo",
                "duration": "30.5",
                "bit_rate": "1411200"
            }],
            "format": {
                "duration": "30.5",
                "size": "1411200",
                "bit_rate": "1411200",
                "format_name": "wav"
            }
        }'''

        with patch('src.services.audio_processing_service.subprocess.run', return_value=mock_result):
            with patch('json.loads', return_value={}) as mock_json:
                metadata = service._extract_audio_metadata(mock_audio_file)

                assert metadata['duration_seconds'] > 0
                assert 'file_format' in metadata
                assert 'file_size' in metadata

    @patch('src.services.audio_processing_service.subprocess.run')
    def test_extract_audio_metadata_ffprobe_failure(self, mock_subprocess):
        """Test audio metadata extraction when ffprobe fails"""
        service = AudioProcessingService()

        # Mock ffprobe failure
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "ffprobe error"
        mock_subprocess.return_value = mock_result

        # Mock fallback method
        with patch.object(service, '_get_audio_duration', return_value=30.0):
            metadata = service._extract_audio_metadata("test.mp3")

            assert metadata['duration_seconds'] == 30.0
            assert 'file_format' in metadata
            assert 'file_size' in metadata

    def test_get_audio_duration_ffprobe_success(self):
        """Test audio duration extraction using ffprobe"""
        service = AudioProcessingService()

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "30.5\n"

        with patch('src.services.audio_processing_service.subprocess.run', return_value=mock_result):
            duration = service._get_audio_duration("test.mp3")
            assert duration == 30.5

    def test_get_audio_duration_ffprobe_timeout(self):
        """Test audio duration extraction when ffprobe times out"""
        service = AudioProcessingService()

        mock_result = Mock()
        mock_result.returncode = 1
        mock_subprocess = Mock(side_effect=Exception("Timeout"))

        with patch('src.services.audio_processing_service.subprocess.run', side_effect=mock_subprocess):
            # Mock file size for estimation
            with patch('os.path.getsize', return_value=16 * 1024):  # 16KB
                duration = service._get_audio_duration("test.mp3")
                # Should fall back to estimation
                assert duration > 0

    def test_get_audio_duration_estimation(self):
        """Test audio duration estimation as fallback"""
        service = AudioProcessingService()

        with patch('os.path.exists', return_value=True):
            with patch('os.path.getsize', return_value=16 * 1024):  # 16KB at 16KB/s = 1 second
                duration = service._get_audio_duration("test.mp3")
                assert duration == 1.0

    def test_transcribe_audio_with_whisper(self, mock_audio_file):
        """Test audio transcription using Whisper"""
        service = AudioProcessingService()
        service.whisper_model = Mock()

        # Mock Whisper transcription result
        mock_whisper_result = {
            'text': 'This is a test transcription from Whisper.',
            'language': 'en',
            'segments': [
                {
                    'start': 0.0,
                    'end': 2.5,
                    'text': 'This is a test',
                    'avg_logprob': -0.1
                },
                {
                    'start': 2.5,
                    'end': 4.0,
                    'text': 'transcription from Whisper.',
                    'avg_logprob': -0.15
                }
            ]
        }

        service.whisper_model.transcribe.return_value = mock_whisper_result

        result = service._transcribe_audio(mock_audio_file)

        assert result['text'] == 'This is a test transcription from Whisper.'
        assert result['language'] == 'en'
        assert result['word_count'] == 7
        assert len(result['segments']) == 2
        assert result['confidence'] > 0.0

        service.whisper_model.transcribe.assert_called_once_with(
            mock_audio_file,
            fp16=False,
            verbose=False,
            word_timestamps=True,
            task="transcribe"
        )

    def test_transcribe_audio_without_whisper(self, mock_audio_file):
        """Test audio transcription when Whisper is not available"""
        service = AudioProcessingService()
        service.whisper_model = None

        result = service._transcribe_audio(mock_audio_file)

        assert result['text'] == ""
        assert result['language'] == 'unknown'
        assert result['confidence'] == 0.0
        assert len(result['segments']) == 0
        assert 'note' in result
        assert result['note'] == 'Whisper model not available'

    def test_transcribe_audio_whisper_error(self, mock_audio_file):
        """Test audio transcription when Whisper fails"""
        service = AudioProcessingService()
        service.whisper_model = Mock()

        service.whisper_model.transcribe.side_effect = Exception("Whisper processing failed")

        result = service._transcribe_audio(mock_audio_file)

        assert result['text'] == ""
        assert result['language'] == 'unknown'
        assert result['confidence'] == 0.0
        assert 'error' in result
        assert result['error'] == 'Whisper processing failed'

    def test_analyze_audio_quality(self):
        """Test audio quality analysis"""
        service = AudioProcessingService()

        metadata = {
            'file_size': 5_000_000,  # 5MB
            'duration_seconds': 180.0,  # 3 minutes
            'file_format': '.flac'
        }

        quality = service._analyze_audio_quality("test.flac", metadata)

        assert 'file_size_category' in quality
        assert 'duration_category' in quality
        assert 'format_quality' in quality
        assert 'estimated_bitrate' in quality
        assert 'is_large_file' in quality
        assert 'is_long_audio' in quality

        assert quality['file_size_category'] == 'large'
        assert quality['duration_category'] == 'medium'
        assert quality['format_quality'] == 'lossless'
        assert quality['is_large_file'] is False  # 5MB < 50MB
        assert quality['is_long_audio'] is False  # 3min < 30min

    def test_categorize_file_size(self):
        """Test file size categorization"""
        service = AudioProcessingService()

        test_cases = [
            (500_000, "small"),      # 500KB
            (3_000_000, "medium"),   # 3MB
            (30_000_000, "large"),   # 30MB
            (100_000_000, "very_large"),  # 100MB
        ]

        for file_size, expected_category in test_cases:
            category = service._categorize_file_size(file_size)
            assert category == expected_category

    def test_categorize_duration(self):
        """Test audio duration categorization"""
        service = AudioProcessingService()

        test_cases = [
            (15, "very_short"),   # 15 seconds
            (90, "short"),        # 1.5 minutes
            (300, "medium"),      # 5 minutes
            (1200, "long"),       # 20 minutes
            (2400, "very_long"),  # 40 minutes
        ]

        for duration, expected_category in test_cases:
            category = service._categorize_duration(duration)
            assert category == expected_category

    def test_assess_format_quality(self):
        """Test audio format quality assessment"""
        service = AudioProcessingService()

        test_cases = [
            ('.flac', 'lossless'),
            ('.wav', 'lossless'),
            ('.m4a', 'high'),
            ('.aac', 'high'),
            ('.mp3', 'medium'),
            ('.ogg', 'medium'),
            ('.wma', 'low'),
            ('.webm', 'variable'),
            ('.xyz', 'unknown'),
        ]

        for file_format, expected_quality in test_cases:
            quality = service._assess_format_quality(file_format)
            assert quality == expected_quality

    def test_estimate_bitrate(self):
        """Test bitrate estimation"""
        service = AudioProcessingService()

        # Test normal calculation
        bitrate = service._estimate_bitrate(1_000_000, 60)  # 1MB over 60 seconds
        expected_bitrate = (1_000_000 * 8) / 60 / 1000  # Convert to kbps
        assert abs(bitrate - expected_bitrate) < 0.01

        # Test zero duration
        bitrate = service._estimate_bitrate(1_000_000, 0)
        assert bitrate == 0.0

    def test_generate_audio_summary(self):
        """Test audio summary generation"""
        service = AudioProcessingService()

        audio_results = {
            'metadata': {
                'duration_seconds': 180.5,
                'file_format': '.mp3',
                'bitrate': 128,
                'sample_rate': 44100
            },
            'transcription': {
                'text': 'This is the transcribed content from the audio file.',
                'language': 'en',
                'confidence': 0.89,
                'word_count': 11
            },
            'quality_analysis': {
                'file_size_category': 'medium',
                'duration_category': 'medium',
                'format_quality': 'medium',
                'estimated_bitrate': 128.0
            }
        }

        summary = service.generate_audio_summary(audio_results)

        assert '180.5 seconds' in summary
        assert '11 words' in summary
        assert '89%' in summary
        assert 'en' in summary
        assert 'medium' in summary
        assert '128 kbps' in summary

    def test_generate_audio_summary_no_transcription(self):
        """Test audio summary generation when transcription is not available"""
        service = AudioProcessingService()

        audio_results = {
            'metadata': {
                'duration_seconds': 120.0,
                'file_format': '.wav',
                'bitrate': 1411,
                'sample_rate': 44100
            },
            'transcription': {
                'text': '',
                'language': 'unknown',
                'confidence': 0.0,
                'word_count': 0,
                'note': 'Whisper model not available'
            },
            'quality_analysis': {
                'file_size_category': 'large',
                'duration_category': 'short',
                'format_quality': 'lossless',
                'estimated_bitrate': 1411.0
            },
            'transcription_available': False
        }

        summary = service.generate_audio_summary(audio_results)

        assert '120.0 seconds' in summary
        assert 'Audio transcription not available' in summary
        assert 'lossless' in summary
        assert '1411 kbps' in summary

    def test_segment_long_audio(self, mock_audio_file):
        """Test audio segmentation for long files"""
        service = AudioProcessingService()

        with patch.object(service, '_get_audio_duration', return_value=900):  # 15 minutes
            segments = service.segment_long_audio(mock_audio_file, segment_duration=300)

            # Should create 3 segments for 15 minute audio with 5 minute segments
            assert len(segments) == 3
            assert all(seg.endswith('.wav') for seg in segments)
            assert 'segment_000' in segments[0]
            assert 'segment_001' in segments[1]
            assert 'segment_002' in segments[2]

    def test_segment_short_audio(self, mock_audio_file):
        """Test audio segmentation for short files"""
        service = AudioProcessingService()

        with patch.object(service, '_get_audio_duration', return_value=120):  # 2 minutes
            segments = service.segment_long_audio(mock_audio_file, segment_duration=300)

            # Should return single segment for short audio
            assert len(segments) == 1
            assert segments[0] == mock_audio_file

    def test_process_audio_performance(self, mock_audio_file):
        """Test audio processing performance"""
        service = AudioProcessingService()
        service.whisper_model = Mock()

        # Mock fast processing
        with patch.object(service, '_extract_audio_metadata', return_value={}):
            with patch.object(service, '_transcribe_audio', return_value={
                'text': 'Test', 'language': 'en', 'confidence': 0.9, 'word_count': 1, 'segments': []
            }):
                with patch.object(service, '_analyze_audio_quality', return_value={}):

                    start_time = time.time()
                    result = service.process_audio(mock_audio_file)
                    end_time = time.time()

                    processing_time = end_time - start_time

                    # Should complete quickly for mocked operations
                    assert processing_time < 1.0
                    assert 'metadata' in result
                    assert 'transcription' in result
                    assert 'quality_analysis' in result

    def test_process_corrupted_audio(self, temp_upload_dir):
        """Test processing of corrupted audio files"""
        service = AudioProcessingService()

        # Create a corrupted audio file
        corrupted_file = os.path.join(temp_upload_dir, "corrupted.mp3")
        with open(corrupted_file, "wb") as f:
            f.write(b"corrupted audio data that is not valid")

        with patch.object(service, '_extract_audio_metadata', side_effect=Exception("Corrupted file")):
            with pytest.raises(Exception, match="Corrupted file"):
                service.process_audio(corrupted_file)

    @patch('src.services.audio_processing_service.Mutagen.File')
    def test_extract_detailed_metadata_with_mutagen(self, mock_mutagen_file, mock_audio_file):
        """Test detailed metadata extraction using mutagen"""
        service = AudioProcessingService()

        # Mock mutagen File object
        mock_file = Mock()
        mock_file.info = Mock()
        mock_file.info.bitrate = 128000
        mock_file.info.sample_rate = 44100
        mock_file.info.channels = 2
        mock_file.info.length = 30.5
        mock_file.tags = Mock()
        mock_file.tags.get.side_effect = lambda key, default: {
            'TIT2': ['Test Song'],
            'TPE1': ['Test Artist'],
            'TALB': ['Test Album'],
            'TDRC': ['2023'],
            'TCON': ['Rock']
        }.get(key, default)
        mock_mutagen_file.return_value = mock_file

        with patch('os.path.getsize', return_value=1_000_000):
            metadata = service._extract_audio_metadata(mock_audio_file)

            assert metadata['bitrate'] == 128000
            assert metadata['sample_rate'] == 44100
            assert metadata['channels'] == 2
            assert metadata['length'] == 30.5
            assert metadata['title'] == 'Test Song'
            assert metadata['artist'] == 'Test Artist'
            assert metadata['album'] == 'Test Album'
            assert metadata['date'] == '2023'
            assert metadata['genre'] == 'Rock'

    def test_transcribe_audio_with_different_languages(self, mock_audio_file):
        """Test audio transcription with different languages"""
        service = AudioProcessingService()
        service.whisper_model = Mock()

        # Mock Spanish transcription
        mock_whisper_result = {
            'text': 'Este es un texto de prueba en español.',
            'language': 'es',
            'segments': [{'start': 0.0, 'end': 3.0, 'text': 'Este es un texto', 'avg_logprob': -0.2}]
        }

        service.whisper_model.transcribe.return_value = mock_whisper_result

        result = service._transcribe_audio(mock_audio_file)

        assert result['text'] == 'Este es un texto de prueba en español.'
        assert result['language'] == 'es'
        assert result['confidence'] > 0.0

    def test_extract_audio_metadata_multiple_streams(self, mock_audio_file):
        """Test metadata extraction for audio with multiple streams"""
        service = AudioProcessingService()

        # Mock ffprobe output with multiple streams
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '''{
            "streams": [
                {
                    "codec_name": "aac",
                    "sample_rate": "44100",
                    "channels": 2,
                    "duration": "30.5"
                },
                {
                    "codec_name": "aac",
                    "sample_rate": "44100",
                    "channels": 1,
                    "duration": "30.5"
                }
            ],
            "format": {
                "duration": "30.5",
                "size": "500000"
            }
        }'''

        with patch('src.services.audio_processing_service.subprocess.run', return_value=mock_result):
            with patch('json.loads', return_value={}) as mock_json:
                metadata = service._extract_audio_metadata(mock_audio_file)

                # Should handle multiple streams
                assert metadata['duration_seconds'] > 0
                assert 'streams' in metadata or 'file_format' in metadata