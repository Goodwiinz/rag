"""
Basic RAG evaluation without external dependencies

This uses simple heuristics instead of LLM-based evaluation.
Works immediately - no API keys or upgrades needed!

Usage:
    python evaluate_rag_basic.py
"""

import re
from typing import List, Dict

def calculate_overlap(text1: str, text2: str) -> float:
    """Calculate word overlap between two texts"""
    words1 = set(re.findall(r'\w+', text1.lower()))
    words2 = set(re.findall(r'\w+', text2.lower()))

    if not words1:
        return 0.0

    overlap = len(words1 & words2)
    return overlap / len(words1)

def evaluate_answer_relevancy(question: str, answer: str) -> Dict:
    """Check if answer addresses the question"""
    score = calculate_overlap(question, answer)

    return {
        "metric": "Answer Relevancy",
        "score": score,
        "passed": score >= 0.3,  # At least 30% word overlap
        "reason": f"Question-answer overlap: {score:.2%}"
    }

def evaluate_faithfulness(answer: str, contexts: List[str]) -> Dict:
    """Check if answer is grounded in context"""
    answer_words = set(re.findall(r'\w+', answer.lower()))
    context_words = set()

    for ctx in contexts:
        context_words.update(re.findall(r'\w+', ctx.lower()))

    if not answer_words:
        return {"metric": "Faithfulness", "score": 0.0, "passed": False, "reason": "Empty answer"}

    faithful_words = len(answer_words & context_words)
    score = faithful_words / len(answer_words)

    return {
        "metric": "Faithfulness",
        "score": score,
        "passed": score >= 0.7,  # 70% of answer words should be in context
        "reason": f"{faithful_words}/{len(answer_words)} answer words found in context"
    }

def evaluate_context_relevancy(question: str, contexts: List[str]) -> Dict:
    """Check if contexts are relevant to question"""
    if not contexts:
        return {"metric": "Context Relevancy", "score": 0.0, "passed": False, "reason": "No contexts"}

    scores = [calculate_overlap(question, ctx) for ctx in contexts]
    avg_score = sum(scores) / len(scores)

    return {
        "metric": "Context Relevancy",
        "score": avg_score,
        "passed": avg_score >= 0.3,
        "reason": f"Average context-question overlap: {avg_score:.2%}"
    }

def evaluate_answer_completeness(answer: str) -> Dict:
    """Check if answer is complete (not too short)"""
    word_count = len(re.findall(r'\w+', answer))
    score = min(word_count / 20.0, 1.0)  # 20+ words = complete

    return {
        "metric": "Answer Completeness",
        "score": score,
        "passed": word_count >= 10,
        "reason": f"Answer length: {word_count} words"
    }

def evaluate_rag_response(question: str, answer: str, contexts: List[str]) -> Dict:
    """Comprehensive evaluation"""
    results = {
        "question": question,
        "answer": answer,
        "contexts_count": len(contexts),
        "metrics": []
    }

    # Run all evaluations
    metrics = [
        evaluate_answer_relevancy(question, answer),
        evaluate_faithfulness(answer, contexts),
        evaluate_context_relevancy(question, contexts),
        evaluate_answer_completeness(answer)
    ]

    results["metrics"] = metrics
    results["all_passed"] = all(m["passed"] for m in metrics)
    results["average_score"] = sum(m["score"] for m in metrics) / len(metrics)

    return results

def print_results(results: Dict):
    """Pretty print results"""
    print("\n" + "="*80)
    print("RAG EVALUATION RESULTS")
    print("="*80)
    print(f"\nQuestion: {results['question']}")
    print(f"Answer: {results['answer']}")
    print(f"Contexts: {results['contexts_count']} documents")
    print("\nMetrics:")
    print("-"*80)

    for metric in results["metrics"]:
        status = "✅ PASS" if metric["passed"] else "❌ FAIL"
        print(f"{metric['metric']:25s} | Score: {metric['score']:.2f} | {status}")
        print(f"  └─ {metric['reason']}")

    print("-"*80)
    print(f"Average Score: {results['average_score']:.2f}")
    print(f"Overall: {'✅ ALL PASSED' if results['all_passed'] else '❌ SOME FAILED'}")
    print("="*80)

def main():
    """Run evaluation examples"""
    print("\n" + "="*80)
    print("BASIC RAG EVALUATION (No API Keys Required)")
    print("="*80)
    print("\nThis uses simple word-overlap heuristics.")
    print("Works immediately without DeepEval configuration!")

    # Example 1: Good response
    print("\n" + "="*80)
    print("EXAMPLE 1: High-Quality Response")
    print("="*80)
    result1 = evaluate_rag_response(
        question="What is machine learning?",
        answer="Machine learning is a subset of artificial intelligence that enables computers to learn from data without being explicitly programmed. It uses algorithms to identify patterns and make predictions.",
        contexts=[
            "Machine learning is a branch of artificial intelligence focused on building systems that learn from data.",
            "AI systems use machine learning algorithms to improve their performance over time without explicit programming.",
            "Machine learning enables computers to identify patterns in data and make predictions based on those patterns."
        ]
    )
    print_results(result1)

    # Example 2: Hallucination
    print("\n" + "="*80)
    print("EXAMPLE 2: Hallucination Detected")
    print("="*80)
    result2 = evaluate_rag_response(
        question="What is the capital of France?",
        answer="The capital of France is Lyon, which was founded by Julius Caesar in 50 BC and became the capital in the 12th century.",
        contexts=[
            "France is a country in Western Europe with a rich history.",
            "The country has many beautiful cities and a diverse culture."
        ]
    )
    print_results(result2)

    # Example 3: Irrelevant context
    print("\n" + "="*80)
    print("EXAMPLE 3: Irrelevant Context")
    print("="*80)
    result3 = evaluate_rag_response(
        question="How does photosynthesis work in plants?",
        answer="Photosynthesis is the process where plants convert sunlight into energy using chlorophyll in their leaves.",
        contexts=[
            "Agriculture has been practiced by humans for thousands of years across different civilizations.",
            "Farmers use various tools and equipment for planting and harvesting crops.",
            "The history of farming dates back to ancient times."
        ]
    )
    print_results(result3)

    # Example 4: Short incomplete answer
    print("\n" + "="*80)
    print("EXAMPLE 4: Incomplete Answer")
    print("="*80)
    result4 = evaluate_rag_response(
        question="Explain the process of photosynthesis in detail",
        answer="Plants make energy.",
        contexts=[
            "Photosynthesis is the process by which plants convert sunlight, carbon dioxide, and water into glucose and oxygen using chlorophyll.",
            "The process occurs in the chloroplasts of plant cells and involves light-dependent and light-independent reactions."
        ]
    )
    print_results(result4)

    # Example 5: Perfect response
    print("\n" + "="*80)
    print("EXAMPLE 5: Near-Perfect Response")
    print("="*80)
    result5 = evaluate_rag_response(
        question="What are the benefits of regular exercise?",
        answer="Regular exercise provides numerous health benefits including improved cardiovascular health, stronger muscles and bones, better mood through endorphin release, improved sleep quality, and helps maintain a healthy weight through increased metabolism.",
        contexts=[
            "Regular exercise has many health benefits including improved heart health and cardiovascular function.",
            "Physical activity strengthens muscles and bones, reducing the risk of osteoporosis and injury.",
            "Exercise releases endorphins which improve mood and reduce stress and anxiety.",
            "Regular physical activity helps maintain healthy weight by boosting metabolism and burning calories.",
            "Exercise improves sleep quality and helps people fall asleep faster and sleep more deeply."
        ]
    )
    print_results(result5)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("\n✅ All examples completed successfully!")
    print("\nThis basic evaluation uses word overlap heuristics:")
    print("• Answer Relevancy: Question words appearing in answer")
    print("• Faithfulness: Answer words appearing in context")
    print("• Context Relevancy: Question words appearing in context")
    print("• Answer Completeness: Sufficient answer length")
    print("\nLimitations:")
    print("• Doesn't understand semantics (synonyms, paraphrasing)")
    print("• Simple word matching (not deep understanding)")
    print("• Fixed thresholds may not fit all use cases")
    print("\nFor production use, consider:")
    print("• Upgrading to DeepEval v3+ for LLM-based evaluation")
    print("• Setting up OpenAI or local LLM for better accuracy")
    print("• Customizing thresholds for your specific domain")
    print("\nSee DEEPEVAL_SETUP.md for more advanced options.")

if __name__ == "__main__":
    main()
