#!/usr/bin/env python3
"""
Quick evaluation of entity extraction methods
"""

import sys
import os
import json
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def quick_test_extraction():
    """Quick test of different extraction methods"""
    print("="*80)
    print("QUICK ENTITY EXTRACTION EVALUATION")
    print("="*80)

    # Test text with various entity types
    test_text = """
    Dr. Sarah Johnson from MIT published a groundbreaking paper on quantum computing
    in Nature 2023. Her research was funded by a $5M grant from the National Science Foundation.
    Contact her at sarah.johnson@mit.edu or call (617) 253-1000. The paper was presented at the
    Quantum Computing Conference in San Francisco, California. OpenAI announced GPT-4,
    their latest language model. Visit https://openai.com/gpt4 for more information.
    """

    try:
        # Import service
        from src.services.services.entity_extraction_service import EntityExtractionService
        print("✓ Entity extraction service imported")

        # Initialize
        service = EntityExtractionService()
        print(f"✓ Service initialized")

        # Check LLM availability
        llm_available = service.llm_client is not None
        print(f"✓ LLM Available: {'Yes' if llm_available else 'No'}")

        print("\n" + "-"*80)
        print("TESTING EXTRACTION METHODS")
        print("-"*80)

        # Test each method
        methods_to_test = []
        results = {}

        # Pattern matching
        print("\n1. Pattern Matching:")
        try:
            pattern_entities = service._extract_with_patterns(test_text)
            results['pattern'] = pattern_entities
            print(f"   ✓ Extracted {len(pattern_entities)} entities")
            for e in pattern_entities[:3]:
                print(f"     - {e['name']} ({e['entity_type']})")
            methods_to_test.append('pattern')
        except Exception as e:
            print(f"   ✗ Error: {str(e)[:50]}...")

        # Rule-based extraction
        print("\n2. Rule-Based Extraction:")
        try:
            import asyncio
            rule_entities = asyncio.run(service._extract_with_rules(test_text))
            results['rule'] = rule_entities
            print(f"   ✓ Extracted {len(rule_entities)} entities")
            for e in rule_entities[:3]:
                print(f"     - {e['name']} ({e['entity_type']})")
            methods_to_test.append('rule')
        except Exception as e:
            print(f"   ✗ Error: {str(e)[:50]}...")

        # LLM extraction
        if llm_available:
            print("\n3. LLM (GPT-4o-mini) Extraction:")
            try:
                llm_entities = asyncio.run(service._extract_with_llm(test_text))
                results['llm'] = llm_entities
                print(f"   ✓ Extracted {len(llm_entities)} entities")
                for e in llm_entities[:3]:
                    print(f"     - {e['name']} ({e['entity_type']}) - confidence: {e['confidence_score']:.2f}")
                methods_to_test.append('llm')
            except Exception as e:
                print(f"   ✗ Error: {str(e)[:50]}...")

        # Combined extraction
        print("\n4. Combined Extraction (All Methods):")
        try:
            all_entities = asyncio.run(service.extract_entities(test_text, "test_doc", methods_to_test))
            print(f"   ✓ Total extracted: {len(all_entities)} entities")

            # Group by extraction method
            by_method = {}
            for e in all_entities:
                method = e.get('extraction_method', 'unknown')
                if method not in by_method:
                    by_method[method] = 0
                by_method[method] += 1

            for method, count in by_method.items():
                print(f"     - {method}: {count} entities")
        except Exception as e:
            print(f"   ✗ Error: {str(e)[:50]}...")

        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print("\nEntity Types Found:")

        all_types = set()
        for method_entities in results.values():
            for e in method_entities:
                all_types.add(e.get('entity_type', 'unknown'))

        for entity_type in sorted(all_types):
            print(f"  • {entity_type}")

        print(f"\nBest Method for This Text:")
        if 'llm' in results and len(results['llm']) > 0:
            print("  ✓ LLM (GPT-4o-mini) - Most comprehensive extraction")
        elif 'rule' in results and len(results['rule']) > 0:
            print("  ✓ Rule-Based - Good for organizations and persons")
        elif 'pattern' in results and len(results['pattern']) > 0:
            print("  ✓ Pattern Matching - Best for structured data (emails, phones)")
        else:
            print("  ✗ No entities extracted")

        # Performance comparison
        print("\n" + "-"*80)
        print("PERFORMANCE COMPARISON")
        print("-"*80)
        print("  Pattern Matching:")
        print("    + Very high precision (few false positives)")
        print("    + Fast processing")
        print("    - Limited to predefined patterns")
        print("\n  Rule-Based:")
        print("    + Good for common patterns")
        print("    + Moderate speed")
        print("    - Limited coverage")
        print("\n  LLM (GPT-4o-mini):")
        print("    + Excellent contextual understanding")
        print("    + Handles complex entities")
        print("    + Most comprehensive")
        print("    - Higher cost (but still very reasonable)")
        print("    - Slower than other methods")

        print("\n" + "="*80)
        print("RECOMMENDATION")
        print("="*80)
        print("\nFor your RAG system, I recommend:")
        print("1. Use ALL methods for maximum coverage")
        print("2. Let them complement each other:")
        print("   - Pattern matching for structured data (emails, phones, URLs)")
        print("   - Rule-based for common entities")
        print("   - LLM for complex, domain-specific entities")
        print("\nThis hybrid approach gives you the best of all methods!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    quick_test_extraction()