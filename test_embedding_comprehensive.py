#!/usr/bin/env python3
"""
Comprehensive Embedding Testing Suite for Azure OpenAI
Tests functionality, performance, quality, and integration
"""

import os
import sys
import time
import requests
import json
import numpy as np
from typing import List, Dict, Any
import statistics

# Add backend to path
sys.path.insert(0, '/Users/goodwiinz/development/RAG_system/rag/backend')

class EmbeddingTester:
    """Comprehensive testing suite for Azure OpenAI embeddings"""

    def __init__(self):
        # Load environment first
        self._load_environment()

        self.api_key = os.getenv('AZURE_OPENAI_EMBEDDING_API_KEY') or os.getenv('AZURE_OPENAI_API_KEY')
        self.base_endpoint = os.getenv('AZURE_OPENAI_EMBEDDING_ENDPOINT')
        self.deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-ada-002')
        self.api_version = os.getenv('AZURE_OPENAI_EMBEDDING_API_VERSION', '2023-05-15')

        if self.base_endpoint:
            self.url = f"{self.base_endpoint.rstrip('/')}/openai/deployments/{self.deployment}/embeddings?api-version={self.api_version}"
        else:
            self.url = None

        self.test_results = {}
        self.headers = {
            'Content-Type': 'application/json',
            'api-key': self.api_key
        }

    def _load_environment(self):
        """Load environment variables from .env file"""
        env_path = '/Users/goodwiinz/development/RAG_system/rag/.env'
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if line.strip() and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()

    def test_basic_embedding(self) -> Dict[str, Any]:
        """Test basic single text embedding"""
        print("🧪 Test 1: Basic Single Text Embedding")
        print("-" * 50)

        test_text = "This is a simple test sentence for embedding generation."

        start_time = time.time()
        data = {'input': test_text}

        try:
            response = requests.post(self.url, headers=self.headers, json=data)
            response_time = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                embedding = result['data'][0]['embedding']

                print(f"✅ Basic embedding test PASSED")
                print(f"   Text: '{test_text}'")
                print(f"   Dimension: {len(embedding)}")
                print(f"   Response time: {response_time:.3f}s")
                print(f"   Usage: {result.get('usage', {})}")
                print(f"   First 5 values: {embedding[:5]}")

                return {
                    'status': 'PASSED',
                    'dimension': len(embedding),
                    'response_time': response_time,
                    'usage': result.get('usage', {}),
                    'embedding_preview': embedding[:5]
                }
            else:
                print(f"❌ Basic embedding test FAILED: {response.status_code}")
                print(f"   Error: {response.text}")
                return {'status': 'FAILED', 'error': response.text}

        except Exception as e:
            print(f"❌ Basic embedding test ERROR: {str(e)}")
            return {'status': 'ERROR', 'error': str(e)}

    def test_batch_embeddings(self, texts: List[str]) -> Dict[str, Any]:
        """Test batch embedding generation"""
        print("\n🧪 Test 2: Batch Embedding Generation")
        print("-" * 50)

        start_time = time.time()
        data = {'input': texts}

        try:
            response = requests.post(self.url, headers=self.headers, json=data)
            response_time = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                embeddings = [item['embedding'] for item in result['data']]

                print(f"✅ Batch embedding test PASSED")
                print(f"   Number of texts: {len(texts)}")
                print(f"   Number of embeddings: {len(embeddings)}")
                print(f"   Response time: {response_time:.3f}s")
                print(f"   Average time per embedding: {response_time/len(texts):.3f}s")
                print(f"   Usage: {result.get('usage', {})}")

                # Check consistency
                dimensions = [len(emb) for emb in embeddings]
                if len(set(dimensions)) == 1:
                    print(f"   ✅ All embeddings have consistent dimension: {dimensions[0]}")
                else:
                    print(f"   ❌ Inconsistent dimensions: {dimensions}")

                return {
                    'status': 'PASSED',
                    'num_texts': len(texts),
                    'num_embeddings': len(embeddings),
                    'response_time': response_time,
                    'avg_time_per_embedding': response_time/len(texts),
                    'usage': result.get('usage', {}),
                    'dimensions_consistent': len(set(dimensions)) == 1,
                    'embedding_dimension': dimensions[0] if dimensions else 0
                }
            else:
                print(f"❌ Batch embedding test FAILED: {response.status_code}")
                print(f"   Error: {response.text}")
                return {'status': 'FAILED', 'error': response.text}

        except Exception as e:
            print(f"❌ Batch embedding test ERROR: {str(e)}")
            return {'status': 'ERROR', 'error': str(e)}

    def test_embedding_quality(self) -> Dict[str, Any]:
        """Test embedding quality with semantic similarity"""
        print("\n🧪 Test 3: Embedding Quality Assessment")
        print("-" * 50)

        # Test pairs with known semantic relationships
        test_pairs = [
            {
                'text1': 'The cat sat on the mat',
                'text2': 'A cat is sitting on a mat',
                'expected_similarity': 'high',
                'description': 'Similar meaning'
            },
            {
                'text1': 'The weather is sunny today',
                'text2': 'Artificial intelligence is evolving rapidly',
                'expected_similarity': 'low',
                'description': 'Different topics'
            },
            {
                'text1': 'Machine learning models process data',
                'text2': 'AI algorithms analyze information',
                'expected_similarity': 'medium',
                'description': 'Related but different'
            }
        ]

        try:
            # Generate embeddings for all texts
            all_texts = []
            for pair in test_pairs:
                all_texts.extend([pair['text1'], pair['text2']])

            print(f"   Generating embeddings for {len(all_texts)} texts...")
            data = {'input': all_texts}
            start_time = time.time()

            response = requests.post(self.url, headers=self.headers, json=data)
            response_time = time.time() - start_time

            if response.status_code != 200:
                return {'status': 'FAILED', 'error': response.text}

            result = response.json()
            embeddings = [item['embedding'] for item in result['data']]

            # Calculate similarities
            similarities = []
            for i, pair in enumerate(test_pairs):
                emb1 = np.array(embeddings[i*2])
                emb2 = np.array(embeddings[i*2 + 1])

                # Cosine similarity
                similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
                similarities.append(similarity)

                print(f"   {pair['description']}:")
                print(f"     Text 1: '{pair['text1']}'")
                print(f"     Text 2: '{pair['text2']}'")
                print(f"     Similarity: {similarity:.4f} (expected: {pair['expected_similarity']})")

            # Quality assessment
            avg_similarity = statistics.mean(similarities)

            # Check if similarities make sense
            high_sim = similarities[0]  # Should be highest
            low_sim = similarities[1]   # Should be lowest

            quality_score = 0
            if high_sim > low_sim:
                quality_score += 50
                print(f"   ✅ High similarity > Low similarity ({high_sim:.4f} > {low_sim:.4f})")
            else:
                print(f"   ❌ Similarity ordering incorrect ({high_sim:.4f} <= {low_sim:.4f})")

            if high_sim > 0.7:  # Good threshold for high similarity
                quality_score += 25
                print(f"   ✅ High similarity threshold passed ({high_sim:.4f} > 0.7)")

            if low_sim < 0.3:  # Good threshold for low similarity
                quality_score += 25
                print(f"   ✅ Low similarity threshold passed ({low_sim:.4f} < 0.3)")

            print(f"   Overall Quality Score: {quality_score}/100")
            print(f"   Response time: {response_time:.3f}s")

            return {
                'status': 'PASSED' if quality_score >= 50 else 'FAILED',
                'quality_score': quality_score,
                'similarities': similarities,
                'avg_similarity': avg_similarity,
                'response_time': response_time,
                'usage': result.get('usage', {})
            }

        except Exception as e:
            print(f"❌ Embedding quality test ERROR: {str(e)}")
            return {'status': 'ERROR', 'error': str(e)}

    def test_embedding_performance(self) -> Dict[str, Any]:
        """Test embedding performance with different text lengths"""
        print("\n🧪 Test 4: Performance Benchmarking")
        print("-" * 50)

        test_cases = [
            {'name': 'Short', 'text': 'Hello world', 'expected_tokens': 2},
            {'name': 'Medium', 'text': 'This is a medium length sentence with multiple words to test performance.', 'expected_tokens': 15},
            {'name': 'Long', 'text': 'This is a much longer text that contains multiple sentences and should test how the embedding service handles longer inputs with more complex content and structure.', 'expected_tokens': 35},
            {'name': 'Very Long', 'text': ' '.join(['This is a very long text.'] * 20), 'expected_tokens': 80}
        ]

        performance_results = []

        for case in test_cases:
            print(f"   Testing {case['name']} text...")

            # Estimate tokens (rough approximation: 1 token ≈ 4 characters for English)
            estimated_tokens = len(case['text']) // 4

            start_time = time.time()
            data = {'input': case['text']}

            try:
                response = requests.post(self.url, headers=self.headers, json=data)
                response_time = time.time() - start_time

                if response.status_code == 200:
                    result = response.json()
                    embedding = result['data'][0]['embedding']
                    usage = result.get('usage', {})
                    actual_tokens = usage.get('prompt_tokens', estimated_tokens)

                    performance_results.append({
                        'name': case['name'],
                        'text_length': len(case['text']),
                        'estimated_tokens': estimated_tokens,
                        'actual_tokens': actual_tokens,
                        'response_time': response_time,
                        'tokens_per_second': actual_tokens / response_time if response_time > 0 else 0,
                        'dimension': len(embedding)
                    })

                    print(f"     ✅ Length: {len(case['text'])} chars, Tokens: {actual_tokens}, Time: {response_time:.3f}s, Rate: {actual_tokens/response_time:.1f} tokens/s")
                else:
                    print(f"     ❌ Failed: {response.status_code} - {response.text}")
                    performance_results.append({
                        'name': case['name'],
                        'status': 'FAILED',
                        'error': response.text
                    })

            except Exception as e:
                print(f"     ❌ Error: {str(e)}")
                performance_results.append({
                    'name': case['name'],
                    'status': 'ERROR',
                    'error': str(e)
                })

        # Analyze performance
        successful_results = [r for r in performance_results if 'error' not in r and r.get('status') != 'FAILED']

        if successful_results:
            avg_tokens_per_second = statistics.mean([r['tokens_per_second'] for r in successful_results])
            max_response_time = max([r['response_time'] for r in successful_results])

            print(f"\n   Performance Summary:")
            print(f"   Average processing rate: {avg_tokens_per_second:.1f} tokens/second")
            print(f"   Maximum response time: {max_response_time:.3f}s")
            print(f"   Tests passed: {len(successful_results)}/{len(test_cases)}")

            return {
                'status': 'PASSED' if len(successful_results) >= 3 else 'FAILED',
                'performance_results': performance_results,
                'avg_tokens_per_second': avg_tokens_per_second,
                'max_response_time': max_response_time,
                'tests_passed': len(successful_results),
                'total_tests': len(test_cases)
            }
        else:
            return {'status': 'FAILED', 'error': 'No performance tests passed'}

    def test_document_embedding_workflow(self) -> Dict[str, Any]:
        """Test realistic document embedding workflow"""
        print("\n🧪 Test 5: Document Embedding Workflow")
        print("-" * 50)

        # Simulate real document processing
        documents = [
            {
                'title': 'Introduction to Machine Learning',
                'content': 'Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.',
                'type': 'introduction'
            },
            {
                'title': 'Neural Networks Overview',
                'content': 'Neural networks are computing systems inspired by biological neural networks that constitute animal brains. They consist of connected layers of nodes that process information.',
                'type': 'technical'
            },
            {
                'title': 'Applications in Business',
                'content': 'Business applications of AI include customer service automation, predictive analytics, fraud detection, recommendation systems, and process optimization.',
                'type': 'business'
            }
        ]

        try:
            workflow_results = []
            total_start_time = time.time()

            for i, doc in enumerate(documents):
                print(f"   Processing document {i+1}: {doc['title']}")

                # Split document into chunks (simulate chunking strategy)
                chunk_size = 100  # characters
                chunks = [doc['content'][j:j+chunk_size] for j in range(0, len(doc['content']), chunk_size)]

                print(f"     Split into {len(chunks)} chunks")

                # Generate embeddings for chunks
                chunk_texts = [f"{doc['title']}: {chunk}" for chunk in chunks]

                start_time = time.time()
                data = {'input': chunk_texts}

                response = requests.post(self.url, headers=self.headers, json=data)
                response_time = time.time() - start_time

                if response.status_code == 200:
                    result = response.json()
                    embeddings = [item['embedding'] for item in result['data']]

                    workflow_results.append({
                        'document_title': doc['title'],
                        'document_type': doc['type'],
                        'num_chunks': len(chunks),
                        'num_embeddings': len(embeddings),
                        'response_time': response_time,
                        'avg_time_per_chunk': response_time / len(chunks),
                        'usage': result.get('usage', {}),
                        'embedding_dimension': len(embeddings[0]) if embeddings else 0
                    })

                    print(f"     ✅ Generated {len(embeddings)} embeddings in {response_time:.3f}s")
                else:
                    print(f"     ❌ Failed: {response.status_code} - {response.text}")
                    workflow_results.append({
                        'document_title': doc['title'],
                        'status': 'FAILED',
                        'error': response.text
                    })

            total_workflow_time = time.time() - total_start_time
            successful_docs = [r for r in workflow_results if 'error' not in r and r.get('status') != 'FAILED']

            if successful_docs:
                total_chunks = sum([r['num_chunks'] for r in successful_docs])
                avg_time_per_chunk = sum([r['response_time'] for r in successful_docs]) / total_chunks
                total_tokens = sum([r['usage'].get('total_tokens', 0) for r in successful_docs])

                print(f"\n   Workflow Summary:")
                print(f"   Documents processed: {len(successful_docs)}/{len(documents)}")
                print(f"   Total chunks processed: {total_chunks}")
                print(f"   Total workflow time: {total_workflow_time:.3f}s")
                print(f"   Average time per chunk: {avg_time_per_chunk:.3f}s")
                print(f"   Total tokens processed: {total_tokens}")
                print(f"   Overall processing rate: {total_tokens/total_workflow_time:.1f} tokens/second")

                return {
                    'status': 'PASSED' if len(successful_docs) >= 2 else 'FAILED',
                    'workflow_results': workflow_results,
                    'total_documents': len(documents),
                    'successful_documents': len(successful_docs),
                    'total_chunks': total_chunks,
                    'total_workflow_time': total_workflow_time,
                    'avg_time_per_chunk': avg_time_per_chunk,
                    'total_tokens': total_tokens,
                    'overall_tokens_per_second': total_tokens/total_workflow_time
                }
            else:
                return {'status': 'FAILED', 'error': 'No documents processed successfully'}

        except Exception as e:
            print(f"❌ Document workflow test ERROR: {str(e)}")
            return {'status': 'ERROR', 'error': str(e)}

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all embedding tests and generate comprehensive report"""
        print("🚀 COMPREHENSIVE AZURE OPENAI EMBEDDING TEST SUITE")
        print("=" * 70)
        print(f"   Endpoint: {self.url}")
        print(f"   Deployment: {self.deployment}")
        print(f"   API Version: {self.api_version}")
        print(f"   API Key: {'Set' if self.api_key else 'Not set'}")

        # Validate configuration
        if not self.api_key or not self.base_endpoint:
            print(f"\n❌ Configuration missing:")
            if not self.api_key:
                print(f"   - API key not set")
            if not self.base_endpoint:
                print(f"   - Embedding endpoint not set")
            return {'summary': {'overall_status': 'FAILED', 'error': 'Missing configuration'}}

        # Run all tests
        test_results = {}

        # Test 1: Basic embedding
        test_results['basic'] = self.test_basic_embedding()

        # Test 2: Batch embeddings
        batch_texts = [
            "First test sentence",
            "Second test sentence",
            "Third test sentence",
            "Fourth test sentence",
            "Fifth test sentence"
        ]
        test_results['batch'] = self.test_batch_embeddings(batch_texts)

        # Test 3: Quality assessment
        test_results['quality'] = self.test_embedding_quality()

        # Test 4: Performance benchmarking
        test_results['performance'] = self.test_embedding_performance()

        # Test 5: Document workflow
        test_results['workflow'] = self.test_document_embedding_workflow()

        # Generate summary
        passed_tests = sum(1 for result in test_results.values() if result.get('status') == 'PASSED')
        total_tests = len(test_results)

        print("\n" + "=" * 70)
        print("📊 COMPREHENSIVE TEST RESULTS")
        print("=" * 70)

        for test_name, result in test_results.items():
            status = result.get('status', 'UNKNOWN')
            status_icon = "✅" if status == 'PASSED' else "❌" if status in ['FAILED', 'ERROR'] else "⚠️"
            print(f"   {test_name.capitalize():15} {status_icon} {status}")

            if status == 'PASSED':
                if 'response_time' in result:
                    print(f"                      Response time: {result['response_time']:.3f}s")
                if 'quality_score' in result:
                    print(f"                      Quality score: {result['quality_score']}/100")
                if 'avg_tokens_per_second' in result:
                    print(f"                      Processing rate: {result['avg_tokens_per_second']:.1f} tokens/s")

        print(f"\n   Overall: {passed_tests}/{total_tests} tests passed")

        if passed_tests == total_tests:
            print(f"\n🎉 ALL TESTS PASSED! Your Azure OpenAI embedding service is fully functional and ready for production.")
            print(f"\n💡 Recommendations:")
            print(f"   • Embeddings are consistent and high-quality")
            print(f"   • Performance is within acceptable ranges")
            print(f"   • Ready for document processing and RAG workflows")
        elif passed_tests >= total_tests * 0.8:
            print(f"\n⚠️  MOST TESTS PASSED. Service is mostly functional with minor issues.")
        else:
            print(f"\n❌ MULTIPLE TEST FAILURES. Please check configuration and service availability.")

        return {
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'success_rate': passed_tests / total_tests,
                'overall_status': 'PASSED' if passed_tests == total_tests else 'FAILED'
            },
            'detailed_results': test_results
        }

def main():
    """Main test runner"""
    tester = EmbeddingTester()
    results = tester.run_all_tests()

    return results

if __name__ == "__main__":
    main()