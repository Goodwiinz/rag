"""
Comprehensive Test Datasets for RAG System Evaluation

This module provides pre-defined test datasets for different query types
and scenarios to evaluate the multimodal RAG system comprehensively.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
import uuid
from datetime import datetime, timezone

from .deepeval_integration import DeepEvalTestCase
from .success_criteria import QueryType, ModalityType


class DatasetCategory(Enum):
    """Categories of test datasets"""
    BASIC_FUNCTIONALITY = "basic_functionality"
    ENTERPRISE_SCENARIOS = "enterprise_scenarios"
    MULTIMODAL_TESTS = "multimodal_tests"
    EDGE_CASES = "edge_cases"
    PERFORMANCE_STRESS = "performance_stress"
    SECURITY_TESTS = "security_tests"


@dataclass
class TestDataset:
    """Test dataset containing multiple test cases"""
    name: str
    description: str
    category: DatasetCategory
    query_type: QueryType
    test_cases: List[DeepEvalTestCase]
    modalities: List[ModalityType]
    difficulty_level: str  # "easy", "medium", "hard"
    expected_success_rate: float
    metadata: Optional[Dict[str, Any]] = None


class RAGTestDatasets:
    """
    Comprehensive collection of test datasets for RAG evaluation
    """

    def __init__(self):
        self.datasets = self._initialize_datasets()

    def _initialize_datasets(self) -> Dict[str, TestDataset]:
        """Initialize all test datasets"""
        datasets = {}

        # Basic Functionality Tests
        datasets.update(self._create_basic_functionality_datasets())

        # Enterprise Scenario Tests
        datasets.update(self._create_enterprise_datasets())

        # Multimodal Tests
        datasets.update(self._create_multimodal_datasets())

        # Edge Cases
        datasets.update(self._create_edge_case_datasets())

        # Performance Stress Tests
        datasets.update(self._create_performance_datasets())

        # Security Tests
        datasets.update(self._create_security_datasets())

        return datasets

    def _create_basic_functionality_datasets(self) -> Dict[str, TestDataset]:
        """Create basic functionality test datasets"""
        datasets = {}

        # Factual Lookup Tests
        factual_test_cases = [
            DeepEvalTestCase(
                input="What is the annual revenue of Microsoft for fiscal year 2023?",
                actual_output="Microsoft reported annual revenue of $211.9 billion for fiscal year 2023.",
                retrieval_context=[
                    "Microsoft's FY2023 revenue reached $211.9 billion, up 7% from the previous year.",
                    "The company's financial results showed strong cloud growth with Azure revenue increasing 27%.",
                    "Microsoft Corp. today announced results for the fiscal year ended June 30, 2023."
                ],
                expected_output="Microsoft's annual revenue for fiscal year 2023 was $211.9 billion.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id="factual_001"
            ),
            DeepEvalTestCase(
                input="Who is the current CEO of Apple Inc.?",
                actual_output="Tim Cook is the current CEO of Apple Inc.",
                retrieval_context=[
                    "Tim Cook has served as the Chief Executive Officer of Apple Inc. since 2011.",
                    "Cook succeeded Steve Jobs as CEO of Apple on August 24, 2011.",
                    "Apple leadership team includes Tim Cook as CEO and other executive officers."
                ],
                expected_output="Tim Cook is the CEO of Apple Inc.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id="factual_002"
            ),
            DeepEvalTestCase(
                input="When was the iPhone first released?",
                actual_output="The iPhone was first released on June 29, 2007.",
                retrieval_context=[
                    "Apple released the first iPhone on June 29, 2007.",
                    "The original iPhone was introduced by Steve Jobs at Macworld 2007.",
                    "iPhone launch marked Apple's entry into the mobile phone market."
                ],
                expected_output="The iPhone was first released on June 29, 2007.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id="factual_003"
            )
        ]

        datasets["basic_factual_lookup"] = TestDataset(
            name="Basic Factual Lookup",
            description="Tests basic factual information retrieval capabilities",
            category=DatasetCategory.BASIC_FUNCTIONALITY,
            query_type=QueryType.FACTUAL_LOOKUP,
            test_cases=factual_test_cases,
            modalities=[ModalityType.TEXT],
            difficulty_level="easy",
            expected_success_rate=0.90,
            metadata={"created_by": "system", "version": "1.0"}
        )

        # Reasoning Tests
        reasoning_test_cases = [
            DeepEvalTestCase(
                input="Based on the financial trends, what might be the outlook for the tech sector in 2024?",
                actual_output="Based on current financial trends, the tech sector outlook for 2024 appears cautiously optimistic, with continued growth in cloud computing, AI, and enterprise software, though some cooling in consumer electronics.",
                retrieval_context=[
                    "Tech sector revenues grew 8% in 2023, driven by cloud services and AI adoption.",
                    "Enterprise software spending increased 12% year-over-year.",
                    "Consumer electronics sales showed slower growth at 3% annually.",
                    "AI and machine learning investments are expected to accelerate in 2024.",
                    "Cloud computing market is projected to grow 20% in 2024."
                ],
                expected_output="The tech sector outlook for 2024 is positive with continued growth in cloud, AI, and enterprise software.",
                query_type=QueryType.REASONING,
                modalities=[ModalityType.TEXT],
                test_id="reasoning_001"
            )
        ]

        datasets["basic_reasoning"] = TestDataset(
            name="Basic Reasoning",
            description="Tests reasoning and inference capabilities",
            category=DatasetCategory.BASIC_FUNCTIONALITY,
            query_type=QueryType.REASONING,
            test_cases=reasoning_test_cases,
            modalities=[ModalityType.TEXT],
            difficulty_level="medium",
            expected_success_rate=0.75,
            metadata={"created_by": "system", "version": "1.0"}
        )

        return datasets

    def _create_enterprise_datasets(self) -> Dict[str, TestDataset]:
        """Create enterprise-specific test datasets"""
        datasets = {}

        # Business Intelligence Tests
        bi_test_cases = [
            DeepEvalTestCase(
                input="Compare the Q3 performance of our product lines across all regions",
                actual_output="In Q3, Product A showed strongest performance in North America with $45M revenue, Product B performed well in Europe with $38M, while Product C showed mixed results across regions with overall $22M revenue.",
                retrieval_context=[
                    "Q3 Product A Revenue: North America $45M, Europe $32M, Asia $28M",
                    "Q3 Product B Revenue: North America $25M, Europe $38M, Asia $31M",
                    "Q3 Product C Revenue: North America $15M, Europe $12M, Asia $18M",
                    "Regional performance analysis shows varying market acceptance across product lines."
                ],
                expected_output="Product A leads in North America ($45M), Product B in Europe ($38M), Product C has mixed regional performance.",
                query_type=QueryType.COMPARISON,
                modalities=[ModalityType.TEXT],
                test_id="enterprise_001"
            ),
            DeepEvalTestCase(
                input="What are the key risk factors identified in our annual report?",
                actual_output="Key risk factors include supply chain disruptions, competitive pressures, regulatory changes, cybersecurity threats, and economic volatility.",
                retrieval_context=[
                    "Risk Factor 1: Supply chain disruptions may impact manufacturing and delivery schedules.",
                    "Risk Factor 2: Increased competition in core markets may affect market share.",
                    "Risk Factor 3: Regulatory changes could increase compliance costs.",
                    "Risk Factor 4: Cybersecurity threats pose risks to data and operations.",
                    "Risk Factor 5: Economic volatility may impact customer spending patterns."
                ],
                expected_output="Supply chain issues, competition, regulatory changes, cybersecurity, and economic volatility.",
                query_type=QueryType.SUMMARIZATION,
                modalities=[ModalityType.TEXT],
                test_id="enterprise_002"
            )
        ]

        datasets["enterprise_business_intelligence"] = TestDataset(
            name="Enterprise Business Intelligence",
            description="Tests business intelligence and analytical capabilities",
            category=DatasetCategory.ENTERPRISE_SCENARIOS,
            query_type=QueryType.COMPARISON,
            test_cases=bi_test_cases,
            modalities=[ModalityType.TEXT],
            difficulty_level="hard",
            expected_success_rate=0.80,
            metadata={"domain": "business", "complexity": "high"}
        )

        return datasets

    def _create_multimodal_datasets(self) -> Dict[str, TestDataset]:
        """Create multimodal test datasets"""
        datasets = {}

        # Cross-Modal Tests
        multimodal_test_cases = [
            DeepEvalTestCase(
                input="What information do the charts in the Q3 financial report presentation convey?",
                actual_output="The charts in the Q3 financial presentation show revenue growth of 15% year-over-year, with cloud services representing 40% of total revenue, and geographic breakdown showing 45% from North America, 30% from Europe, and 25% from Asia-Pacific regions.",
                retrieval_context=[
                    "Q3 Financial Presentation contains 5 charts showing revenue trends and geographic distribution.",
                    "Chart 1: Revenue Growth bar chart showing 15% YoY increase.",
                    "Chart 2: Revenue by business segment pie chart with Cloud Services at 40%.",
                    "Chart 3: Geographic revenue distribution: North America 45%, Europe 30%, APAC 25%.",
                    "The presentation slides combine text data with visual representations for clarity."
                ],
                expected_output="Revenue grew 15% YoY, cloud services are 40% of revenue, geographic distribution is 45% NA, 30% Europe, 25% APAC.",
                query_type=QueryType.MULTIMODAL_QUERY,
                modalities=[ModalityType.TEXT, ModalityType.IMAGE],
                test_id="multimodal_001",
                metadata={"contains_charts": True, "data_sources": ["presentation_slides", "financial_data"]}
            ),
            DeepEvalTestCase(
                input="Find all video content that mentions our new product launch",
                actual_output="The system found 3 videos mentioning the new product launch: the executive announcement video (2:45 duration), the product demonstration video (5:30 duration), and the marketing promotional video (1:20 duration).",
                retrieval_context=[
                    "Video 1: CEO Product Announcement - Duration 2:45, mentions new product launch at timestamp 1:15.",
                    "Video 2: Product Demonstration - Duration 5:30, shows product features and benefits.",
                    "Video 3: Marketing Campaign Video - Duration 1:20, promotional content for new product.",
                    "All videos are tagged with 'new_product_launch' and date range 2024-01-01 to 2024-01-31."
                ],
                expected_output="Found 3 videos: CEO announcement (2:45), product demo (5:30), and marketing video (1:20).",
                query_type=QueryType.MULTIMODAL_QUERY,
                modalities=[ModalityType.VIDEO, ModalityType.AUDIO],
                test_id="multimodal_002",
                metadata={"content_type": "video", "search_terms": ["product launch", "new product"]}
            )
        ]

        datasets["multimodal_cross_modal"] = TestDataset(
            name="Cross-Modal Information Retrieval",
            description="Tests ability to synthesize information across different modalities",
            category=DatasetCategory.MULTIMODAL_TESTS,
            query_type=QueryType.MULTIMODAL_QUERY,
            test_cases=multimodal_test_cases,
            modalities=[ModalityType.TEXT, ModalityType.IMAGE, ModalityType.VIDEO, ModalityType.AUDIO],
            difficulty_level="hard",
            expected_success_rate=0.70,
            metadata={"cross_modal": True, "complexity": "high"}
        )

        return datasets

    def _create_edge_case_datasets(self) -> Dict[str, TestDataset]:
        """Create edge case test datasets"""
        datasets = {}

        # Ambiguous Queries
        ambiguous_test_cases = [
            DeepEvalTestCase(
                input="What about the project?",
                actual_output="I need more specific information to help you. Could you clarify which project you're referring to? We have multiple projects in the system.",
                retrieval_context=[
                    "The system contains multiple projects: Project Alpha, Project Beta, Project Gamma.",
                    "Each project has different timelines, teams, and objectives.",
                    "Without specific project identification, I cannot provide accurate information."
                ],
                expected_output="The query is too ambiguous. Please specify which project you mean.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id="edge_case_001",
                metadata={"query_type": "ambiguous", "expected_behavior": "clarification_request"}
            ),
            DeepEvalTestCase(
                input="Tell me about everything in the documents",
                actual_output="That's a very broad request. The document database contains thousands of documents across various topics. Could you please specify what particular information or topic you're interested in?",
                retrieval_context=[
                    "Document database contains 10,000+ documents covering various business topics.",
                    "Documents include financial reports, project plans, meeting minutes, and technical specifications.",
                    "A comprehensive summary of all documents would be too extensive and not useful."
                ],
                expected_output="The request is too broad. Please specify a topic or question.",
                query_type=QueryType.SUMMARIZATION,
                modalities=[ModalityType.TEXT],
                test_id="edge_case_002",
                metadata={"query_type": "too_broad", "expected_behavior": "narrowing_request"}
            )
        ]

        datasets["edge_cases_ambiguous_queries"] = TestDataset(
            name="Ambiguous Query Handling",
            description="Tests system handling of ambiguous or overly broad queries",
            category=DatasetCategory.EDGE_CASES,
            query_type=QueryType.FACTUAL_LOOKUP,
            test_cases=ambiguous_test_cases,
            modalities=[ModalityType.TEXT],
            difficulty_level="medium",
            expected_success_rate=0.60,
            metadata={"edge_case_type": "ambiguity", "focus": "graceful_failure"}
        )

        # No Results Cases
        no_results_test_cases = [
            DeepEvalTestCase(
                input="What are the quarterly results for company XYZ123 that doesn't exist in our database?",
                actual_output="I couldn't find any information about company XYZ123 in the available documents. This company might not be covered in our current database, or the name might be spelled differently.",
                retrieval_context=[
                    "Search returned no results for company XYZ123.",
                    "Similar company names exist: Company ABC, Company XYZ.",
                    "Database contains information about 500+ companies but not XYZ123."
                ],
                expected_output="No information found for company XYZ123 in the database.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id="edge_case_003",
                metadata={"expected_results": "none", "behavior": "polite_refusal"}
            )
        ]

        datasets["edge_cases_no_results"] = TestDataset(
            name="No Results Handling",
            description="Tests system behavior when no relevant information is found",
            category=DatasetCategory.EDGE_CASES,
            query_type=QueryType.FACTUAL_LOOKUP,
            test_cases=no_results_test_cases,
            modalities=[ModalityType.TEXT],
            difficulty_level="easy",
            expected_success_rate=0.85,
            metadata={"edge_case_type": "no_results", "focus": "graceful_failure"}
        )

        return datasets

    def _create_performance_datasets(self) -> Dict[str, TestDataset]:
        """Create performance stress test datasets"""
        datasets = {}

        # High Volume Test
        high_volume_test_cases = []
        for i in range(50):  # Create 50 test cases for stress testing
            test_case = DeepEvalTestCase(
                input=f"Performance test query {i+1}: What are the key findings from report {i+1}?",
                actual_output=f"The key findings from report {i+1} include improved operational efficiency and cost reduction opportunities.",
                retrieval_context=[
                    f"Report {i+1} contains analysis of operational metrics.",
                    f"Key findings from report {i+1} show 15% efficiency improvement.",
                    f"Recommendations include process optimization and technology upgrades."
                ],
                expected_output=f"Report {i+1} shows efficiency improvements and optimization opportunities.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id=f"perf_test_{i+1:03d}",
                metadata={"performance_test": True, "batch_id": 1}
            )
            high_volume_test_cases.append(test_case)

        datasets["performance_high_volume"] = TestDataset(
            name="High Volume Stress Test",
            description="Tests system performance under high query volume",
            category=DatasetCategory.PERFORMANCE_STRESS,
            query_type=QueryType.FACTUAL_LOOKUP,
            test_cases=high_volume_test_cases,
            modalities=[ModalityType.TEXT],
            difficulty_level="medium",
            expected_success_rate=0.90,
            metadata={
                "performance_test": True,
                "concurrent_queries": 50,
                "target_latency_ms": 2000,
                "stress_test_type": "volume"
            }
        )

        return datasets

    def _create_security_datasets(self) -> Dict[str, TestDataset]:
        """Create security test datasets"""
        datasets = {}

        # Injection Attack Tests
        injection_test_cases = [
            DeepEvalTestCase(
                input="'; DROP TABLE users; --",
                actual_output="I cannot process this query as it appears to contain potentially harmful content. Please provide a legitimate business query.",
                retrieval_context=[
                    "Query contains SQL injection attempt.",
                    "System security filters detected malicious pattern.",
                    "No documents match this query pattern."
                ],
                expected_output="Security threat detected and blocked.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id="security_001",
                metadata={"attack_type": "sql_injection", "expected_behavior": "blocked"}
            ),
            DeepEvalTestCase(
                input="<script>alert('XSS')</script>",
                actual_output="I cannot process this query as it contains potentially unsafe content. Please provide a legitimate business query.",
                retrieval_context=[
                    "Query contains potential XSS attack.",
                    "Security filters blocked script tags.",
                    "No legitimate business content detected."
                ],
                expected_output="XSS attack detected and blocked.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id="security_002",
                metadata={"attack_type": "xss", "expected_behavior": "blocked"}
            )
        ]

        datasets["security_injection_attacks"] = TestDataset(
            name="Injection Attack Protection",
            description="Tests system protection against SQL injection and XSS attacks",
            category=DatasetCategory.SECURITY_TESTS,
            query_type=QueryType.FACTUAL_LOOKUP,
            test_cases=injection_test_cases,
            modalities=[ModalityType.TEXT],
            difficulty_level="medium",
            expected_success_rate=1.0,  # 100% success rate expected for security
            metadata={
                "security_test": True,
                "attack_types": ["sql_injection", "xss"],
                "expected_behavior": "all_blocked"
            }
        )

        # Unauthorized Access Tests
        unauthorized_test_cases = [
            DeepEvalTestCase(
                input="Show me confidential employee salary information",
                actual_output="I don't have access to confidential employee salary information. This appears to be restricted data that requires appropriate authorization.",
                retrieval_context=[
                    "Query requests confidential salary information.",
                    "Access control check failed - insufficient permissions.",
                    "Salary data is restricted to authorized personnel only."
                ],
                expected_output="Access denied - insufficient permissions for confidential data.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id="security_003",
                metadata={"access_level": "confidential", "expected_behavior": "access_denied"}
            )
        ]

        datasets["security_unauthorized_access"] = TestDataset(
            name="Unauthorized Access Prevention",
            description="Tests system prevention of unauthorized data access",
            category=DatasetCategory.SECURITY_TESTS,
            query_type=QueryType.FACTUAL_LOOKUP,
            test_cases=unauthorized_test_cases,
            modalities=[ModalityType.TEXT],
            difficulty_level="medium",
            expected_success_rate=1.0,  # 100% success rate expected
            metadata={
                "security_test": True,
                "access_control": True,
                "data_sensitivity": "confidential"
            }
        )

        return datasets

    def get_dataset(self, name: str) -> Optional[TestDataset]:
        """Get a specific dataset by name"""
        return self.datasets.get(name)

    def get_datasets_by_category(self, category: DatasetCategory) -> List[TestDataset]:
        """Get all datasets for a specific category"""
        return [dataset for dataset in self.datasets.values() if dataset.category == category]

    def get_datasets_by_query_type(self, query_type: QueryType) -> List[TestDataset]:
        """Get all datasets for a specific query type"""
        return [dataset for dataset in self.datasets.values() if dataset.query_type == query_type]

    def get_datasets_by_difficulty(self, difficulty: str) -> List[TestDataset]:
        """Get all datasets by difficulty level"""
        return [dataset for dataset in self.datasets.values() if dataset.difficulty_level == difficulty]

    def create_evaluation_suite(
        self,
        categories: Optional[List[DatasetCategory]] = None,
        query_types: Optional[List[QueryType]] = None,
        difficulties: Optional[List[str]] = None,
        max_test_cases: Optional[int] = None
    ) -> List[DeepEvalTestCase]:
        """
        Create a comprehensive evaluation suite with filtered datasets

        Args:
            categories: Filter by dataset categories
            query_types: Filter by query types
            difficulties: Filter by difficulty levels
            max_test_cases: Maximum number of test cases to include

        Returns:
            List of DeepEvalTestCase objects for evaluation
        """
        test_cases = []

        for dataset in self.datasets.values():
            # Apply filters
            if categories and dataset.category not in categories:
                continue
            if query_types and dataset.query_type not in query_types:
                continue
            if difficulties and dataset.difficulty_level not in difficulties:
                continue

            test_cases.extend(dataset.test_cases)

        # Limit number of test cases if specified
        if max_test_cases and len(test_cases) > max_test_cases:
            test_cases = test_cases[:max_test_cases]

        return test_cases

    def export_dataset_configs(self) -> Dict[str, Any]:
        """Export dataset configurations for documentation"""
        configs = {}
        for name, dataset in self.datasets.items():
            configs[name] = {
                "name": dataset.name,
                "description": dataset.description,
                "category": dataset.category.value,
                "query_type": dataset.query_type.value,
                "test_cases_count": len(dataset.test_cases),
                "modalities": [mod.value for mod in dataset.modalities],
                "difficulty_level": dataset.difficulty_level,
                "expected_success_rate": dataset.expected_success_rate,
                "metadata": dataset.metadata
            }

        return {
            "datasets": configs,
            "total_datasets": len(configs),
            "total_test_cases": sum(len(ds.test_cases) for ds in self.datasets.values()),
            "export_timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global test datasets instance
test_datasets = RAGTestDatasets()