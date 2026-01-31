"""
Evaluation Services Package

Provides RAG evaluation capabilities:
- LLM Judge: GPT-4o/GPT-5 based semantic evaluation
- HHEM: Vectara hallucination detection
- Advanced RAG Evaluator: Combined evaluation service
"""

from .advanced_rag_evaluator import (
    AdvancedRAGEvaluator,
    QuickEvaluationResult,
    RAGEvaluationResult,
    evaluate_rag_response,
    get_advanced_evaluator,
)
from .hhem_faithfulness_service import (
    FaithfulnessResult,
    HHEMFaithfulnessService,
    get_hhem_service,
)
from .llm_judge_service import (
    FullJudgeEvaluation,
    JudgeCriteria,
    JudgeScore,
    LLMJudgeService,
    get_llm_judge_service,
)

__all__ = [
    # LLM Judge
    "LLMJudgeService",
    "JudgeScore",
    "FullJudgeEvaluation",
    "JudgeCriteria",
    "get_llm_judge_service",
    # HHEM
    "HHEMFaithfulnessService",
    "FaithfulnessResult",
    "get_hhem_service",
    # Advanced Evaluator
    "AdvancedRAGEvaluator",
    "RAGEvaluationResult",
    "QuickEvaluationResult",
    "get_advanced_evaluator",
    "evaluate_rag_response",
]
