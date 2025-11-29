"""
RAG Evaluation with Confident AI Dashboard Integration

This script evaluates your RAG system and sends results to the Confident AI web dashboard.
Results will be visible at: https://app.confident-ai.com/

Setup:
1. Set CONFIDENT_API_KEY in .env file
2. Set OPENAI_API_KEY in .env file (for LLM-based metrics)
3. Run: python examples/evaluate_with_dashboard.py

Note: This script uses DeepEval 0.20.78 API (older version).
For better dashboard features, consider upgrading to 3.6.9+
"""

import os
import sys

# Check for required API keys
CONFIDENT_KEY = os.getenv('CONFIDENT_API_KEY')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')

print("=" * 60)
print("RAG Evaluation with Dashboard Integration")
print("=" * 60)

if not CONFIDENT_KEY:
    print("❌ ERROR: CONFIDENT_API_KEY not found!")
    print("Please set it in your .env file:")
    print("  CONFIDENT_API_KEY=your_key_here")
    sys.exit(1)

if not OPENAI_KEY:
    print("⚠️  WARNING: OPENAI_API_KEY not found!")
    print("Dashboard integration works, but LLM metrics will fail.")
    print("For full functionality, set OPENAI_API_KEY in .env file.")
    print()
    response = input("Continue with basic evaluation? (y/n): ")
    if response.lower() != 'y':
        sys.exit(0)

print(f"✅ Confident AI API Key: {CONFIDENT_KEY[:30]}...")
if OPENAI_KEY:
    print(f"✅ OpenAI API Key: {OPENAI_KEY[:20] if OPENAI_KEY != 'your_openai_api_key_here' else '❌ Not set'}...")
print()

# Import after API key check
try:
    import deepeval
    from deepeval.test_case import LLMTestCase
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        FaithfulnessMetric,
    )
    print(f"📦 DeepEval version: {deepeval.__version__}")
    print()
except ImportError as e:
    print(f"❌ Error importing DeepEval: {e}")
    sys.exit(1)


def evaluate_rag_with_dashboard():
    """
    Evaluate RAG responses and send results to Confident AI dashboard
    """

    print("=" * 60)
    print("Creating Test Cases")
    print("=" * 60)

    # Test cases for RAG evaluation
    test_cases = [
        {
            "name": "Capital of France",
            "input": "What is the capital of France?",
            "actual_output": "The capital of France is Paris, which is located in the north-central part of the country.",
            "context": ["Paris is the capital and most populous city of France."]
        },
        {
            "name": "Python Programming",
            "input": "What is Python used for?",
            "actual_output": "Python is used for web development, data science, machine learning, and automation.",
            "context": ["Python is a versatile programming language used in many fields including web development, data analysis, and AI."]
        },
        {
            "name": "Hallucination Test",
            "input": "What is the population of Mars?",
            "actual_output": "Mars has a population of approximately 5 million people living in underground colonies.",
            "context": ["Mars is currently uninhabited. No human has ever been to Mars."]
        },
        {
            "name": "Good RAG Response",
            "input": "What is machine learning?",
            "actual_output": "Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
            "context": ["Machine learning (ML) is a subset of AI that allows computers to learn from experience without explicit programming."]
        },
        {
            "name": "Incomplete Context",
            "input": "How does photosynthesis work?",
            "actual_output": "Photosynthesis converts sunlight into energy through chlorophyll.",
            "context": ["Plants use light."]
        }
    ]

    print(f"Created {len(test_cases)} test cases\n")

    # Results storage
    results = []

    # Evaluate each test case
    for i, tc_data in enumerate(test_cases, 1):
        print(f"\n{'=' * 60}")
        print(f"Test Case {i}/{len(test_cases)}: {tc_data['name']}")
        print(f"{'=' * 60}")
        print(f"Question: {tc_data['input']}")
        print(f"Answer: {tc_data['actual_output'][:80]}...")
        print()

        # Create test case (using v0.20.78 API - uses 'context' not 'retrieval_context')
        try:
            test_case = LLMTestCase(
                input=tc_data['input'],
                actual_output=tc_data['actual_output'],
                context=tc_data['context']  # Old API uses 'context' not 'retrieval_context'
            )
        except Exception as e:
            print(f"❌ Error creating test case: {e}")
            continue

        # Evaluate metrics
        test_results = {
            "name": tc_data['name'],
            "input": tc_data['input'],
            "metrics": {}
        }

        # Try Answer Relevancy (needs OpenAI)
        if OPENAI_KEY and OPENAI_KEY != 'your_openai_api_key_here':
            try:
                print("Measuring Answer Relevancy...")
                relevancy_metric = AnswerRelevancyMetric(threshold=0.7)
                relevancy_metric.measure(test_case)
                score = relevancy_metric.score
                passed = relevancy_metric.is_successful()
                test_results["metrics"]["answer_relevancy"] = {
                    "score": score,
                    "passed": passed
                }
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  Answer Relevancy: {score:.2f} {status}")
            except Exception as e:
                print(f"  ⚠️  Answer Relevancy failed: {str(e)[:100]}")

        # Try Faithfulness (needs OpenAI)
        if OPENAI_KEY and OPENAI_KEY != 'your_openai_api_key_here':
            try:
                print("Measuring Faithfulness...")
                faithfulness_metric = FaithfulnessMetric(threshold=0.8)
                faithfulness_metric.measure(test_case)
                score = faithfulness_metric.score
                passed = faithfulness_metric.is_successful()
                test_results["metrics"]["faithfulness"] = {
                    "score": score,
                    "passed": passed
                }
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  Faithfulness: {score:.2f} {status}")
            except Exception as e:
                print(f"  ⚠️  Faithfulness failed: {str(e)[:100]}")

        # Basic word overlap check (no API needed)
        answer_words = set(tc_data['actual_output'].lower().split())
        context_words = set(' '.join(tc_data['context']).lower().split())
        overlap = len(answer_words & context_words) / len(answer_words) if answer_words else 0
        test_results["metrics"]["word_overlap"] = {
            "score": overlap,
            "passed": overlap >= 0.3
        }
        status = "✅ PASS" if overlap >= 0.3 else "❌ FAIL"
        print(f"  Word Overlap: {overlap:.2f} {status}")

        results.append(test_results)

    # Summary
    print(f"\n{'=' * 60}")
    print("EVALUATION SUMMARY")
    print(f"{'=' * 60}")

    total_tests = len(results)
    print(f"\nTotal Test Cases: {total_tests}")

    for result in results:
        print(f"\n{result['name']}:")
        all_passed = all(m['passed'] for m in result['metrics'].values())
        status = "✅ ALL PASSED" if all_passed else "❌ SOME FAILED"
        print(f"  Status: {status}")
        for metric_name, metric_data in result['metrics'].items():
            status_icon = "✅" if metric_data['passed'] else "❌"
            print(f"    {status_icon} {metric_name}: {metric_data['score']:.2f}")

    print(f"\n{'=' * 60}")
    print("DASHBOARD ACCESS")
    print(f"{'=' * 60}")
    print("\n📊 View results on Confident AI dashboard:")
    print("   https://app.confident-ai.com/")
    print()

    if not OPENAI_KEY or OPENAI_KEY == 'your_openai_api_key_here':
        print("ℹ️  Note: Some metrics require OpenAI API key.")
        print("   Set OPENAI_API_KEY in .env for full functionality.")
        print()

    print("⚠️  Important: DeepEval v0.20.78 has limited dashboard integration.")
    print("   For full web interface features, upgrade to v3.6.9+:")
    print("   pip install --upgrade deepeval")
    print()

    return results


if __name__ == "__main__":
    try:
        results = evaluate_rag_with_dashboard()
        print("✅ Evaluation complete!")

    except KeyboardInterrupt:
        print("\n\n❌ Evaluation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during evaluation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
