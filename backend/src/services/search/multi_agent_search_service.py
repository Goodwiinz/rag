"""
Multi-Agent Search Orchestration Service using CrewAI

This service implements intelligent search orchestration using multiple specialized agents
that collaborate to improve search result quality and provide comprehensive answers.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# CrewAI imports
try:
    from crewai import Agent, Crew, Process, Task
    from crewai.tools import BaseTool
    from langchain_community.llms import OpenAI
    from langchain_openai import AzureChatOpenAI, ChatOpenAI

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    BaseTool = object  # Fallback base class
    logging.warning(
        "CrewAI not available. Multi-agent search will use fallback implementation."
    )

from src.core.config import settings
from src.core.database import get_db
from src.models.document import Document
from src.models.search_schemas import (
    SearchQuery,
    SearchResponse,
    SearchResult,
    SearchType,
)
from src.services.knowledge_graph import knowledge_graph_service

from .hybrid_search_service import hybrid_search_service
from .search_quality_service import search_quality_service

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Types of search agents"""

    RETRIEVAL = "retrieval"
    GRAPH_NAVIGATION = "graph_navigation"
    QUALITY_ASSURANCE = "quality_assurance"
    ANSWER_SYNTHESIS = "answer_synthesis"
    QUERY_UNDERSTANDING = "query_understanding"
    RESULT_ENRICHMENT = "result_enrichment"


@dataclass
class AgentTask:
    """Individual agent task definition"""

    task_id: str
    agent_type: AgentType
    description: str
    expected_output: str
    context: Dict[str, Any]
    dependencies: List[str] = None
    priority: int = 1
    estimated_duration: float = 30.0


@dataclass
class AgentExecution:
    """Execution result from an agent"""

    task_id: str
    agent_type: AgentType
    execution_time: float
    success: bool
    result: Dict[str, Any]
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class MultiAgentSearchResult:
    """Complete multi-agent search result"""

    original_query: str
    refined_query: str
    search_results: List[SearchResult]
    agent_executions: List[AgentExecution]
    synthesized_answer: str
    confidence_score: float
    execution_time: float
    quality_metrics: Dict[str, float]
    recommendations: List[str]
    metadata: Dict[str, Any]


class SearchTool(BaseTool):
    """Custom tool for search operations"""

    name: str = "hybrid_search"
    description: str = "Perform hybrid search across multiple data sources"

    def _run(self, query: str, max_results: int = 10) -> str:
        """Execute the tool"""
        try:
            search_query = SearchQuery(
                query=query, search_type=SearchType.HYBRID, limit=max_results
            )

            search_response = hybrid_search_service.search(
                search_request=search_query,
                user_id="multi_agent_user",
                organization_id="default_org",
            )

            results = []
            for result in search_response.results[:5]:  # Limit for context
                results.append(
                    {
                        "title": result.title,
                        "content": result.content_preview,
                        "score": result.relevance_score,
                        "source": result.source_type.value,
                    }
                )

            return json.dumps(results, indent=2)

        except Exception as e:
            logger.error(f"Search tool error: {e}")
            return json.dumps({"error": str(e)})


class KnowledgeGraphTool(BaseTool):
    """Custom tool for knowledge graph operations"""

    name: str = "knowledge_graph"
    description: str = "Query the knowledge graph for entity relationships"

    def _run(self, entity_name: str, relationship_type: str = None) -> str:
        """Execute the tool"""
        try:
            # Simple graph query
            query = f"""
            MATCH (e1:Entity {{name: '{entity_name}'}})-[r]->(e2:Entity)
            RETURN e1.name as source, type(r) as relationship, e2.name as target
            LIMIT 10
            """

            if relationship_type:
                query = f"""
                MATCH (e1:Entity {{name: '{entity_name}'}})-[r:{relationship_type}]->(e2:Entity)
                RETURN e1.name as source, type(r) as relationship, e2.name as target
                LIMIT 10
                """

            results = knowledge_graph_service.query_graph(query)
            return json.dumps(results, indent=2)

        except Exception as e:
            logger.error(f"Knowledge graph tool error: {e}")
            return json.dumps({"error": str(e)})


class MultiAgentSearchService:
    """Service for orchestrating multi-agent search workflows"""

    def __init__(self):
        self.agent_tools = {
            "search": SearchTool(),
            "knowledge_graph": KnowledgeGraphTool(),
        }

        if CREWAI_AVAILABLE:
            # Prioritize Azure OpenAI if configured
            if settings.AZURE_OPENAI_API_KEY and (
                settings.AZURE_OPENAI_ENDPOINT or settings.AZURE_OPENAI_CHAT_ENDPOINT
            ):
                try:
                    # Set environment variables for CrewAI/LiteLLM
                    os.environ["AZURE_OPENAI_API_KEY"] = (
                        settings.AZURE_OPENAI_CHAT_API_KEY
                        or settings.AZURE_OPENAI_API_KEY
                    )
                    os.environ["AZURE_OPENAI_ENDPOINT"] = (
                        settings.AZURE_OPENAI_CHAT_ENDPOINT
                        or settings.AZURE_OPENAI_ENDPOINT
                    )
                    os.environ[
                        "OPENAI_API_VERSION"
                    ] = settings.AZURE_OPENAI_CHAT_API_VERSION
                    os.environ["OPENAI_API_TYPE"] = "azure"

                    # Set variables for CrewAI Native Azure Provider
                    os.environ["AZURE_API_KEY"] = (
                        settings.AZURE_OPENAI_CHAT_API_KEY
                        or settings.AZURE_OPENAI_API_KEY
                    )
                    os.environ["AZURE_ENDPOINT"] = (
                        settings.AZURE_OPENAI_CHAT_ENDPOINT
                        or settings.AZURE_OPENAI_ENDPOINT
                    )

                    deployment = (
                        settings.AZURE_OPENAI_CHAT_DEPLOYMENT_NAME
                        or settings.AZURE_OPENAI_DEPLOYMENT_NAME
                    )
                    self.llm = f"azure/{deployment}"
                    logger.info(
                        f"Initialized MultiAgentSearchService with Azure OpenAI using model: {self.llm}"
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize Azure OpenAI: {e}")
                    self.llm = None
            # Fallback to standard OpenAI if configured
            elif settings.OPENAI_API_KEY:
                # Ensure OPENAI_API_KEY is in env for LiteLLM
                os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
                self.llm = "gpt-3.5-turbo"
                logger.info("Initialized MultiAgentSearchService with standard OpenAI")
            else:
                logger.warning(
                    "No valid OpenAI API key found (Azure or Standard). Multi-agent search will be disabled."
                )
                self.llm = None

            if self.llm:
                self._initialize_agents()
        else:
            self.llm = None
            logger.warning("CrewAI not available - using fallback implementation")

    def _initialize_agents(self):
        """Initialize CrewAI agents for different search tasks"""
        if not CREWAI_AVAILABLE:
            return

        # Retrieval Agent - finds relevant content
        self.retrieval_agent = Agent(
            role="Content Retrieval Specialist",
            goal="Find the most relevant and comprehensive content for user queries",
            backstory="""You are an expert information retrieval specialist with deep knowledge
            of search strategies across multiple data sources. You excel at understanding user intent
            and finding the most relevant documents, entities, and information.""",
            verbose=True,
            allow_delegation=False,
            tools=[self.agent_tools["search"]],
            llm=self.llm,
        )

        # Graph Navigation Agent - explores entity relationships
        self.graph_agent = Agent(
            role="Knowledge Graph Navigator",
            goal="Discover related entities and concepts through graph traversal",
            backstory="""You are an expert knowledge graph analyst who can navigate complex
            entity relationships to find connected concepts, related topics, and hidden patterns
            that enhance search results.""",
            verbose=True,
            allow_delegation=False,
            tools=[self.agent_tools["knowledge_graph"]],
            llm=self.llm,
        )

        # Quality Assurance Agent - validates result accuracy
        self.qa_agent = Agent(
            role="Search Quality Assurance Specialist",
            goal="Validate search result accuracy, relevance, and completeness",
            backstory="""You are a meticulous quality assurance specialist who evaluates
            search results for accuracy, relevance to the query, completeness of information,
            and overall quality. You identify gaps and suggest improvements.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
        )

        # Answer Synthesis Agent - generates comprehensive responses
        self.synthesis_agent = Agent(
            role="Answer Synthesis Expert",
            goal="Synthesize search results into coherent, comprehensive responses",
            backstory="""You are an expert communicator who can synthesize information
            from multiple sources into clear, accurate, and comprehensive answers that
            directly address user queries.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
        )

        # Query Understanding Agent - refines and expands queries
        self.query_agent = Agent(
            role="Query Understanding Specialist",
            goal="Analyze, refine, and expand user queries for better search results",
            backstory="""You are an expert in natural language understanding who can
            analyze user intent, identify key concepts, suggest query refinements, and
            expand queries with related terms for comprehensive search coverage.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
        )

        # Result Enrichment Agent - enhances search results
        self.enrichment_agent = Agent(
            role="Search Result Enrichment Specialist",
            goal="Enhance search results with additional context and metadata",
            backstory="""You are an expert in information enrichment who can add valuable
            context, summaries, categorizations, and metadata to search results to make
            them more useful and actionable.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
        )

    async def orchestrate_search(
        self,
        query: str,
        user_id: str,
        organization_id: str,
        max_agents: int = 4,
        timeout: float = 120.0,
    ) -> MultiAgentSearchResult:
        """
        Orchestrate multi-agent search workflow

        Args:
            query: Original search query
            user_id: User ID for personalization
            organization_id: Organization ID for data scope
            max_agents: Maximum number of agents to use
            timeout: Maximum execution time in seconds

        Returns:
            MultiAgentSearchResult with agent collaboration results
        """
        start_time = time.time()

        if not CREWAI_AVAILABLE:
            return await self._fallback_search(query, user_id, organization_id)

        try:
            # Create agent tasks
            tasks = self._create_agent_tasks(query, user_id, organization_id)

            # Select most relevant tasks based on query complexity
            selected_tasks = self._select_tasks(tasks, max_agents)

            # Execute tasks in parallel where possible
            execution_results = await self._execute_agent_tasks(selected_tasks, timeout)

            # Synthesize final answer
            synthesized_answer = await self._synthesize_answer(query, execution_results)

            # Generate quality metrics
            quality_metrics = await self._generate_quality_metrics(execution_results)

            execution_time = time.time() - start_time

            # Extract search results from execution results
            search_results = self._extract_search_results(execution_results)

            return MultiAgentSearchResult(
                original_query=query,
                refined_query=self._get_refined_query(execution_results),
                search_results=search_results,
                agent_executions=execution_results,
                synthesized_answer=synthesized_answer,
                confidence_score=self._calculate_confidence_score(execution_results),
                execution_time=execution_time,
                quality_metrics=quality_metrics,
                recommendations=self._generate_recommendations(execution_results),
                metadata={
                    "agents_used": len(selected_tasks),
                    "query_complexity": self._assess_query_complexity(query),
                    "collaboration_score": self._calculate_collaboration_score(
                        execution_results
                    ),
                },
            )

        except Exception as e:
            logger.error(f"Multi-agent search orchestration failed: {e}")
            # Fallback to simple hybrid search
            return await self._fallback_search(query, user_id, organization_id)

    def _create_agent_tasks(
        self, query: str, user_id: str, organization_id: str
    ) -> List[AgentTask]:
        """Create tasks for different agents based on query analysis"""
        tasks = []

        # Query understanding task
        tasks.append(
            AgentTask(
                task_id="query_understanding",
                agent_type=AgentType.QUERY_UNDERSTANDING,
                description=f"Analyze the query '{query}' and provide refined queries, key entities, and search strategy",
                expected_output="Refined query, key entities, search terms, and strategy recommendations",
                context={"query": query, "user_id": user_id},
                priority=1,
                estimated_duration=15.0,
            )
        )

        # Retrieval task
        tasks.append(
            AgentTask(
                task_id="content_retrieval",
                agent_type=AgentType.RETRIEVAL,
                description=f"Find relevant documents and content for the query '{query}' using hybrid search",
                expected_output="List of relevant documents with relevance scores and summaries",
                context={"query": query, "organization_id": organization_id},
                dependencies=["query_understanding"],
                priority=2,
                estimated_duration=20.0,
            )
        )

        # Graph navigation task
        tasks.append(
            AgentTask(
                task_id="graph_navigation",
                agent_type=AgentType.GRAPH_NAVIGATION,
                description=f"Explore knowledge graph for entities related to '{query}' and find connected concepts",
                expected_output="Related entities, relationships, and conceptual connections",
                context={"query": query},
                dependencies=["query_understanding"],
                priority=2,
                estimated_duration=25.0,
            )
        )

        # Quality assurance task
        tasks.append(
            AgentTask(
                task_id="quality_assurance",
                agent_type=AgentType.QUALITY_ASSURANCE,
                description="Evaluate search results for accuracy, relevance, and completeness",
                expected_output="Quality assessment with scores and improvement suggestions",
                context={"query": query},
                dependencies=["content_retrieval", "graph_navigation"],
                priority=3,
                estimated_duration=20.0,
            )
        )

        # Answer synthesis task
        tasks.append(
            AgentTask(
                task_id="answer_synthesis",
                agent_type=AgentType.ANSWER_SYNTHESIS,
                description=f"Synthesize all gathered information into a comprehensive answer for '{query}'",
                expected_output="Coherent, comprehensive answer addressing the original query",
                context={"query": query},
                dependencies=[
                    "content_retrieval",
                    "graph_navigation",
                    "quality_assurance",
                ],
                priority=4,
                estimated_duration=30.0,
            )
        )

        # Result enrichment task
        tasks.append(
            AgentTask(
                task_id="result_enrichment",
                agent_type=AgentType.RESULT_ENRICHMENT,
                description="Enhance search results with additional context and metadata",
                expected_output="Enriched results with categories, summaries, and additional context",
                context={"query": query},
                dependencies=["content_retrieval"],
                priority=3,
                estimated_duration=15.0,
            )
        )

        return tasks

    def _select_tasks(self, tasks: List[AgentTask], max_agents: int) -> List[AgentTask]:
        """Select most relevant tasks based on query complexity and dependencies"""
        # Simple selection based on priority and dependencies
        # In a real implementation, this could be more sophisticated
        selected = []

        # Always include query understanding
        query_task = next(
            (t for t in tasks if t.agent_type == AgentType.QUERY_UNDERSTANDING), None
        )
        if query_task:
            selected.append(query_task)

        # Add retrieval task
        retrieval_task = next(
            (t for t in tasks if t.agent_type == AgentType.RETRIEVAL), None
        )
        if retrieval_task:
            selected.append(retrieval_task)

        # Add other tasks based on available slots
        remaining_tasks = [t for t in tasks if t not in selected]
        remaining_tasks.sort(key=lambda x: x.priority)

        selected.extend(remaining_tasks[: max_agents - len(selected)])

        return selected

    async def _execute_agent_tasks(
        self, tasks: List[AgentTask], timeout: float
    ) -> List[AgentExecution]:
        """Execute agent tasks with dependency management"""
        if not CREWAI_AVAILABLE:
            return []

        executions = []
        completed_tasks = set()

        # Execute tasks in order of dependencies
        remaining_tasks = tasks.copy()

        while remaining_tasks and len(executions) < len(tasks):
            # Find tasks whose dependencies are satisfied
            ready_tasks = [
                task
                for task in remaining_tasks
                if not task.dependencies
                or all(dep in completed_tasks for dep in task.dependencies)
            ]

            if not ready_tasks:
                # Circular dependency or missing dependency
                logger.warning("No ready tasks found, breaking execution")
                break

            # Execute ready tasks in parallel
            for task in ready_tasks:
                try:
                    execution = await self._execute_single_task(task)
                    executions.append(execution)
                    completed_tasks.add(task.task_id)
                    remaining_tasks.remove(task)

                except Exception as e:
                    logger.error(f"Task {task.task_id} failed: {e}")
                    # Create failed execution
                    execution = AgentExecution(
                        task_id=task.task_id,
                        agent_type=task.agent_type,
                        execution_time=0.0,
                        success=False,
                        result={},
                        error_message=str(e),
                    )
                    executions.append(execution)
                    completed_tasks.add(task.task_id)
                    remaining_tasks.remove(task)

        return executions

    async def _execute_single_task(self, task: AgentTask) -> AgentExecution:
        """Execute a single agent task"""
        start_time = time.time()

        try:
            # Map task to CrewAI agents
            agent = self._get_agent_for_type(task.agent_type)
            if not agent:
                raise ValueError(f"No agent found for type {task.agent_type}")

            # Create CrewAI task
            crew_task = Task(
                description=task.description,
                expected_output=task.expected_output,
                agent=agent,
                tools=self._get_tools_for_task(task),
            )

            # Create crew with single agent
            crew = Crew(
                agents=[agent], tasks=[crew_task], verbose=1, process=Process.sequential
            )

            # Execute task
            result = crew.kickoff()

            execution_time = time.time() - start_time

            return AgentExecution(
                task_id=task.task_id,
                agent_type=task.agent_type,
                execution_time=execution_time,
                success=True,
                result={"output": str(result)},
                metadata={
                    "estimated_duration": task.estimated_duration,
                    "priority": task.priority,
                },
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Task execution failed: {e}")

            return AgentExecution(
                task_id=task.task_id,
                agent_type=task.agent_type,
                execution_time=execution_time,
                success=False,
                result={},
                error_message=str(e),
                metadata={
                    "estimated_duration": task.estimated_duration,
                    "priority": task.priority,
                },
            )

    def _get_agent_for_type(self, agent_type: AgentType):
        """Get CrewAI agent for task type"""
        if not CREWAI_AVAILABLE:
            return None

        agent_map = {
            AgentType.RETRIEVAL: getattr(self, "retrieval_agent", None),
            AgentType.GRAPH_NAVIGATION: getattr(self, "graph_agent", None),
            AgentType.QUALITY_ASSURANCE: getattr(self, "qa_agent", None),
            AgentType.ANSWER_SYNTHESIS: getattr(self, "synthesis_agent", None),
            AgentType.QUERY_UNDERSTANDING: getattr(self, "query_agent", None),
            AgentType.RESULT_ENRICHMENT: getattr(self, "enrichment_agent", None),
        }

        return agent_map.get(agent_type)

    def _get_tools_for_task(self, task: AgentTask) -> List:
        """Get appropriate tools for task type"""
        tools = []

        if task.agent_type in [AgentType.RETRIEVAL, AgentType.RESULT_ENRICHMENT]:
            tools.append(self.agent_tools["search"])

        if task.agent_type == AgentType.GRAPH_NAVIGATION:
            tools.append(self.agent_tools["knowledge_graph"])

        return tools

    async def _fallback_search(
        self, query: str, user_id: str, organization_id: str
    ) -> MultiAgentSearchResult:
        """Fallback implementation when CrewAI is not available"""
        start_time = time.time()

        try:
            # Perform simple hybrid search
            search_query = SearchQuery(
                query=query, search_type=SearchType.HYBRID, limit=10
            )

            search_response = hybrid_search_service.search(
                search_request=search_query,
                user_id=user_id,
                organization_id=organization_id,
            )

            # Create mock agent execution
            execution = AgentExecution(
                task_id="fallback_search",
                agent_type=AgentType.RETRIEVAL,
                execution_time=time.time() - start_time,
                success=True,
                result={
                    "output": f"Found {len(search_response.results)} results for '{query}'"
                },
                metadata={"fallback": True},
            )

            # Generate simple synthesized answer
            synthesized_answer = self._generate_simple_answer(
                query, search_response.results
            )

            execution_time = time.time() - start_time

            return MultiAgentSearchResult(
                original_query=query,
                refined_query=query,
                search_results=search_response.results,
                agent_executions=[execution],
                synthesized_answer=synthesized_answer,
                confidence_score=0.7,
                execution_time=execution_time,
                quality_metrics={"relevancy": 0.7, "completeness": 0.6},
                recommendations=[
                    "Consider adding more specific terms to refine results"
                ],
                metadata={"fallback_mode": True, "agents_used": 1},
            )

        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            execution_time = time.time() - start_time

            return MultiAgentSearchResult(
                original_query=query,
                refined_query=query,
                search_results=[],
                agent_executions=[],
                synthesized_answer=f"I encountered an error while searching for '{query}': {str(e)}",
                confidence_score=0.0,
                execution_time=execution_time,
                quality_metrics={},
                recommendations=["Please try rephrasing your query or contact support"],
                metadata={"error": str(e), "fallback_mode": True},
            )

    def _generate_simple_answer(self, query: str, results: List[SearchResult]) -> str:
        """Generate a simple answer from search results"""
        if not results:
            return f"I couldn't find relevant information for '{query}'. Please try different search terms."

        # Create a simple summary from top results
        answer_parts = [f"Based on the search results for '{query}':\n"]

        for i, result in enumerate(results[:3], 1):
            answer_parts.append(f"{i}. {result.title}")
            if result.content_preview:
                # Truncate preview to reasonable length
                preview = (
                    result.content_preview[:200] + "..."
                    if len(result.content_preview) > 200
                    else result.content_preview
                )
                answer_parts.append(f"   {preview}")

        answer_parts.append(f"\nFound {len(results)} total results.")

        return "\n".join(answer_parts)

    async def _synthesize_answer(
        self, query: str, executions: List[AgentExecution]
    ) -> str:
        """Synthesize final answer from agent executions"""
        # Look for synthesis agent result
        synthesis_execution = next(
            (
                e
                for e in executions
                if e.agent_type == AgentType.ANSWER_SYNTHESIS and e.success
            ),
            None,
        )

        if synthesis_execution:
            return synthesis_execution.result.get(
                "output", "Unable to synthesize answer"
            )

        # Fallback: combine results from other agents
        relevant_results = [
            e for e in executions if e.success and e.result.get("output")
        ]

        if relevant_results:
            combined_output = "\n\n".join(
                [
                    f"{e.agent_type.value}: {e.result.get('output', '')}"
                    for e in relevant_results[:3]  # Limit to avoid too much text
                ]
            )
            return f"Search results for '{query}':\n\n{combined_output}"

        return f"No agent could provide results for '{query}'"

    def _extract_search_results(
        self, executions: List[AgentExecution]
    ) -> List[SearchResult]:
        """Extract search results from agent executions"""
        # Look for retrieval agent results
        retrieval_execution = next(
            (
                e
                for e in executions
                if e.agent_type == AgentType.RETRIEVAL and e.success
            ),
            None,
        )

        if retrieval_execution:
            # Parse search results from agent output
            try:
                output = retrieval_execution.result.get("output", "")
                # This would need proper parsing in a real implementation
                # For now, return empty list
                pass
            except Exception as e:
                logger.error(f"Failed to parse search results from agent: {e}")

        return []

    def _get_refined_query(self, executions: List[AgentExecution]) -> str:
        """Get refined query from query understanding agent"""
        query_execution = next(
            (
                e
                for e in executions
                if e.agent_type == AgentType.QUERY_UNDERSTANDING and e.success
            ),
            None,
        )

        if query_execution:
            # Parse refined query from agent output
            output = query_execution.result.get("output", "")
            # Simple extraction - would need more sophisticated parsing
            return output.split("\n")[0] if output else ""

        return ""

    def _calculate_confidence_score(self, executions: List[AgentExecution]) -> float:
        """Calculate overall confidence score from agent executions"""
        if not executions:
            return 0.0

        # Simple confidence calculation based on success rate
        successful_executions = [e for e in executions if e.success]
        base_confidence = len(successful_executions) / len(executions)

        # Adjust based on agent types that succeeded
        has_synthesis = any(
            e.agent_type == AgentType.ANSWER_SYNTHESIS and e.success for e in executions
        )
        has_quality_check = any(
            e.agent_type == AgentType.QUALITY_ASSURANCE and e.success
            for e in executions
        )

        if has_synthesis and has_quality_check:
            base_confidence *= 1.2
        elif has_synthesis:
            base_confidence *= 1.1

        return min(base_confidence, 1.0)

    async def _generate_quality_metrics(
        self, executions: List[AgentExecution]
    ) -> Dict[str, float]:
        """Generate quality metrics from agent executions"""
        metrics = {}

        # Success rate
        successful = len([e for e in executions if e.success])
        metrics["agent_success_rate"] = (
            successful / len(executions) if executions else 0.0
        )

        # Execution efficiency
        total_estimated = sum(
            e.metadata.get("estimated_duration", 30) for e in executions
        )
        total_actual = sum(e.execution_time for e in executions)
        metrics["execution_efficiency"] = (
            min(total_estimated / total_actual, 2.0) if total_actual > 0 else 1.0
        )

        # Collaboration score
        metrics["collaboration_score"] = self._calculate_collaboration_score(executions)

        # Quality assurance score
        qa_execution = next(
            (
                e
                for e in executions
                if e.agent_type == AgentType.QUALITY_ASSURANCE and e.success
            ),
            None,
        )
        if qa_execution:
            # Extract quality score from QA agent output
            metrics["qa_score"] = 0.8  # Placeholder - would parse from actual output
        else:
            metrics["qa_score"] = 0.5  # Neutral score without QA

        return metrics

    def _calculate_collaboration_score(self, executions: List[AgentExecution]) -> float:
        """Calculate how well agents collaborated"""
        if len(executions) <= 1:
            return 0.5

        # Simple collaboration score based on diversity of agent types and success
        successful_types = set(e.agent_type for e in executions if e.success)
        diversity_score = len(successful_types) / len(set(AgentType))

        success_rate = len([e for e in executions if e.success]) / len(executions)

        return (diversity_score + success_rate) / 2

    def _generate_recommendations(self, executions: List[AgentExecution]) -> List[str]:
        """Generate recommendations based on agent execution results"""
        recommendations = []

        # Check for failed executions
        failed_executions = [e for e in executions if not e.success]
        if failed_executions:
            recommendations.append(
                f"Some agents failed: {', '.join(e.agent_type.value for e in failed_executions)}"
            )

        # Check for long execution times
        slow_executions = [
            e
            for e in executions
            if e.execution_time > e.metadata.get("estimated_duration", 30) * 1.5
        ]
        if slow_executions:
            recommendations.append(
                "Some agents took longer than expected - consider optimizing queries"
            )

        # Quality recommendations
        qa_execution = next(
            (
                e
                for e in executions
                if e.agent_type == AgentType.QUALITY_ASSURANCE and e.success
            ),
            None,
        )
        if qa_execution and qa_execution.result.get("output"):
            recommendations.append(
                "Quality assessment completed - see detailed quality report"
            )

        # General recommendations
        successful_executions = len([e for e in executions if e.success])
        if successful_executions < len(executions):
            recommendations.append(
                "Consider enabling more agents for comprehensive results"
            )

        return recommendations

    def _assess_query_complexity(self, query: str) -> str:
        """Assess the complexity of the original query"""
        # Simple complexity assessment
        word_count = len(query.split())
        has_question_words = any(
            word in query.lower()
            for word in ["what", "how", "why", "when", "where", "who"]
        )
        has_entities = any(word[0].isupper() for word in query.split())

        if word_count > 10 or has_question_words:
            return "complex"
        elif word_count > 5 or has_entities:
            return "moderate"
        else:
            return "simple"

    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        configured_agents = self._get_configured_agents()
        return {
            "crewai_available": CREWAI_AVAILABLE,
            "agents_configured": configured_agents,
            "tools_available": list(self.agent_tools.keys()),
            "llm_configured": self.llm is not None,
        }

    def _get_configured_agents(self) -> List[str]:
        """Get list of configured agents"""
        if not CREWAI_AVAILABLE:
            return []

        agents = []
        agent_attrs = [
            "retrieval_agent",
            "graph_agent",
            "qa_agent",
            "synthesis_agent",
            "query_agent",
            "enrichment_agent",
        ]

        for attr in agent_attrs:
            if hasattr(self, attr) and getattr(self, attr) is not None:
                agents.append(attr.replace("_agent", ""))

        return agents


# Global multi-agent search service instance
multi_agent_search_service = MultiAgentSearchService()
