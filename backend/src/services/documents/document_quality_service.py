"""
Document Quality Service for real-time quality assessment and metrics collection
"""

import re
import asyncio
import time
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import Depends
import logging
import numpy as np

# Initialize logger early so it's available for import-time initialization
logger = logging.getLogger(__name__)

# Text processing libraries
SPACY_AVAILABLE = False
nlp = None

def load_spacy_if_available():
    """Load spaCy model if available"""
    global SPACY_AVAILABLE, nlp
    # Only try to load once - use a flag to track if we've attempted loading
    if not hasattr(load_spacy_if_available, '_attempted'):
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")
            SPACY_AVAILABLE = True
            logger.info("spaCy model loaded successfully")
        except (ImportError, OSError) as e:
            logger.warning(f"spaCy not available or model not found: {e}. Using basic text analysis.")
            SPACY_AVAILABLE = False
            nlp = None

        # Mark that we've attempted loading
        load_spacy_if_available._attempted = True

# Initialize spaCy availability status
load_spacy_if_available()

# AI processing for quality assessment
try:
    from textstat import textstat
    TEXTSTAT_AVAILABLE = True
except ImportError:
    TEXTSTAT_AVAILABLE = False

from src.core.database import get_db
from src.models.document import Document, DocumentType

# Note: QualityMetrics model not yet implemented - quality storage is disabled
# from src.models.quality import QualityMetrics, QualityDimension, QualityThreshold
QualityMetrics = None  # Placeholder until model is properly implemented

class QualityIssue:
    """Represents a quality issue found in a document"""

    def __init__(self, dimension: str, severity: str, description: str, location: str = None, suggestion: str = None):
        self.dimension = dimension
        self.severity = severity  # low, medium, high, critical
        self.description = description
        self.location = location
        self.suggestion = suggestion
        self.detected_at = datetime.utcnow()

class DocumentQualityService:
    """Service for assessing and monitoring document quality"""

    def __init__(self, db: Session):
        self.db = db
        self.quality_thresholds = self.get_default_quality_thresholds()

    def get_default_quality_thresholds(self) -> Dict[str, float]:
        """Get default quality thresholds for different dimensions"""
        return {
            "readability": 0.6,
            "coherence": 0.7,
            "completeness": 0.8,
            "accuracy": 0.9,
            "technical_quality": 0.7,
            "content_quality": 0.75,
            "metadata_quality": 0.8,
            "overall": 0.7
        }

    async def quick_quality_assessment(self, document: Document) -> Dict[str, Any]:
        """
        Perform quick quality assessment during upload
        Focus on basic checks that can be done quickly
        """
        try:
            start_time = time.time()
            text_content = document.content_text or ""

            assessment = {
                "overall_score": 0.0,
                "readability_score": 0.0,
                "content_quality_score": 0.0,
                "technical_quality_score": 0.0,
                "recommendations": [],
                "issues": [],
                "processing_time_ms": 0
            }

            if not text_content:
                assessment["issues"].append({
                    "dimension": "content_quality",
                    "severity": "high",
                    "description": "No text content found for quality assessment",
                    "suggestion": "Ensure the document contains extractable text"
                })
                assessment["processing_time_ms"] = (time.time() - start_time) * 1000
                return assessment

            # Quick readability assessment
            readability_score = self.quick_readability_assessment(text_content)
            assessment["readability_score"] = readability_score

            # Quick content quality assessment
            content_score = self.quick_content_quality_assessment(text_content, document)
            assessment["content_quality_score"] = content_score

            # Quick technical quality assessment
            technical_score = self.quick_technical_quality_assessment(document)
            assessment["technical_quality_score"] = technical_score

            # Calculate overall score
            assessment["overall_score"] = (readability_score + content_score + technical_score) / 3

            # Generate quick recommendations
            assessment["recommendations"] = self.generate_quick_recommendations(assessment)

            assessment["processing_time_ms"] = (time.time() - start_time) * 1000

            return assessment

        except Exception as e:
            logger.error(f"Quick quality assessment failed: {str(e)}")
            return {
                "overall_score": 0.0,
                "error": str(e),
                "processing_time_ms": (time.time() - start_time) * 1000 if 'start_time' in locals() else 0
            }

    async def comprehensive_quality_assessment(self, document: Document) -> Dict[str, Any]:
        """
        Perform comprehensive quality assessment
        Includes detailed analysis of multiple quality dimensions
        """
        try:
            start_time = time.time()
            text_content = document.content_text or ""

            assessment = {
                "overall_score": 0.0,
                "readability_score": 0.0,
                "coherence_score": 0.0,
                "completeness_score": 0.0,
                "accuracy_score": 0.0,
                "technical_quality_score": 0.0,
                "content_quality_score": 0.0,
                "metadata_quality_score": 0.0,
                "dimension_scores": {},
                "recommendations": [],
                "issues": [],
                "detailed_metrics": {},
                "processing_time_ms": 0
            }

            if not text_content:
                assessment["issues"].append({
                    "dimension": "content_quality",
                    "severity": "high",
                    "description": "No text content available for comprehensive quality assessment",
                    "suggestion": "Ensure document processing extracted text successfully"
                })
                assessment["processing_time_ms"] = (time.time() - start_time) * 1000
                return assessment

            # Assess each quality dimension
            dimensions_tasks = [
                ("readability", self.assess_readability, text_content),
                ("coherence", self.assess_coherence, text_content),
                ("completeness", self.assess_completeness, text_content, document),
                ("accuracy", self.assess_accuracy, text_content),
                ("technical_quality", self.assess_technical_quality, document),
                ("content_quality", self.assess_content_quality, text_content, document),
                ("metadata_quality", self.assess_metadata_quality, document)
            ]

            # Run assessments in parallel where possible
            dimension_scores = {}
            all_issues = []

            for dimension_name, assessment_func, *args in dimensions_tasks:
                try:
                    if asyncio.iscoroutinefunction(assessment_func):
                        result = await assessment_func(*args)
                    else:
                        result = assessment_func(*args)

                    dimension_scores[dimension_name] = result["score"]
                    assessment[f"{dimension_name}_score"] = result["score"]
                    assessment["dimension_scores"][dimension_name] = result

                    # Collect issues
                    if "issues" in result:
                        all_issues.extend(result["issues"])

                except Exception as e:
                    logger.error(f"Dimension {dimension_name} assessment failed: {str(e)}")
                    dimension_scores[dimension_name] = 0.0
                    assessment[f"{dimension_name}_score"] = 0.0

            # Calculate overall score (weighted average)
            weights = {
                "readability": 0.15,
                "coherence": 0.20,
                "completeness": 0.15,
                "accuracy": 0.20,
                "technical_quality": 0.10,
                "content_quality": 0.15,
                "metadata_quality": 0.05
            }

            overall_score = sum(
                dimension_scores[dim] * weights[dim]
                for dim in weights
                if dim in dimension_scores
            )

            assessment["overall_score"] = overall_score
            assessment["issues"] = [
                {
                    "dimension": issue.dimension,
                    "severity": issue.severity,
                    "description": issue.description,
                    "location": issue.location,
                    "suggestion": issue.suggestion
                }
                for issue in all_issues
            ]

            # Generate comprehensive recommendations
            assessment["recommendations"] = self.generate_comprehensive_recommendations(assessment, dimension_scores)

            # Store quality metrics in database
            await self.store_quality_metrics(document, assessment)

            assessment["processing_time_ms"] = (time.time() - start_time) * 1000

            return assessment

        except Exception as e:
            logger.error(f"Comprehensive quality assessment failed: {str(e)}")
            return {
                "overall_score": 0.0,
                "error": str(e),
                "processing_time_ms": (time.time() - start_time) * 1000 if 'start_time' in locals() else 0
            }

    def quick_readability_assessment(self, text: str) -> float:
        """Quick readability assessment using basic metrics"""
        try:
            if not text or len(text.strip()) < 50:
                return 0.3

            # Basic readability metrics
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]

            words = text.split()
            avg_sentence_length = len(words) / len(sentences) if sentences else 0

            # Score based on average sentence length (ideal: 15-20 words)
            if 10 <= avg_sentence_length <= 25:
                sentence_score = 1.0
            elif 5 <= avg_sentence_length < 10 or 25 < avg_sentence_length <= 35:
                sentence_score = 0.7
            else:
                sentence_score = 0.4

            # Check for very long words (complexity indicator)
            long_words = sum(1 for word in words if len(word) > 12)
            complexity_penalty = min(0.3, long_words / len(words) * 2) if words else 0

            # Basic text structure check
            has_paragraphs = '\n\n' in text
            structure_score = 0.8 if has_paragraphs else 0.5

            readability_score = (sentence_score + structure_score) / 2 - complexity_penalty
            return max(0.0, min(1.0, readability_score))

        except Exception as e:
            logger.error(f"Quick readability assessment failed: {str(e)}")
            return 0.5

    def quick_content_quality_assessment(self, text: str, document: Document) -> float:
        """Quick content quality assessment"""
        try:
            if not text:
                return 0.0

            score = 0.5  # Base score

            # Length check (documents that are too short or too long get lower scores)
            word_count = len(text.split())
            if 100 <= word_count <= 10000:
                score += 0.2
            elif word_count < 50:
                score -= 0.3
            elif word_count > 20000:
                score -= 0.1

            # Language pattern check (basic)
            if re.search(r'\b(the|and|or|but|in|on|at|to|for)\b', text, re.IGNORECASE):
                score += 0.1  # Has common English words

            # Structure check
            if re.search(r'[.!?]', text):  # Has sentence endings
                score += 0.1

            if '\n' in text:  # Has line breaks
                score += 0.1

            # Content type specific checks
            if document.document_type == DocumentType.PDF:
                # PDFs should have reasonable structure
                if len(text) > 500:
                    score += 0.1

            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.error(f"Quick content quality assessment failed: {str(e)}")
            return 0.5

    def quick_technical_quality_assessment(self, document: Document) -> float:
        """Quick technical quality assessment"""
        try:
            score = 0.8  # Start with good score

            # File size checks
            if document.file_size_bytes < 100:  # Very small file
                score -= 0.3
            elif document.file_size_bytes > 100 * 1024 * 1024:  # Very large file (>100MB)
                score -= 0.1

            # Processing status check
            if document.processing_status.value == "completed":
                score += 0.1
            elif document.processing_status.value == "failed":
                score -= 0.4

            # Metadata check
            metadata = document.get_metadata()
            if metadata:
                score += 0.1

            # MIME type consistency
            if document.mime_type:
                score += 0.1

            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.error(f"Quick technical quality assessment failed: {str(e)}")
            return 0.5

    async def assess_readability(self, text: str) -> Dict[str, Any]:
        """Comprehensive readability assessment"""
        try:
            result = {"score": 0.0, "issues": [], "metrics": {}}

            if not text:
                result["issues"].append(QualityIssue(
                    dimension="readability",
                    severity="high",
                    description="No text content for readability assessment"
                ))
                return result

            metrics = {}

            # Basic text statistics
            words = text.split()
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]

            metrics["word_count"] = len(words)
            metrics["sentence_count"] = len(sentences)
            metrics["avg_sentence_length"] = len(words) / len(sentences) if sentences else 0

            # Advanced readability metrics (if textstat is available)
            if TEXTSTAT_AVAILABLE:
                try:
                    metrics["flesch_reading_ease"] = textstat.flesch_reading_ease(text)
                    metrics["flesch_kincaid_grade"] = textstat.flesch_kincaid_grade(text)
                    metrics["gunning_fog"] = textstat.gunning_fog(text)
                    metrics["coleman_liau_index"] = textstat.coleman_liau_index(text)
                except Exception as e:
                    logger.warning(f"Textstat metrics calculation failed: {str(e)}")

            # Calculate readability score
            readability_score = 0.5

            # Score based on sentence length
            avg_len = metrics["avg_sentence_length"]
            if 15 <= avg_len <= 20:
                readability_score += 0.3
            elif 10 <= avg_len < 15 or 20 < avg_len <= 25:
                readability_score += 0.2
            elif avg_len > 35 or avg_len < 5:
                result["issues"].append(QualityIssue(
                    dimension="readability",
                    severity="medium",
                    description=f"Average sentence length is {avg_len:.1f} words (ideal: 15-20)",
                    suggestion="Break long sentences or combine short ones for better readability"
                ))
                readability_score -= 0.2

            # Score based on text length
            word_count = metrics["word_count"]
            if 100 <= word_count <= 5000:
                readability_score += 0.2
            elif word_count < 50:
                result["issues"].append(QualityIssue(
                    dimension="readability",
                    severity="high",
                    description="Text is very short for meaningful readability assessment",
                    suggestion="Consider adding more content"
                ))
                readability_score -= 0.3

            result["score"] = max(0.0, min(1.0, readability_score))
            result["metrics"] = metrics

            return result

        except Exception as e:
            logger.error(f"Readability assessment failed: {str(e)}")
            return {"score": 0.0, "issues": [QualityIssue("readability", "high", str(e))], "metrics": {}}

    async def assess_coherence(self, text: str) -> Dict[str, Any]:
        """Assess text coherence and logical flow"""
        try:
            result = {"score": 0.5, "issues": [], "metrics": {}}

            if not text or len(text.strip()) < 100:
                result["score"] = 0.3
                result["issues"].append(QualityIssue(
                    dimension="coherence",
                    severity="medium",
                    description="Text too short for coherence assessment"
                ))
                return result

            metrics = {}

            # Basic coherence indicators
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]

            # Check for transition words
            transition_words = ['however', 'therefore', 'moreover', 'furthermore', 'consequently',
                              'meanwhile', 'nevertheless', 'nonetheless', 'thus', 'hence']
            transition_count = sum(1 for s in sentences if any(word in s.lower() for word in transition_words))
            metrics["transition_word_ratio"] = transition_count / len(sentences) if sentences else 0

            # Check paragraph structure
            paragraphs = text.split('\n\n')
            metrics["paragraph_count"] = len(paragraphs)
            metrics["avg_paragraph_length"] = len(text) / len(paragraphs) if paragraphs else 0

            # Calculate coherence score
            coherence_score = 0.5

            # Transition words improve coherence
            if metrics["transition_word_ratio"] > 0.1:
                coherence_score += 0.2
            elif metrics["transition_word_ratio"] < 0.02:
                result["issues"].append(QualityIssue(
                    dimension="coherence",
                    severity="low",
                    description="Few transition words detected",
                    suggestion="Add transition words to improve logical flow"
                ))

            # Paragraph structure
            if 2 <= metrics["paragraph_count"] <= 10:
                coherence_score += 0.2
            elif metrics["paragraph_count"] == 1 and len(text) > 500:
                result["issues"].append(QualityIssue(
                    dimension="coherence",
                    severity="medium",
                    description="Long text without paragraph breaks",
                    suggestion="Break text into paragraphs for better readability"
                ))

            # Check for repetitive patterns (simple heuristic)
            words = text.lower().split()
            if len(words) > 50:
                unique_words = len(set(words))
                repetition_ratio = unique_words / len(words)
                metrics["vocabulary_diversity"] = repetition_ratio

                if repetition_ratio < 0.3:
                    coherence_score -= 0.2
                    result["issues"].append(QualityIssue(
                        dimension="coherence",
                        severity="medium",
                        description="High word repetition detected",
                        suggestion="Vary vocabulary to improve text quality"
                    ))

            result["score"] = max(0.0, min(1.0, coherence_score))
            result["metrics"] = metrics

            return result

        except Exception as e:
            logger.error(f"Coherence assessment failed: {str(e)}")
            return {"score": 0.0, "issues": [QualityIssue("coherence", "high", str(e))], "metrics": {}}

    async def assess_completeness(self, text: str, document: Document) -> Dict[str, Any]:
        """Assess document completeness"""
        try:
            result = {"score": 0.5, "issues": [], "metrics": {}}

            metrics = {}

            # Basic completeness checks
            word_count = len(text.split())
            metrics["word_count"] = word_count

            # Document type specific completeness
            if document.document_type == DocumentType.PDF:
                # Check for common PDF document elements
                has_title = bool(re.search(r'^[A-Z\s]{20,}', text, re.MULTILINE))
                has_conclusion = bool(re.search(r'(conclusion|summary|final)', text, re.IGNORECASE))
                has_structure = bool(re.search(r'(chapter|section|part)', text, re.IGNORECASE))

                completeness_score = 0.3
                if has_title:
                    completeness_score += 0.2
                if has_structure:
                    completeness_score += 0.3
                if has_conclusion:
                    completeness_score += 0.2

                metrics["has_title"] = has_title
                metrics["has_structure"] = has_structure
                metrics["has_conclusion"] = has_conclusion

            else:
                # Generic completeness assessment
                if word_count < 50:
                    completeness_score = 0.2
                    result["issues"].append(QualityIssue(
                        dimension="completeness",
                        severity="high",
                        description="Document appears incomplete (very short)",
                        suggestion="Ensure document has sufficient content"
                    ))
                elif word_count > 100:
                    completeness_score = 0.8
                else:
                    completeness_score = 0.5

            # Check for abrupt ending
            if text and not text.endswith(('.', '!', '?', '"', "'")):
                result["issues"].append(QualityIssue(
                    dimension="completeness",
                    severity="low",
                    description="Document may end abruptly",
                    suggestion="Review document ending"
                ))
                completeness_score -= 0.1

            result["score"] = max(0.0, min(1.0, completeness_score))
            result["metrics"] = metrics

            return result

        except Exception as e:
            logger.error(f"Completeness assessment failed: {str(e)}")
            return {"score": 0.0, "issues": [QualityIssue("completeness", "high", str(e))], "metrics": {}}

    async def assess_accuracy(self, text: str) -> Dict[str, Any]:
        """Assess text accuracy (basic heuristics)"""
        try:
            result = {"score": 0.7, "issues": [], "metrics": {}}

            # Note: This is a basic implementation
            # Real accuracy assessment would require fact-checking, external validation, etc.

            metrics = {}

            # Check for spelling errors (basic)
            words = text.split()
            misspelled_count = 0
            for word in words:
                if len(word) > 8 and word.isalpha() and not word[0].isupper():
                    # Very basic heuristic for potential misspellings
                    if re.search(r'[qjxzx]', word.lower()):
                        misspelled_count += 1

            metrics["potential_spelling_errors"] = misspelled_count
            metrics["spelling_error_rate"] = misspelled_count / len(words) if words else 0

            accuracy_score = 0.7

            if metrics["spelling_error_rate"] > 0.05:
                accuracy_score -= 0.2
                result["issues"].append(QualityIssue(
                    dimension="accuracy",
                    severity="low",
                    description="Potential spelling errors detected",
                    suggestion="Review document for spelling accuracy"
                ))

            # Check for formatting consistency
            has_inconsistent_spacing = bool(re.search(r' {2,}', text))
            has_inconsistent_capitalization = bool(re.search(r'[a-z][A-Z]', text))

            if has_inconsistent_spacing or has_inconsistent_capitalization:
                accuracy_score -= 0.1
                result["issues"].append(QualityIssue(
                    dimension="accuracy",
                    severity="low",
                    description="Formatting inconsistencies detected",
                    suggestion="Review document formatting for consistency"
                ))

            result["score"] = max(0.0, min(1.0, accuracy_score))
            result["metrics"] = metrics

            return result

        except Exception as e:
            logger.error(f"Accuracy assessment failed: {str(e)}")
            return {"score": 0.0, "issues": [QualityIssue("accuracy", "high", str(e))], "metrics": {}}

    async def assess_technical_quality(self, document: Document) -> Dict[str, Any]:
        """Assess technical quality of document"""
        try:
            result = {"score": 0.8, "issues": [], "metrics": {}}

            metrics = {}

            # File integrity checks
            metrics["file_size_bytes"] = document.file_size_bytes
            metrics["file_size_mb"] = document.file_size_mb
            metrics["mime_type"] = document.mime_type
            metrics["processing_status"] = document.processing_status.value

            technical_score = 0.8

            # Check processing status
            if document.processing_status.value == "failed":
                technical_score -= 0.4
                result["issues"].append(QualityIssue(
                    dimension="technical_quality",
                    severity="high",
                    description="Document processing failed",
                    suggestion="Review document format and content"
                ))
            elif document.processing_status.value == "completed":
                technical_score += 0.1

            # Check file size reasonableness
            if document.file_size_bytes < 100:
                technical_score -= 0.2
                result["issues"].append(QualityIssue(
                    dimension="technical_quality",
                    severity="medium",
                    description="File size is suspiciously small",
                    suggestion="Verify file integrity"
                ))

            # Check metadata completeness
            metadata = document.get_metadata()
            metadata_score = min(1.0, len(metadata) / 5)  # Normalize to 5 expected metadata fields
            technical_score = (technical_score * 0.7) + (metadata_score * 0.3)

            metrics["metadata_completeness"] = metadata_score
            metrics["metadata_field_count"] = len(metadata)

            result["score"] = max(0.0, min(1.0, technical_score))
            result["metrics"] = metrics

            return result

        except Exception as e:
            logger.error(f"Technical quality assessment failed: {str(e)}")
            return {"score": 0.0, "issues": [QualityIssue("technical_quality", "high", str(e))], "metrics": {}}

    async def assess_content_quality(self, text: str, document: Document) -> Dict[str, Any]:
        """Assess overall content quality"""
        try:
            result = {"score": 0.6, "issues": [], "metrics": {}}

            metrics = {}

            # Content length assessment
            word_count = len(text.split())
            metrics["word_count"] = word_count
            metrics["character_count"] = len(text)

            # Content structure assessment
            sentences = re.split(r'[.!?]+', text)
            metrics["sentence_count"] = len([s for s in sentences if s.strip()])

            # Vocabulary richness
            words = text.lower().split()
            unique_words = len(set(words))
            metrics["vocabulary_richness"] = unique_words / len(words) if words else 0

            content_score = 0.6

            # Score based on content length
            if 100 <= word_count <= 10000:
                content_score += 0.2
            elif word_count < 50:
                content_score -= 0.3
                result["issues"].append(QualityIssue(
                    dimension="content_quality",
                    severity="medium",
                    description="Very limited content",
                    suggestion="Consider expanding document content"
                ))

            # Score based on vocabulary richness
            if metrics["vocabulary_richness"] > 0.6:
                content_score += 0.1
            elif metrics["vocabulary_richness"] < 0.3:
                content_score -= 0.1
                result["issues"].append(QualityIssue(
                    dimension="content_quality",
                    severity="low",
                    description="Limited vocabulary diversity",
                    suggestion="Vary word choice to improve content quality"
                ))

            # Check for meaningful content (basic heuristic)
            meaningful_words = [w for w in words if len(w) > 3 and w.isalpha()]
            meaningful_ratio = len(meaningful_words) / len(words) if words else 0
            metrics["meaningful_word_ratio"] = meaningful_ratio

            if meaningful_ratio < 0.5:
                content_score -= 0.1

            result["score"] = max(0.0, min(1.0, content_score))
            result["metrics"] = metrics

            return result

        except Exception as e:
            logger.error(f"Content quality assessment failed: {str(e)}")
            return {"score": 0.0, "issues": [QualityIssue("content_quality", "high", str(e))], "metrics": {}}

    async def assess_metadata_quality(self, document: Document) -> Dict[str, Any]:
        """Assess metadata quality"""
        try:
            result = {"score": 0.7, "issues": [], "metrics": {}}

            metadata = document.get_metadata()
            metrics = {
                "metadata_field_count": len(metadata),
                "has_title": bool(document.title),
                "has_tags": bool(document.tags),
                "has_description": bool(document.get_metadata_value("description")),
                "creation_date": document.created_at.isoformat() if document.created_at else None
            }

            # Essential metadata fields
            essential_fields = ["title", "file_hash"]
            present_essential = sum(1 for field in essential_fields
                                 if field in metadata or
                                 (field == "title" and document.title))

            metadata_score = present_essential / len(essential_fields)

            # Optional metadata fields
            optional_fields = ["description", "author", "language", "keywords"]
            present_optional = sum(1 for field in optional_fields if field in metadata)
            optional_score = present_optional / len(optional_fields) * 0.3  # Weight less

            total_score = metadata_score + optional_score

            # Check metadata quality issues
            if not document.title or len(document.title.strip()) < 3:
                result["issues"].append(QualityIssue(
                    dimension="metadata_quality",
                    severity="medium",
                    description="Missing or inadequate title",
                    suggestion="Add a descriptive title"
                ))
                total_score -= 0.2

            if not document.tags:
                result["issues"].append(QualityIssue(
                    dimension="metadata_quality",
                    severity="low",
                    description="No tags assigned",
                    suggestion="Add relevant tags for better organization"
                ))
                total_score -= 0.1

            result["score"] = max(0.0, min(1.0, total_score))
            result["metrics"] = metrics

            return result

        except Exception as e:
            logger.error(f"Metadata quality assessment failed: {str(e)}")
            return {"score": 0.0, "issues": [QualityIssue("metadata_quality", "high", str(e))], "metrics": {}}

    def generate_quick_recommendations(self, assessment: Dict[str, Any]) -> List[str]:
        """Generate quick recommendations based on assessment"""
        recommendations = []

        if assessment["readability_score"] < 0.6:
            recommendations.append("Consider breaking long sentences and improving text structure for better readability")

        if assessment["content_quality_score"] < 0.5:
            recommendations.append("Document content appears limited. Consider expanding with more detailed information")

        if assessment["technical_quality_score"] < 0.6:
            recommendations.append("Technical issues detected. Check document processing status and file integrity")

        return recommendations

    def generate_comprehensive_recommendations(self, assessment: Dict[str, Any], dimension_scores: Dict[str, float]) -> List[str]:
        """Generate comprehensive recommendations"""
        recommendations = []

        # Overall score recommendations
        if assessment["overall_score"] < 0.4:
            recommendations.append("Document requires significant improvement across multiple quality dimensions")
        elif assessment["overall_score"] < 0.7:
            recommendations.append("Document quality can be improved with targeted enhancements")

        # Dimension-specific recommendations
        for dimension, score in dimension_scores.items():
            threshold = self.quality_thresholds.get(dimension, 0.7)
            if score < threshold:
                if dimension == "readability":
                    recommendations.append("Improve readability by using shorter sentences and clearer language")
                elif dimension == "coherence":
                    recommendations.append("Enhance logical flow with transition words and better paragraph structure")
                elif dimension == "completeness":
                    recommendations.append("Expand content to ensure document completeness")
                elif dimension == "accuracy":
                    recommendations.append("Review content for accuracy and proper formatting")
                elif dimension == "technical_quality":
                    recommendations.append("Address technical issues and improve file processing")
                elif dimension == "content_quality":
                    recommendations.append("Enhance content quality with more detailed and diverse information")
                elif dimension == "metadata_quality":
                    recommendations.append("Improve metadata by adding titles, descriptions, and tags")

        return recommendations

    async def store_quality_metrics(self, document: Document, assessment: Dict[str, Any]):
        """Store quality metrics in database"""
        # Skip if QualityMetrics model not implemented yet
        if QualityMetrics is None:
            logger.warning("QualityMetrics model not implemented - skipping quality metrics storage")
            return

        try:
            # Create quality metrics record
            quality_metrics = QualityMetrics(
                document_id=document.id,
                organization_id=document.organization_id,
                overall_score=assessment["overall_score"],
                readability_score=assessment.get("readability_score", 0.0),
                coherence_score=assessment.get("coherence_score", 0.0),
                completeness_score=assessment.get("completeness_score", 0.0),
                accuracy_score=assessment.get("accuracy_score", 0.0),
                technical_quality_score=assessment.get("technical_quality_score", 0.0),
                content_quality_score=assessment.get("content_quality_score", 0.0),
                metadata_quality_score=assessment.get("metadata_quality_score", 0.0),
                detailed_metrics=assessment.get("detailed_metrics", {}),
                recommendations=assessment.get("recommendations", []),
                assessment_version="1.0"
            )

            self.db.add(quality_metrics)
            self.db.commit()

        except Exception as e:
            logger.error(f"Failed to store quality metrics: {str(e)}")
            # Don't raise error as this is not critical

# Dependency injection
def get_document_quality_service(db: Session = Depends(get_db)) -> DocumentQualityService:
    """Get document quality service instance"""
    return DocumentQualityService(db)