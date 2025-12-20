"""
Comprehensive test suite for the enhanced multi-agent search service v2.
Tests agent performance, collaboration, and quality metrics.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
import json

from backend.src.services.multi_agent_search_service_v2 import (
    MultiAgentSearchServiceV2,
    AgentType,
    WorkflowType,
    AgentTask,
    AgentExecution,
    MultiAgentSearchResult
)
from backend.src.models.search_schemas import SearchType


class TestMultiAgentSearchServiceV2:
    """Test suite for enhanced multi-agent search service"""

    @pytest.fixture
    def service(self):
        """Create service instance for testing"""
        with patch('backend.src.services.multi_agent_search_service_v2.CREWAI_AVAILABLE', True):
            service = MultiAgentSearchServiceV2()
            return service

    @pytest.fixture
    def mock_search_results(self):
        """Mock search results for testing"""
        from backend.src.models.search_schemas import SearchResult, SourceType

        return [
            SearchResult(
                id="1",
                title="Test Document 1",
                content_preview="This is a test document about machine learning algorithms...",
                relevance_score=0.95,
                source_type=SourceType.DOCUMENT,
                metadata={"entities": ["machine learning", "algorithms"], "date": "2024-01-01"}
            ),
            SearchResult(
                id="2",
                title="Test Document 2",
                content_preview="Another document discussing artificial intelligence applications...",
                relevance_score=0.87,
                source_type=SourceType.DOCUMENT,
                metadata={"entities": ["artificial intelligence", "applications"], "date": "2024-01-15"}
            )
        ]

    @pytest.mark.asyncio
    async def test_query_analysis(self, service):
        """Test query analysis functionality"""
        # Test simple query
        analysis = await service._analyze_query("machine learning", WorkflowType.FACTUAL_LOOKUP)

        assert analysis['original_query'] == "machine learning"
        assert analysis['complexity'] == 'simple'
        assert analysis['keywords'] == ['machine', 'learning']
        assert analysis['refined_query'] == "machine learning"

        # Test complex query
        complex_query = "Explain why machine learning algorithms are effective in predicting outcomes"
        analysis = await service._analyze_query(complex_query, WorkflowType.REASONING)

        assert analysis['complexity'] == 'complex'
        assert analysis['intent'] == 'question'
        assert 'deep_analysis' in analysis['optimizations']
        assert len(analysis['expanded_queries']) > 0

    @pytest.mark.asyncio
    async def test_workflow_task_creation(self, service):
        """Test workflow-specific task creation"""
        query = "Compare neural networks and decision trees"
        analysis = {
            'workflow_type': WorkflowType.COMPARATIVE,
            'complexity': 'moderate',
            'intent': 'comparative',
            'domain': 'technology',
            'entities': ['neural networks', 'decision trees'],
            'keywords': ['compare', 'neural', 'networks', 'decision', 'trees']
        }

        tasks = service._create_workflow_tasks(query, analysis, "user1", "org1")

        # Verify core tasks are created
        task_ids = [task.task_id for task in tasks]
        assert 'context_analysis' in task_ids
        assert 'query_understanding' in task_ids
        assert 'content_retrieval' in task_ids
        assert 'answer_synthesis' in task_ids

        # Check workflow-specific tasks
        comparative_tasks = [t for t in tasks if t.workflow_type == WorkflowType.COMPARATIVE]
        assert len(comparative_tasks) > 0

    @pytest.mark.asyncio
    async def test_intelligent_task_selection(self, service):
        """Test intelligent task selection based on query analysis"""
        # Create sample tasks
        tasks = [
            AgentTask(task_id="context_analysis", agent_type=AgentType.CONTEXT_ANALYSIS),
            AgentTask(task_id="query_understanding", agent_type=AgentType.QUERY_UNDERSTANDING),
            AgentTask(task_id="content_retrieval", agent_type=AgentType.RETRIEVAL),
            AgentTask(task_id="graph_navigation", agent_type=AgentType.GRAPH_NAVIGATION),
            AgentTask(task_id="quality_assurance", agent_type=AgentType.QUALITY_ASSURANCE),
            AgentTask(task_id="result_enrichment", agent_type=AgentType.RESULT_ENRICHMENT)
        ]

        # Test simple query selection
        query_analysis = {
            'complexity': 'simple',
            'workflow_type': WorkflowType.FACTUAL_LOOKUP
        }
        selected = service._intelligent_task_selection(tasks, 3, query_analysis)

        # Should include core tasks
        selected_ids = [t.task_id for t in selected]
        assert 'context_analysis' in selected_ids
        assert 'query_understanding' in selected_ids
        assert 'content_retrieval' in selected_ids
        assert len(selected) <= 3

        # Test complex query selection
        query_analysis = {
            'complexity': 'complex',
            'workflow_type': WorkflowType.REASONING
        }
        selected = service._intelligent_task_selection(tasks, 4, query_analysis)

        # Should include additional tasks for complexity
        selected_ids = [t.task_id for t in selected]
        assert 'graph_navigation' in selected_ids or 'quality_assurance' in selected_ids

    @pytest.mark.asyncio
    async def test_enhanced_fallback_search(self, service, mock_search_results):
        """Test enhanced fallback search functionality"""
        with patch('backend.src.services.multi_agent_search_service_v2.hybrid_search_service') as mock_service:
            # Setup mock response
            mock_response = Mock()
            mock_response.results = mock_search_results
            mock_service.search.return_value = mock_response

            # Execute fallback search
            result = await service._enhanced_fallback_search(
                "test query",
                "user1",
                "org1"
            )

            # Verify result structure
            assert isinstance(result, MultiAgentSearchResult)
            assert result.original_query == "test query"
            assert result.refined_query == "test query"
            assert len(result.agent_executions) == 1
            assert result.agent_executions[0].agent_type == AgentType.RETRIEVAL
            assert result.metadata.get('fallback_mode') == True
            assert result.confidence_score == 0.75

            # Verify answer generation
            assert "## Search Results for 'test query'" in result.synthesized_answer
            assert "Total Results Found" in result.synthesized_answer

    @pytest.mark.asyncio
    async def test_agent_metrics_update(self, service):
        """Test agent metrics updating after execution"""
        # Create mock executions
        executions = [
            AgentExecution(
                task_id="test1",
                agent_type=AgentType.RETRIEVAL,
                execution_time=25.0,
                success=True,
                result={"output": "Test result"},
                confidence_score=0.85
            ),
            AgentExecution(
                task_id="test2",
                agent_type=AgentType.RETRIEVAL,
                execution_time=35.0,
                success=False,
                result={},
                error_message="Test error",
                confidence_score=0.0
            ),
            AgentExecution(
                task_id="test3",
                agent_type=AgentType.QUERY_UNDERSTANDING,
                execution_time=15.0,
                success=True,
                result={"output": "Query analysis"},
                confidence_score=0.90
            )
        ]

        # Update metrics
        service._update_agent_metrics(executions)

        # Verify retrieval agent metrics
        retrieval_metrics = service.agent_metrics[AgentType.RETRIEVAL]
        assert retrieval_metrics.total_executions == 2
        assert retrieval_metrics.successful_executions == 1
        assert retrieval_metrics.average_execution_time == 30.0  # (25 + 35) / 2
        assert retrieval_metrics.confidence_score == 0.425  # (0.85 + 0.0) / 2
        assert retrieval_metrics.error_count == 1

        # Verify query agent metrics
        query_metrics = service.agent_metrics[AgentType.QUERY_UNDERSTANDING]
        assert query_metrics.total_executions == 1
        assert query_metrics.successful_executions == 1
        assert query_metrics.average_execution_time == 15.0

    @pytest.mark.asyncio
    async def test_enhanced_synthesis(self, service):
        """Test enhanced answer synthesis"""
        # Create mock executions
        executions = [
            AgentExecution(
                task_id="context",
                agent_type=AgentType.CONTEXT_ANALYSIS,
                success=True,
                result={"output": "This query is about machine learning technology"}
            ),
            AgentExecution(
                task_id="retrieval",
                agent_type=AgentType.RETRIEVAL,
                success=True,
                result={"output": "Found 5 relevant documents about ML algorithms"}
            ),
            AgentExecution(
                task_id="synthesis",
                agent_type=AgentType.ANSWER_SYNTHESIS,
                success=True,
                result={"output": "Machine learning algorithms are effective because..."}
            )
        ]

        analysis = {
            'complexity': 'moderate',
            'workflow_type': WorkflowType.REASONING
        }

        # Test synthesis with dedicated synthesis agent
        result = await service._enhanced_synthesis("ML algorithms", executions, analysis)
        assert result == "Machine learning algorithms are effective because..."

        # Test synthesis without dedicated synthesis agent
        executions_no_synthesis = executions[:2]
        result = await service._enhanced_synthesis("ML algorithms", executions_no_synthesis, analysis)
        assert "## Analysis for 'ML algorithms'" in result
        assert "### Context Analysis" in result
        assert "### Key Findings" in result

    @pytest.mark.asyncio
    async def test_quality_metrics_generation(self, service):
        """Test enhanced quality metrics generation"""
        # Create mock executions
        executions = [
            AgentExecution(
                task_id="test1",
                agent_type=AgentType.RETRIEVAL,
                execution_time=20.0,
                success=True,
                confidence_score=0.8,
                metadata={"estimated_duration": 25.0},
                quality_indicators={"execution_efficiency": 1.0, "output_length_score": 0.9}
            ),
            AgentExecution(
                task_id="test2",
                agent_type=AgentType.QUERY_UNDERSTANDING,
                execution_time=15.0,
                success=True,
                confidence_score=0.9,
                metadata={"estimated_duration": 20.0},
                quality_indicators={"execution_efficiency": 1.0, "output_length_score": 0.95}
            )
        ]

        analysis = {
            'complexity': 'moderate',
            'workflow_type': WorkflowType.FACTUAL_LOOKUP
        }

        metrics = await service._generate_enhanced_quality_metrics(executions, analysis)

        # Verify key metrics
        assert metrics["agent_success_rate"] == 1.0  # Both succeeded
        assert metrics["total_agents_used"] == 2
        assert metrics["successful_agents"] == 2
        assert metrics["average_confidence"] == 0.85  # (0.8 + 0.9) / 2
        assert metrics["query_complexity_score"] == 0.6  # moderate
        assert metrics["workflow_effectiveness"] == 0.8  # all succeeded

    def test_workflow_recommendations(self, service):
        """Test workflow recommendation system"""
        # Test comparative query
        recommendations = service.get_workflow_recommendations("Compare Python vs JavaScript")
        assert recommendations["recommended_workflow"] == WorkflowType.COMPARATIVE
        assert AgentType.CONTEXT_ANALYSIS in recommendations["suggested_agents"]
        assert recommendations["estimated_duration"] > 60  # Base time for comparative

        # Test reasoning query
        recommendations = service.get_workflow_recommendations("Explain why the sky is blue")
        assert recommendations["recommended_workflow"] == WorkflowType.REASONING
        assert AgentType.QUALITY_ASSURANCE in recommendations["suggested_agents"]

        # Test simple query
        recommendations = service.get_workflow_recommendations("machine learning")
        assert recommendations["recommended_workflow"] == WorkflowType.FACTUAL_LOOKUP
        assert "Add more context" in recommendations["optimization_tips"]

    @pytest.mark.asyncio
    async def test_performance_tracking(self, service):
        """Test performance tracking and learning"""
        # Simulate query execution
        analysis = {
            'complexity': 'moderate',
            'workflow_type': WorkflowType.REASONING
        }
        executions = [
            AgentExecution(
                task_id="test1",
                agent_type=AgentType.RETRIEVAL,
                execution_time=25.0,
                success=True,
                confidence_score=0.8
            )
        ]

        await service._update_learning("test query", analysis, executions, 50.0)

        # Verify learning data was stored
        assert len(service.query_history) == 1
        learning_data = service.query_history[0]
        assert learning_data["query"] == "test query"
        assert learning_data["execution_time"] == 50.0
        assert learning_data["success_rate"] == 1.0
        assert "agent_performance" in learning_data

        # Test history limit
        for i in range(1005):
            await service._update_learning(f"query_{i}", analysis, executions, 50.0)

        assert len(service.query_history) == 1000  # Should be limited

    def test_agent_performance_report(self, service):
        """Test agent performance report generation"""
        # Update some metrics
        service.agent_metrics[AgentType.RETRIEVAL].total_executions = 100
        service.agent_metrics[AgentType.RETRIEVAL].successful_executions = 95
        service.agent_metrics[AgentType.RETRIEVAL].average_execution_time = 25.5

        # Generate report
        report = service.get_agent_performance_report()

        # Verify report structure
        assert "timestamp" in report
        assert "crewai_available" in report
        assert "agent_metrics" in report
        assert "total_queries_processed" in report

        # Verify retrieval agent metrics
        retrieval_metrics = report["agent_metrics"]["retrieval"]
        assert retrieval_metrics["total_executions"] == 100
        assert retrieval_metrics["success_rate"] == 0.95
        assert retrieval_metrics["average_execution_time"] == 25.5

    @pytest.mark.asyncio
    async def test_error_handling(self, service):
        """Test error handling in various scenarios"""
        # Test timeout handling
        task = AgentTask(
            task_id="timeout_test",
            agent_type=AgentType.RETRIEVAL,
            estimated_duration=1.0
        )

        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            execution = await service._execute_enhanced_task(task)

            assert execution.success == False
            assert "timed out" in execution.error_message.lower()
            assert execution.metadata.get("timeout") == True

        # Test CrewAI unavailable
        with patch('backend.src.services.multi_agent_search_service_v2.CREWAI_AVAILABLE', False):
            service_no_crewai = MultiAgentSearchServiceV2()
            result = await service_no_crewai.orchestrate_search(
                "test query",
                "user1",
                "org1"
            )

            assert result.metadata.get("fallback_mode") == True
            assert len(result.agent_executions) == 1

    @pytest.mark.asyncio
    async def test_collaboration_score_calculation(self, service):
        """Test enhanced collaboration score calculation"""
        # Test single agent
        executions = [
            AgentExecution(
                task_id="test1",
                agent_type=AgentType.RETRIEVAL,
                success=True,
                execution_time=20.0,
                metadata={"estimated_duration": 25.0}
            )
        ]
        score = service._calculate_enhanced_collaboration_score(executions)
        assert score == 0.5  # Minimum for single agent

        # Test multiple successful agents
        executions = [
            AgentExecution(
                task_id="test1",
                agent_type=AgentType.RETRIEVAL,
                success=True,
                execution_time=20.0,
                metadata={"estimated_duration": 25.0}
            ),
            AgentExecution(
                task_id="test2",
                agent_type=AgentType.QUERY_UNDERSTANDING,
                success=True,
                execution_time=15.0,
                metadata={"estimated_duration": 20.0}
            ),
            AgentExecution(
                task_id="test3",
                agent_type=AgentType.SYNTHESIS,
                success=True,
                execution_time=30.0,
                metadata={"estimated_duration": 35.0}
            )
        ]
        score = service._calculate_enhanced_collaboration_score(executions)
        assert 0.7 <= score <= 1.0  # Should be high for multiple successful agents

        # Test mixed success
        executions[1].success = False
        score = service._calculate_enhanced_collaboration_score(executions)
        assert score < 0.7  # Should be lower with failures

    @pytest.mark.asyncio
    async def test_complete_workflow_integration(self, service, mock_search_results):
        """Test complete workflow integration"""
        with patch.object(service, '_execute_agent_tasks_v2') as mock_execute, \
             patch.object(service, '_enhanced_fallback_search') as mock_fallback:

            # Setup mock executions
            mock_executions = [
                AgentExecution(
                    task_id="context",
                    agent_type=AgentType.CONTEXT_ANALYSIS,
                    success=True,
                    result={"output": "Context analysis complete"},
                    execution_time=15.0,
                    confidence_score=0.9
                ),
                AgentExecution(
                    task_id="query",
                    agent_type=AgentType.QUERY_UNDERSTANDING,
                    success=True,
                    result={"output": "Query understood and optimized"},
                    execution_time=20.0,
                    confidence_score=0.85
                ),
                AgentExecution(
                    task_id="retrieval",
                    agent_type=AgentType.RETRIEVAL,
                    success=True,
                    result={"output": "Relevant documents found"},
                    execution_time=25.0,
                    confidence_score=0.8
                )
            ]
            mock_execute.return_value = mock_executions

            # Execute full orchestration
            result = await service.orchestrate_search(
                "How do neural networks learn?",
                "user1",
                "org1",
                workflow_type=WorkflowType.REASONING,
                max_agents=4
            )

            # Verify complete result
            assert isinstance(result, MultiAgentSearchResult)
            assert result.original_query == "How do neural networks learn?"
            assert result.workflow_type == WorkflowType.REASONING
            assert len(result.agent_executions) == 3
            assert result.confidence_score > 0.5
            assert "agents_used" in result.metadata
            assert "collaboration_score" in result.metadata
            assert len(result.quality_metrics) > 0

    def test_tool_enhancements(self, service):
        """Test enhanced tool functionality"""
        # Test enhanced search tool
        search_tool = service.agent_tools["search"]
        assert search_tool.name == "enhanced_hybrid_search"
        assert search_tool._cache == {}  # Cache initialized

        # Test enhanced knowledge graph tool
        kg_tool = service.agent_tools["knowledge_graph"]
        assert kg_tool.name == "enhanced_knowledge_graph"
        assert "relationship discovery" in kg_tool.description

    @pytest.mark.asyncio
    async def test_concurrent_execution(self, service):
        """Test concurrent task execution"""
        tasks = [
            AgentTask(
                task_id=f"task_{i}",
                agent_type=AgentType.RETRIEVAL if i % 2 == 0 else AgentType.QUERY_UNDERSTANDING,
                estimated_duration=30.0
            )
            for i in range(6)
        ]

        with patch.object(service, '_execute_enhanced_task') as mock_execute:
            # Mock successful execution
            mock_execute.return_value = AgentExecution(
                task_id="mock",
                agent_type=AgentType.RETRIEVAL,
                success=True,
                execution_time=20.0
            )

            executions = await service._execute_agent_tasks_v2(tasks, timeout=60.0)

            # Should execute all tasks in parallel batches
            assert len(executions) == 6
            # Should be called for each task
            assert mock_execute.call_count == 6


class TestAgentPerformanceBenchmarks:
    """Performance benchmarking for agents"""

    @pytest.fixture
    def benchmark_service(self):
        """Create service for benchmarking"""
        with patch('backend.src.services.multi_agent_search_service_v2.CREWAI_AVAILABLE', True):
            return MultiAgentSearchServiceV2()

    @pytest.mark.asyncio
    async def test_query_throughput(self, benchmark_service):
        """Test query throughput performance"""
        queries = [
            "What is machine learning?",
            "Explain deep learning algorithms",
            "Compare supervised and unsupervised learning",
            "How do neural networks work?",
            "What is overfitting in ML?"
        ]

        start_time = time.time()

        # Mock execution to avoid actual agent calls
        with patch.object(benchmark_service, '_execute_agent_tasks_v2') as mock_execute:
            mock_execute.return_value = [
                AgentExecution(
                    task_id="mock",
                    agent_type=AgentType.RETRIEVAL,
                    success=True,
                    execution_time=20.0,
                    confidence_score=0.8
                )
            ]

            # Execute queries concurrently
            tasks = [
                benchmark_service.orchestrate_search(query, "user1", "org1")
                for query in queries
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        execution_time = time.time() - start_time
        throughput = len(queries) / execution_time

        # Verify all queries succeeded
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == len(queries)

        # Verify throughput is reasonable (should handle at least 1 query per 10 seconds)
        assert throughput >= 0.1  # 1 query per 10 seconds

    @pytest.mark.asyncio
    async def test_memory_usage(self, benchmark_service):
        """Test memory usage during operations"""
        import sys
        import gc

        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Execute many queries to populate query history
        for i in range(100):
            await benchmark_service._update_learning(
                f"test query {i}",
                {"complexity": "simple"},
                [AgentExecution(
                    task_id=f"test_{i}",
                    agent_type=AgentType.RETRIEVAL,
                    success=True,
                    execution_time=20.0
                )],
                30.0
            )

        # Check memory hasn't grown excessively
        gc.collect()
        final_objects = len(gc.get_objects())
        object_growth = final_objects - initial_objects

        # Should not grow more than 1000 objects for 100 queries
        assert object_growth < 1000

        # Verify history is properly limited
        assert len(benchmark_service.query_history) == 100

    @pytest.mark.asyncio
    async def test_cache_effectiveness(self, benchmark_service):
        """Test caching effectiveness"""
        search_tool = benchmark_service.agent_tools["search"]

        # Mock search service to avoid actual calls
        with patch('backend.src.services.multi_agent_search_service_v2.hybrid_search_service') as mock_service:
            mock_response = Mock()
            mock_response.results = []
            mock_service.search.return_value = mock_response

            # Execute same query twice
            query1 = "machine learning algorithms"
            query2 = "machine learning algorithms"  # Same query

            result1 = search_tool._run(query1)
            result2 = search_tool._run(query2)

            # Should only call service once due to caching
            assert mock_service.search.call_count == 1
            assert result1 == result2

            # Different query should call service again
            search_tool._run("deep learning")
            assert mock_service.search.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])