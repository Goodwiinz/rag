"""
Success Criteria Framework for Multimodal Enterprise RAG System

This module defines comprehensive success criteria and evaluation metrics
for the multimodal RAG system following evaluation-first development principles.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json


class QueryType(str, Enum):
    """Types of queries the RAG system should support"""
    FACTUAL_LOOKUP = "factual_lookup"
    REASONING = "reasoning"
    SUMMARIZATION = "summarization"
    COMPARISON = "comparison"
    SEMANTIC_LINKAGE = "semantic_linkage"
    MULTIMODAL_QUERY = "multimodal_query"
    TEMPORAL_QUERY = "temporal_query"
    CAUSAL_QUERY = "causal_query"


class ModalityType(str, Enum):
    """Supported modalities for ingestion and retrieval"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


class MetricCategory(str, Enum):
    """Categories of evaluation metrics"""
    RETRIEVAL_QUALITY = "retrieval_quality"
    ANSWER_QUALITY = "answer_quality"
    MULTIMODAL_COHERENCE = "multimodal_coherence"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    SECURITY = "security"


@dataclass
class SuccessThreshold:
    """Defines success thresholds for different metrics"""
    metric_name: str
    minimum_threshold: float
    target_threshold: float
    description: str
    category: MetricCategory
    weight: float = 1.0


class RAGSuccessCriteria:
    """
    Comprehensive success criteria for the multimodal RAG system
    """

    def __init__(self):
        self.thresholds = self._define_success_thresholds()
        self.query_type_requirements = self._define_query_type_requirements()
        self.modality_requirements = self._define_modality_requirements()

    def _define_success_thresholds(self) -> Dict[str, SuccessThreshold]:
        """Define success thresholds for all metrics"""
        return {
            # Core RAG Triad Metrics
            "answer_relevancy": SuccessThreshold(
                metric_name="answer_relevancy",
                minimum_threshold=0.70,
                target_threshold=0.85,
                description="Answer should be relevant to the query",
                category=MetricCategory.ANSWER_QUALITY,
                weight=0.25
            ),
            "faithfulness": SuccessThreshold(
                metric_name="faithfulness",
                minimum_threshold=0.90,
                target_threshold=0.95,
                description="Answer should be supported by retrieved context",
                category=MetricCategory.ANSWER_QUALITY,
                weight=0.30
            ),
            "contextual_relevancy": SuccessThreshold(
                metric_name="contextual_relevancy",
                minimum_threshold=0.70,
                target_threshold=0.85,
                description="Retrieved context should be relevant to query",
                category=MetricCategory.RETRIEVAL_QUALITY,
                weight=0.25
            ),

            # Performance Metrics
            "latency_p95": SuccessThreshold(
                metric_name="latency_p95",
                minimum_threshold=3000.0,  # ms
                target_threshold=2000.0,   # ms
                description="95th percentile response time",
                category=MetricCategory.PERFORMANCE,
                weight=0.10
            ),
            "throughput_qps": SuccessThreshold(
                metric_name="throughput_qps",
                minimum_threshold=10.0,    # queries/second
                target_threshold=50.0,    # queries/second
                description="Queries per second sustained",
                category=MetricCategory.PERFORMANCE,
                weight=0.05
            ),

            # Reliability Metrics
            "hallucination_rate": SuccessThreshold(
                metric_name="hallucination_rate",
                minimum_threshold=0.15,    # 15% max
                target_threshold=0.05,    # 5% target
                description="Rate of fabricated information",
                category=MetricCategory.RELIABILITY,
                weight=0.20
            ),
            "error_rate": SuccessThreshold(
                metric_name="error_rate",
                minimum_threshold=0.05,    # 5% max
                target_threshold=0.01,    # 1% target
                description="System error rate",
                category=MetricCategory.RELIABILITY,
                weight=0.15
            ),
            "availability_uptime": SuccessThreshold(
                metric_name="availability_uptime",
                minimum_threshold=0.99,    # 99% uptime
                target_threshold=0.999,   # 99.9% uptime
                description="System availability percentage",
                category=MetricCategory.RELIABILITY,
                weight=0.10
            ),

            # Multimodal Metrics
            "cross_modal_coherence": SuccessThreshold(
                metric_name="cross_modal_coherence",
                minimum_threshold=0.65,
                target_threshold=0.80,
                description="Consistency across different modalities",
                category=MetricCategory.MULTIMODAL_COHERENCE,
                weight=0.15
            ),
            "modality_coverage": SuccessThreshold(
                metric_name="modality_coverage",
                minimum_threshold=0.80,    # 80% of modalities supported
                target_threshold=0.95,    # 95% of modalities supported
                description="Coverage of supported modalities",
                category=MetricCategory.MULTIMODAL_COHERENCE,
                weight=0.10
            ),

            # Security & Compliance
            "access_control_violations": SuccessThreshold(
                metric_name="access_control_violations",
                minimum_threshold=0.0,     # Zero violations
                target_threshold=0.0,     # Zero violations
                description="Security access control violations",
                category=MetricCategory.SECURITY,
                weight=0.25
            ),
            "data_leakage_incidents": SuccessThreshold(
                metric_name="data_leakage_incidents",
                minimum_threshold=0.0,     # Zero incidents
                target_threshold=0.0,     # Zero incidents
                description="Data leakage incidents",
                category=MetricCategory.SECURITY,
                weight=0.25
            ),

            # Advanced Metrics
            "entity_extraction_accuracy": SuccessThreshold(
                metric_name="entity_extraction_accuracy",
                minimum_threshold=0.80,
                target_threshold=0.90,
                description="Accuracy of entity extraction from documents",
                category=MetricCategory.RETRIEVAL_QUALITY,
                weight=0.15
            ),
            "relationship_extraction_precision": SuccessThreshold(
                metric_name="relationship_extraction_precision",
                minimum_threshold=0.75,
                target_threshold=0.85,
                description="Precision of relationship extraction",
                category=MetricCategory.RETRIEVAL_QUALITY,
                weight=0.15
            ),
            "semantic_search_precision": SuccessThreshold(
                metric_name="semantic_search_precision",
                minimum_threshold=0.70,
                target_threshold=0.85,
                description="Precision of semantic vector search",
                category=MetricCategory.RETRIEVAL_QUALITY,
                weight=0.20
            ),
            "graph_traversal_accuracy": SuccessThreshold(
                metric_name="graph_traversal_accuracy",
                minimum_threshold=0.75,
                target_threshold=0.90,
                description="Accuracy of knowledge graph navigation",
                category=MetricCategory.RETRIEVAL_QUALITY,
                weight=0.20
            )
        }

    def _define_query_type_requirements(self) -> Dict[QueryType, Dict[str, Any]]:
        """Define specific requirements for each query type"""
        return {
            QueryType.FACTUAL_LOOKUP: {
                "description": "Direct fact retrieval queries",
                "example_queries": [
                    "What is the revenue of Company X in 2023?",
                    "Who is the CEO of Organization Y?",
                    "When was Product Z launched?"
                ],
                "required_modalities": [ModalityType.TEXT],
                "success_metrics": [
                    "answer_relevancy", "faithfulness", "contextual_relevancy",
                    "entity_extraction_accuracy", "latency_p95"
                ],
                "minimum_threshold": 0.80,
                "test_data_size": 100,
                "evaluation_frequency": "daily"
            },

            QueryType.REASONING: {
                "description": "Complex reasoning and inference queries",
                "example_queries": [
                    "How might the acquisition of Company A affect Company B's market position?",
                    "What are the potential risks of expanding into Market X?",
                    "Based on the financial trends, what is the outlook for Industry Y?"
                ],
                "required_modalities": [ModalityType.TEXT],
                "success_metrics": [
                    "answer_relevancy", "faithfulness", "contextual_relevancy",
                    "hallucination_rate", "graph_traversal_accuracy"
                ],
                "minimum_threshold": 0.75,
                "test_data_size": 50,
                "evaluation_frequency": "weekly"
            },

            QueryType.SUMMARIZATION: {
                "description": "Document and multi-document summarization",
                "example_queries": [
                    "Summarize the key findings from the Q3 financial report",
                    "Provide an executive summary of the board meeting minutes",
                    "What are the main points from the product documentation?"
                ],
                "required_modalities": [ModalityType.TEXT, ModalityType.IMAGE],
                "success_metrics": [
                    "answer_relevancy", "faithfulness", "cross_modal_coherence",
                    "contextual_relevancy"
                ],
                "minimum_threshold": 0.70,
                "test_data_size": 30,
                "evaluation_frequency": "weekly"
            },

            QueryType.COMPARISON: {
                "description": "Comparative analysis between entities",
                "example_queries": [
                    "Compare the market share of Company A vs Company B",
                    "What are the differences between Product X and Product Y?",
                    "How do the financial metrics compare across quarters?"
                ],
                "required_modalities": [ModalityType.TEXT],
                "success_metrics": [
                    "answer_relevancy", "faithfulness", "entity_extraction_accuracy",
                    "graph_traversal_accuracy"
                ],
                "minimum_threshold": 0.75,
                "test_data_size": 40,
                "evaluation_frequency": "weekly"
            },

            QueryType.SEMANTIC_LINKAGE: {
                "description": "Finding relationships and connections",
                "example_queries": [
                    "What is the relationship between Project X and Executive Y?",
                    "How are Department A and Department B connected?",
                    "Find all documents related to Initiative Z"
                ],
                "required_modalities": [ModalityType.TEXT],
                "success_metrics": [
                    "contextual_relevancy", "entity_extraction_accuracy",
                    "relationship_extraction_precision", "graph_traversal_accuracy"
                ],
                "minimum_threshold": 0.70,
                "test_data_size": 60,
                "evaluation_frequency": "daily"
            },

            QueryType.MULTIMODAL_QUERY: {
                "description": "Queries spanning multiple modalities",
                "example_queries": [
                    "What information do the charts and images in the annual report convey?",
                    "Find all video content that mentions Product X",
                    "What do the meeting recordings and transcripts say about Project Y?"
                ],
                "required_modalities": [ModalityType.TEXT, ModalityType.IMAGE, ModalityType.AUDIO, ModalityType.VIDEO],
                "success_metrics": [
                    "answer_relevancy", "cross_modal_coherence", "modality_coverage",
                    "contextual_relevancy", "faithfulness"
                ],
                "minimum_threshold": 0.65,
                "test_data_size": 25,
                "evaluation_frequency": "weekly"
            },

            QueryType.TEMPORAL_QUERY: {
                "description": "Time-based queries and trend analysis",
                "example_queries": [
                    "How has the company performance evolved over the past 5 years?",
                    "What were the key events in Q2 2023?",
                    "Show trends in customer satisfaction over time"
                ],
                "required_modalities": [ModalityType.TEXT],
                "success_metrics": [
                    "answer_relevancy", "faithfulness", "entity_extraction_accuracy",
                    "contextual_relevancy"
                ],
                "minimum_threshold": 0.70,
                "test_data_size": 35,
                "evaluation_frequency": "monthly"
            },

            QueryType.CAUSAL_QUERY: {
                "description": "Cause-and-effect relationship queries",
                "example_queries": [
                    "What caused the decline in sales in Region X?",
                    "How did the marketing campaign impact customer acquisition?",
                    "What factors contributed to the project delay?"
                ],
                "required_modalities": [ModalityType.TEXT],
                "success_metrics": [
                    "answer_relevancy", "faithfulness", "hallucination_rate",
                    "graph_traversal_accuracy", "reasoning_quality"
                ],
                "minimum_threshold": 0.70,
                "test_data_size": 30,
                "evaluation_frequency": "monthly"
            }
        }

    def _define_modality_requirements(self) -> Dict[ModalityType, Dict[str, Any]]:
        """Define requirements for each modality type"""
        return {
            ModalityType.TEXT: {
                "supported_formats": [".txt", ".pdf", ".docx", ".md", ".rtf"],
                "processing_capabilities": [
                    "text_extraction", "ocr", "entity_extraction",
                    "summarization", "sentiment_analysis"
                ],
                "quality_metrics": [
                    "text_extraction_accuracy", "entity_extraction_f1",
                    "summarization_rouge_score", "sentiment_accuracy"
                ],
                "minimum_accuracy": 0.85,
                "target_throughput": 100,  # documents/minute
                "storage_requirements": "Raw text + extracted metadata"
            },

            ModalityType.IMAGE: {
                "supported_formats": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"],
                "processing_capabilities": [
                    "object_detection", "scene_classification", "text_extraction_ocr",
                    "face_detection", "image_captioning", "chart_analysis"
                ],
                "quality_metrics": [
                    "object_detection_map", "ocr_accuracy", "captioning_bleu_score",
                    "classification_accuracy", "face_detection_f1"
                ],
                "minimum_accuracy": 0.80,
                "target_throughput": 50,   # images/minute
                "storage_requirements": "Original image + extracted features + metadata"
            },

            ModalityType.AUDIO: {
                "supported_formats": [".mp3", ".wav", ".m4a", ".flac", ".aac"],
                "processing_capabilities": [
                    "speech_to_text", "speaker_diarization", "emotion_detection",
                    "keyword_spotting", "audio_classification", "transcription"
                ],
                "quality_metrics": [
                    "transcription_wer", "speaker_diarization_der", "emotion_accuracy",
                    "keyword_detection_f1", "classification_accuracy"
                ],
                "minimum_accuracy": 0.85,
                "target_throughput": 20,   # audio files/minute
                "storage_requirements": "Original audio + transcript + timestamps + metadata"
            },

            ModalityType.VIDEO: {
                "supported_formats": [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"],
                "processing_capabilities": [
                    "frame_extraction", "scene_detection", "audio_transcription",
                    "object_tracking", "action_recognition", "video_summarization"
                ],
                "quality_metrics": [
                    "frame_extraction_quality", "scene_detection_accuracy",
                    "action_recognition_map", "summarization_quality"
                ],
                "minimum_accuracy": 0.75,
                "target_throughput": 5,    # videos/minute
                "storage_requirements": "Original video + keyframes + audio transcript + metadata"
            }
        }

    def get_success_criteria_for_query_type(self, query_type: QueryType) -> Dict[str, Any]:
        """Get success criteria for a specific query type"""
        return self.query_type_requirements.get(query_type, {})

    def get_thresholds_for_category(self, category: MetricCategory) -> List[SuccessThreshold]:
        """Get all thresholds for a specific metric category"""
        return [
            threshold for threshold in self.thresholds.values()
            if threshold.category == category
        ]

    def calculate_overall_success_score(
        self,
        metric_scores: Dict[str, float],
        query_type: Optional[QueryType] = None
    ) -> Dict[str, Any]:
        """
        Calculate overall success score from individual metric scores

        Args:
            metric_scores: Dictionary of metric names to scores
            query_type: Optional query type for query-specific weighting

        Returns:
            Dictionary containing overall scores and analysis
        """
        total_weighted_score = 0.0
        total_weight = 0.0
        category_scores = {}

        for metric_name, score in metric_scores.items():
            if metric_name in self.thresholds:
                threshold = self.thresholds[metric_name]
                weight = threshold.weight

                # Apply query-type specific adjustments if applicable
                if query_type and query_type in self.query_type_requirements:
                    required_metrics = self.query_type_requirements[query_type]["success_metrics"]
                    if metric_name in required_metrics:
                        weight *= 1.2  # Boost weight for query-type critical metrics

                total_weighted_score += score * weight
                total_weight += weight

                # Track category scores
                category = threshold.category.value
                if category not in category_scores:
                    category_scores[category] = {"total": 0.0, "weight": 0.0}
                category_scores[category]["total"] += score * weight
                category_scores[category]["weight"] += weight

        # Calculate final scores
        overall_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

        # Calculate category scores
        final_category_scores = {}
        for category, scores in category_scores.items():
            final_category_scores[category] = (
                scores["total"] / scores["weight"] if scores["weight"] > 0 else 0.0
            )

        # Determine success status
        success_threshold = 0.75  # Overall success threshold
        if query_type:
            success_threshold = self.query_type_requirements.get(query_type, {}).get("minimum_threshold", 0.75)

        is_successful = overall_score >= success_threshold

        # Identify failing metrics
        failing_metrics = []
        for metric_name, score in metric_scores.items():
            if metric_name in self.thresholds:
                threshold = self.thresholds[metric_name]
                if score < threshold.minimum_threshold:
                    failing_metrics.append({
                        "metric": metric_name,
                        "score": score,
                        "threshold": threshold.minimum_threshold,
                        "gap": threshold.minimum_threshold - score
                    })

        return {
            "overall_score": overall_score,
            "is_successful": is_successful,
            "success_threshold": success_threshold,
            "category_scores": final_category_scores,
            "failing_metrics": failing_metrics,
            "total_metrics_evaluated": len(metric_scores),
            "query_type": query_type.value if query_type else None
        }

    def validate_evaluation_completeness(
        self,
        metric_scores: Dict[str, float],
        query_type: Optional[QueryType] = None
    ) -> Dict[str, Any]:
        """
        Validate if the evaluation covers all required metrics

        Args:
            metric_scores: Dictionary of metric names to scores
            query_type: Optional query type for query-specific requirements

        Returns:
            Dictionary containing validation results
        """
        required_metrics = set(self.thresholds.keys())

        # Add query-type specific requirements
        if query_type and query_type in self.query_type_requirements:
            query_metrics = set(self.query_type_requirements[query_type]["success_metrics"])
            required_metrics.update(query_metrics)

        evaluated_metrics = set(metric_scores.keys())
        missing_metrics = required_metrics - evaluated_metrics
        extra_metrics = evaluated_metrics - required_metrics

        completeness_percentage = (len(evaluated_metrics & required_metrics) / len(required_metrics)) * 100

        return {
            "is_complete": len(missing_metrics) == 0,
            "completeness_percentage": completeness_percentage,
            "missing_metrics": list(missing_metrics),
            "extra_metrics": list(extra_metrics),
            "total_required": len(required_metrics),
            "total_evaluated": len(evaluated_metrics)
        }

    def export_success_criteria(self) -> Dict[str, Any]:
        """Export success criteria for documentation or configuration"""
        return {
            "thresholds": {
                name: {
                    "minimum_threshold": threshold.minimum_threshold,
                    "target_threshold": threshold.target_threshold,
                    "description": threshold.description,
                    "category": threshold.category.value,
                    "weight": threshold.weight
                }
                for name, threshold in self.thresholds.items()
            },
            "query_type_requirements": {
                query_type.value: requirements
                for query_type, requirements in self.query_type_requirements.items()
            },
            "modality_requirements": {
                modality.value: requirements
                for modality, requirements in self.modality_requirements.items()
            },
            "evaluation_schema_version": "1.0.0",
            "last_updated": "2025-01-03"
        }


# Global success criteria instance
success_criteria = RAGSuccessCriteria()