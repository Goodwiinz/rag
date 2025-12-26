"""
Evaluation Services Package

Provides RAG evaluation capabilities:
- LLM Judge: GPT-4o/GPT-5 based semantic evaluation
- HHEM: Vectara hallucination detection
- Advanced RAG Evaluator: Combined evaluation service
"""

from .llm_judge_service import (
    LLMJudgeService,
    JudgeScore,
    FullJudgeEvaluation,
    JudgeCriteria,
    get_llm_judge_service
)

from .hhem_faithfulness_service import (
    HHEMFaithfulnessService,
    FaithfulnessResult,
    get_hhem_service
)

from .advanced_rag_evaluator import (
    AdvancedRAGEvaluator,
    RAGEvaluationResult,
    QuickEvaluationResult,
    get_advanced_evaluator,
    evaluate_rag_response
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
    "evaluate_rag_response"
]
