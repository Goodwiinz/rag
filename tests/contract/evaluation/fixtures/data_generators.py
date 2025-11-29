"""
Data generators for evaluation contract tests
"""

import uuid
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from faker import Faker

fake = Faker()


class EvaluationDataGenerator:
    """Generate realistic evaluation test data"""

    def __init__(self):
        self.queries = [
            "What are the key principles of machine learning?",
            "How does natural language processing work?",
            "Explain the concept of deep learning neural networks",
            "What are the main challenges in computer vision?",
            "Describe the applications of artificial intelligence in healthcare",
            "How do recommendation systems work?",
            "What is the difference between supervised and unsupervised learning?",
            "Explain the role of feature engineering in ML models",
            "How are reinforcement learning algorithms trained?",
            "What are the ethical considerations in AI development?"
        ]

        self.reference_answers = [
            "Machine learning involves training algorithms to find patterns in data and make predictions without explicit programming.",
            "NLP enables computers to understand and process human language through techniques like tokenization, embedding, and transformer models.",
            "Deep learning uses multi-layered neural networks to automatically learn hierarchical features from raw data.",
            "Computer vision faces challenges in object detection, image segmentation, and handling variations in lighting and perspective.",
            "AI in healthcare includes diagnostic imaging, drug discovery, personalized treatment plans, and predictive analytics.",
            "Recommendation systems use collaborative filtering, content-based filtering, or hybrid approaches to suggest relevant items.",
            "Supervised learning uses labeled data while unsupervised learning finds patterns in unlabeled data without predefined outputs.",
            "Feature engineering transforms raw data into meaningful features that improve model performance and interpretability.",
            "Reinforcement learning trains agents through reward-based feedback in an environment using trial and error.",
            "AI ethics involves addressing bias, transparency, accountability, privacy, and the societal impact of automated systems."
        ]

        self.contexts = [
            [
                "Machine learning is a subset of artificial intelligence that focuses on algorithms that can learn from data.",
                "The three main types of machine learning are supervised, unsupervised, and reinforcement learning.",
                "Training data is crucial for developing accurate machine learning models."
            ],
            [
                "Natural Language Processing combines computational linguistics with statistical and machine learning models.",
                "Modern NLP heavily relies on transformer architectures like BERT and GPT.",
                "Tokenization is the first step in processing text for NLP tasks."
            ],
            [
                "Deep learning models consist of multiple layers that progressively extract higher-level features.",
                "Backpropagation is used to train deep neural networks by adjusting weights based on prediction errors.",
                "Activation functions introduce non-linearity into neural networks."
            ],
            [
                "Computer vision tasks include image classification, object detection, and semantic segmentation.",
                "Convolutional Neural Networks are the foundation of modern computer vision.",
                "Data augmentation helps improve model generalization in vision tasks."
            ],
            [
                "AI applications in healthcare range from diagnostic imaging to drug discovery and personalized medicine.",
                "Machine learning models can detect patterns in medical data that humans might miss.",
                "Ethical considerations include patient privacy and algorithmic bias."
            ]
        ]

    def generate_evaluation_request(
        self,
        job_name: Optional[str] = None,
        evaluation_type: str = "rag_triad",
        question_count: Optional[int] = None,
        include_references: bool = True,
        include_contexts: bool = True
    ) -> Dict[str, Any]:
        """Generate evaluation request data"""
        if question_count is None:
            question_count = random.randint(1, 10)

        selected_queries = random.sample(self.queries, min(question_count, len(self.queries)))

        request_data = {
            "name": job_name or f"Evaluation Job {fake.uuid4()}",
            "description": fake.sentence(),
            "evaluation_type": evaluation_type,
            "questions": selected_queries[:question_count],
            "search_type": random.choice(["vector", "graph", "hybrid"]),
            "search_limit": random.randint(3, 10)
        }

        if include_references:
            request_data["reference_answers"] = self.reference_answers[:question_count]

        if include_contexts:
            request_data["contexts"] = self.contexts[:question_count]

        return request_data

    def generate_batch_evaluation_request(
        self,
        query_count: Optional[int] = None,
        search_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate batch evaluation request data"""
        if query_count is None:
            query_count = random.randint(5, 20)

        return {
            "name": f"Batch Evaluation {fake.uuid4()}",
            "description": fake.paragraph(),
            "queries": random.sample(self.queries, min(query_count, len(self.queries))),
            "search_type": search_type or random.choice(["vector", "graph", "hybrid"]),
            "search_limit": random.randint(3, 10)
        }

    def generate_real_time_evaluation_request(
        self,
        include_reference: bool = True
    ) -> Dict[str, Any]:
        """Generate real-time evaluation request data"""
        query = random.choice(self.queries)
        answer = random.choice(self.reference_answers)
        context = random.choice(self.contexts)

        request_data = {
            "query": query,
            "generated_answer": answer,
            "retrieved_context": context
        }

        if include_reference:
            request_data["reference_answer"] = random.choice(self.reference_answers)

        return request_data

    def generate_comparison_request(
        self,
        baseline_job_id: Optional[str] = None,
        comparison_job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate comparison request data"""
        return {
            "name": f"Comparison {fake.uuid4()}",
            "baseline_job_id": baseline_job_id or str(uuid.uuid4()),
            "comparison_job_id": comparison_job_id or str(uuid.uuid4())
        }


class JobDataGenerator:
    """Generate evaluation job data for testing"""

    def __init__(self):
        self.statuses = [
            EvaluationStatus.PENDING.value,
            EvaluationStatus.RUNNING.value,
            EvaluationStatus.COMPLETED.value,
            EvaluationStatus.FAILED.value,
            EvaluationStatus.CANCELLED.value
        ]

        self.evaluation_types = [
            EvaluationType.ANSWER_RELEVANCY.value,
            EvaluationType.FAITHFULNESS.value,
            EvaluationType.CONTEXTUAL_RELEVANCY.value,
            EvaluationType.BATCH_EVALUATION.value,
            EvaluationType.REAL_TIME_EVALUATION.value
        ]

    def generate_job_record(
        self,
        organization_id: str,
        user_id: str,
        status: Optional[str] = None,
        evaluation_type: Optional[str] = None,
        dataset_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate evaluation job record"""
        if status is None:
            status = random.choice(self.statuses)

        if evaluation_type is None:
            evaluation_type = random.choice(self.evaluation_types)

        if dataset_size is None:
            dataset_size = random.randint(1, 100)

        now = datetime.utcnow()
        started_at = now if status in [EvaluationStatus.RUNNING.value, EvaluationStatus.COMPLETED.value, EvaluationStatus.FAILED.value] else None
        completed_at = now + timedelta(minutes=random.randint(5, 30)) if status in [EvaluationStatus.COMPLETED.value, EvaluationStatus.FAILED.value] else None
        duration = (completed_at - started_at).total_seconds() if completed_at and started_at else None

        processed_count = dataset_size if status == EvaluationStatus.COMPLETED.value else random.randint(0, dataset_size)

        return {
            "id": uuid.uuid4(),
            "name": f"Evaluation Job {fake.uuid4()}",
            "description": fake.sentence(),
            "evaluation_type": evaluation_type,
            "status": status,
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": duration,
            "parameters": {
                "search_type": random.choice(["vector", "graph", "hybrid"]),
                "search_limit": random.randint(3, 10),
                "model": "gpt-4"
            },
            "dataset_size": dataset_size,
            "processed_count": processed_count,
            "user_id": user_id,
            "organization_id": organization_id,
            "overall_score": random.uniform(0.5, 1.0) if status == EvaluationStatus.COMPLETED.value else None,
            "success_rate": random.uniform(0.6, 1.0) if status == EvaluationStatus.COMPLETED.value else None,
            "error_message": fake.sentence() if status == EvaluationStatus.FAILED.value else None,
            "created_at": now - timedelta(minutes=random.randint(1, 60))
        }

    def generate_job_summary_response(
        self,
        job_record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate job summary response data"""
        base_response = {
            "job_id": str(job_record["id"]),
            "name": job_record["name"],
            "description": job_record["description"],
            "status": job_record["status"],
            "evaluation_type": job_record["evaluation_type"],
            "dataset_size": job_record["dataset_size"],
            "processed_count": job_record["processed_count"],
            "created_at": job_record["created_at"].isoformat() if job_record["created_at"] else None,
            "started_at": job_record["started_at"].isoformat() if job_record["started_at"] else None,
            "completed_at": job_record["completed_at"].isoformat() if job_record["completed_at"] else None,
            "duration_seconds": job_record["duration_seconds"],
            "parameters": job_record["parameters"]
        }

        if job_record["status"] == EvaluationStatus.COMPLETED.value:
            base_response.update({
                "overall_score": job_record["overall_score"],
                "success_rate": job_record["success_rate"],
                "metrics_summary": {
                    "answer_relevancy": random.uniform(0.6, 0.95),
                    "faithfulness": random.uniform(0.7, 0.98),
                    "contextual_relevancy": random.uniform(0.65, 0.92)
                },
                "threshold_violations": random.randint(0, 5)
            })

        if job_record["status"] == EvaluationStatus.FAILED.value:
            base_response["error_message"] = job_record["error_message"]

        return base_response


class MetricDataGenerator:
    """Generate evaluation metric data for testing"""

    def __init__(self):
        self.metric_types = [
            MetricType.RAG_TRIAD_ANSWER_RELEVANCY.value,
            MetricType.RAG_TRIAD_FAITHFULNESS.value,
            MetricType.RAG_TRIAD_CONTEXTUAL_RELEVANCY.value,
            MetricType.RESPONSE_TIME.value,
            MetricType.HALLUCINATION_RATE.value,
            MetricType.CROSS_MODAL_COHERENCE.value,
            MetricType.PRECISION.value,
            MetricType.RECALL.value,
            MetricType.F1_SCORE.value
        ]

    def generate_metric_record(
        self,
        job_id: str,
        metric_type: Optional[str] = None,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate evaluation metric record"""
        if metric_type is None:
            metric_type = random.choice(self.metric_types)

        if query is None:
            query = fake.sentence()

        value = random.uniform(0.0, 1.0)
        threshold_min = 0.7 if "relevancy" in metric_type or "faithfulness" in metric_type else 0.5
        threshold_max = 1.0

        return {
            "id": uuid.uuid4(),
            "job_id": job_id,
            "metric_type": metric_type,
            "metric_name": metric_type.replace("_", " ").title(),
            "value": value,
            "min_value": random.uniform(0.0, value),
            "max_value": random.uniform(value, 1.0),
            "mean_value": random.uniform(0.5, 0.9),
            "threshold_min": threshold_min,
            "threshold_max": threshold_max,
            "is_threshold_violation": value < threshold_min,
            "query": query,
            "generated_answer": fake.paragraph(),
            "reference_answer": fake.paragraph(),
            "retrieved_context": fake.paragraph(),
            "metadata": {
                "calculation_method": random.choice(["deep_eval", "custom", "llm_judge"]),
                "model_used": random.choice(["gpt-4", "claude-3", "llama-2"]),
                "confidence_score": random.uniform(0.7, 0.95)
            },
            "calculation_method": random.choice(["deep_eval", "custom", "llm_judge"]),
            "model_used": random.choice(["gpt-4", "claude-3", "llama-2"]),
            "additional_data": {
                "processing_time_ms": random.randint(100, 5000),
                "token_count": random.randint(100, 2000)
            },
            "created_at": datetime.utcnow() - timedelta(minutes=random.randint(1, 60))
        }

    def generate_metrics_response(
        self,
        job_id: str,
        metric_count: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Generate metrics response data"""
        if metric_count is None:
            metric_count = random.randint(5, 20)

        metrics = []
        for _ in range(metric_count):
            metric_record = self.generate_metric_record(job_id)
            metric_response = {
                "id": str(metric_record["id"]),
                "metric_type": metric_record["metric_type"],
                "metric_name": metric_record["metric_name"],
                "value": metric_record["value"],
                "min_value": metric_record["min_value"],
                "max_value": metric_record["max_value"],
                "mean_value": metric_record["mean_value"],
                "threshold_min": metric_record["threshold_min"],
                "threshold_max": metric_record["threshold_max"],
                "is_threshold_violation": metric_record["is_threshold_violation"],
                "query": metric_record["query"],
                "calculation_method": metric_record["calculation_method"],
                "model_used": metric_record["model_used"],
                "created_at": metric_record["created_at"].isoformat()
            }
            metrics.append(metric_response)

        return metrics

    def generate_metrics_summary(
        self,
        days: int = 30,
        organization_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate metrics summary response"""
        total_metrics = random.randint(50, 500)
        threshold_violations = random.randint(5, 50)

        return {
            "period_days": days,
            "total_metrics": total_metrics,
            "metric_summary": {
                "rag_triad_answer_relevancy": {
                    "count": random.randint(20, 100),
                    "mean": random.uniform(0.7, 0.9),
                    "min": 0.3,
                    "max": 1.0,
                    "std_dev": random.uniform(0.1, 0.2)
                },
                "rag_triad_faithfulness": {
                    "count": random.randint(20, 100),
                    "mean": random.uniform(0.8, 0.95),
                    "min": 0.4,
                    "max": 1.0,
                    "std_dev": random.uniform(0.05, 0.15)
                },
                "rag_triad_contextual_relevancy": {
                    "count": random.randint(20, 100),
                    "mean": random.uniform(0.65, 0.85),
                    "min": 0.2,
                    "max": 1.0,
                    "std_dev": random.uniform(0.1, 0.25)
                }
            },
            "threshold_violations": threshold_violations,
            "average_scores": {
                "rag_triad_answer_relevancy": random.uniform(0.7, 0.9),
                "rag_triad_faithfulness": random.uniform(0.8, 0.95),
                "rag_triad_contextual_relevancy": random.uniform(0.65, 0.85)
            },
            "violation_rate": (threshold_violations / total_metrics) * 100 if total_metrics > 0 else 0
        }