"""
Pydantic Schemas for AI Response Validation

Provides runtime validation for AI responses, ensuring structured
outputs conform to expected formats.

Usage:
    from src.core.ai.schemas import JudgeScoreSchema
    
    # Validate AI response
    score = JudgeScoreSchema.model_validate({
        "score": 0.85,
        "reasoning": "Good answer",
        "confidence": 0.9
    })
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class JudgeCriteriaEnum(str, Enum):
    """Evaluation criteria types."""
    ANSWER_RELEVANCY = "answer_relevancy"
    CONTEXT_RELEVANCY = "context_relevancy"
    COMPLETENESS = "completeness"
    SAFETY = "safety"
    FAITHFULNESS = "faithfulness"


class JudgeScoreSchema(BaseModel):
    """
    Validated LLM judge score.
    
    Represents a single evaluation score with reasoning and confidence.
    """
    
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Evaluation score between 0 and 1"
    )
    reasoning: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Explanation for the score"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the evaluation"
    )
    
    @field_validator('score', 'confidence')
    @classmethod
    def round_to_precision(cls, v: float) -> float:
        """Round scores to 4 decimal places."""
        return round(v, 4)
    
    @field_validator('reasoning')
    @classmethod
    def clean_reasoning(cls, v: str) -> str:
        """Clean and normalize reasoning text."""
        return v.strip()

    model_config = ConfigDict(
        extra="ignore",  # Ignore unknown fields from AI responses
        str_strip_whitespace=True
    )


class FullJudgeEvaluationSchema(BaseModel):
    """
    Complete LLM judge evaluation with all criteria.
    
    Used for comprehensive RAG evaluation including answer relevancy,
    context relevancy, completeness, and safety.
    """
    
    answer_relevancy: JudgeScoreSchema
    context_relevancy: JudgeScoreSchema
    completeness: JudgeScoreSchema
    safety: JudgeScoreSchema
    overall_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    pass_fail: bool
    evaluation_time_ms: float = Field(..., ge=0)
    
    @model_validator(mode='before')
    @classmethod
    def calculate_overall_if_missing(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall score if not provided."""
        if isinstance(data, dict) and data.get('overall_score') is None:
            weights = {
                "answer_relevancy": 0.35,
                "context_relevancy": 0.20,
                "completeness": 0.25,
                "safety": 0.20
            }
            total = 0.0
            for key, weight in weights.items():
                if key in data and isinstance(data[key], dict):
                    total += data[key].get('score', 0.5) * weight
                elif key in data and hasattr(data[key], 'score'):
                    total += data[key].score * weight
            data['overall_score'] = round(total, 4)
        return data

    model_config = ConfigDict(extra="ignore")


class ChatMessageSchema(BaseModel):
    """Schema for chat messages in AI conversations."""

    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str = Field(..., min_length=1)
    name: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class EvaluationRequestSchema(BaseModel):
    """Schema for evaluation request parameters."""
    
    query: str = Field(..., min_length=1, max_length=10000)
    answer: str = Field(..., min_length=1, max_length=50000)
    contexts: List[str] = Field(default_factory=list, max_length=10)
    
    @field_validator('contexts')
    @classmethod
    def limit_context_length(cls, v: List[str]) -> List[str]:
        """Limit each context to reasonable length."""
        return [ctx[:10000] for ctx in v[:10]]  # Max 10 contexts, 10k chars each


class SimilarityScoreSchema(BaseModel):
    """Schema for similarity/relevance scores."""

    document_id: str
    score: float = Field(..., ge=0.0, le=1.0)
    content_snippet: str = Field(default="", max_length=1000)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")
