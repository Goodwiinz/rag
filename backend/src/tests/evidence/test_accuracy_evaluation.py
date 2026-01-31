"""
Accuracy evaluation tests for stance classification

Creates test fixtures for evaluating model accuracy against human labels (SC-001)
"""

import json
import pytest
from pathlib import Path
from uuid import uuid4
from typing import List, Dict

from src.services.evidence.stance_classifier import StanceClassifier
from src.services.evidence.cache import EvidenceCacheService


# Sample test data (in production this would be loaded from a larger dataset)
SAMPLE_TEST_CASES = [
    {
        "claim": "Vitamin D supplementation reduces COVID-19 severity",
        "source_excerpt": "Our meta-analysis of 15 studies found that vitamin D supplementation significantly reduced ICU admission rates (RR=0.64, 95% CI: 0.49-0.84, p<0.001) and mortality (RR=0.51, 95% CI: 0.37-0.70, p<0.001) in COVID-19 patients.",
        "human_label": "supporting",
        "confidence_threshold": 0.80
    },
    {
        "claim": "Vitamin D supplementation reduces COVID-19 severity", 
        "source_excerpt": "No significant association was found between vitamin D supplementation and COVID-19 outcomes in our randomized controlled trial of 500 participants (p=0.42 for hospitalization, p=0.38 for mortality).",
        "human_label": "opposing",
        "confidence_threshold": 0.75
    },
    {
        "claim": "Vitamin D supplementation reduces COVID-19 severity",
        "source_excerpt": "Vitamin D levels were measured in all participants at baseline using standardized assays. The mean baseline 25(OH)D level was 28.5 ng/mL in the treatment group.",
        "human_label": "not_addressed",
        "confidence_threshold": 0.70
    },
    {
        "claim": "Machine learning improves medical diagnosis accuracy",
        "source_excerpt": "The deep learning algorithm achieved 94% accuracy in diagnosing skin cancer from dermatoscopic images, compared to 87% accuracy by dermatologists in our validation study (p<0.001).",
        "human_label": "supporting", 
        "confidence_threshold": 0.85
    },
    {
        "claim": "Machine learning improves medical diagnosis accuracy",
        "source_excerpt": "While AI systems showed promise in controlled studies, implementation in real clinical settings revealed performance degradation, with accuracy dropping to 72% due to image quality and population differences.",
        "human_label": "neutral",
        "confidence_threshold": 0.70
    },
    {
        "claim": "Exercise prevents cognitive decline in aging",
        "source_excerpt": "Participants in the exercise intervention group showed significantly slower rates of cognitive decline over 24 months compared to sedentary controls (MMSE decline: 1.2 vs 2.8 points, p<0.01).",
        "human_label": "supporting",
        "confidence_threshold": 0.85
    },
    {
        "claim": "Exercise prevents cognitive decline in aging",
        "source_excerpt": "Our systematic review found mixed evidence, with 12 studies showing benefits and 8 studies showing no significant effect of exercise on cognitive function in older adults.",
        "human_label": "neutral",
        "confidence_threshold": 0.75
    },
    {
        "claim": "Social media use increases depression in teenagers",
        "source_excerpt": "Heavy social media use (>3 hours daily) was associated with a 70% increased risk of depression symptoms in our longitudinal cohort of 2,000 adolescents (OR=1.70, 95% CI: 1.25-2.31).",
        "human_label": "supporting",
        "confidence_threshold": 0.80
    },
    {
        "claim": "Social media use increases depression in teenagers", 
        "source_excerpt": "The relationship between social media and mental health is complex, with both positive and negative effects depending on usage patterns, content consumption, and individual factors.",
        "human_label": "neutral",
        "confidence_threshold": 0.65
    },
    {
        "claim": "Climate change is caused primarily by human activities",
        "source_excerpt": "Multiple lines of evidence conclusively demonstrate that recent global warming is primarily driven by human emissions of greenhouse gases, particularly CO2 from fossil fuel combustion.",
        "human_label": "supporting",
        "confidence_threshold": 0.90
    }
]


class AccuracyEvaluator:
    """Evaluates stance classification accuracy against human labels"""
    
    def __init__(self, stance_classifier: StanceClassifier):
        self.stance_classifier = stance_classifier
        
    async def evaluate_test_cases(self, test_cases: List[Dict]) -> Dict:
        """
        Evaluate model accuracy on test cases
        
        Args:
            test_cases: List of test cases with claim, excerpt, and human_label
            
        Returns:
            Evaluation metrics including overall accuracy
        """
        results = []
        correct_predictions = 0
        total_cases = len(test_cases)
        
        stance_confusion = {
            "supporting": {"supporting": 0, "opposing": 0, "neutral": 0, "not_addressed": 0},
            "opposing": {"supporting": 0, "opposing": 0, "neutral": 0, "not_addressed": 0},
            "neutral": {"supporting": 0, "opposing": 0, "neutral": 0, "not_addressed": 0},
            "not_addressed": {"supporting": 0, "opposing": 0, "neutral": 0, "not_addressed": 0}
        }
        
        for i, case in enumerate(test_cases):
            claim = case["claim"]
            excerpt = case["source_excerpt"] 
            human_label = case["human_label"]
            expected_confidence = case.get("confidence_threshold", 0.7)
            
            # Generate dummy data for testing
            claim_hash = f"test_claim_{i}"
            source_id = uuid4()
            
            # Classify with model
            try:
                result = await self.stance_classifier.classify_stance(
                    claim=claim,
                    claim_hash=claim_hash,
                    source_id=source_id,
                    source_excerpt=excerpt
                )
                
                if result:
                    predicted_stance = result["stance"]
                    confidence = result["confidence"]
                    
                    is_correct = predicted_stance == human_label
                    meets_confidence = confidence >= expected_confidence
                    
                    if is_correct:
                        correct_predictions += 1
                    
                    # Update confusion matrix
                    stance_confusion[human_label][predicted_stance] += 1
                    
                    results.append({
                        "case_id": i,
                        "claim": claim[:50] + "..." if len(claim) > 50 else claim,
                        "human_label": human_label,
                        "predicted_stance": predicted_stance,
                        "confidence": confidence,
                        "is_correct": is_correct,
                        "meets_confidence_threshold": meets_confidence
                    })
                else:
                    results.append({
                        "case_id": i,
                        "claim": claim[:50] + "..." if len(claim) > 50 else claim,
                        "human_label": human_label,
                        "predicted_stance": None,
                        "confidence": 0.0,
                        "is_correct": False,
                        "meets_confidence_threshold": False,
                        "error": "Classification failed"
                    })
                    
            except Exception as e:
                results.append({
                    "case_id": i,
                    "error": str(e),
                    "is_correct": False
                })
        
        # Calculate metrics
        overall_accuracy = correct_predictions / total_cases if total_cases > 0 else 0.0
        
        # Calculate per-stance metrics
        stance_metrics = {}
        for stance in stance_confusion.keys():
            true_positives = stance_confusion[stance][stance]
            total_predicted_as_stance = sum(stance_confusion[label][stance] for label in stance_confusion.keys())
            total_actual_stance = sum(stance_confusion[stance].values())
            
            precision = true_positives / total_predicted_as_stance if total_predicted_as_stance > 0 else 0.0
            recall = true_positives / total_actual_stance if total_actual_stance > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
            
            stance_metrics[stance] = {
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "support": total_actual_stance
            }
        
        return {
            "overall_accuracy": overall_accuracy,
            "total_cases": total_cases,
            "correct_predictions": correct_predictions,
            "stance_metrics": stance_metrics,
            "confusion_matrix": stance_confusion,
            "detailed_results": results,
            "passes_sc001": overall_accuracy >= 0.85  # SC-001 success criteria
        }


@pytest.fixture
def cache_service():
    """Cache service for testing"""
    return EvidenceCacheService()


@pytest.fixture 
def stance_classifier(cache_service):
    """Stance classifier for evaluation"""
    return StanceClassifier(cache_service)


@pytest.fixture
def accuracy_evaluator(stance_classifier):
    """Accuracy evaluator instance"""
    return AccuracyEvaluator(stance_classifier)


class TestAccuracyEvaluation:
    """Test accuracy evaluation functionality"""
    
    @pytest.mark.asyncio
    async def test_evaluate_sample_cases(self, accuracy_evaluator):
        """Test evaluation on sample cases (mock test)"""
        # Use a subset for quick testing
        sample_cases = SAMPLE_TEST_CASES[:3]
        
        # Mock the stance classifier to return predictable results
        with patch.object(accuracy_evaluator.stance_classifier, 'classify_stance') as mock_classify:
            mock_classify.side_effect = [
                {"stance": "supporting", "confidence": 0.85},
                {"stance": "opposing", "confidence": 0.80}, 
                {"stance": "not_addressed", "confidence": 0.75}
            ]
            
            results = await accuracy_evaluator.evaluate_test_cases(sample_cases)
            
            assert results["total_cases"] == 3
            assert results["correct_predictions"] == 3  # All correct with mocked data
            assert results["overall_accuracy"] == 1.0
            assert results["passes_sc001"] is True
    
    @pytest.mark.asyncio 
    async def test_evaluate_with_failures(self, accuracy_evaluator):
        """Test evaluation with some classification failures"""
        sample_cases = SAMPLE_TEST_CASES[:2]
        
        with patch.object(accuracy_evaluator.stance_classifier, 'classify_stance') as mock_classify:
            mock_classify.side_effect = [
                {"stance": "supporting", "confidence": 0.85},  # Correct
                None  # Failed classification
            ]
            
            results = await accuracy_evaluator.evaluate_test_cases(sample_cases)
            
            assert results["total_cases"] == 2
            assert results["correct_predictions"] == 1
            assert results["overall_accuracy"] == 0.5
            assert results["passes_sc001"] is False
    
    @pytest.mark.asyncio
    async def test_confusion_matrix_calculation(self, accuracy_evaluator):
        """Test confusion matrix calculation"""
        test_cases = [
            {"claim": "Test", "source_excerpt": "Test", "human_label": "supporting"},
            {"claim": "Test", "source_excerpt": "Test", "human_label": "supporting"}, 
            {"claim": "Test", "source_excerpt": "Test", "human_label": "opposing"}
        ]
        
        with patch.object(accuracy_evaluator.stance_classifier, 'classify_stance') as mock_classify:
            mock_classify.side_effect = [
                {"stance": "supporting", "confidence": 0.85},  # Correct
                {"stance": "neutral", "confidence": 0.75},     # Incorrect 
                {"stance": "opposing", "confidence": 0.80}     # Correct
            ]
            
            results = await accuracy_evaluator.evaluate_test_cases(test_cases)
            
            confusion = results["confusion_matrix"]
            assert confusion["supporting"]["supporting"] == 1
            assert confusion["supporting"]["neutral"] == 1
            assert confusion["opposing"]["opposing"] == 1
    
    def test_generate_test_fixture(self):
        """Test generation of test fixture file"""
        # This would generate the full 100 test cases for SC-001
        # For now, just verify the sample data structure
        
        for case in SAMPLE_TEST_CASES:
            assert "claim" in case
            assert "source_excerpt" in case
            assert "human_label" in case
            assert case["human_label"] in ["supporting", "opposing", "neutral", "not_addressed"]
            assert isinstance(case.get("confidence_threshold", 0.7), float)
    
    def test_save_evaluation_results(self, tmp_path):
        """Test saving evaluation results to file"""
        results = {
            "overall_accuracy": 0.87,
            "total_cases": 100,
            "passes_sc001": True,
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
        # Save results
        results_file = tmp_path / "evaluation_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Verify file was created and readable
        assert results_file.exists()
        with open(results_file, 'r') as f:
            loaded_results = json.load(f)
        
        assert loaded_results["overall_accuracy"] == 0.87
        assert loaded_results["passes_sc001"] is True


# Test runner for full evaluation
if __name__ == "__main__":
    import asyncio
    from unittest.mock import patch
    
    async def run_full_evaluation():
        """Run full accuracy evaluation"""
        cache_service = EvidenceCacheService()
        stance_classifier = StanceClassifier(cache_service)
        evaluator = AccuracyEvaluator(stance_classifier)
        
        print("Running accuracy evaluation on sample test cases...")
        results = await evaluator.evaluate_test_cases(SAMPLE_TEST_CASES)
        
        print(f"\nEvaluation Results:")
        print(f"Overall Accuracy: {results['overall_accuracy']:.2%}")
        print(f"Cases Evaluated: {results['total_cases']}")
        print(f"Correct Predictions: {results['correct_predictions']}")
        print(f"Passes SC-001 (≥85%): {results['passes_sc001']}")
        
        print(f"\nPer-Stance Metrics:")
        for stance, metrics in results['stance_metrics'].items():
            print(f"  {stance.title()}:")
            print(f"    Precision: {metrics['precision']:.2%}")
            print(f"    Recall: {metrics['recall']:.2%}")
            print(f"    F1-Score: {metrics['f1_score']:.2%}")
            print(f"    Support: {metrics['support']}")
    
    # Only run if executed directly (not during pytest)
    # asyncio.run(run_full_evaluation())