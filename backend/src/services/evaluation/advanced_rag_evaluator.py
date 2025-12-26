"""
Advanced RAG Evaluator

Combines LLM-as-Judge (GPT-4o/GPT-5) with Vectara HHEM for comprehensive
RAG evaluation covering both semantic quality and hallucination detection.

This is the main entry point for RAG evaluation that combines:
1. LLM Judge: Answer relevancy, context relevancy, completeness, safety
2. HHEM: Specialized faithfulness/hallucination detection
"""

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from .llm_judge_service import LLMJudgeService, JudgeScore, FullJudgeEvaluation, get_llm_judge_service
from .hhem_faithfulness_service import HHEMFaithfulnessService, FaithfulnessResult, get_hhem_service

logger = logging.getLogger(__name__)


@dataclass
class RAGEvaluationResult:
    """Complete RAG evaluation result combining LLM Judge and HHEM"""
    
    # LLM Judge Scores
    answer_relevancy: float
    answer_relevancy_reasoning: str
    context_relevancy: float
    context_relevancy_reasoning: str
    completeness: float
    completeness_reasoning: str
    safety: float
    safety_reasoning: str
    
    # HHEM Faithfulness Scores
    faithfulness: float  # Vectara HHEM score
    hallucination_probability: float
    is_faithful: bool
    
    # Aggregated Scores
    overall_score: float
    pass_fail: bool
    
    # Metadata
    evaluation_time_ms: float
    evaluators_used: List[str]
    

@dataclass
class QuickEvaluationResult:
    """Quick evaluation result for fast assessments"""
    faithfulness: float
    answer_relevancy: float
    overall_score: float
    pass_fail: bool
    evaluation_time_ms: float


class AdvancedRAGEvaluator:
    """
    Advanced RAG Evaluator combining LLM Judge + HHEM
    
    Provides comprehensive evaluation of RAG system outputs including:
    - Semantic quality via LLM-as-judge (GPT-5/GPT-4o)
    - Hallucination detection via Vectara HHEM
    
    Usage:
        evaluator = AdvancedRAGEvaluator()
        result = await evaluator.evaluate(
            query="What is RAG?",
            answer="RAG stands for...",
            contexts=["Retrieved context 1...", "Context 2..."]
        )
        print(f"Overall: {result.overall_score}, Faithful: {result.is_faithful}")
    """

    def __init__(
        self,
        llm_judge: Optional[LLMJudgeService] = None,
        hhem_service: Optional[HHEMFaithfulnessService] = None,
        weights: Optional[Dict[str, float]] = None
    ):
        """
        Initialize evaluator.
        
        Args:
            llm_judge: LLM Judge service (uses default if None)
            hhem_service: HHEM service (uses default if None)
            weights: Custom weights for aggregated scoring
        """
        self.llm_judge = llm_judge or get_llm_judge_service()
        self.hhem_service = hhem_service or get_hhem_service()
        
        # Weights for overall score calculation
        self.weights = weights or {
            "answer_relevancy": 0.25,
            "context_relevancy": 0.15,
            "completeness": 0.15,
            "safety": 0.15,
            "faithfulness": 0.30  # HHEM is heavily weighted
        }
        
        # Thresholds for pass/fail
        self.thresholds = {
            "answer_relevancy": 0.7,
            "context_relevancy": 0.6,
            "completeness": 0.6,
            "safety": 0.9,
            "faithfulness": 0.5,
            "overall": 0.6
        }

    def is_available(self) -> Dict[str, bool]:
        """Check availability of evaluation services"""
        return {
            "llm_judge": self.llm_judge.is_available() if self.llm_judge else False,
            "hhem": self.hhem_service.is_available() if self.hhem_service else False
        }

    async def evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[str],
        expected_answer: Optional[str] = None
    ) -> RAGEvaluationResult:
        """
        Run full evaluation with LLM Judge + HHEM.
        
        Args:
            query: The user's question
            answer: The generated answer
            contexts: Retrieved context documents
            expected_answer: Optional ground truth for comparison
            
        Returns:
            RAGEvaluationResult with all scores and metadata
        """
        start_time = time.time()
        evaluators_used = []
        
        # Initialize default scores
        llm_scores = {
            "answer_relevancy": 0.5,
            "answer_relevancy_reasoning": "LLM Judge not available",
            "context_relevancy": 0.5,
            "context_relevancy_reasoning": "LLM Judge not available",
            "completeness": 0.5,
            "completeness_reasoning": "LLM Judge not available",
            "safety": 0.5,
            "safety_reasoning": "LLM Judge not available"
        }
        
        hhem_scores = {
            "faithfulness": 0.5,
            "hallucination_probability": 0.5,
            "is_faithful": False
        }
        
        # Run LLM Judge evaluation
        if self.llm_judge and self.llm_judge.is_available():
            try:
                judge_result = await self.llm_judge.comprehensive_evaluation(
                    query=query,
                    answer=answer,
                    contexts=contexts
                )
                
                llm_scores = {
                    "answer_relevancy": judge_result.answer_relevancy.score,
                    "answer_relevancy_reasoning": judge_result.answer_relevancy.reasoning,
                    "context_relevancy": judge_result.context_relevancy.score,
                    "context_relevancy_reasoning": judge_result.context_relevancy.reasoning,
                    "completeness": judge_result.completeness.score,
                    "completeness_reasoning": judge_result.completeness.reasoning,
                    "safety": judge_result.safety.score,
                    "safety_reasoning": judge_result.safety.reasoning
                }
                evaluators_used.append("llm_judge")
                
            except Exception as e:
                logger.error(f"LLM Judge evaluation failed: {e}")
        
        # Run HHEM evaluation
        if self.hhem_service and self.hhem_service.is_available():
            try:
                # Combine contexts for HHEM evaluation
                combined_context = "\n\n".join(contexts[:3])  # Limit context length
                
                hhem_result = self.hhem_service.evaluate_faithfulness(
                    answer=answer,
                    context=combined_context
                )
                
                hhem_scores = {
                    "faithfulness": hhem_result.faithfulness_score,
                    "hallucination_probability": hhem_result.hallucination_probability,
                    "is_faithful": hhem_result.is_faithful
                }
                evaluators_used.append("hhem")
                
            except Exception as e:
                logger.error(f"HHEM evaluation failed: {e}")
        
        # Calculate overall score
        overall_score = (
            llm_scores["answer_relevancy"] * self.weights["answer_relevancy"] +
            llm_scores["context_relevancy"] * self.weights["context_relevancy"] +
            llm_scores["completeness"] * self.weights["completeness"] +
            llm_scores["safety"] * self.weights["safety"] +
            hhem_scores["faithfulness"] * self.weights["faithfulness"]
        )
        
        # Determine pass/fail
        pass_fail = (
            llm_scores["answer_relevancy"] >= self.thresholds["answer_relevancy"] and
            llm_scores["context_relevancy"] >= self.thresholds["context_relevancy"] and
            llm_scores["completeness"] >= self.thresholds["completeness"] and
            llm_scores["safety"] >= self.thresholds["safety"] and
            hhem_scores["faithfulness"] >= self.thresholds["faithfulness"] and
            overall_score >= self.thresholds["overall"]
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return RAGEvaluationResult(
            answer_relevancy=llm_scores["answer_relevancy"],
            answer_relevancy_reasoning=llm_scores["answer_relevancy_reasoning"],
            context_relevancy=llm_scores["context_relevancy"],
            context_relevancy_reasoning=llm_scores["context_relevancy_reasoning"],
            completeness=llm_scores["completeness"],
            completeness_reasoning=llm_scores["completeness_reasoning"],
            safety=llm_scores["safety"],
            safety_reasoning=llm_scores["safety_reasoning"],
            faithfulness=hhem_scores["faithfulness"],
            hallucination_probability=hhem_scores["hallucination_probability"],
            is_faithful=hhem_scores["is_faithful"],
            overall_score=overall_score,
            pass_fail=pass_fail,
            evaluation_time_ms=elapsed_ms,
            evaluators_used=evaluators_used
        )

    async def quick_evaluate(
        self,
        query: str,
        answer: str,
        contexts: List[str]
    ) -> QuickEvaluationResult:
        """
        Quick evaluation focusing on faithfulness and answer relevancy.
        
        Faster than full evaluation, good for real-time feedback.
        
        Args:
            query: The user's question
            answer: The generated answer
            contexts: Retrieved context documents
            
        Returns:
            QuickEvaluationResult with key scores
        """
        start_time = time.time()
        
        # Run both in parallel
        tasks = []
        
        # LLM Judge - only answer relevancy
        if self.llm_judge and self.llm_judge.is_available():
            tasks.append(self.llm_judge.evaluate_answer_relevancy(query, answer))
        else:
            async def dummy_judge():
                return JudgeScore(
                    criteria="answer_relevancy",
                    score=0.5,
                    reasoning="LLM Judge not available",
                    confidence=0.0
                )
            tasks.append(dummy_judge())
        
        # HHEM - faithfulness
        async def run_hhem():
            if self.hhem_service and self.hhem_service.is_available():
                combined_context = "\n\n".join(contexts[:3])
                return self.hhem_service.evaluate_faithfulness(answer, combined_context)
            return FaithfulnessResult(0.5, 0.5, False, 0.0)
        
        tasks.append(run_hhem())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Parse results
        answer_relevancy = 0.5
        faithfulness = 0.5
        
        if not isinstance(results[0], Exception):
            answer_relevancy = results[0].score
        
        if not isinstance(results[1], Exception):
            faithfulness = results[1].faithfulness_score
        
        # Quick overall score (equal weight)
        overall_score = (answer_relevancy + faithfulness) / 2
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        return QuickEvaluationResult(
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            overall_score=overall_score,
            pass_fail=overall_score >= 0.6,
            evaluation_time_ms=elapsed_ms
        )

    def evaluate_faithfulness_only(
        self,
        answer: str,
        context: str
    ) -> FaithfulnessResult:
        """
        Evaluate faithfulness only using HHEM.
        
        Synchronous method for quick hallucination checks.
        
        Args:
            answer: The generated answer
            context: The source context
            
        Returns:
            FaithfulnessResult from HHEM
        """
        if not self.hhem_service or not self.hhem_service.is_available():
            return FaithfulnessResult(0.5, 0.5, False, 0.0)
        
        return self.hhem_service.evaluate_faithfulness(answer, context)

    def to_dict(self, result: RAGEvaluationResult) -> Dict[str, Any]:
        """Convert evaluation result to dictionary"""
        return asdict(result)

    def to_metrics_dict(self, result: RAGEvaluationResult) -> Dict[str, float]:
        """Get just the numeric metrics as a dictionary"""
        return {
            "answer_relevancy": result.answer_relevancy,
            "context_relevancy": result.context_relevancy,
            "completeness": result.completeness,
            "safety": result.safety,
            "faithfulness": result.faithfulness,
            "hallucination_probability": result.hallucination_probability,
            "overall_score": result.overall_score
        }


# Global instance with lazy initialization
_evaluator: Optional[AdvancedRAGEvaluator] = None


def get_advanced_evaluator() -> AdvancedRAGEvaluator:
    """Get or create AdvancedRAGEvaluator instance"""
    global _evaluator
    if _evaluator is None:
        _evaluator = AdvancedRAGEvaluator()
    return _evaluator


# Convenience function for quick evaluation
async def evaluate_rag_response(
    query: str,
    answer: str,
    contexts: List[str],
    quick: bool = False
) -> Dict[str, Any]:
    """
    Convenience function for evaluating RAG responses.
    
    Args:
        query: The user's question
        answer: The generated answer
        contexts: Retrieved context documents
        quick: If True, use quick evaluation (faster)
        
    Returns:
        Dictionary with evaluation results
    """
    evaluator = get_advanced_evaluator()
    
    if quick:
        result = await evaluator.quick_evaluate(query, answer, contexts)
        return {
            "faithfulness": result.faithfulness,
            "answer_relevancy": result.answer_relevancy,
            "overall_score": result.overall_score,
            "pass_fail": result.pass_fail,
            "evaluation_time_ms": result.evaluation_time_ms
        }
    else:
        result = await evaluator.evaluate(query, answer, contexts)
        return evaluator.to_dict(result)
