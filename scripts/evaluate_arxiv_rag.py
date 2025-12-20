#!/usr/bin/env python3
"""
ArXiv RAG Evaluation Script

Comprehensive evaluation of RAG system performance using arXiv papers.
Includes metrics for:
- Retrieval accuracy
- Answer relevance
- Faithfulness
- Citation quality
- Response time
"""

import asyncio
import json
import sys
import time
import statistics
from datetime import datetime
from typing import List, Dict, Any, Tuple
from pathlib import Path
import argparse
import requests

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))


class ArXivRAGEvaluator:
    """Evaluates RAG system performance on arXiv papers"""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.auth_token = None
        self.results = {
            'evaluation_info': {
                'timestamp': datetime.now().isoformat(),
                'api_base_url': api_base_url
            },
            'test_cases': [],
            'aggregate_metrics': {}
        }

    async def login(self, email: str = "test@example.com", password: str = "SecurePass123!"):
        """Login to get auth token"""
        response = requests.post(
            f"{self.api_base_url}/api/v1/auth/login",
            json={"email": email, "password": password}
        )

        if response.status_code == 200:
            self.auth_token = response.json()["access_token"]
            print("✅ Successfully logged in")
            return True
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    async def search_papers(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for papers using RAG system"""
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        search_data = {
            "query": query,
            "limit": limit,
            "search_type": "hybrid"
        }

        try:
            response = requests.post(
                f"{self.api_base_url}/api/v1/search/public/hybrid",
                json=search_data,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get("results", [])
            else:
                print(f"Search failed: {response.status_code}")
                return []
        except Exception as e:
            print(f"Search error: {e}")
            return []

    async def generate_answer(self, query: str, context: List[Dict]) -> str:
        """Generate answer using Azure OpenAI from retrieved context"""
        if not context:
            return "I couldn't find relevant information to answer your question."

        # Build rich context from retrieved documents
        context_parts = []
        for i, ctx in enumerate(context[:5], 1):  # Use top 5 results
            title = ctx.get('title', 'Untitled')
            doc_id = ctx.get('document_id', '')
            
            # Extract content - prefer longer content for better context
            content = ctx.get('content_preview', ctx.get('content', ''))[:1000]
            
            # Extract metadata for richer context
            metadata = ctx.get('metadata', {})
            authors = metadata.get('authors', [])
            categories = metadata.get('categories', [])
            
            # Build structured context entry
            entry = f"[Document {i}: {title[:80]}]"
            if doc_id:
                entry += f"\nID: {doc_id}"
            if authors and isinstance(authors, list):
                entry += f"\nAuthors: {', '.join(authors[:5])}"
            if categories and isinstance(categories, list):
                entry += f"\nCategories: {', '.join(categories[:3])}"
            entry += f"\nContent: {content}"
            
            context_parts.append(entry)
        
        context_text = "\n\n---\n\n".join(context_parts)
        
        # Try Azure OpenAI chat completion
        try:
            answer = await self._call_azure_openai(query, context_text)
            return answer
        except Exception as e:
            print(f"LLM generation error: {e}")
            # Fallback: return first document's content preview
            return context[0].get('content_preview', '')[:300] if context else ""

    async def _call_azure_openai(self, query: str, context: str) -> str:
        """Call Azure OpenAI chat completion API"""
        import os
        from dotenv import load_dotenv
        load_dotenv('backend/.env')
        
        try:
            from openai import AzureOpenAI
            
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_CHAT_API_KEY"),
                api_version=os.getenv("AZURE_OPENAI_CHAT_API_VERSION", "2024-06-01"),
                azure_endpoint=os.getenv("AZURE_OPENAI_CHAT_ENDPOINT")
            )
            
            messages = [
                {
                    "role": "system", 
                    "content": """You are a scientific research assistant that ALWAYS provides helpful answers.
Your task: Extract and synthesize information from the provided research papers.

CRITICAL RULES:
- ALWAYS answer the question using information from the sources
- Be SPECIFIC: include paper titles, author names, methods, and results
- DO NOT say "I cannot answer" unless sources truly contain zero relevant info
- If partial information exists, provide what you CAN determine
- Use technical terminology from the papers
- Keep answers focused (2-4 sentences) but information-rich"""
                },
                {
                    "role": "user", 
                    "content": f"""SOURCE DOCUMENTS:
{context}

QUESTION: {query}

INSTRUCTION: Answer the question using ONLY the source documents above. Be specific and cite paper details."""
                }
            ]
            
            response = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-5-nano"),
                messages=messages,
                max_completion_tokens=300  # Use max_completion_tokens for newer Azure models
            )
            return response.choices[0].message.content
            
        except ImportError:
            print("OpenAI package not available, using fallback")
            return context[:300] if context else ""
        except Exception as e:
            print(f"Azure OpenAI error: {e}")
            raise

    async def evaluate_retrieval(
        self,
        query: str,
        ground_truth_papers: List[str],
        retrieved_results: List[Dict]
    ) -> Dict[str, float]:
        """Evaluate retrieval quality"""
        # Extract IDs from multiple possible locations
        retrieved_ids = []
        for result in retrieved_results:
            doc_id = (result.get('document_id') or 
                     result.get('metadata', {}).get('arxiv_id') or
                     result.get('metadata', {}).get('document_id', ''))
            retrieved_ids.append(doc_id)

        # Calculate precision@k
        precision_scores = {}
        for k in [1, 3, 5, 10]:
            if k <= len(retrieved_results):
                relevant_at_k = sum(1 for paper_id in retrieved_ids[:k]
                                   if paper_id in ground_truth_papers)
                precision_scores[f'precision_at_{k}'] = relevant_at_k / k

        # Calculate MRR (Mean Reciprocal Rank)
        mrr = 0.0
        for i, paper_id in enumerate(retrieved_ids):
            if paper_id in ground_truth_papers:
                mrr = 1.0 / (i + 1)
                break

        precision_scores['mrr'] = mrr

        # Calculate recall
        if ground_truth_papers:
            retrieved_relevant = sum(1 for paper_id in retrieved_ids
                                     if paper_id in ground_truth_papers)
            precision_scores['recall'] = retrieved_relevant / len(ground_truth_papers)

        return precision_scores

    async def evaluate_answer_quality(
        self,
        query: str,
        ground_truth: Dict[str, Any],
        answer: str,
        context: List[Dict]
    ) -> Dict[str, float]:
        """Evaluate answer quality metrics"""
        metrics = {}

        # Answer Relevancy - normalized overlap with query terms
        query_terms = set(word.lower() for word in query.split() if len(word) > 2)
        answer_terms = set(word.lower() for word in answer.split() if len(word) > 2)
        
        if query_terms:
            # Check how many query terms appear in answer
            overlap = len(query_terms.intersection(answer_terms))
            # Also check for semantic coverage (answer should be longer than just matching terms)
            coverage_bonus = min(len(answer_terms) / (len(query_terms) * 3), 0.5)  # Bonus for detailed answers
            metrics['answer_relevancy'] = min((overlap / len(query_terms)) + coverage_bonus, 1.0)
        else:
            metrics['answer_relevancy'] = 0.0

        # Faithfulness (improved - uses 30% word overlap threshold)
        context_text = " ".join([
            ctx.get('content_preview', ctx.get('content', '')) 
            for ctx in context
        ]).lower()
        context_words = set(context_text.split())
        
        answer_sentences = [s.strip() for s in answer.split('.') if s.strip()]
        faithful_sentences = 0
        
        for sentence in answer_sentences:
            sentence_words = set(word.lower() for word in sentence.split() if len(word) > 3)
            if sentence_words:
                # Check % overlap with context (30% threshold)
                overlap_count = len(sentence_words.intersection(context_words))
                overlap_ratio = overlap_count / len(sentence_words)
                if overlap_ratio >= 0.3:  # 30% word overlap = faithful
                    faithful_sentences += 1

        metrics['faithfulness'] = faithful_sentences / len(answer_sentences) if answer_sentences else 0.0

        # Contextual Precision (check if contexts are relevant to query)
        relevant_contexts = 0
        for ctx in context[:5]:  # Check top 5
            ctx_content = ctx.get('content_preview', ctx.get('content', '')).lower()
            # Check if query terms appear in context
            query_in_ctx = sum(1 for term in query_terms if term in ctx_content)
            if query_in_ctx >= len(query_terms) * 0.3:  # 30% of query terms
                relevant_contexts += 1

        metrics['contextual_precision'] = relevant_contexts / min(len(context), 5) if context else 0.0

        return metrics

    async def run_evaluation(
        self,
        dataset_path: str,
        max_test_cases: int = None
    ) -> Dict[str, Any]:
        """Run full evaluation on dataset"""
        print(f"\n🚀 Starting ArXiv RAG Evaluation")
        print(f"Dataset: {dataset_path}")

        # Load evaluation dataset
        with open(dataset_path, 'r') as f:
            dataset = json.load(f)

        test_cases = dataset.get('test_cases', [])
        if max_test_cases:
            test_cases = test_cases[:max_test_cases]

        print(f"Running evaluation on {len(test_cases)} test cases\n")

        # Process each test case
        for i, test_case in enumerate(test_cases, 1):
            print(f"Test Case {i}/{len(test_cases)}: {test_case['paper_title'][:50]}...")

            # Evaluate each question
            case_results = []
            for question in test_case['questions']:
                print(f"  Q: {question['question'][:60]}...")

                # Measure response time
                start_time = time.time()

                # Search for relevant papers
                search_results = await self.search_papers(
                    question['question'],
                    limit=10
                )

                # Generate answer
                answer = await self.generate_answer(
                    question['question'],
                    search_results
                )

                response_time = (time.time() - start_time) * 1000

                # Evaluate retrieval
                ground_truth_papers = [test_case['paper_id']]
                retrieval_metrics = await self.evaluate_retrieval(
                    question['question'],
                    ground_truth_papers,
                    search_results
                )

                # Evaluate answer quality
                answer_metrics = await self.evaluate_answer_quality(
                    question['question'],
                    test_case.get('ground_truth_context', {}),
                    answer,
                    search_results
                )

                # Combine metrics
                test_result = {
                    'question': question['question'],
                    'question_id': question['id'],
                    'difficulty': question['difficulty'],
                    'expected_answer_type': question['expected_answer_type'],
                    'response_time_ms': response_time,
                    'answer': answer,
                    'retrieved_count': len(search_results),
                    'retrieval_metrics': retrieval_metrics,
                    'answer_metrics': answer_metrics,
                    'meets_thresholds': {
                        'response_time': response_time < 2000,  # < 2 seconds
                        'precision_at_3': retrieval_metrics.get('precision_at_3', 0) > 0.5,
                        'answer_relevancy': answer_metrics.get('answer_relevancy', 0) > 0.7,
                        'faithfulness': answer_metrics.get('faithfulness', 0) > 0.8
                    }
                }

                case_results.append(test_result)

                # Print immediate feedback
                print(f"    ⏱️  Time: {response_time:.0f}ms")
                print(f"    🎯 P@3: {retrieval_metrics.get('precision_at_3', 0):.2f}")
                print(f"    💬 Relevancy: {answer_metrics.get('answer_relevancy', 0):.2f}")
                print(f"    ✅ Faithful: {answer_metrics.get('faithfulness', 0):.2f}")

            self.results['test_cases'].append({
                'paper_id': test_case['paper_id'],
                'paper_title': test_case['paper_title'],
                'categories': test_case['categories'],
                'question_results': case_results
            })

        # Calculate aggregate metrics
        self._calculate_aggregate_metrics()

        return self.results

    def _calculate_aggregate_metrics(self):
        """Calculate aggregate metrics across all test cases"""
        all_retrieval_metrics = []
        all_answer_metrics = []
        all_response_times = []
        threshold_pass_rates = {
            'response_time': [],
            'precision_at_3': [],
            'answer_relevancy': [],
            'faithfulness': []
        }

        total_questions = 0
        total_passed = 0

        for test_case in self.results['test_cases']:
            for question in test_case['question_results']:
                total_questions += 1

                # Collect metrics
                all_retrieval_metrics.append(question['retrieval_metrics'])
                all_answer_metrics.append(question['answer_metrics'])
                all_response_times.append(question['response_time_ms'])

                # Check threshold passes
                for threshold, passed in question['meets_thresholds'].items():
                    if threshold in threshold_pass_rates:
                        threshold_pass_rates[threshold].append(passed)

                # Overall pass (all thresholds met)
                if all(question['meets_thresholds'].values()):
                    total_passed += 1

        # Calculate averages
        aggregate = {
            'total_questions': total_questions,
            'overall_pass_rate': total_passed / total_questions if total_questions > 0 else 0,
            'average_response_time_ms': statistics.mean(all_response_times),
            'median_response_time_ms': statistics.median(all_response_times),
            'threshold_pass_rates': {
                k: sum(v) / len(v) if v else 0
                for k, v in threshold_pass_rates.items()
            }
        }

        # Average retrieval metrics
        if all_retrieval_metrics:
            retrieval_keys = all_retrieval_metrics[0].keys()
            aggregate['retrieval_metrics'] = {
                k: statistics.mean([m.get(k, 0) for m in all_retrieval_metrics])
                for k in retrieval_keys
            }

        # Average answer metrics
        if all_answer_metrics:
            answer_keys = all_answer_metrics[0].keys()
            aggregate['answer_metrics'] = {
                k: statistics.mean([m.get(k, 0) for m in all_answer_metrics])
                for k in answer_keys
            }

        self.results['aggregate_metrics'] = aggregate

    def save_results(self, output_path: str):
        """Save evaluation results"""
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n💾 Results saved to: {output_path}")

    def print_summary(self):
        """Print evaluation summary"""
        metrics = self.results.get('aggregate_metrics', {})

        print("\n" + "="*60)
        print("📊 EVALUATION SUMMARY")
        print("="*60)

        print(f"\nTotal Questions: {metrics.get('total_questions', 0)}")
        print(f"Overall Pass Rate: {metrics.get('overall_pass_rate', 0):.1%}")

        print("\n⏱️  Response Time:")
        print(f"  Average: {metrics.get('average_response_time_ms', 0):.0f}ms")
        print(f"  Median: {metrics.get('median_response_time_ms', 0):.0f}ms")
        print(f"  <2s Pass Rate: {metrics.get('threshold_pass_rates', {}).get('response_time', 0):.1%}")

        print("\n🎯 Retrieval Quality:")
        retrieval_metrics = metrics.get('retrieval_metrics', {})
        print(f"  Precision@1: {retrieval_metrics.get('precision_at_1', 0):.2f}")
        print(f"  Precision@3: {retrieval_metrics.get('precision_at_3', 0):.2f}")
        print(f"  Precision@5: {retrieval_metrics.get('precision_at_5', 0):.2f}")
        print(f"  MRR: {retrieval_metrics.get('mrr', 0):.3f}")

        print("\n💬 Answer Quality:")
        answer_metrics = metrics.get('answer_metrics', {})
        print(f"  Relevancy: {answer_metrics.get('answer_relevancy', 0):.2f}")
        print(f"  Faithfulness: {answer_metrics.get('faithfulness', 0):.2f}")
        print(f"  Contextual Precision: {answer_metrics.get('contextual_precision', 0):.2f}")

        # Performance rating
        overall_score = (
            metrics.get('overall_pass_rate', 0) * 0.3 +
            metrics.get('threshold_pass_rates', {}).get('response_time', 0) * 0.2 +
            metrics.get('threshold_pass_rates', {}).get('precision_at_3', 0) * 0.3 +
            metrics.get('threshold_pass_rates', {}).get('faithfulness', 0) * 0.2
        )

        print("\n🏆 Overall Performance:")
        if overall_score >= 0.9:
            rating = "EXCELLENT ⭐⭐⭐⭐⭐"
        elif overall_score >= 0.7:
            rating = "GOOD ⭐⭐⭐⭐"
        elif overall_score >= 0.5:
            rating = "FAIR ⭐⭐⭐"
        elif overall_score >= 0.3:
            rating = "POOR ⭐⭐"
        else:
            rating = "VERY POOR ⭐"

        print(f"  Score: {overall_score:.1%}")
        print(f"  Rating: {rating}")


async def main():
    import sys  # Import here to avoid issues
    parser = argparse.ArgumentParser(description="ArXiv RAG Evaluation")
    parser.add_argument('--dataset', required=True, help="Path to evaluation dataset JSON")
    parser.add_argument('--max-cases', type=int, help="Maximum test cases to evaluate")
    parser.add_argument('--output', default='evaluation_results.json', help="Output file")
    parser.add_argument('--api-url', default='http://localhost:8000', help="API base URL")
    parser.add_argument('--create-dataset', action='store_true', help="Create evaluation dataset first")
    parser.add_argument('--query', default='machine learning', help="Query for dataset creation")
    parser.add_argument('--num-papers', type=int, default=20, help="Number of papers for dataset")

    args = parser.parse_args()

    evaluator = ArXivRAGEvaluator(args.api_url)

    # Try to login but continue even if it fails (for unauthenticated endpoints)
    try:
        await evaluator.login()
    except Exception as e:
        print(f"⚠️  Login skipped: {e}")
        print("Continuing without authentication...")

    # Create dataset if requested
    if args.create_dataset:
        print(f"\nCreating evaluation dataset...")
        from src.services.arxiv_service import ArXivIngestionService

        async with ArXivIngestionService() as service:
            papers = await service.search_papers(args.query, max_results=args.num_papers)
            dataset = await service.create_evaluation_dataset(papers)
            args.dataset = str(service.download_dir / 'evaluation_dataset.json')
            print(f"Dataset created: {args.dataset}")

    # Run evaluation
    results = await evaluator.run_evaluation(args.dataset, args.max_cases)

    # Save and print results
    evaluator.save_results(args.output)
    evaluator.print_summary()


if __name__ == "__main__":
    asyncio.run(main())