"""
Simple DeepEval example for RAG evaluation

This demonstrates how to use DeepEval to evaluate your RAG system's quality.

Usage:
    python evaluate_rag_simple.py
"""

from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualRelevancyMetric
)

def example_1_answer_relevancy():
    """Example 1: Check if answer is relevant to the question"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Answer Relevancy")
    print("="*80)

    # Simulate a RAG query
    question = "What is machine learning?"
    answer = "Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed."

    # Create test case
    test_case = LLMTestCase(
        input=question,
        actual_output=answer
    )

    # Evaluate
    metric = AnswerRelevancyMetric(threshold=0.7)
    metric.measure(test_case)

    print(f"Question: {question}")
    print(f"Answer: {answer}")
    print(f"\nScore: {metric.score:.2f} (threshold: {metric.threshold})")
    print(f"Passed: {'✅' if metric.score >= metric.threshold else '❌'}")
    print(f"Reason: {metric.reason}")


def example_2_faithfulness():
    """Example 2: Check if answer is faithful to retrieved context (anti-hallucination)"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Faithfulness (Hallucination Detection)")
    print("="*80)

    question = "What is the capital of France?"

    # Good case - faithful to context
    context_good = ["Paris is the capital and largest city of France."]
    answer_good = "Paris is the capital of France."

    test_case_good = LLMTestCase(
        input=question,
        actual_output=answer_good,
        retrieval_context=context_good
    )

    metric = FaithfulnessMetric(threshold=0.7)
    metric.measure(test_case_good)

    print("GOOD CASE (Faithful):")
    print(f"Context: {context_good[0]}")
    print(f"Answer: {answer_good}")
    print(f"Score: {metric.score:.2f} - {'✅ Passed' if metric.score >= 0.7 else '❌ Failed'}")

    # Bad case - hallucination
    context_bad = ["France is a country in Western Europe."]
    answer_bad = "The capital of France is Lyon, founded in 50 BC by Julius Caesar."

    test_case_bad = LLMTestCase(
        input=question,
        actual_output=answer_bad,
        retrieval_context=context_bad
    )

    metric.measure(test_case_bad)

    print("\nBAD CASE (Hallucination):")
    print(f"Context: {context_bad[0]}")
    print(f"Answer: {answer_bad}")
    print(f"Score: {metric.score:.2f} - {'✅ Passed' if metric.score >= 0.7 else '❌ Failed (Made up facts!)'}")


def example_3_contextual_relevancy():
    """Example 3: Check if retrieved documents are relevant"""
    print("\n" + "="*80)
    print("EXAMPLE 3: Contextual Relevancy")
    print("="*80)

    question = "How does photosynthesis work?"

    # Good case - relevant context
    good_contexts = [
        "Photosynthesis is the process by which plants convert sunlight into energy.",
        "During photosynthesis, plants use chlorophyll to capture light energy.",
        "The process involves converting CO2 and water into glucose and oxygen."
    ]

    answer = "Photosynthesis is the process where plants convert sunlight, CO2, and water into glucose and oxygen using chlorophyll."

    test_case_good = LLMTestCase(
        input=question,
        actual_output=answer,
        retrieval_context=good_contexts
    )

    metric = ContextualRelevancyMetric(threshold=0.7)
    metric.measure(test_case_good)

    print("GOOD CASE (Relevant Context):")
    print(f"Question: {question}")
    print(f"Retrieved {len(good_contexts)} documents:")
    for i, ctx in enumerate(good_contexts, 1):
        print(f"  {i}. {ctx[:70]}...")
    print(f"\nScore: {metric.score:.2f} - {'✅ Passed' if metric.score >= 0.7 else '❌ Failed'}")

    # Bad case - irrelevant context
    bad_contexts = [
        "The history of agriculture spans thousands of years.",
        "Farmers use various tools for planting crops.",
        "Climate change affects growing seasons."
    ]

    test_case_bad = LLMTestCase(
        input=question,
        actual_output=answer,
        retrieval_context=bad_contexts
    )

    metric.measure(test_case_bad)

    print("\nBAD CASE (Irrelevant Context):")
    print(f"Question: {question}")
    print(f"Retrieved {len(bad_contexts)} documents:")
    for i, ctx in enumerate(bad_contexts, 1):
        print(f"  {i}. {ctx[:70]}...")
    print(f"\nScore: {metric.score:.2f} - {'✅ Passed' if metric.score >= 0.7 else '❌ Failed (Wrong documents!)'}")


def example_4_multiple_metrics():
    """Example 4: Evaluate multiple metrics at once"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Multiple Metrics Evaluation")
    print("="*80)

    question = "What are the benefits of exercise?"
    answer = "Exercise improves cardiovascular health, strengthens muscles, boosts mood, and helps maintain healthy weight."
    contexts = [
        "Regular exercise has numerous health benefits including improved heart health.",
        "Physical activity strengthens muscles and bones.",
        "Exercise releases endorphins which improve mood and reduce stress.",
        "Maintaining an active lifestyle helps with weight management."
    ]

    test_case = LLMTestCase(
        input=question,
        actual_output=answer,
        retrieval_context=contexts
    )

    # Define metrics
    metrics = {
        "Answer Relevancy": AnswerRelevancyMetric(threshold=0.7),
        "Faithfulness": FaithfulnessMetric(threshold=0.7),
        "Context Relevancy": ContextualRelevancyMetric(threshold=0.7)
    }

    print(f"Question: {question}")
    print(f"Answer: {answer}")
    print(f"Retrieved {len(contexts)} documents")
    print("\nEvaluation Results:")
    print("-" * 80)

    all_passed = True
    for name, metric in metrics.items():
        metric.measure(test_case)
        passed = metric.score >= metric.threshold
        all_passed = all_passed and passed

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:20s} | Score: {metric.score:.2f} | Threshold: {metric.threshold} | {status}")

    print("-" * 80)
    print(f"Overall: {'✅ ALL PASSED' if all_passed else '❌ SOME FAILED'}")


def main():
    """Run all examples"""
    print("\n" + "="*80)
    print("DeepEval RAG Evaluation Examples")
    print("="*80)
    print("\nThis demonstrates how to use DeepEval to evaluate your RAG system.")
    print("You can adapt these examples to evaluate your actual RAG queries.")

    try:
        example_1_answer_relevancy()
        example_2_faithfulness()
        example_3_contextual_relevancy()
        example_4_multiple_metrics()

        print("\n" + "="*80)
        print("✅ All examples completed!")
        print("="*80)
        print("\nNext steps:")
        print("1. Adapt these examples to your actual RAG system")
        print("2. Create test questions specific to your domain")
        print("3. Run regular evaluations to track quality over time")
        print("4. Set up monitoring for production queries")
        print("\nSee DEEPEVAL_GUIDE.md for more details.")

    except Exception as e:
        print(f"\n❌ Error running examples: {str(e)}")
        print("\nMake sure you have:")
        print("1. DeepEval installed: pip install deepeval")
        print("2. OpenAI API key set: export OPENAI_API_KEY=your-key")
        print("   (DeepEval uses OpenAI for evaluation by default)")


if __name__ == "__main__":
    main()
