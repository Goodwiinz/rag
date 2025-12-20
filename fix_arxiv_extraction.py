#!/usr/bin/env python3
"""Fix the ArXiv extraction to use actual extracted topics"""

import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

# Fix the placeholder topic extraction
fix_topics = """
# Replace the _extract_topics_with_llm function in src/api/arxiv_extraction.py

async def _extract_topics_with_llm(text: str, max_topics: int = 5) -> List[str]:
    \"\"\"Extract topics from text using LLM\"\"\"
    try:
        # Import LLM service
        from ..services.llm_service import LLMService

        # Create prompt for topic extraction
        prompt = f\"\"\"
        Extract 5-7 key topics from the following academic paper text.
        Return only the topics as a Python list, one topic per line.
        Topics should be specific concepts, domains, or areas of study.

        Text:
        {text[:2000]}

        Topics:
        \"\"\"

        llm = LLMService()
        response = await llm.generate_text(prompt)

        # Parse response
        topics = []
        for line in response.strip().split('\\n'):
            line = line.strip().strip('- ').strip()
            if line and len(line) > 2:
                topics.append(line)

        return topics[:max_topics]
    except Exception as e:
        logger.error(f"Topic extraction failed: {e}")
        # Fallback to simple keyword extraction
        words = text.lower().split()
        # Common academic topics
        academic_terms = ['machine learning', 'deep learning', 'computer vision', 'natural language processing',
                          'robotics', 'algorithms', 'databases', 'distributed systems', 'graph theory',
                          'statistics', 'optimization', 'neural networks', 'artificial intelligence']
        found_topics = [term for term in academic_terms if term in text.lower()]
        return found_topics[:max_topics]
"""

# Fix the placeholder keyphrase extraction
fix_keyphrases = """
# Replace the _extract_keyphrases function in src/api/arxiv_extraction.py

async def _extract_keyphrases(text: str, max_phrases: int = 10) -> List[str]:
    \"\"\"Extract key phrases from text\"\"\"
    try:
        # Simple but effective keyphrase extraction
        import re
        from collections import Counter

        # Extract noun phrases and important terms
        # Look for patterns: adjective + noun, multi-word technical terms
        text = text.lower()

        # Common technical terms and patterns
        patterns = [
            r'\\b[a-z]+ (?:learning|network|model|algorithm|method|approach|technique|system|framework)\\b',
            r'\\b(?:deep|neural|convolutional|recurrent|transformer|generative) (?:neural)? networks?\\b',
            r'\\b(?:supervised|unsupervised|semi-supervised|reinforcement) learning\\b',
            r'\\b(?:computer|machine) vision\\b',
            r'\\bnatural language processing\\b',
            r'\\b(?:feature|data|model) (?:extraction|selection|engineering)\\b',
            r'\\b(?:cross|multi)-modal\\b',
            r'\\b(?:pre|post)-training\\b',
        ]

        phrases = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            phrases.extend(matches)

        # Also extract important single words
        important_words = ['pixels', 'masking', 'tokens', 'embeddings', 'attention',
                           'gradient', 'optimizer', 'regularization', 'generalization',
                           'encoder', 'decoder', 'latent', 'representation']

        for word in important_words:
            if word in text and word not in phrases:
                phrases.append(word)

        # Remove duplicates and return
        unique_phrases = list(set(phrases))
        return unique_phrases[:max_phrases]

    except Exception as e:
        logger.error(f"Keyphrase extraction failed: {e}")
        return []
"""

print("The ArXiv extraction is using placeholder functions that don't extract real topics.")
print("\nTo fix this:")
print("1. The _extract_topics_with_llm and _extract_keyphrases functions need to be replaced")
print("2. They should use actual extraction methods, not placeholders")
print("3. OR, use the same extraction method that the frontend is using")
print("\nThis explains why you see correct topics in the frontend but not in Neo4j!")