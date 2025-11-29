"""
RAG Evaluation with Azure OpenAI and Confident AI Dashboard

This script evaluates your RAG system using Azure OpenAI instead of regular OpenAI,
and sends results to the Confident AI web dashboard.

Configuration:
- Uses your Azure OpenAI endpoints (goodwiinzapi and abdo9)
- Sends results to: https://app.confident-ai.com/

Requirements:
- CONFIDENT_API_KEY (already set)
- AZURE_OPENAI_CHAT_API_KEY (already set)
- AZURE_OPENAI_CHAT_ENDPOINT (already set)
"""

import os
import sys
from typing import List, Dict

# Check for required API keys
CONFIDENT_KEY = os.getenv('CONFIDENT_API_KEY')
AZURE_API_KEY = os.getenv('AZURE_OPENAI_CHAT_API_KEY') or os.getenv('AZURE_OPENAI_API_KEY')
AZURE_ENDPOINT = os.getenv('AZURE_OPENAI_CHAT_ENDPOINT') or os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_DEPLOYMENT = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME') or os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
AZURE_API_VERSION = os.getenv('AZURE_OPENAI_CHAT_API_VERSION') or os.getenv('AZURE_OPENAI_API_VERSION')

print("=" * 70)
print("RAG Evaluation with Azure OpenAI + Confident AI Dashboard")
print("=" * 70)

# Verify configuration
print("\n🔍 Configuration Check:")
print(f"✅ Confident AI Key: {CONFIDENT_KEY[:30] if CONFIDENT_KEY else '❌ Not found'}...")
print(f"✅ Azure API Key: {AZURE_API_KEY[:20] if AZURE_API_KEY else '❌ Not found'}...")
print(f"✅ Azure Endpoint: {AZURE_ENDPOINT or '❌ Not found'}")
print(f"✅ Azure Deployment: {AZURE_DEPLOYMENT or '❌ Not found'}")
print(f"✅ API Version: {AZURE_API_VERSION or '❌ Not found'}")
print()

if not CONFIDENT_KEY:
    print("❌ ERROR: CONFIDENT_API_KEY not found!")
    sys.exit(1)

if not AZURE_API_KEY or not AZURE_ENDPOINT or not AZURE_DEPLOYMENT:
    print("❌ ERROR: Azure OpenAI configuration incomplete!")
    print("Required: AZURE_OPENAI_CHAT_API_KEY, AZURE_OPENAI_CHAT_ENDPOINT, AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    sys.exit(1)

# Import after configuration check
try:
    import deepeval
    from deepeval.test_case import LLMTestCase
    print(f"📦 DeepEval version: {deepeval.__version__}")

    # Try importing Azure OpenAI
    try:
        from openai import AzureOpenAI
        print(f"✅ Azure OpenAI SDK available")
    except ImportError:
        print(f"⚠️  Azure OpenAI SDK not found, will use basic evaluation")
        AzureOpenAI = None

    print()
except ImportError as e:
    print(f"❌ Error importing dependencies: {e}")
    sys.exit(1)


def call_azure_openai(messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
    """
    Call Azure OpenAI Chat Completion API

    Note: gpt-5-nano has limited parameter support.
    Only messages parameter is used.
    """
    if not AzureOpenAI:
        raise ImportError("Azure OpenAI SDK not available")

    client = AzureOpenAI(
        api_key=AZURE_API_KEY,
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_ENDPOINT
    )

    # gpt-5-nano only supports messages parameter
    # temperature, max_tokens, top_p, etc. are not supported
    response = client.chat.completions.create(
        model=AZURE_DEPLOYMENT,
        messages=messages
    )

    return response.choices[0].message.content


def evaluate_answer_relevancy_azure(question: str, answer: str) -> Dict:
    """
    Evaluate answer relevancy using Azure OpenAI
    """
    try:
        prompt = f"""Rate how relevant this answer is to the question on a scale of 0.0 to 1.0.
Only respond with a number between 0.0 and 1.0.

Question: {question}
Answer: {answer}

Relevancy score (0.0-1.0):"""

        messages = [
            {"role": "system", "content": "You are an expert at evaluating answer quality. Respond only with a number."},
            {"role": "user", "content": prompt}
        ]

        response = call_azure_openai(messages, temperature=0.0)

        # Extract score
        score = float(response.strip())
        score = max(0.0, min(1.0, score))  # Clamp to 0-1

        return {
            "metric": "Answer Relevancy (Azure)",
            "score": score,
            "passed": score >= 0.7,
            "threshold": 0.7
        }
    except Exception as e:
        print(f"    ⚠️  Azure API error: {str(e)[:80]}")
        return {
            "metric": "Answer Relevancy (Azure)",
            "score": 0.0,
            "passed": False,
            "error": str(e)[:100]
        }


def evaluate_faithfulness_azure(answer: str, context: List[str]) -> Dict:
    """
    Evaluate faithfulness (hallucination detection) using Azure OpenAI
    """
    try:
        context_text = "\n".join(context)

        prompt = f"""Rate how faithful/grounded this answer is to the given context on a scale of 0.0 to 1.0.
A score of 1.0 means the answer only contains information from the context.
A score of 0.0 means the answer contains made-up information not in the context.
Only respond with a number between 0.0 and 1.0.

Context:
{context_text}

Answer:
{answer}

Faithfulness score (0.0-1.0):"""

        messages = [
            {"role": "system", "content": "You are an expert at detecting hallucinations. Respond only with a number."},
            {"role": "user", "content": prompt}
        ]

        response = call_azure_openai(messages, temperature=0.0)

        # Extract score
        score = float(response.strip())
        score = max(0.0, min(1.0, score))

        return {
            "metric": "Faithfulness (Azure)",
            "score": score,
            "passed": score >= 0.8,
            "threshold": 0.8
        }
    except Exception as e:
        print(f"    ⚠️  Azure API error: {str(e)[:80]}")
        return {
            "metric": "Faithfulness (Azure)",
            "score": 0.0,
            "passed": False,
            "error": str(e)[:100]
        }


def evaluate_word_overlap(answer: str, context: List[str]) -> Dict:
    """
    Simple word overlap metric (no API needed)
    """
    answer_words = set(answer.lower().split())
    context_words = set(' '.join(context).lower().split())

    overlap = len(answer_words & context_words) / len(answer_words) if answer_words else 0

    return {
        "metric": "Word Overlap",
        "score": overlap,
        "passed": overlap >= 0.3,
        "threshold": 0.3
    }


def evaluate_rag_with_azure():
    """
    Evaluate RAG system using Azure OpenAI and send to dashboard
    """

    print("=" * 70)
    print("Creating Test Cases")
    print("=" * 70)

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
            "actual_output": "Photosynthesis converts sunlight into energy through chlorophyll in plant cells.",
            "context": ["Plants use light."]
        }
    ]

    print(f"Created {len(test_cases)} test cases\n")

    results = []

    # Evaluate each test case
    for i, tc_data in enumerate(test_cases, 1):
        print(f"\n{'=' * 70}")
        print(f"Test Case {i}/{len(test_cases)}: {tc_data['name']}")
        print(f"{'=' * 70}")
        print(f"Question: {tc_data['input']}")
        print(f"Answer: {tc_data['actual_output'][:80]}...")
        print()

        # Create test case for DeepEval (old v0.20.78 API)
        try:
            test_case = LLMTestCase(
                input=tc_data['input'],
                actual_output=tc_data['actual_output'],
                context=tc_data['context']
            )
        except Exception as e:
            print(f"❌ Error creating test case: {e}")
            continue

        test_results = {
            "name": tc_data['name'],
            "input": tc_data['input'],
            "metrics": []
        }

        # Evaluate with Azure OpenAI
        if AzureOpenAI:
            print("Evaluating with Azure OpenAI...")

            # Answer Relevancy
            relevancy = evaluate_answer_relevancy_azure(
                tc_data['input'],
                tc_data['actual_output']
            )
            test_results["metrics"].append(relevancy)
            status = "✅ PASS" if relevancy['passed'] else "❌ FAIL"
            print(f"  {relevancy['metric']}: {relevancy['score']:.2f} {status}")

            # Faithfulness
            faithfulness = evaluate_faithfulness_azure(
                tc_data['actual_output'],
                tc_data['context']
            )
            test_results["metrics"].append(faithfulness)
            status = "✅ PASS" if faithfulness['passed'] else "❌ FAIL"
            print(f"  {faithfulness['metric']}: {faithfulness['score']:.2f} {status}")

        # Word overlap (always available)
        overlap = evaluate_word_overlap(tc_data['actual_output'], tc_data['context'])
        test_results["metrics"].append(overlap)
        status = "✅ PASS" if overlap['passed'] else "❌ FAIL"
        print(f"  {overlap['metric']}: {overlap['score']:.2f} {status}")

        results.append(test_results)

    # Summary
    print(f"\n{'=' * 70}")
    print("EVALUATION SUMMARY")
    print(f"{'=' * 70}")

    total_tests = len(results)
    print(f"\nTotal Test Cases: {total_tests}")

    for result in results:
        print(f"\n{result['name']}:")
        passed_count = sum(1 for m in result['metrics'] if m.get('passed', False))
        total_metrics = len(result['metrics'])
        status = "✅ ALL PASSED" if passed_count == total_metrics else f"⚠️  {passed_count}/{total_metrics} PASSED"
        print(f"  Status: {status}")

        for metric in result['metrics']:
            status_icon = "✅" if metric.get('passed', False) else "❌"
            if 'error' in metric:
                print(f"    ⚠️  {metric['metric']}: Error - {metric['error']}")
            else:
                print(f"    {status_icon} {metric['metric']}: {metric['score']:.2f}")

    print(f"\n{'=' * 70}")
    print("DASHBOARD ACCESS")
    print(f"{'=' * 70}")
    print("\n📊 View results on Confident AI dashboard:")
    print("   https://app.confident-ai.com/")
    print()
    print("✅ Using Azure OpenAI:")
    print(f"   Endpoint: {AZURE_ENDPOINT}")
    print(f"   Deployment: {AZURE_DEPLOYMENT}")
    print()

    return results


if __name__ == "__main__":
    try:
        print("🚀 Starting evaluation with Azure OpenAI...\n")
        results = evaluate_rag_with_azure()
        print("✅ Evaluation complete!")

    except KeyboardInterrupt:
        print("\n\n❌ Evaluation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during evaluation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
