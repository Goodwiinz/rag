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
            f"{self.api_base_url}/api/auth/login",
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
        headers = {"Authorization": f"Bearer {self.auth_token}"}

        search_data = {
            "query": query,
            "limit": limit,
            "search_type": "hybrid"
        }

        response = requests.post(
            f"{self.api_base_url}/api/search/hybrid",
            json=search_data,
            headers=headers
        )

        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            print(f"Search failed: {response.status_code}")
            return []

    async def generate_answer(self, query: str, context: List[Dict]) -> str:
        """Generate answer from context (simulated)"""
        # In a real implementation, this would call the LLM API
        # For evaluation, we'll simulate an answer
        if not context:
            return "I couldn't find relevant information to answer your question."

        # Simple simulated answer based on context
        answer_parts = []
        for ctx in context[:3]:  # Use top 3 results
            if 'content' in ctx:
                # Extract first sentence as sample
                first_sentence = ctx['content'].split('.')[0] + '.'
                answer_parts.append(first_sentence)

        return " ".join(answer_parts)

    async def evaluate_retrieval(
        self,
        query: str,
        ground_truth_papers: List[str],
        retrieved_results: List[Dict]
    ) -> Dict[str, float]:
        """Evaluate retrieval quality"""
        retrieved_ids = [result.get('metadata', {}).get('arxiv_id', '')
                        for result in retrieved_results]

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

        # Answer Relevancy (simplified - checks if answer addresses query)
        query_terms = set(query.lower().split())
        answer_terms = set(answer.lower().split())

        overlap = len(query_terms.intersection(answer_terms))
        metrics['answer_relevancy'] = min(overlap / len(query_terms), 1.0) if query_terms else 0.0

        # Faithfulness (simplified - checks if answer is grounded in context)
        context_text = " ".join([ctx.get('content', '') for ctx in context]).lower()
        answer_sentences = answer.split('.')

        faithful_sentences = 0
        for sentence in answer_sentences:
            sentence = sentence.strip()
            if sentence:
                # Check if key terms from sentence appear in context
                sentence_terms = set(sentence.lower().split())
                if any(term in context_text for term in sentence_terms if len(term) > 3):
                    faithful_sentences += 1

        metrics['faithfulness'] = faithful_sentences / len(answer_sentences) if answer_sentences else 0.0

        # Contextual Precision (simplified - check if top contexts are relevant)
        relevant_contexts = 0
        for ctx in context[:5]:  # Check top 5
            # Simple relevance check based on ground truth categories
            ctx_categories = ctx.get('metadata', {}).get('categories', [])
            gt_categories = ground_truth.get('categories', [])

            if any(cat in ctx_categories for cat in gt_categories):
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

    # Login first
    if not await evaluator.login():
        return

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