#!/usr/bin/env python3
"""
Evaluation Framework for RAG System Datasets
Supports evaluation of DocVQA, PubLayNet, LAION-400M and custom datasets
"""

import asyncio
import json
import time
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import requests
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EvaluationMetric:
    """Evaluation metric definition"""
    name: str
    description: str
    higher_is_better: bool
    threshold: Optional[float] = None

@dataclass
class QueryResult:
    """Result of a single query evaluation"""
    query: str
    ground_truth: str
    generated_answer: str
    retrieval_context: List[str]
    metrics: Dict[str, float]
    response_time: float
    timestamp: datetime

@dataclass
class DatasetEvaluation:
    """Complete dataset evaluation results"""
    dataset_name: str
    dataset_type: str
    total_queries: int
    successful_queries: int
    average_response_time: float
    metrics: Dict[str, float]
    query_results: List[QueryResult]
    timestamp: datetime

class RAGEvaluator:
    """Evaluates RAG system performance on various datasets"""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.session = requests.Session()
        self.metrics = self.define_metrics()

    def define_metrics(self) -> Dict[str, EvaluationMetric]:
        """Define evaluation metrics"""
        return {
            "answer_relevancy": EvaluationMetric(
                name="Answer Relevancy",
                description="Relevance of generated answer to the query",
                higher_is_better=True,
                threshold=0.7
            ),
            "faithfulness": EvaluationMetric(
                name="Faithfulness",
                description="Factual consistency of answer with context",
                higher_is_better=True,
                threshold=0.9
            ),
            "context_relevancy": EvaluationMetric(
                name="Context Relevancy",
                description="Relevance of retrieved context to query",
                higher_is_better=True,
                threshold=0.7
            ),
            "accuracy": EvaluationMetric(
                name="Accuracy",
                description="Exact match accuracy for factual queries",
                higher_is_better=True,
                threshold=0.8
            ),
            "response_time": EvaluationMetric(
                name="Response Time",
                description="Time taken to generate response (ms)",
                higher_is_better=False,
                threshold=2000
            )
        }

    def authenticate(self, username: str = "admin", password: str = "REDACTED") -> bool:
        """Authenticate with the RAG system"""
        try:
            response = self.session.post(
                f"{self.api_base_url}/auth/login",
                json={"username": username, "password": password}
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False

    def execute_query(self, query: str, dataset_type: str = "general") -> Tuple[str, List[str], float]:
        """Execute a query against the RAG system"""
        start_time = time.time()

        try:
            # Prepare request payload
            payload = {
                "query": query,
                "dataset_type": dataset_type,
                "max_context_items": 5,
                "include_sources": True
            }

            response = self.session.post(
                f"{self.api_base_url}/query",
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                answer = data.get("answer", "")
                context = data.get("context", [])
                response_time = (time.time() - start_time) * 1000  # Convert to ms
                return answer, context, response_time
            else:
                logger.error(f"Query failed with status {response.status_code}")
                return "", [], (time.time() - start_time) * 1000

        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return "", [], (time.time() - start_time) * 1000

    def calculate_answer_relevancy(self, query: str, answer: str) -> float:
        """Calculate answer relevancy score"""
        if not answer:
            return 0.0

        # Simple heuristic-based relevancy calculation
        # In a real implementation, you would use a more sophisticated method
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())

        if not query_words:
            return 0.0

        # Calculate overlap and length ratio
        overlap = len(query_words.intersection(answer_words))
        query_coverage = overlap / len(query_words)
        answer_conciseness = min(len(answer.split()) / 50, 1.0)  # Prefer concise answers

        # Combined score
        relevancy = (query_coverage * 0.7) + (answer_conciseness * 0.3)
        return min(relevancy, 1.0)

    def calculate_faithfulness(self, answer: str, context: List[str]) -> float:
        """Calculate faithfulness score (answer consistency with context)"""
        if not answer or not context:
            return 0.0

        answer_words = set(answer.lower().split())
        context_words = set()

        for ctx in context:
            context_words.update(ctx.lower().split())

        if not answer_words:
            return 0.0

        # Calculate how much of the answer is supported by context
        supported_words = answer_words.intersection(context_words)
        faithfulness = len(supported_words) / len(answer_words)

        return min(faithfulness, 1.0)

    def calculate_context_relevancy(self, query: str, context: List[str]) -> float:
        """Calculate context relevancy score"""
        if not query or not context:
            return 0.0

        query_words = set(query.lower().split())
        relevant_context = 0

        for ctx in context:
            context_words = set(ctx.lower().split())
            if context_words:
                overlap = len(query_words.intersection(context_words))
                if overlap > 0:
                    relevant_context += overlap / len(context_words)

        return min(relevant_context / len(context), 1.0) if context else 0.0

    def calculate_accuracy(self, ground_truth: str, generated_answer: str) -> float:
        """Calculate exact match accuracy"""
        if not ground_truth or not generated_answer:
            return 0.0

        # Normalize both strings
        gt_normalized = ground_truth.lower().strip()
        answer_normalized = generated_answer.lower().strip()

        return 1.0 if gt_normalized == answer_normalized else 0.0

    def evaluate_query(self, query: str, ground_truth: str, dataset_type: str = "general") -> QueryResult:
        """Evaluate a single query"""
        answer, context, response_time = self.execute_query(query, dataset_type)

        # Calculate metrics
        metrics = {
            "answer_relevancy": self.calculate_answer_relevancy(query, answer),
            "faithfulness": self.calculate_faithfulness(answer, context),
            "context_relevancy": self.calculate_context_relevancy(query, context),
            "accuracy": self.calculate_accuracy(ground_truth, answer),
            "response_time": response_time
        }

        return QueryResult(
            query=query,
            ground_truth=ground_truth,
            generated_answer=answer,
            retrieval_context=context,
            metrics=metrics,
            response_time=response_time,
            timestamp=datetime.now()
        )

    def evaluate_dataset(self, dataset_path: Path, dataset_type: str) -> DatasetEvaluation:
        """Evaluate the RAG system on a complete dataset"""
        logger.info(f"Evaluating {dataset_type} dataset: {dataset_path}")

        with open(dataset_path, 'r') as f:
            data = json.load(f)

        query_results = []
        total_queries = 0
        successful_queries = 0
        total_response_time = 0

        # Prepare queries based on dataset type
        if dataset_type == "docvqa":
            test_items = self.prepare_docvqa_queries(data)
        elif dataset_type == "publaynet":
            test_items = self.prepare_publaynet_queries(data)
        elif dataset_type == "laion":
            test_items = self.prepare_laion_queries(data)
        else:
            test_items = self.prepare_general_queries(data)

        logger.info(f"Prepared {len(test_items)} test queries")

        for i, (query, ground_truth) in enumerate(test_items):
            total_queries += 1

            try:
                result = self.evaluate_query(query, ground_truth, dataset_type)
                query_results.append(result)
                successful_queries += 1
                total_response_time += result.response_time

                if (i + 1) % 10 == 0:
                    logger.info(f"Evaluated {i + 1}/{len(test_items)} queries")

            except Exception as e:
                logger.error(f"Error evaluating query {i + 1}: {str(e)}")
                continue

        # Calculate aggregate metrics
        if query_results:
            aggregate_metrics = self.calculate_aggregate_metrics(query_results)
            avg_response_time = total_response_time / len(query_results)
        else:
            aggregate_metrics = {}
            avg_response_time = 0.0

        return DatasetEvaluation(
            dataset_name=dataset_path.name,
            dataset_type=dataset_type,
            total_queries=total_queries,
            successful_queries=successful_queries,
            average_response_time=avg_response_time,
            metrics=aggregate_metrics,
            query_results=query_results,
            timestamp=datetime.now()
        )

    def prepare_docvqa_queries(self, data: Dict) -> List[Tuple[str, str]]:
        """Prepare test queries from DocVQA dataset"""
        queries = []
        for item in data.get('data', [])[:50]:  # Limit to 50 for demo
            question = item.get('question', '')
            answer = item.get('answer', '')
            if question and answer:
                queries.append((question, answer))
        return queries

    def prepare_publaynet_queries(self, data: Dict) -> List[Tuple[str, str]]:
        """Prepare test queries from PubLayNet dataset"""
        queries = []
        for item in data.get('annotations', [])[:50]:  # Limit to 50 for demo
            # Create queries based on layout information
            layout_type = item.get('category', '')
            image_id = item.get('image_id', '')

            if layout_type:
                query = f"What is the layout type of document {image_id}?"
                ground_truth = f"The layout type is {layout_type}"
                queries.append((query, ground_truth))
        return queries

    def prepare_laion_queries(self, data: Dict) -> List[Tuple[str, str]]:
        """Prepare test queries from LAION dataset"""
        queries = []
        for item in data.get('images', [])[:50]:  # Limit to 50 for demo
            caption = item.get('caption', '')
            if caption:
                query = f"Describe the image content"
                ground_truth = caption
                queries.append((query, ground_truth))
        return queries

    def prepare_general_queries(self, data: Dict) -> List[Tuple[str, str]]:
        """Prepare test queries from general dataset"""
        queries = []
        # This would be customized based on the dataset structure
        return queries

    def calculate_aggregate_metrics(self, query_results: List[QueryResult]) -> Dict[str, float]:
        """Calculate aggregate metrics from query results"""
        if not query_results:
            return {}

        metrics = {}
        for metric_name in self.metrics.keys():
            values = [result.metrics.get(metric_name, 0) for result in query_results]
            metrics[metric_name] = np.mean(values) if values else 0.0

        return metrics

    def generate_evaluation_report(self, evaluation: DatasetEvaluation) -> str:
        """Generate a detailed evaluation report"""
        report = []
        report.append("RAG System Evaluation Report")
        report.append("=" * 50)
        report.append(f"Dataset: {evaluation.dataset_name}")
        report.append(f"Type: {evaluation.dataset_type}")
        report.append(f"Evaluated: {evaluation.timestamp.isoformat()}")
        report.append("")

        # Summary statistics
        report.append("Summary Statistics:")
        report.append(f"  Total Queries: {evaluation.total_queries}")
        report.append(f"  Successful Queries: {evaluation.successful_queries}")
        report.append(f"  Success Rate: {(evaluation.successful_queries / evaluation.total_queries * 100):.1f}%")
        report.append(f"  Average Response Time: {evaluation.average_response_time:.2f}ms")
        report.append("")

        # Performance metrics
        report.append("Performance Metrics:")
        for metric_name, value in evaluation.metrics.items():
            metric_def = self.metrics.get(metric_name)
            if metric_def:
                threshold = metric_def.threshold
                status = "✅ PASS" if threshold and ((value >= threshold and metric_def.higher_is_better) or (value <= threshold and not metric_def.higher_is_better)) else "❌ FAIL"
                report.append(f"  {metric_def.name}: {value:.3f} {status}")
        report.append("")

        return "\n".join(report)

    def create_visualizations(self, evaluation: DatasetEvaluation) -> None:
        """Create evaluation visualizations"""
        if not evaluation.query_results:
            return

        # Create plots directory
        plots_dir = Path("evaluation/plots")
        plots_dir.mkdir(parents=True, exist_ok=True)

        # 1. Metrics distribution
        self.plot_metrics_distribution(evaluation, plots_dir)

        # 2. Response time distribution
        self.plot_response_times(evaluation, plots_dir)

        # 3. Performance comparison
        self.plot_performance_comparison(evaluation, plots_dir)

    def plot_metrics_distribution(self, evaluation: DatasetEvaluation, plots_dir: Path) -> None:
        """Plot distribution of evaluation metrics"""
        metrics_data = {}
        for result in evaluation.query_results:
            for metric_name, value in result.metrics.items():
                if metric_name not in metrics_data:
                    metrics_data[metric_name] = []
                metrics_data[metric_name].append(value)

        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.flatten()

        for i, (metric_name, values) in enumerate(metrics_data.items()):
            if i < len(axes):
                axes[i].hist(values, bins=20, alpha=0.7, edgecolor='black')
                axes[i].set_title(f'{metric_name.replace("_", " ").title()}')
                axes[i].set_xlabel('Score')
                axes[i].set_ylabel('Frequency')

                # Add threshold line if available
                metric_def = self.metrics.get(metric_name)
                if metric_def and metric_def.threshold:
                    axes[i].axvline(metric_def.threshold, color='red', linestyle='--',
                                   label=f'Threshold: {metric_def.threshold}')
                    axes[i].legend()

        # Remove empty subplots
        for i in range(len(metrics_data), len(axes)):
            fig.delaxes(axes[i])

        plt.tight_layout()
        plt.savefig(plots_dir / f"{evaluation.dataset_type}_metrics_distribution.png", dpi=300, bbox_inches='tight')
        plt.close()

    def plot_response_times(self, evaluation: DatasetEvaluation, plots_dir: Path) -> None:
        """Plot response time distribution"""
        response_times = [result.response_time for result in evaluation.query_results]

        plt.figure(figsize=(10, 6))
        plt.hist(response_times, bins=20, alpha=0.7, edgecolor='black')
        plt.axvline(np.mean(response_times), color='red', linestyle='--',
                   label=f'Mean: {np.mean(response_times):.2f}ms')
        plt.axvline(2000, color='orange', linestyle='--',
                   label='Target: 2000ms')
        plt.title(f'Response Time Distribution - {evaluation.dataset_type.upper()}')
        plt.xlabel('Response Time (ms)')
        plt.ylabel('Frequency')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(plots_dir / f"{evaluation.dataset_type}_response_times.png", dpi=300, bbox_inches='tight')
        plt.close()

    def plot_performance_comparison(self, evaluation: DatasetEvaluation, plots_dir: Path) -> None:
        """Plot performance comparison against thresholds"""
        metric_names = list(self.metrics.keys())
        actual_values = [evaluation.metrics.get(name, 0) for name in metric_names]
        thresholds = [self.metrics[name].threshold for name in metric_names]

        x = np.arange(len(metric_names))
        width = 0.35

        fig, ax = plt.subplots(figsize=(12, 8))
        bars1 = ax.bar(x - width/2, actual_values, width, label='Actual', alpha=0.7)
        bars2 = ax.bar(x + width/2, thresholds, width, label='Threshold', alpha=0.7)

        ax.set_xlabel('Metrics')
        ax.set_ylabel('Values')
        ax.set_title(f'Performance vs Thresholds - {evaluation.dataset_type.upper()}')
        ax.set_xticks(x)
        ax.set_xticklabels([name.replace('_', ' ').title() for name in metric_names], rotation=45)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add value labels on bars
        for bar in bars1:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.3f}', ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig(plots_dir / f"{evaluation.dataset_type}_performance_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()

class EvaluationRunner:
    """Main evaluation orchestrator"""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.evaluator = RAGEvaluator(api_base_url)

    def run_all_evaluations(self) -> Dict[str, DatasetEvaluation]:
        """Run evaluations on all available datasets"""
        results = {}
        datasets_dir = Path("datasets/downloads")

        # Define dataset files and their types
        dataset_files = {
            "docvqa_sample.json": "docvqa",
            "publaynet_sample.json": "publaynet",
            "laion_sample.json": "laion"
        }

        for filename, dataset_type in dataset_files.items():
            dataset_path = datasets_dir / filename
            if dataset_path.exists():
                logger.info(f"Running evaluation on {dataset_type} dataset...")
                try:
                    evaluation = self.evaluator.evaluate_dataset(dataset_path, dataset_type)
                    results[dataset_type] = evaluation

                    # Generate report
                    report = self.evaluator.generate_evaluation_report(evaluation)
                    report_path = Path(f"evaluation/reports/{dataset_type}_evaluation_report.txt")
                    report_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(report_path, 'w') as f:
                        f.write(report)

                    # Create visualizations
                    self.evaluator.create_visualizations(evaluation)

                    logger.info(f"Completed evaluation for {dataset_type}")

                except Exception as e:
                    logger.error(f"Failed to evaluate {dataset_type}: {str(e)}")
            else:
                logger.warning(f"Dataset file not found: {dataset_path}")

        return results

    def generate_summary_report(self, results: Dict[str, DatasetEvaluation]) -> str:
        """Generate a summary report across all evaluations"""
        report = []
        report.append("RAG System Evaluation Summary Report")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")

        # Overall statistics
        total_queries = sum(eval.total_queries for eval in results.values())
        successful_queries = sum(eval.successful_queries for eval in results.values())
        overall_success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0

        report.append("Overall Statistics:")
        report.append(f"  Datasets Evaluated: {len(results)}")
        report.append(f"  Total Queries: {total_queries}")
        report.append(f"  Successful Queries: {successful_queries}")
        report.append(f"  Overall Success Rate: {overall_success_rate:.1f}%")
        report.append("")

        # Performance by dataset
        report.append("Performance by Dataset:")
        report.append("-" * 40)

        for dataset_type, evaluation in results.items():
            report.append(f"\n{dataset_type.upper()}:")
            report.append(f"  Queries: {evaluation.successful_queries}/{evaluation.total_queries}")
            report.append(f"  Avg Response Time: {evaluation.average_response_time:.2f}ms")

            for metric_name, value in evaluation.metrics.items():
                metric_def = self.evaluator.metrics.get(metric_name)
                if metric_def:
                    threshold = metric_def.threshold
                    status = "✅" if threshold and ((value >= threshold and metric_def.higher_is_better) or (value <= threshold and not metric_def.higher_is_better)) else "❌"
                    report.append(f"  {metric_def.name}: {value:.3f} {status}")

        # Recommendations
        report.append("\nRecommendations:")
        report.append("-" * 40)

        for dataset_type, evaluation in results.items():
            recommendations = self.generate_recommendations(evaluation)
            if recommendations:
                report.append(f"\n{dataset_type.upper()}:")
                for rec in recommendations:
                    report.append(f"  • {rec}")

        return "\n".join(report)

    def generate_recommendations(self, evaluation: DatasetEvaluation) -> List[str]:
        """Generate improvement recommendations based on evaluation results"""
        recommendations = []

        for metric_name, value in evaluation.metrics.items():
            metric_def = self.evaluator.metrics.get(metric_name)
            if metric_def and metric_def.threshold:
                if metric_def.higher_is_better and value < metric_def.threshold:
                    if metric_name == "answer_relevancy":
                        recommendations.append("Improve answer relevance through better prompt engineering")
                    elif metric_name == "faithfulness":
                        recommendations.append("Enhance context quality and retrieval accuracy")
                    elif metric_name == "context_relevancy":
                        recommendations.append("Optimize search and retrieval algorithms")
                elif not metric_def.higher_is_better and value > metric_def.threshold:
                    if metric_name == "response_time":
                        recommendations.append("Optimize response time through caching and parallel processing")

        if evaluation.successful_queries < evaluation.total_queries * 0.9:
            recommendations.append("Improve system reliability to handle edge cases")

        return recommendations

def main():
    """Main execution function"""
    print("🔍 RAG System Evaluation Framework")
    print("=" * 50)

    runner = EvaluationRunner()

    # Authenticate
    print("\n🔐 Authenticating with RAG system...")
    if not runner.evaluator.authenticate():
        print("❌ Authentication failed. Please check if the RAG system is running.")
        return

    print("✅ Authentication successful")

    # Run evaluations
    print("\n📊 Running evaluations on all datasets...")
    results = runner.run_all_evaluations()

    if not results:
        print("❌ No datasets found for evaluation. Please run dataset integration first.")
        return

    # Generate summary report
    print("\n📋 Generating summary report...")
    summary = runner.generate_summary_report(results)

    # Save summary report
    summary_path = Path("evaluation/summary_report.txt")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, 'w') as f:
        f.write(summary)

    print("\n" + summary)
    print(f"\n✅ Evaluation complete! Reports saved to: evaluation/")
    print("📊 Visualizations saved to: evaluation/plots/")

if __name__ == "__main__":
    main()