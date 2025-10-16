"""
Unit tests for Document Quality Service
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from src.services.document_quality_service import (
    DocumentQualityService,
    QualityIssue
)
from src.models.document import Document, DocumentType, ProcessingStatus
from src.models.organization import Organization
from src.models.user import User

class TestDocumentQualityService:
    """Test suite for DocumentQualityService"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)

    @pytest.fixture
    def quality_service(self, mock_db):
        """Create DocumentQualityService instance with mocked database"""
        return DocumentQualityService(mock_db)

    @pytest.fixture
    def mock_document(self):
        """Mock document"""
        doc = Mock(spec=Document)
        doc.id = "test-doc-id"
        doc.title = "Test Document"
        doc.filename = "test.pdf"
        doc.file_size_bytes = 1024 * 1024
        doc.file_size_mb = 1.0
        doc.mime_type = "application/pdf"
        doc.document_type = DocumentType.PDF
        doc.processing_status = ProcessingStatus.COMPLETED
        doc.content_text = "This is a test document with some content for quality assessment."
        doc.created_at = datetime.utcnow()
        doc.processing_started_at = datetime.utcnow()
        doc.processing_completed_at = datetime.utcnow()
        doc.processing_error = None
        doc.tags = ["test", "document"]
        doc.is_embedded = True
        doc.is_indexed = True
        doc.organization_id = "test-org-id"
        doc.uploaded_by_user_id = "test-user-id"
        doc.get_metadata.return_value = {
            "file_hash": "abc123",
            "author": "Test Author",
            "description": "Test Description"
        }
        doc.get_metadata_value.side_effect = lambda key, default=None: {
            "description": "Test Description",
            "author": "Test Author"
        }.get(key, default)
        doc.add_metadata = Mock()
        return doc

    class TestQuickQualityAssessment:
        """Test quick quality assessment methods"""

        @pytest.mark.asyncio
        async def test_quick_quality_assessment_success(self, quality_service, mock_document):
            """Test successful quick quality assessment"""
            result = await quality_service.quick_quality_assessment(mock_document)

            assert "overall_score" in result
            assert "readability_score" in result
            assert "content_quality_score" in result
            assert "technical_quality_score" in result
            assert "recommendations" in result
            assert "issues" in result
            assert "processing_time_ms" in result

            # Check that scores are in valid range
            assert 0.0 <= result["overall_score"] <= 1.0
            assert 0.0 <= result["readability_score"] <= 1.0
            assert 0.0 <= result["content_quality_score"] <= 1.0
            assert 0.0 <= result["technical_quality_score"] <= 1.0

        @pytest.mark.asyncio
        async def test_quick_quality_assessment_no_content(self, quality_service, mock_document):
            """Test quick quality assessment with no content"""
            mock_document.content_text = ""

            result = await quality_service.quick_quality_assessment(mock_document)

            assert result["overall_score"] == 0.0
            assert len(result["issues"]) > 0
            assert any("No text content found" in issue["description"] for issue in result["issues"])

        def test_quick_readability_assessment_good_text(self, quality_service):
            """Test readability assessment with good text"""
            good_text = """
            This is a well-structured document with proper sentence length.
            It contains multiple sentences that are of appropriate length.
            The text flows nicely and is easy to read and understand.
            """
            score = quality_service.quick_readability_assessment(good_text)

            assert 0.6 <= score <= 1.0  # Should be good score

        def test_quick_readability_assessment_poor_text(self, quality_service):
            """Test readability assessment with poor text"""
            poor_text = "Thisisaverylongrunonsentencethatisdifficulttoreadandhasnopunctuationorproperstructureandcontainssomereallylongwordsthatarehardtounderstand"

            score = quality_service.quick_readability_assessment(poor_text)

            assert score < 0.6  # Should be poor score

        def test_quick_content_quality_assessment_good_content(self, quality_service, mock_document):
            """Test content quality assessment with good content"""
            good_content = "This is a comprehensive document with substantial content. It contains multiple paragraphs and detailed information about the topic. The content is well-structured and provides value to the reader."
            mock_document.content_text = good_content

            score = quality_service.quick_content_quality_assessment(good_content, mock_document)

            assert 0.6 <= score <= 1.0  # Should be good score

        def test_quick_content_quality_assessment_poor_content(self, quality_service, mock_document):
            """Test content quality assessment with poor content"""
            poor_content = "Short"
            mock_document.content_text = poor_content

            score = quality_service.quick_content_quality_assessment(poor_content, mock_document)

            assert score < 0.6  # Should be poor score

        def test_quick_technical_quality_assessment_good(self, quality_service, mock_document):
            """Test technical quality assessment with good technical attributes"""
            mock_document.processing_status = ProcessingStatus.COMPLETED
            mock_document.file_size_bytes = 1024 * 1024  # 1MB
            mock_document.mime_type = "application/pdf"

            score = quality_service.quick_technical_quality_assessment(mock_document)

            assert 0.6 <= score <= 1.0  # Should be good score

        def test_quick_technical_quality_assessment_poor(self, quality_service, mock_document):
            """Test technical quality assessment with poor technical attributes"""
            mock_document.processing_status = ProcessingStatus.FAILED
            mock_document.file_size_bytes = 50  # Very small
            mock_document.mime_type = None

            score = quality_service.quick_technical_quality_assessment(mock_document)

            assert score < 0.6  # Should be poor score

    class TestComprehensiveQualityAssessment:
        """Test comprehensive quality assessment methods"""

        @pytest.mark.asyncio
        async def test_comprehensive_quality_assessment_success(self, quality_service, mock_document):
            """Test successful comprehensive quality assessment"""
            with patch.object(quality_service, 'assess_readability') as mock_readability, \
                 patch.object(quality_service, 'assess_coherence') as mock_coherence, \
                 patch.object(quality_service, 'assess_completeness') as mock_completeness, \
                 patch.object(quality_service, 'assess_accuracy') as mock_accuracy, \
                 patch.object(quality_service, 'assess_technical_quality') as mock_technical, \
                 patch.object(quality_service, 'assess_content_quality') as mock_content, \
                 patch.object(quality_service, 'assess_metadata_quality') as mock_metadata, \
                 patch.object(quality_service, 'store_quality_metrics') as mock_store:

                # Setup mock returns
                mock_readability.return_value = {"score": 0.8, "issues": [], "metrics": {}}
                mock_coherence.return_value = {"score": 0.7, "issues": [], "metrics": {}}
                mock_completeness.return_value = {"score": 0.9, "issues": [], "metrics": {}}
                mock_accuracy.return_value = {"score": 0.85, "issues": [], "metrics": {}}
                mock_technical.return_value = {"score": 0.9, "issues": [], "metrics": {}}
                mock_content.return_value = {"score": 0.8, "issues": [], "metrics": {}}
                mock_metadata.return_value = {"score": 0.75, "issues": [], "metrics": {}}

                result = await quality_service.comprehensive_quality_assessment(mock_document)

                assert result["overall_score"] > 0.7  # Should be good overall score
                assert "readability_score" in result
                assert "coherence_score" in result
                assert "completeness_score" in result
                assert "accuracy_score" in result
                assert "technical_quality_score" in result
                assert "content_quality_score" in result
                assert "metadata_quality_score" in result
                assert "dimension_scores" in result
                assert "recommendations" in result
                assert "issues" in result
                assert "detailed_metrics" in result
                assert "processing_time_ms" in result

                # Verify all assessment methods were called
                mock_readability.assert_called_once()
                mock_coherence.assert_called_once()
                mock_completeness.assert_called_once()
                mock_accuracy.assert_called_once()
                mock_technical.assert_called_once()
                mock_content.assert_called_once()
                mock_metadata.assert_called_once()
                mock_store.assert_called_once()

        @pytest.mark.asyncio
        async def test_comprehensive_quality_assessment_no_content(self, quality_service, mock_document):
            """Test comprehensive quality assessment with no content"""
            mock_document.content_text = ""

            result = await quality_service.comprehensive_quality_assessment(mock_document)

            assert result["overall_score"] == 0.0
            assert len(result["issues"]) > 0
            assert any("No text content available" in issue["description"] for issue in result["issues"])

    class TestReadabilityAssessment:
        """Test readability assessment methods"""

        @pytest.mark.asyncio
        async def test_assess_readability_good_text(self, quality_service):
            """Test readability assessment with good text"""
            good_text = """
            This document has proper sentence structure. The sentences are of reasonable length.
            There are appropriate paragraph breaks and good formatting. The text is easy to read.
            """
            result = await quality_service.assess_readability(good_text)

            assert result["score"] >= 0.6
            assert "metrics" in result
            assert "word_count" in result["metrics"]
            assert "sentence_count" in result["metrics"]
            assert "avg_sentence_length" in result["metrics"]
            assert len(result["issues"]) == 0

        @pytest.mark.asyncio
        async def test_assess_readability_poor_text(self, quality_service):
            """Test readability assessment with poor text"""
            poor_text = "This is a single very long sentence that goes on and on without any proper punctuation or breaks and makes it very difficult to read and understand because it lacks proper structure and has very long words that are hard to pronounce and understand"

            result = await quality_service.assess_readability(poor_text)

            assert result["score"] < 0.6
            assert len(result["issues"]) > 0
            assert any("Average sentence length" in issue["description"] for issue in result["issues"])

        @pytest.mark.asyncio
        async def test_assess_readability_no_text(self, quality_service):
            """Test readability assessment with no text"""
            result = await quality_service.assess_readability("")

            assert result["score"] == 0.0
            assert len(result["issues"]) > 0
            assert result["issues"][0].dimension == "readability"
            assert result["issues"][0].severity == "high"

    class TestCoherenceAssessment:
        """Test coherence assessment methods"""

        @pytest.mark.asyncio
        async def test_assess_coherence_good_text(self, quality_service):
            """Test coherence assessment with coherent text"""
            coherent_text = """
            Introduction to the topic.

            However, we must consider the implications. Furthermore, the data suggests several important trends.

            In conclusion, the findings support our initial hypothesis.
            """
            result = await quality_service.assess_coherence(coherent_text)

            assert result["score"] >= 0.6
            assert "transition_word_ratio" in result["metrics"]
            assert "paragraph_count" in result["metrics"]

        @pytest.mark.asyncio
        async def test_assess_coherence_poor_text(self, quality_service):
            """Test coherence assessment with incoherent text"""
            incoherent_text = "Random words without connection another unrelated topic completely different subject no logical flow between ideas."

            result = await quality_service.assess_coherence(incoherent_text)

            assert result["score"] < 0.6
            assert len(result["issues"]) > 0

        @pytest.mark.asyncio
        async def test_assess_coherence_short_text(self, quality_service):
            """Test coherence assessment with very short text"""
            result = await quality_service.assess_coherence("Short")

            assert result["score"] <= 0.5  # Should be penalized for short text
            assert len(result["issues"]) > 0

    class TestCompletenessAssessment:
        """Test completeness assessment methods"""

        @pytest.mark.asyncio
        async def test_assess_completeness_complete_document(self, quality_service, mock_document):
            """Test completeness assessment with complete document"""
            complete_text = """
            Title: Comprehensive Analysis Report

            Chapter 1: Introduction
            This chapter introduces the topic and methodology.

            Chapter 2: Analysis
            Detailed analysis of the findings and data.

            Chapter 3: Conclusion
            Summary of results and final conclusions.
            """
            result = await quality_service.assess_completeness(complete_text, mock_document)

            assert result["score"] >= 0.7
            assert "has_title" in result["metrics"]
            assert "has_structure" in result["metrics"]
            assert "has_conclusion" in result["metrics"]

        @pytest.mark.asyncio
        async def test_assess_completeness_incomplete_document(self, quality_service, mock_document):
            """Test completeness assessment with incomplete document"""
            incomplete_text = "Brief note."

            result = await quality_service.assess_completeness(incomplete_text, mock_document)

            assert result["score"] < 0.5
            assert len(result["issues"]) > 0
            assert any("appears incomplete" in issue["description"] for issue in result["issues"])

        @pytest.mark.asyncio
        async def test_assess_completeness_abrupt_ending(self, quality_service, mock_document):
            """Test completeness assessment with abrupt ending"""
            abrupt_text = "This document has content but ends very suddenly without proper conclusio"

            result = await quality_service.assess_completeness(abrupt_text, mock_document)

            assert len(result["issues"]) > 0
            assert any("end abruptly" in issue["description"] for issue in result["issues"])

    class TestAccuracyAssessment:
        """Test accuracy assessment methods"""

        @pytest.mark.asyncio
        async def test_assess_accuracy_good_text(self, quality_service):
            """Test accuracy assessment with well-formatted text"""
            good_text = """
            This document is properly formatted and well-written.
            It contains appropriate sentence structure and punctuation.
            The spelling and grammar appear to be correct.
            """
            result = await quality_service.assess_accuracy(good_text)

            assert result["score"] >= 0.6
            assert "potential_spelling_errors" in result["metrics"]
            assert "spelling_error_rate" in result["metrics"]

        @pytest.mark.asyncio
        async def test_assess_accuracy_poor_formatting(self, quality_service):
            """Test accuracy assessment with poor formatting"""
            poor_text = "This document has  inconsistent  spacing and BadCapitalization"

            result = await quality_service.assess_accuracy(poor_text)

            assert result["score"] < 0.7
            assert len(result["issues"]) > 0
            assert any("formatting inconsistencies" in issue["description"] for issue in result["issues"])

    class TestTechnicalQualityAssessment:
        """Test technical quality assessment methods"""

        @pytest.mark.asyncio
        async def test_assess_technical_quality_good(self, quality_service, mock_document):
            """Test technical quality assessment with good technical attributes"""
            mock_document.processing_status = ProcessingStatus.COMPLETED
            mock_document.file_size_bytes = 1024 * 1024  # 1MB
            mock_document.mime_type = "application/pdf"
            mock_document.get_metadata.return_value = {"file_hash": "abc123", "author": "Test"}

            result = await quality_service.assess_technical_quality(mock_document)

            assert result["score"] >= 0.7
            assert "file_size_bytes" in result["metrics"]
            assert "processing_status" in result["metrics"]
            assert "metadata_completeness" in result["metrics"]

        @pytest.mark.asyncio
        async def test_assess_technical_quality_failed_processing(self, quality_service, mock_document):
            """Test technical quality assessment with failed processing"""
            mock_document.processing_status = ProcessingStatus.FAILED
            mock_document.processing_error = "Processing failed"

            result = await quality_service.assess_technical_quality(mock_document)

            assert result["score"] < 0.5
            assert len(result["issues"]) > 0
            assert any("processing failed" in issue["description"] for issue in result["issues"])

        @pytest.mark.asyncio
        async def test_assess_technical_quality_small_file(self, quality_service, mock_document):
            """Test technical quality assessment with very small file"""
            mock_document.file_size_bytes = 50  # Very small

            result = await quality_service.assess_technical_quality(mock_document)

            assert result["score"] < 0.7
            assert len(result["issues"]) > 0
            assert any("suspiciously small" in issue["description"] for issue in result["issues"])

    class TestContentQualityAssessment:
        """Test content quality assessment methods"""

        @pytest.mark.asyncio
        async def test_assess_content_quality_good(self, quality_service, mock_document):
            """Test content quality assessment with good content"""
            good_content = """
            This document contains comprehensive information about the subject matter.
            It includes detailed explanations, examples, and analysis.
            The vocabulary is diverse and the content is well-structured.
            Multiple aspects of the topic are covered thoroughly.
            """
            result = await quality_service.assess_content_quality(good_content, mock_document)

            assert result["score"] >= 0.7
            assert "word_count" in result["metrics"]
            assert "vocabulary_richness" in result["metrics"]
            assert "meaningful_word_ratio" in result["metrics"]

        @pytest.mark.asyncio
        async def test_assess_content_quality_poor(self, quality_service, mock_document):
            """Test content quality assessment with poor content"""
            poor_content = "Bad bad bad bad bad bad bad bad bad bad bad"

            result = await quality_service.assess_content_quality(poor_content, mock_document)

            assert result["score"] < 0.6
            assert len(result["issues"]) > 0
            assert any("Limited vocabulary diversity" in issue["description"] for issue in result["issues"])

    class TestMetadataQualityAssessment:
        """Test metadata quality assessment methods"""

        @pytest.mark.asyncio
        async def test_assess_metadata_quality_good(self, quality_service, mock_document):
            """Test metadata quality assessment with good metadata"""
            mock_document.title = "Comprehensive Document Title"
            mock_document.tags = ["tag1", "tag2", "tag3"]
            mock_document.get_metadata.return_value = {
                "title": "Comprehensive Document Title",
                "description": "Detailed description",
                "author": "Author Name",
                "language": "en",
                "keywords": ["keyword1", "keyword2"],
                "file_hash": "abc123"
            }

            result = await quality_service.assess_metadata_quality(mock_document)

            assert result["score"] >= 0.7
            assert "metadata_field_count" in result["metrics"]
            assert "has_title" in result["metrics"]
            assert "has_tags" in result["metrics"]
            assert "has_description" in result["metrics"]

        @pytest.mark.asyncio
        async def test_assess_metadata_quality_poor(self, quality_service, mock_document):
            """Test metadata quality assessment with poor metadata"""
            mock_document.title = ""
            mock_document.tags = []
            mock_document.get_metadata.return_value = {"file_hash": "abc123"}

            result = await quality_service.assess_metadata_quality(mock_document)

            assert result["score"] < 0.6
            assert len(result["issues"]) >= 2  # Should have issues for title and tags
            assert any("Missing or inadequate title" in issue["description"] for issue in result["issues"])
            assert any("No tags assigned" in issue["description"] for issue in result["issues"])

    class TestRecommendations:
        """Test recommendation generation methods"""

        def test_generate_quick_recommendations_good_scores(self, quality_service):
            """Test quick recommendations for good scores"""
            assessment = {
                "readability_score": 0.8,
                "content_quality_score": 0.9,
                "technical_quality_score": 0.85
            }

            recommendations = quality_service.generate_quick_recommendations(assessment)

            assert len(recommendations) == 0  # No recommendations needed for good scores

        def test_generate_quick_recommendations_poor_scores(self, quality_service):
            """Test quick recommendations for poor scores"""
            assessment = {
                "readability_score": 0.4,
                "content_quality_score": 0.3,
                "technical_quality_score": 0.2
            }

            recommendations = quality_service.generate_quick_recommendations(assessment)

            assert len(recommendations) > 0
            assert any("readability" in rec.lower() for rec in recommendations)
            assert any("content" in rec.lower() for rec in recommendations)
            assert any("technical" in rec.lower() for rec in recommendations)

        def test_generate_comprehensive_recommendations(self, quality_service):
            """Test comprehensive recommendations generation"""
            assessment = {
                "overall_score": 0.4
            }
            dimension_scores = {
                "readability": 0.3,
                "coherence": 0.4,
                "completeness": 0.2,
                "metadata_quality": 0.3
            }

            recommendations = quality_service.generate_comprehensive_recommendations(assessment, dimension_scores)

            assert len(recommendations) > 0
            # Should have recommendations for low-scoring dimensions
            assert any("readability" in rec.lower() for rec in recommendations)
            assert any("coherence" in rec.lower() for rec in recommendations)
            assert any("completeness" in rec.lower() for rec in recommendations)

    class TestQualityMetricsStorage:
        """Test quality metrics storage"""

        @pytest.mark.asyncio
        async def test_store_quality_metrics_success(self, quality_service, mock_document):
            """Test successful storage of quality metrics"""
            assessment = {
                "overall_score": 0.8,
                "readability_score": 0.7,
                "coherence_score": 0.9,
                "completeness_score": 0.8,
                "accuracy_score": 0.85,
                "technical_quality_score": 0.9,
                "content_quality_score": 0.8,
                "metadata_quality_score": 0.75,
                "detailed_metrics": {"test": "data"},
                "recommendations": ["Recommendation 1"]
            }

            with patch('src.services.document_quality_service.QualityMetrics') as mock_quality_metrics:
                mock_metrics_instance = Mock()
                mock_quality_metrics.return_value = mock_metrics_instance

                await quality_service.store_quality_metrics(mock_document, assessment)

                mock_quality_metrics.assert_called_once_with(
                    document_id=mock_document.id,
                    organization_id=mock_document.organization_id,
                    overall_score=0.8,
                    readability_score=0.7,
                    coherence_score=0.9,
                    completeness_score=0.8,
                    accuracy_score=0.85,
                    technical_quality_score=0.9,
                    content_quality_score=0.8,
                    metadata_quality_score=0.75,
                    detailed_metrics={"test": "data"},
                    recommendations=["Recommendation 1"],
                    assessment_version="1.0"
                )
                quality_service.db.add.assert_called_once_with(mock_metrics_instance)
                quality_service.db.commit.assert_called_once()

        @pytest.mark.asyncio
        async def test_store_quality_metrics_error_handling(self, quality_service, mock_document):
            """Test quality metrics storage error handling"""
            assessment = {"overall_score": 0.8}

            # Mock database error
            quality_service.db.add.side_effect = Exception("Database error")

            # Should not raise exception, should log error instead
            with patch('src.services.document_quality_service.logger') as mock_logger:
                await quality_service.store_quality_metrics(mock_document, assessment)

                mock_logger.error.assert_called_once()

    class TestQualityIssue:
        """Test QualityIssue class"""

        def test_quality_issue_creation(self):
            """Test QualityIssue creation"""
            issue = QualityIssue(
                dimension="readability",
                severity="medium",
                description="Test issue",
                location="line 10",
                suggestion="Fix the issue"
            )

            assert issue.dimension == "readability"
            assert issue.severity == "medium"
            assert issue.description == "Test issue"
            assert issue.location == "line 10"
            assert issue.suggestion == "Fix the issue"
            assert isinstance(issue.detected_at, datetime)

if __name__ == "__main__":
    pytest.main([__file__])