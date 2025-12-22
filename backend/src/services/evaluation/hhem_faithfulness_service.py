"""
HHEM Faithfulness Service

Uses Vectara's Hughes Hallucination Evaluation Model (HHEM) for specialized
hallucination/faithfulness detection in RAG systems.

IMPORTANT: HHEM must be used via sentence_transformers.CrossEncoder with the
hhem-1.0-open revision. HHEM 2.1 has breaking changes with AutoTokenizer that
prevent direct loading. The CrossEncoder handles correct tokenization internally.

References:
- https://github.com/vectara/example-notebooks/blob/main/notebooks/using-hhem-with-RAG.ipynb
- https://huggingface.co/vectara/hallucination_evaluation_model/discussions/14
"""

import logging
from dataclasses import dataclass
from typing import List, Tuple, Optional
import time
import sys

logger = logging.getLogger(__name__)

# Lazy load objects
_hhem_model = None
_model_loaded = False


def _get_hhem_model():
    """Lazy load the HHEM model using CrossEncoder (official method)"""
    global _hhem_model, _model_loaded

    if _model_loaded:
        return _hhem_model

    try:
        from sentence_transformers import CrossEncoder

        logger.info("Loading Vectara HHEM model via CrossEncoder...")

        model_name = 'vectara/hallucination_evaluation_model'
        # HHEM 2.1 has breaking changes with AutoTokenizer
        # Use hhem-1.0-open revision for CrossEncoder compatibility
        revision = "hhem-1.0-open"

        _hhem_model = CrossEncoder(model_name, revision=revision)

        _model_loaded = True
        logger.info("HHEM CrossEncoder model loaded successfully")

    except ImportError as e:
        logger.error(f"sentence_transformers not installed: {e}")
        logger.error("Install with: pip install sentence-transformers")
        _hhem_model = None
        _model_loaded = True

    except Exception as e:
        logger.error(f"Failed to load HHEM model: {e}")
        _hhem_model = None
        _model_loaded = True

    return _hhem_model


@dataclass
class FaithfulnessResult:
    """Result from faithfulness evaluation"""
    faithfulness_score: float  # 0.0 to 1.0 (higher = more faithful)
    hallucination_probability: float  # 0.0 to 1.0 (higher = more likely hallucinated)
    is_faithful: bool  # True if faithfulness_score >= threshold
    evaluation_time_ms: float


class HHEMFaithfulnessService:
    """
    Vectara HHEM (Hughes Hallucination Evaluation Model) Service

    Uses CrossEncoder for proper tokenization and inference.
    Input format: [(premise/context, hypothesis/answer), ...]
    Output: Scores from 0 to 1, where 1 = factually consistent, 0 = hallucinated
    """

    def __init__(self, threshold: float = 0.5, device: str = "cpu"):
        self.threshold = threshold
        self.device = device
        self._model = None

    def _get_model(self):
        if self._model is None:
            self._model = _get_hhem_model()
        return self._model

    def is_available(self) -> bool:
        return self._get_model() is not None

    def _predict(self, pairs: list) -> list:
        """
        Run inference using CrossEncoder.

        Args:
            pairs: List of (context, answer) tuples

        Returns:
            List of scores from 0-1 (1 = factually consistent)
        """
        model = self._get_model()
        if model is None:
            return [0.5] * len(pairs)

        try:
            # CrossEncoder.predict() expects list of [text_a, text_b] pairs
            # Format: [premise/context, hypothesis/answer]
            scores = model.predict(pairs)

            # Handle both single value and array returns
            if hasattr(scores, '__iter__') and not isinstance(scores, str):
                return [float(s) for s in scores]
            else:
                return [float(scores)]

        except Exception as e:
            logger.error(f"HHEM predict failed: {e}")
            return [0.5] * len(pairs)


    def evaluate_faithfulness(
        self, 
        answer: str, 
        context: str
    ) -> FaithfulnessResult:
        """Evaluate faithfulness"""
        start_time = time.time()
        
        try:
            # HHEM expects (context, answer) pairs
            scores = self._predict([(context, answer)])
            score = float(scores[0])
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            return FaithfulnessResult(
                faithfulness_score=score,
                hallucination_probability=1.0 - score,
                is_faithful=score >= self.threshold,
                evaluation_time_ms=elapsed_ms
            )
            
        except Exception as e:
            logger.error(f"HHEM evaluation failed: {e}")
            print(f"DEBUG: Eval error: {e}")
            return FaithfulnessResult(0.5, 0.5, False, 0.0)

    def evaluate_with_multiple_contexts(self, answer: str, contexts: List[str]) -> FaithfulnessResult:
        if not contexts: return FaithfulnessResult(0.0, 1.0, False, 0.0)
        try:
            pairs = [(ctx, answer) for ctx in contexts]
            scores = self._predict(pairs)
            max_score = float(max(scores))
            return FaithfulnessResult(max_score, 1.0-max_score, max_score>=self.threshold, 0.0)
        except: return FaithfulnessResult(0.5, 0.5, False, 0.0)

    def batch_evaluate(self, pairs: List[Tuple[str, str]]) -> List[FaithfulnessResult]:
        if not pairs: return []
        try:
            hhem_pairs = [(ctx, ans) for ans, ctx in pairs]
            scores = self._predict(hhem_pairs)
            return [FaithfulnessResult(s, 1.0-s, s>=self.threshold, 0.0) for s in scores]
        except: return [FaithfulnessResult(0.5, 0.5, False, 0.0) for _ in pairs]

    def get_hallucination_probability(self, answer: str, context: str) -> float:
        return self.evaluate_faithfulness(answer, context).hallucination_probability


# Global instance
_hhem_service: Optional[HHEMFaithfulnessService] = None

def get_hhem_service() -> HHEMFaithfulnessService:
    global _hhem_service
    if _hhem_service is None:
        _hhem_service = HHEMFaithfulnessService()
    return _hhem_service
