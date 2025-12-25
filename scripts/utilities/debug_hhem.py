"""
HHEM Debug Script - Using CrossEncoder (Official Method)

Reference: https://github.com/vectara/example-notebooks/blob/main/notebooks/using-hhem-with-RAG.ipynb
"""

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def debug_hhem():
    print("Testing HHEM via CrossEncoder (Official Method)...")

    try:
        from sentence_transformers import CrossEncoder
    except ImportError:
        print("ERROR: sentence-transformers not installed")
        print("Install with: pip install sentence-transformers")
        return

    model_name = 'vectara/hallucination_evaluation_model'
    # HHEM 2.1 has breaking changes - use hhem-1.0-open revision for CrossEncoder compatibility
    revision = "hhem-1.0-open"

    print(f"Loading model: {model_name} (revision: {revision})")
    model = CrossEncoder(model_name, revision=revision)
    print("Model loaded successfully!")

    # Test cases: (context/premise, answer/hypothesis)
    test_cases = [
        # Should be CONSISTENT (high score ~1.0)
        (
            "The capital of France is Paris.",
            "Paris is the capital of France."
        ),
        # Should be HALLUCINATED (low score ~0.0)
        (
            "The capital of France is Paris.",
            "Berlin is the capital of France."
        ),
        # Should be CONSISTENT
        (
            "Machine learning is a subset of artificial intelligence.",
            "AI includes machine learning as one of its subfields."
        ),
        # Should be HALLUCINATED (information not in context)
        (
            "The Eiffel Tower is in Paris.",
            "The Eiffel Tower was built in 1950."
        ),
    ]

    print("\n" + "=" * 60)
    print("HHEM Score Interpretation:")
    print("  Score ~1.0 = Factually CONSISTENT with context")
    print("  Score ~0.0 = HALLUCINATED / not supported by context")
    print("=" * 60)

    for i, (context, answer) in enumerate(test_cases, 1):
        # CrossEncoder expects pairs as [[text_a, text_b]]
        score = model.predict([(context, answer)])[0]

        print(f"\n--- Test {i} ---")
        print(f"Context: {context}")
        print(f"Answer:  {answer}")
        print(f"Score:   {score:.4f}")

        if score >= 0.5:
            print("Result:  ✓ CONSISTENT")
        else:
            print("Result:  ✗ HALLUCINATED")


if __name__ == "__main__":
    debug_hhem()
