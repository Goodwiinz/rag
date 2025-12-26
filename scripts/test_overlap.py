
import sys
import os
from pathlib import Path

# Add backend to path to import services
sys.path.append(str(Path(__file__).parent.parent / "backend"))

from src.services.embedding_service import embedding_service

def test_chunking():
    print("Testing Chunk Overlap Configuration...")
    
    # Create a test string with word numbers for easy verification
    # Generates a string like "word0 word1 word2 ... word200"
    words = [f"word{i}" for i in range(200)]
    text = " ".join(words)
    
    # 1. Test EmbeddingService chunking (default should be 150 overlap)
    print("\n[EmbeddingService] Default Chunking:")
    chunks = embedding_service.chunk_text(text, chunk_size=50, overlap=10) # Using small values to visualize
    
    # We want to verify the DEFAULTs which are hardcoded in the method signature
    # Since we can't inspect the signature easily at runtime without introspection,
    # we will use the defaults by not passing arguments, but we need a longer text to trigger split.
    
    long_text = " ".join([f"word{i}" for i in range(1000)])
    
    # Chunk with defaults (expected: size=500, overlap=150)
    chunks = embedding_service.chunk_text(long_text)
    
    print(f"Total chunks: {len(chunks)}")
    if chunks:
        print(f"Chunk 0 length: {len(chunks[0])}")
        print(f"Chunk 0 end: ...{chunks[0][-30:]}")
        if len(chunks) > 1:
            print(f"Chunk 1 start: {chunks[1][:30]}...")
            
            # Verify overlap manually
            # We can check if the end of chunk 0 matches start of chunk 1
            # But since it's character based or word based? 
            # The implementation is: words[i:i + chunk_size]
            # stride = chunk_size - overlap
            
            # Let's verify the calculated overlap
            pass

    print("\nTo truly see the effect, you would need to re-index documents.")
    print("This script confirms the service is loaded with the new code.")

if __name__ == "__main__":
    test_chunking()
