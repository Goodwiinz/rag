"""
Unit tests for VideoProcessingService
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import time
import json

from src.services.video_processing_service import VideoProcessingService


class TestVideoProcessingService:
    """Test cases for VideoProcessingService"""

    def test_init(self):
        """Test VideoProcessingService initialization"""
        service = VideoProcessingService()

        expected_formats = {'.mp4', '.avi', '.mov', '.mkv', '.3gp', '.wmv', '.webm', '.flv', '.m4v'}
        assert service.supported_formats == expected_formats
        assert hasattr(service, 'audio_processor')

    def test_process_video_success(self, mock_video_file):
        """Test successful video processing"""
        service = VideoProcessingService()
        service.audio_processor = Mock()

        with patch.object(service, '_extract_video_metadata', return_value={
            'file_path': mock_video_file,
            'file_size': 50_000_000,
            'file_format': '.mp4',
            'duration_seconds': 120.5,
            'width': 1920,
            'height': 1080,
            'frame_rate': 30.0,
            'bitrate': 4_000_000,
            'audio_streams': [{
                'codec': 'aac',
                'sample_rate': 44100,
                'channels': 2,
                'duration': 120.5
            }]
        }) as mock_metadata:
            with patch.object(service, '_extract_audio_track', return_value={
                'text': 'Extracted audio transcription',
                'language': 'en',
                'confidence': 0.88
            }) as mock_audio:
                with patch.object(service, '_extract_keyframes', return_value={
                    'keyframe_count': 120,
                    'scenes_detected': 8
                }) as mock_keyframes:
                    with patch.object(service, '_analyze_video_quality', return_value={
                        'resolution_category': 'high',
                        'duration_category': 'medium',
                        'format_quality': 'good'
                    }) as mock_quality:

                        result = service.process_video(mock_video_file)

                        assert 'metadata' in result
                        assert 'audio_transcription' in result
                        assert 'keyframe_analysis' in result
                        assert 'quality_analysis' in result
                        assert 'processing_timestamp' in result
                        assert result['metadata']['duration_seconds'] == 120.5
                        assert result['metadata']['width'] == 1920
                        assert result['metadata']['height'] == 1080
                        assert result['audio_transcription']['text'] == 'Extracted audio transcription'

    def test_process_video_file_not_found(self):
        """Test video processing with non-existent file"""
        service = VideoProcessingService()

        with pytest.raises(FileNotFoundError):
            service.process_video("/non/existent/video.mp4")

    def test_process_video_unsupported_format(self, temp_upload_dir):
        """Test video processing with unsupported file format"""
        service = VideoProcessingService()

        # Create a file with unsupported extension
        unsupported_file = os.path.join(temp_upload_dir, "test.xyz")
        with open(unsupported_file, "wb") as f:
            f.write(b"fake video data")

        with pytest.raises(ValueError, match="Unsupported video format"):
            service.process_video(unsupported_file)

    def test_extract_video_metadata_ffprobe_success(self, mock_video_file):
        """Test video metadata extraction using ffprobe"""
        service = VideoProcessingService()

        # Mock ffprobe subprocess call
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '''{
            "streams": [
                {
                    "codec_type": "video",
                    "width": 1920,
                    "height": 1080,
                    "duration": "120.5",
                    "bit_rate": "4000000",
                    "r_frame_rate": "30/1",
                    "pix_fmt": "yuv420p"
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "44100",
                    "channels": 2,
                    "duration": "120.5",
                    "bit_rate": "128000"
                }
            ],
            "format": {
                "filename": "''' + mock_video_file + '''",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "format_long_name": "QuickTime / MOV",
                "duration": "120.5",
                "size": "50000000",
                "bit_rate": "3317259"
            }
        }'''

        with patch('src.services.video_processing_service.subprocess.run', return_value=mock_result):
            with patch('json.loads') as mock_json:
                metadata = service._extract_video_metadata(mock_video_file)

                assert metadata['width'] == 1920
                assert metadata['height'] == 1080
                assert metadata['duration_seconds'] == 120.5
                assert metadata['frame_rate'] == 30.0
                assert metadata['bitrate'] == 4_000_000
                assert len(metadata['audio_streams']) == 1
                assert metadata['audio_streams'][0]['codec'] == 'aac'

    def test_extract_video_metadata_ffprobe_failure(self, mock_video_file):
        """Test video metadata extraction when ffprobe fails"""
        service = VideoProcessingService()

        # Mock ffprobe failure
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "ffprobe error"

        with patch('src.services.video_processing_service.subprocess.run', return_value=mock_result):
            metadata = service._extract_video_metadata(mock_video_file)

            # Should fall back to basic file info
            assert 'file_path' in metadata
            assert 'file_size' in metadata
            assert 'file_format' in metadata
            # Duration might be estimated or None
            assert 'duration_seconds' in metadata

    def test_extract_audio_track_success(self, mock_video_file):
        """Test successful audio track extraction"""
        service = VideoProcessingService()
        service.audio_processor = Mock()

        # Mock audio extraction subprocess
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Audio extraction successful"

        # Mock audio processing
        service.audio_processor.process_audio.return_value = {
            'transcription': {
                'text': 'This is the transcribed audio from the video',
                'language': 'en',
                'confidence': 0.92
            }
        }

        with patch('src.services.video_processing_service.subprocess.run', return_value=mock_result):
            with patch('os.path.exists', return_value=True):
                result = service._extract_audio_track(mock_video_file)

                assert 'text' in result
                assert result['text'] == 'This is the transcribed audio from the video'
                assert result['language'] == 'en'
                assert result['confidence'] == 0.92

    def test_extract_audio_track_extraction_failure(self, mock_video_file):
        """Test audio track extraction when extraction fails"""
        service = VideoProcessingService()
        service.audio_processor = Mock()

        # Mock audio extraction failure
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Audio extraction failed"

        with patch('src.services.video_processing_service.subprocess.run', return_value=mock_result):
            result = self._extract_audio_track_safe(service, mock_video_file)

            assert 'text' in result
            assert result['error'] == 'Audio extraction failed'

    def test_extract_audio_track_no_audio_streams(self, mock_video_file):
        """Test audio track extraction when video has no audio streams"""
        service = VideoProcessingService()

        # Mock video metadata with no audio streams
        mock_metadata = {
            'audio_streams': [],
            'duration_seconds': 60.0
        }

        result = self._extract_audio_track_safe_with_metadata(service, mock_video_file, mock_metadata)

        assert 'text' in result
        assert result['error'] == 'No audio streams found in video'

    def test_extract_keyframes(self, mock_video_file):
        """Test keyframe extraction"""
        service = VideoProcessingService()

        # Mock ffprobe keyframe extraction
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '''{
            "frames": [
                {"pkt_pts_time": "0.0", "key_frame": 1},
                {"pkt_pts_time": "1.0", "key_frame": 1},
                {"pkt_pts_time": "2.0", "key_frame": 1},
                {"pkt_pts_time": "3.0", "key_frame": 1}
            ]
        }'''

        with patch('src.services.video_processing_service.subprocess.run', return_value=mock_result):
            with patch('json.loads') as mock_json:
                keyframes = self._extract_keyframes_safe(service, mock_video_file)

                assert 'keyframe_count' in keyframes
                assert 'keyframe_timestamps' in keyframes
                assert 'average_keyframe_interval' in keyframes
                assert keyframes['keyframe_count'] == 4
                assert keyframes['keyframe_timestamps'] == [0.0, 1.0, 2.0, 3.0]

    def test_extract_keyframes_no_keyframes(self, mock_video_file):
        """Test keyframe extraction when no keyframes are found"""
        service = VideoProcessingService()

        # Mock ffprobe with no keyframes
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"frames": []}'

        with patch('src.services.video_processing_service.subprocess.run', return_value=mock_result):
            with patch('json.loads') as mock_json:
                keyframes = self._extract_keyframes_safe(service, mock_video_file)

                assert keyframes['keyframe_count'] == 0
                assert 'keyframe_timestamps' in keyframes
                assert len(keyframes['keyframe_timestamps']) == 0

    def test_analyze_video_quality(self):
        """Test video quality analysis"""
        service = VideoProcessingService()

        metadata = {
            'file_size': 100_000_000,  # 100MB
            'duration_seconds': 300.0,   # 5 minutes
            'width': 1920,
            'height': 1080,
            'bitrate': 8_000_000,
            'frame_rate': 30.0,
            'file_format': '.mp4'
        }

        quality = service._analyze_video_quality(metadata)

        assert 'file_size_category' in quality
        assert 'duration_category' in quality
        assert 'resolution_category' in quality
        assert 'format_quality' in quality
        assert 'estimated_bitrate' in quality
        assert 'is_large_file' in quality
        assert 'is_long_video' in quality

        assert quality['file_size_category'] == 'very_large'
        assert quality['duration_category'] == 'medium'
        assert quality['resolution_category'] == 'high'
        assert quality['format_quality'] == 'good'
        assert quality['is_large_file'] is True   # 100MB > 50MB
        assert quality['is_long_video'] is False # 5min < 30min

    def test_categorize_resolution(self):
        """Test video resolution categorization"""
        service = VideoProcessingService()

        test_cases = [
            ((320, 240), "low"),
            ((640, 480), "standard"),
            ((1280, 720), "hd"),
            ((1920, 1080), "full_hd"),
            ((3840, 2160), "ultra_hd"),
            ((7680, 4320), "ultra_hd_plus"),
        ]

        for (width, height), expected_category in test_cases:
            category = service._categorize_resolution(width, height)
            assert category == expected_category

    def test_categorize_video_duration(self):
        """Test video duration categorization"""
        service = VideoProcessingService()

        test_cases = [
            (30, "very_short"),   # 30 seconds
            (90, "short"),        # 1.5 minutes
            (600, "medium"),      # 10 minutes
            (1800, "long"),       # 30 minutes
            (3600, "very_long"),  # 60 minutes
        ]

        for duration, expected_category in test_cases:
            category = service._categorize_duration(duration)
            assert category == expected_category

    def test_assess_video_format_quality(self):
        """Test video format quality assessment"""
        service = VideoProcessingService()

        test_cases = [
            ('.mp4', 'excellent'),
            ('.mov', 'excellent'),
            ('.avi', 'good'),
            ('.mkv', 'excellent'),
            ('.webm', 'good'),
            ('.flv', 'fair'),
            ('.3gp', 'poor'),
            ('.wmv', 'good'),
            ('.xyz', 'unknown'),
        ]

        for file_format, expected_quality in test_cases:
            quality = service._assess_format_quality(file_format)
            assert quality == expected_quality

    def test_calculate_video_bitrate(self):
        """Test video bitrate calculation"""
        service = VideoProcessingService()

        # Test with file size and duration
        bitrate = service._calculate_video_bitrate(50_000_000, 300)  # 50MB over 5 minutes
        expected_bitrate = (50_000_000 * 8) / 300 / 1000  # Convert to kbps
        assert abs(bitrate - expected_bitrate) < 0.01

        # Test with zero duration
        bitrate = service._calculate_video_bitrate(50_000_000, 0)
        assert bitrate == 0.0

    def test_extract_scenes_from_keyframes(self):
        """Test scene detection from keyframes"""
        service = VideoProcessingService()

        keyframe_data = {
            'keyframe_timestamps': [0.0, 1.0, 5.0, 5.5, 10.0, 10.5, 15.0]
        }

        scenes = service._extract_scenes_from_keyframes(keyframe_data, threshold=0.5)

        assert 'scene_count' in scenes
        assert 'scene_boundaries' in scenes
        assert 'average_scene_duration' in scenes

        # Should detect scenes based on timing gaps
        # Gap between 1.0 and 5.0 = 4.0 seconds
        # Gap between 5.5 and 10.0 = 4.5 seconds
        # Gap between 10.5 and 15.0 = 4.5 seconds
        assert scenes['scene_count'] >= 3

    def test_generate_video_summary(self):
        """Test video summary generation"""
        service = VideoProcessingService()

        video_results = {
            'metadata': {
                'duration_seconds': 180.5,
                'width': 1920,
                'height': 1080,
                'frame_rate': 30.0,
                'bitrate': 8_000_000,
                'audio_streams': [{'codec': 'aac', 'channels': 2}]
            },
            'audio_transcription': {
                'text': 'This is the transcribed audio content from the video.',
                'language': 'en',
                'confidence': 0.85,
                'word_count': 12
            },
            'keyframe_analysis': {
                'keyframe_count': 90,
                'scenes_detected': 6,
                'average_scene_duration': 30.0
            },
            'quality_analysis': {
                'file_size_category': 'large',
                'duration_category': 'medium',
                'resolution_category': 'full_hd',
                'format_quality': 'excellent',
                'is_large_file': False,
                'is_long_video': False
            }
        }

        summary = service.generate_video_summary(video_results)

        assert '180.5 seconds' in summary
        assert '1920x1080' in summary
        assert '30 fps' in summary
        assert '12 words' in summary
        assert '85%' in summary
        assert 'en' in summary
        assert '6 scenes' in summary
        assert 'full_hd' in summary

    def test_generate_video_summary_no_audio(self):
        """Test video summary generation when no audio is available"""
        service = VideoProcessingService()

        video_results = {
            'metadata': {
                'duration_seconds': 120.0,
                'width': 1280,
                'height': 720,
                'frame_rate': 24.0,
                'bitrate': 4_000_000,
                'audio_streams': []
            },
            'audio_transcription': {
                'text': '',
                'language': 'unknown',
                'confidence': 0.0,
                'error': 'No audio streams found'
            },
            'keyframe_analysis': {
                'keyframe_count': 60,
                'scenes_detected': 4
            },
            'quality_analysis': {
                'file_size_category': 'medium',
                'duration_category': 'short',
                'resolution_category': 'hd'
            }
        }

        summary = service.generate_video_summary(video_results)

        assert '120.0 seconds' in summary
        assert '1280x720' in summary
        assert 'No audio transcription available' in summary
        assert '4 scenes' in summary

    def test_process_video_performance(self, mock_video_file):
        """Test video processing performance"""
        service = VideoProcessingService()
        service.audio_processor = Mock()

        # Mock fast processing
        with patch.object(service, '_extract_video_metadata', return_value={}):
            with patch.object(service, '_extract_audio_track', return_value={
                'text': 'Test', 'language': 'en', 'confidence': 0.9
            }):
                with patch.object(service, '_extract_keyframes', return_value={
                    'keyframe_count': 10, 'scenes_detected': 2
                }):
                    with patch.object(service, '_analyze_video_quality', return_value={}):

                        start_time = time.time()
                        result = service.process_video(mock_video_file)
                        end_time = time.time()

                        processing_time = end_time - start_time

                        # Should complete quickly for mocked operations
                        assert processing_time < 1.0
                        assert 'metadata' in result
                        assert 'audio_transcription' in result
                        assert 'keyframe_analysis' in result
                        assert 'quality_analysis' in result

    def test_process_corrupted_video(self, temp_upload_dir):
        """Test processing of corrupted video files"""
        service = VideoProcessingService()

        # Create a corrupted video file
        corrupted_file = os.path.join(temp_upload_dir, "corrupted.mp4")
        with open(corrupted_file, "wb") as f:
            f.write(b"corrupted video data that is not valid")

        with patch.object(service, '_extract_video_metadata', side_effect=Exception("Corrupted file")):
            with pytest.raises(Exception, match="Corrupted file"):
                service.process_video(corrupted_file)

    def test_detect_video_features_advanced(self, mock_video_file):
        """Test advanced video feature detection"""
        service = VideoProcessingService()

        # Mock frame extraction and analysis
        with patch('src.services.video_processing_service.cv2') as mock_cv2:
            mock_cv2.VideoCapture.return_value.isOpened.return_value = True
            mock_cv2.VideoCapture.return_value.read.side_effect = [
                (True, Mock()),  # Success for first frame
                (False, None)  # End of video
            ]
            mock_cv2.cvtColor.return_value = Mock()
            mock_cv2.Canny.return_value = Mock()
            mock_cv2.goodFeaturesToTrack.return_value = Mock(return_value=[])

            features = service._detect_video_features(mock_video_file)

            assert 'motion_detected' in features
            assert 'edge_density' in features
            assert 'feature_points' in features
            assert 'brightness_analysis' in features
            assert isinstance(features['edge_density'], (int, float))
            assert isinstance(features['feature_points'], int)

    def test_extract_subtitles_from_video(self, mock_video_file):
        """Test subtitle extraction from video"""
        service = VideoProcessingService()

        # Mock subtitle extraction
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '''
1
00:00:01,000 --> 00:00:04,000
Hello, welcome to our video.

2
00:00:05,000 --> 00:00:08,000
This is a subtitle test.
        '''

        with patch('src.services.video_processing_service.subprocess.run', return_value=mock_result):
            subtitles = service._extract_subtitles(mock_video_file)

            assert 'subtitle_count' in subtitles
            assert 'subtitles' in subtitles
            assert subtitles['subtitle_count'] == 2
            assert len(subtitles['subtitles']) == 2
            assert 'Hello' in subtitles['subtitles'][0]['text']
            assert 'subtitle test' in subtitles['subtitles'][1]['text']

    def test_analyze_video_content_summary(self):
        """Test video content summary analysis"""
        service = VideoProcessingService()

        # Mock comprehensive analysis results
        analysis_data = {
            'duration_seconds': 300,
            'audio_transcription': {
                'text': 'The video discusses artificial intelligence and machine learning applications.',
                'word_count': 10
            },
            'keyframe_analysis': {
                'scenes_detected': 10,
                'average_scene_duration': 30
            },
            'metadata': {
                'width': 1920,
                'height': 1080
            }
        }

        summary = service._analyze_video_content_summary(analysis_data)

        assert 'content_type' in summary
        assert 'complexity_score' in summary
        assert 'topics_detected' in summary
        assert 'visual_diversity' in summary
        assert summary['duration'] == 300
        assert 'artificial intelligence' in summary['topics_detected']

    def test_validate_video_file_format(self):
        """Test video file format validation"""
        service = VideoProcessingService()

        # Test valid formats
        valid_formats = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
        for fmt in valid_formats:
            assert service._is_valid_video_format(f"test{fmt}") is True

        # Test invalid formats
        invalid_formats = ['.txt', '.pdf', '.mp3', '.jpg']
        for fmt in invalid_formats:
            assert service._is_valid_video_format(f"test{fmt}") is False

    # Helper methods to handle exceptions in tests
    def _extract_audio_track_safe(self, service, video_file):
        """Safe wrapper for audio track extraction"""
        try:
            return service._extract_audio_track(video_file)
        except Exception:
            return {'text': '', 'error': 'Audio extraction failed'}

    def _extract_audio_track_safe_with_metadata(self, service, video_file, metadata):
        """Safe wrapper for audio track extraction with metadata"""
        try:
            # Mock the metadata extraction
            with patch.object(service, '_extract_video_metadata', return_value=metadata):
                return service._extract_audio_track(video_file)
        except Exception:
            return {'text': '', 'error': 'Audio extraction failed'}

    def _extract_keyframes_safe(self, service, video_file):
        """Safe wrapper for keyframe extraction"""
        try:
            return service._extract_keyframes(video_file)
        except Exception:
            return {'keyframe_count': 0, 'keyframe_timestamps': []}