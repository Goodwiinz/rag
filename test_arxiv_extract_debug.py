#!/usr/bin/env python3
"""Debug ArXiv extraction to see what's happening"""

import sys
import os
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

import asyncio
from src.api.arxiv_extraction import _extract_topics_with_llm, _extract_keyphrases

# Test text from the paper you showed
test_text = """
In Pursuit of Pixel Supervision for Visual Pre-training Lihe Yang2,1* Shang-Wen Li1 Yang Li1 Xinjie Lei1 Dong Wang1 Abdelrahman Mohamed1 Hengshuang Zhao2 Hu Xu1 1FAIR, Meta 2HKU https://github.com/facebookresearch/pixio Abstract At the most basic level, pixels are the source of the visual information through which we perceive the world. Pixels contain information at all levels, ranging from low- level attributes to high-level concepts. Autoencoders represent a classical and long-standing par...
"""

async def test_extraction():
    print("Testing topic and keyphrase extraction...")
    print(f"\nInput text (first 200 chars): {test_text[:200]}...\n")

    # Test topic extraction
    print("Topics extracted:")
    topics = await _extract_topics_with_llm(test_text)
    for i, topic in enumerate(topics, 1):
        print(f"  {i}. {topic}")

    # Test keyphrase extraction
    print("\nKeyphrases extracted:")
    keyphrases = await _extract_keyphrases(test_text)
    for i, kp in enumerate(keyphrases, 1):
        print(f"  {i}. {kp}")

    # Compare with what you showed me
    expected_topics = [
        "graph theory",
        "databases",
        "statistics",
        "distributed systems",
        "robotics",
        "algorithms",
        "computer vision"
    ]

    expected_keyphrases = [
        "masking",
        "training",
        "decoder",
        "pixio",
        "learning",
        "depth",
        "visual",
        "model",
        "data",
        "tokens"
    ]

    print("\n❌ ISSUE FOUND!")
    print("The topics/keyphrases you're seeing in the frontend are NOT what's being extracted by the ArXiv extraction!")
    print(f"\nExpected topics: {expected_topics}")
    print(f"Extracted topics: {topics}")
    print(f"\nExpected keyphrases: {expected_keyphrases[:5]}...")
    print(f"Extracted keyphrases: {keyphrases[:5]}...")

# Run the test
asyncio.run(test_extraction())