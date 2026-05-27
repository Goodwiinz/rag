"""
Enhanced Multi-Agent Search Orchestration Service v2.0

This service implements intelligent search orchestration using multiple specialized agents
with optimized prompts, better performance monitoring, and advanced collaboration patterns.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.config import settings

# CrewAI imports
try:
    from crewai import Agent, Crew, Process, Task
    from crewai.tools import BaseTool
    from langchain_community.llms import OpenAI
    from langchain_openai import ChatOpenAI

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    BaseTool = object
    logging.info(
        "CrewAI not available. Multi-agent search will use fallback implementation."
    )

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
    CONTEXT_ANALYSIS = "context_analysis"
    STRUCTURED_EXTRACTION = "structured_extraction"  # SciSpace: extraction matrix (placeholder — agent not yet wired)


class WorkflowType(Enum):
    """Types of search workflows"""

    FACTUAL_LOOKUP = "factual_lookup"
    REASONING = "reasoning"
    MULTIMODAL = "multimodal"
    EXPLORATORY = "exploratory"
    COMPARATIVE = "comparative"


@dataclass
class AgentMetrics:
    """Performance metrics for agents"""

    agent_type: AgentType
    total_executions: int = 0
    successful_executions: int = 0
    average_execution_time: float = 0.0
    confidence_score: float = 0.0
    last_execution: Optional[datetime] = None
    error_count: int = 0
    token_usage: int = 0


@dataclass
class AgentTask:
    """Enhanced individual agent task definition"""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: AgentType = AgentType.RETRIEVAL
    description: str = ""
    expected_output: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    dependencies: Set[str] = field(default_factory=set)
    priority: int = 1
    estimated_duration: float = 30.0
    workflow_type: WorkflowType = WorkflowType.FACTUAL_LOOKUP
    retry_count: int = 0
    max_retries: int = 2


@dataclass
class AgentExecution:
    """Enhanced execution result from an agent"""

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_type: AgentType = AgentType.RETRIEVAL
    execution_time: float = 0.0
    success: bool = False
    result: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_usage: Dict[str, int] = field(default_factory=dict)
    confidence_score: float = 0.0
    quality_indicators: Dict[str, float] = field(default_factory=dict)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None


@dataclass
class MultiAgentSearchResult:
    """Enhanced complete multi-agent search result"""

    original_query: str
    refined_query: str
    expanded_queries: List[str] = field(default_factory=list)
    search_results: List[SearchResult] = field(default_factory=list)
    agent_executions: List[AgentExecution] = field(default_factory=list)
    synthesized_answer: str = ""
    confidence_score: float = 0.0
    execution_time: float = 0.0
    quality_metrics: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    workflow_type: WorkflowType = WorkflowType.FACTUAL_LOOKUP
    agent_metrics: Dict[str, AgentMetrics] = field(default_factory=dict)


class EnhancedSearchTool(BaseTool):
    """Enhanced custom tool for search operations with caching"""

    name: str = "enhanced_hybrid_search"
    description: str = (
        "Perform advanced hybrid search with filtering and ranking options"
    )

    def __init__(self):
        super().__init__()
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes

    def _run(
        self, query: str, max_results: int = 10, filters: Dict[str, Any] = None
    ) -> str:
        """Execute the tool with caching"""
        try:
            # Check cache
            cache_key = f"{query}_{max_results}_{str(filters or {})}"
            if cache_key in self._cache:
                cached_data = self._cache[cache_key]
                if time.time() - cached_data["timestamp"] < self._cache_ttl:
                    logger.info(f"Cache hit for query: {query}")
                    return cached_data["result"]

            # Perform search
            search_query = SearchQuery(
                query=query,
                search_type=SearchType.HYBRID,
                limit=max_results,
                filters=filters or {},
            )

            search_response = hybrid_search_service.search(
                search_request=search_query,
                user_id="multi_agent_user",
                organization_id="default_org",
            )

            # Enhanced result processing
            results = []
            for result in search_response.results[:max_results]:
                results.append(
                    {
                        "id": result.id,
                        "title": result.title,
                        "content": result.content_preview,
                        "score": result.relevance_score,
                        "source": result.source_type.value
                        if hasattr(result.source_type, "value")
                        else str(result.source_type),
                        "metadata": result.metadata or {},
                        "highlights": getattr(result, "highlights", []),
                        "entity_count": len(result.metadata.get("entities", []))
                        if result.metadata
                        else 0,
                    }
                )

            result_data = {
                "results": results,
                "total_found": len(search_response.results),
                "query_time": getattr(search_response, "query_time", 0),
                "search_strategy": getattr(
                    search_response, "search_strategy", "hybrid"
                ),
            }

            result_json = json.dumps(result_data, indent=2)

            # Cache result
            self._cache[cache_key] = {"result": result_json, "timestamp": time.time()}

            return result_json

        except Exception as e:
            logger.error(f"Enhanced search tool error: {e}")
            return json.dumps({"error": str(e), "results": []})


class EnhancedKnowledgeGraphTool(BaseTool):
    """Enhanced custom tool for knowledge graph operations"""

    name: str = "enhanced_knowledge_graph"
    description: str = "Query knowledge graph with advanced relationship discovery and entity resolution"

    def _run(
        self,
        entity_name: str = None,
        relationship_type: str = None,
        entity_type: str = None,
        depth: int = 2,
        limit: int = 20,
    ) -> str:
        """Execute enhanced graph query"""
        try:
            # Build flexible query
            query_parts = []

            if entity_name:
                query_parts.append(f"MATCH (e1:Entity {{name: '{entity_name}'}})")
                if entity_type:
                    query_parts[
                        -1
                    ] = f"MATCH (e1:Entity {{name: '{entity_name}', type: '{entity_type}'}})"
            else:
                query_parts.append("MATCH (e1:Entity)")
                if entity_type:
                    query_parts[-1] = f"MATCH (e1:Entity {{type: '{entity_type}'}})"

            # Add relationship pattern
            if relationship_type:
                query_parts.append(
                    f"MATCH (e1)-[r:{relationship_type}*1..{depth}]->(e2)"
                )
            else:
                query_parts.append(f"MATCH (e1)-[r*1..{depth}]->(e2)")

            # Return pattern
            query_parts.append(
                """
                RETURN DISTINCT
                    e1.name as source_entity,
                    e1.type as source_type,
                    type(r) as relationship,
                    e2.name as target_entity,
                    e2.type as target_type,
                    length(r) as path_length,
                    r.weight as weight
                ORDER BY weight DESC, path_length ASC
                LIMIT $limit
            """
            )

            query = "\n".join(query_parts)

            results = knowledge_graph_service.query_graph(query, {"limit": limit})

            # Enhance results with analytics
            if results:
                # Analyze relationship patterns
                relationship_counts = defaultdict(int)
                entity_types = defaultdict(int)

                for result in results:
                    relationship_counts[result.get("relationship", "unknown")] += 1
                    entity_types[result.get("source_type", "unknown")] += 1
                    entity_types[result.get("target_type", "unknown")] += 1

                enhanced_results = {
                    "entities": results,
                    "analytics": {
                        "relationship_distribution": dict(relationship_counts),
                        "entity_type_distribution": dict(entity_types),
                        "total_entities": len(results),
                        "max_depth": max(r.get("path_length", 1) for r in results)
                        if results
                        else 0,
                    },
                }
            else:
                enhanced_results = {
                    "entities": [],
                    "analytics": {"message": "No entities found matching the criteria"},
                }

            return json.dumps(enhanced_results, indent=2, default=str)

        except Exception as e:
            logger.error(f"Enhanced knowledge graph tool error: {e}")
            return json.dumps({"error": str(e), "entities": []})


class MultiAgentSearchServiceV2:
    """Enhanced service for orchestrating multi-agent search workflows"""

    def __init__(self):
        self.agent_tools = {
            "search": EnhancedSearchTool(),
            "knowledge_graph": EnhancedKnowledgeGraphTool(),
        }

        # Performance tracking
        self.agent_metrics: Dict[AgentType, AgentMetrics] = {
            agent_type: AgentMetrics(agent_type=agent_type) for agent_type in AgentType
        }

        # Query history for learning
        self.query_history: List[Dict[str, Any]] = []

        if CREWAI_AVAILABLE:
            # Azure OpenAI Configuration
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
                        f"Initialized MultiAgentSearchServiceV2 with Azure OpenAI using model: {self.llm}"
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize Azure OpenAI: {e}")
                    self.llm = None

            # Standard OpenAI Configuration
            elif settings.OPENAI_API_KEY:
                os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
                self.llm = "gpt-4-turbo-preview"
                logger.info(
                    "Initialized MultiAgentSearchServiceV2 with standard OpenAI"
                )
            else:
                logger.warning(
                    "No valid OpenAI API key found (Azure or Standard). Multi-agent search will be disabled."
                )
                self.llm = None

            if self.llm:
                self._initialize_optimized_agents()
        else:
            self.llm = None
            logger.warning("CrewAI not available - using fallback implementation")

    def _initialize_optimized_agents(self):
        """Initialize CrewAI agents with optimized prompts and constitutional AI principles"""
        if not CREWAI_AVAILABLE:
            return

        # Constitutional AI principles
        constitutional_principles = [
            "Always verify factual accuracy before providing information",
            "Self-check for potential biases or incomplete information",
            "Validate that your output directly addresses the user's query",
            "Ensure your response is comprehensive yet concise",
            "Maintain consistency with established facts and previous responses",
            "Acknowledge uncertainty when information is not definitive",
        ]

        # Retrieval Agent - Enhanced with domain expertise
        self.retrieval_agent = Agent(
            role="Advanced Information Retrieval Specialist",
            goal="Find the most relevant, accurate, and comprehensive content using optimal search strategies",
            backstory="""You are an elite information retrieval specialist with 15+ years of experience
            in search strategy optimization across multiple domains. You excel at:

            1. Understanding nuanced user intent beyond surface-level keywords
            2. Identifying the most effective search queries and filters
            3. Evaluating source credibility and information freshness
            4. Recognizing patterns in how information is structured and accessed
            5. Adapting search strategies based on content type and domain

            You always consider:
            - Semantic relationships between query terms
            - Potential synonyms and related concepts
            - The most reliable sources for the topic
            - Whether information needs to be recent or can be historical
            - The level of detail required by the user

            Before executing any search, you analyze the query to determine the optimal approach.""",
            verbose=True,
            allow_delegation=False,
            tools=[self.agent_tools["search"]],
            llm=self.llm,
            max_iter=2,  # Allow for self-correction
            max_rpm=100,  # Rate limiting
        )

        # Graph Navigation Agent - Enhanced with graph theory expertise
        self.graph_agent = Agent(
            role="Expert Knowledge Graph Analyst",
            goal="Discover meaningful relationships and patterns through intelligent graph traversal",
            backstory="""You are a knowledge graph expert with deep understanding of:

            1. Graph theory and network analysis principles
            2. Entity relationship patterns across different domains
            3. Pathfinding algorithms for discovering indirect connections
            4. Centrality measures to identify important entities
            5. Community detection for finding related concepts

            Your approach:
            - Start with direct relationships before exploring indirect ones
            - Prioritize strong, weighted connections
            - Look for bridging entities that connect different concepts
            - Identify clusters or communities of related information
            - Consider temporal aspects of relationships

            You can navigate complex multi-hop relationships to find non-obvious connections
            that enhance the user's understanding of the topic.""",
            verbose=True,
            allow_delegation=False,
            tools=[self.agent_tools["knowledge_graph"]],
            llm=self.llm,
            max_iter=2,
            max_rpm=100,
        )

        # Query Understanding Agent - Enhanced with NLP expertise
        self.query_agent = Agent(
            role="Natural Language Understanding & Query Optimization Expert",
            goal="Analyze, understand, and optimize queries for maximum information retrieval effectiveness",
            backstory="""You are an NLP expert specializing in query understanding and optimization.
            Your expertise includes:

            1. Semantic analysis and intent recognition
            2. Entity recognition and disambiguation
            3. Query expansion and reformulation
            4. Understanding implicit user needs
            5. Identifying the most fruitful search directions

            Your process:
            1. Parse the query to identify key entities and concepts
            2. Determine the user's intent (factual, analytical, exploratory, etc.)
            3. Recognize potential ambiguities and clarify them
            4. Generate optimized query variations
            5. Suggest the most effective search strategy

            You always consider context, previous interactions, and the most likely information
            the user needs to satisfy their query effectively.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            max_iter=2,
            max_rpm=100,
        )

        # Quality Assurance Agent - Enhanced with critical thinking
        self.qa_agent = Agent(
            role="Information Quality Assurance & Verification Specialist",
            goal="Rigorously validate information accuracy, relevance, completeness, and potential biases",
            backstory="""You are a meticulous quality assurance specialist with expertise in:

            1. Critical thinking and logical reasoning
            2. Fact-checking and source verification
            3. Identifying logical fallacies and misinformation
            4. Assessing information completeness and relevance
            5. Recognizing potential biases in sources

            Your evaluation criteria:
            - Factual accuracy and verifiability
            - Relevance to the original query
            - Completeness of information
            - Source credibility and authority
            - Presence of contradictory information
            - Timeliness and currency of information

            You provide specific feedback on quality issues and suggest concrete improvements
            to ensure users receive accurate, reliable information.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            max_iter=2,
            max_rpm=100,
        )

        # Answer Synthesis Agent - Enhanced with communication expertise
        self.synthesis_agent = Agent(
            role="Expert Information Synthesizer & Technical Communicator",
            goal="Synthesize complex information into clear, accurate, and comprehensive responses",
            backstory="""You are an expert technical communicator and information synthesizer with
            exceptional ability to:

            1. Integrate information from multiple sources
            2. Structure information logically and coherently
            3. Explain complex concepts clearly
            4. Balance detail with readability
            5. Anticipate follow-up questions

            Your synthesis approach:
            1. Identify key themes and patterns across sources
            2. Resolve any contradictions or discrepancies
            3. Structure the information logically
            4. Provide context and background where helpful
            5. Include specific details and examples
            6. Acknowledge uncertainties or limitations

            You ensure your response is comprehensive yet accessible, addressing the user's
            query directly while providing valuable context and insights.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            max_iter=2,
            max_rpm=100,
        )

        # Context Analysis Agent - New specialized agent
        self.context_agent = Agent(
            role="Context & Domain Analysis Specialist",
            goal="Analyze query context and domain to optimize search strategy and results",
            backstory="""You are a domain analysis expert who excels at:

            1. Identifying the domain and context of queries
            2. Understanding domain-specific terminology and conventions
            3. Recognizing the appropriate level of technical detail
            4. Identifying related subdomains or cross-disciplinary connections
            5. Adapting search strategies to domain requirements

            Your analysis helps other agents:
            - Use appropriate terminology and filters
            - Find domain-specific sources
            - Adjust the level of detail provided
            - Include relevant domain context
            - Connect to related areas of knowledge

            You ensure the search and response are tailored to the specific domain context
            of the user's query.""",
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            max_iter=2,
            max_rpm=100,
        )

        # Result Enrichment Agent - Enhanced with metadata expertise
        self.enrichment_agent = Agent(
            role="Information Enrichment & Metadata Enhancement Specialist",
            goal="Enhance search results with valuable context, metadata, and actionable insights",
            backstory="""You are an information enrichment specialist who excels at:

            1. Extracting and adding relevant metadata
            2. Categorizing and tagging information
            3. Identifying key themes and topics
            4. Generating concise, informative summaries
            5. Identifying actionable insights or next steps

            Your enrichment process:
            1. Extract key entities, concepts, and themes
            2. Categorize information by topic and type
            3. Add relevant metadata for better organization
            4. Generate concise summaries for quick understanding
            5. Identify connections to related information
            6. Suggest follow-up queries or actions

            You transform raw search results into organized, enriched information
            that is more useful and actionable for users.""",
            verbose=True,
            allow_delegation=False,
            tools=[self.agent_tools["search"]],
            llm=self.llm,
            max_iter=2,
            max_rpm=100,
        )

    async def orchestrate_search(
        self,
        query: str,
        user_id: str,
        organization_id: str,
        workflow_type: WorkflowType = WorkflowType.FACTUAL_LOOKUP,
        max_agents: int = 4,
        timeout: float = 180.0,
        enable_learning: bool = True,
    ) -> MultiAgentSearchResult:
        """
        Enhanced multi-agent search orchestration with workflow optimization

        Args:
            query: Original search query
            user_id: User ID for personalization and learning
            organization_id: Organization ID for data scope
            workflow_type: Type of search workflow to use
            max_agents: Maximum number of agents to use
            timeout: Maximum execution time in seconds
            enable_learning: Whether to use query learning

        Returns:
            Enhanced MultiAgentSearchResult with comprehensive agent collaboration
        """
        start_time = time.time()

        if not CREWAI_AVAILABLE:
            return await self._enhanced_fallback_search(query, user_id, organization_id)

        try:
            # Analyze query and determine optimal workflow
            query_analysis = await self._analyze_query(query, workflow_type)

            # Create optimized agent tasks based on workflow
            tasks = self._create_workflow_tasks(
                query, query_analysis, user_id, organization_id
            )

            # Select most relevant tasks using intelligent selection
            selected_tasks = self._intelligent_task_selection(
                tasks, max_agents, query_analysis
            )

            # Execute tasks with advanced dependency management
            execution_results = await self._execute_agent_tasks_v2(
                selected_tasks, timeout
            )

            # Synthesize enhanced final answer
            synthesized_answer = await self._enhanced_synthesis(
                query, execution_results, query_analysis
            )

            # Generate comprehensive quality metrics
            quality_metrics = await self._generate_enhanced_quality_metrics(
                execution_results, query_analysis
            )

            execution_time = time.time() - start_time

            # Extract and enhance search results
            search_results = self._extract_and_enhance_results(execution_results)

            # Update learning from this query
            if enable_learning:
                await self._update_learning(
                    query, query_analysis, execution_results, execution_time
                )

            # Update agent performance metrics
            self._update_agent_metrics(execution_results)

            return MultiAgentSearchResult(
                original_query=query,
                refined_query=query_analysis.get("refined_query", query),
                expanded_queries=query_analysis.get("expanded_queries", []),
                search_results=search_results,
                agent_executions=execution_results,
                synthesized_answer=synthesized_answer,
                confidence_score=self._calculate_enhanced_confidence_score(
                    execution_results, query_analysis
                ),
                execution_time=execution_time,
                quality_metrics=quality_metrics,
                recommendations=self._generate_enhanced_recommendations(
                    execution_results, query_analysis
                ),
                metadata={
                    "agents_used": len(selected_tasks),
                    "workflow_type": workflow_type.value,
                    "query_complexity": query_analysis.get("complexity", "moderate"),
                    "collaboration_score": self._calculate_enhanced_collaboration_score(
                        execution_results
                    ),
                    "learning_enabled": enable_learning,
                    "optimizations_applied": query_analysis.get("optimizations", []),
                },
                workflow_type=workflow_type,
                agent_metrics=self.agent_metrics,
            )

        except Exception as e:
            logger.error(f"Enhanced multi-agent search orchestration failed: {e}")
            return await self._enhanced_fallback_search(query, user_id, organization_id)

    async def _analyze_query(
        self, query: str, workflow_type: WorkflowType
    ) -> Dict[str, Any]:
        """Analyze query to determine optimal search strategy"""
        analysis = {
            "original_query": query,
            "complexity": "moderate",
            "intent": "informational",
            "entities": [],
            "keywords": [],
            "domain": "general",
            "workflow_type": workflow_type,
            "optimizations": [],
        }

        # Basic query analysis
        words = query.lower().split()
        word_count = len(words)

        # Determine complexity
        if word_count > 15 or any(
            q in query.lower()
            for q in ["explain why", "how does", "compare", "analyze"]
        ):
            analysis["complexity"] = "complex"
            analysis["optimizations"].append("deep_analysis")
        elif word_count > 7:
            analysis["complexity"] = "moderate"
        else:
            analysis["complexity"] = "simple"

        # Determine intent
        question_words = [
            "what",
            "how",
            "why",
            "when",
            "where",
            "who",
            "which",
            "explain",
            "compare",
            "analyze",
        ]
        if any(q in query.lower() for q in question_words):
            analysis["intent"] = "question"
        elif any(q in query.lower() for q in ["list", "show", "find", "search"]):
            analysis["intent"] = "retrieval"
        elif any(q in query.lower() for q in ["compare", "difference", "versus"]):
            analysis["intent"] = "comparative"

        # Extract potential entities (simplified)
        entities = [word for word in words if word[0].isupper() and len(word) > 2]
        analysis["entities"] = entities[:5]  # Limit to top 5

        # Extract keywords (remove stop words)
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        analysis["keywords"] = keywords[:10]

        # Determine potential domain based on keywords
        domain_keywords = {
            "technology": ["computer", "software", "programming", "algorithm", "data"],
            "science": ["research", "experiment", "theory", "study", "analysis"],
            "business": ["market", "financial", "economic", "business", "company"],
            "medical": ["health", "medical", "disease", "treatment", "patient"],
        }

        for domain, keywords_list in domain_keywords.items():
            if any(keyword in keywords for keyword in keywords_list):
                analysis["domain"] = domain
                analysis["optimizations"].append(f"domain_{domain}")
                break

        # Generate refined query
        if analysis["complexity"] == "complex":
            analysis["refined_query"] = query + " " + " ".join(keywords[:5])
        else:
            analysis["refined_query"] = query

        # Generate expanded queries
        expanded = []
        if analysis["keywords"]:
            expanded.append(" ".join(analysis["keywords"][:3]))
        if analysis["entities"]:
            expanded.append(" AND ".join(analysis["entities"]))
        analysis["expanded_queries"] = expanded[:3]

        return analysis

    def _create_workflow_tasks(
        self,
        query: str,
        query_analysis: Dict[str, Any],
        user_id: str,
        organization_id: str,
    ) -> List[AgentTask]:
        """Create tasks optimized for specific workflow type"""
        workflow_type = query_analysis.get("workflow_type", WorkflowType.FACTUAL_LOOKUP)
        tasks = []

        # Context analysis task - always first for domain understanding
        tasks.append(
            AgentTask(
                task_id="context_analysis",
                agent_type=AgentType.CONTEXT_ANALYSIS,
                description=f"Analyze the query '{query}' to determine domain context, identify key concepts, and suggest optimal search strategies",
                expected_output="Domain analysis, key concepts, search strategy recommendations, and context-aware optimizations",
                context={
                    "query": query,
                    "user_id": user_id,
                    "domain": query_analysis.get("domain", "general"),
                    "complexity": query_analysis.get("complexity", "moderate"),
                },
                priority=1,
                estimated_duration=15.0,
                workflow_type=workflow_type,
            )
        )

        # Query understanding task
        tasks.append(
            AgentTask(
                task_id="query_understanding",
                agent_type=AgentType.QUERY_UNDERSTANDING,
                description=f"Analyze and optimize the query '{query}' based on context analysis. Generate refined queries and identify search terms",
                expected_output="Optimized query variations, key entities, search terms, and execution plan",
                context={
                    "query": query,
                    "user_id": user_id,
                    "intent": query_analysis.get("intent", "informational"),
                    "expanded_queries": query_analysis.get("expanded_queries", []),
                },
                dependencies={"context_analysis"},
                priority=2,
                estimated_duration=20.0,
                workflow_type=workflow_type,
            )
        )

        # Retrieval task
        tasks.append(
            AgentTask(
                task_id="content_retrieval",
                agent_type=AgentType.RETRIEVAL,
                description=f"Execute comprehensive search using optimized queries and filters for '{query}'",
                expected_output="Relevant documents with detailed metadata, relevance scores, and source information",
                context={
                    "query": query,
                    "refined_query": query_analysis.get("refined_query", query),
                    "organization_id": organization_id,
                    "domain": query_analysis.get("domain", "general"),
                },
                dependencies={"query_understanding"},
                priority=3,
                estimated_duration=25.0,
                workflow_type=workflow_type,
            )
        )

        # Graph navigation task - conditional on complexity
        if query_analysis.get("complexity") in [
            "complex",
            "moderate",
        ] or query_analysis.get("entities"):
            tasks.append(
                AgentTask(
                    task_id="graph_navigation",
                    agent_type=AgentType.GRAPH_NAVIGATION,
                    description=f"Explore knowledge graph for entities and relationships related to '{query}' to enhance understanding",
                    expected_output="Related entities, relationship networks, conceptual connections, and domain insights",
                    context={
                        "query": query,
                        "entities": query_analysis.get("entities", []),
                        "domain": query_analysis.get("domain", "general"),
                        "depth": 2
                        if query_analysis.get("complexity") == "complex"
                        else 1,
                    },
                    dependencies={"context_analysis", "query_understanding"},
                    priority=3,
                    estimated_duration=30.0,
                    workflow_type=workflow_type,
                )
            )

        # Result enrichment task
        tasks.append(
            AgentTask(
                task_id="result_enrichment",
                agent_type=AgentType.RESULT_ENRICHMENT,
                description="Enhance and organize search results with metadata, categorization, and summaries",
                expected_output="Enriched results with categories, themes, summaries, and actionable insights",
                context={
                    "query": query,
                    "domain": query_analysis.get("domain", "general"),
                },
                dependencies={"content_retrieval"},
                priority=4,
                estimated_duration=20.0,
                workflow_type=workflow_type,
            )
        )

        # Quality assurance task - always included for consistency
        tasks.append(
            AgentTask(
                task_id="quality_assurance",
                agent_type=AgentType.QUALITY_ASSURANCE,
                description="Comprehensive quality validation of search results, accuracy checks, and gap identification",
                expected_output="Detailed quality assessment with scores, identified issues, and improvement recommendations",
                context={
                    "query": query,
                    "domain": query_analysis.get("domain", "general"),
                    "complexity": query_analysis.get("complexity", "moderate"),
                },
                dependencies={"content_retrieval", "result_enrichment"},
                priority=5,
                estimated_duration=25.0,
                workflow_type=workflow_type,
            )
        )

        # Answer synthesis task - final step
        tasks.append(
            AgentTask(
                task_id="answer_synthesis",
                agent_type=AgentType.ANSWER_SYNTHESIS,
                description=f"Synthesize all gathered information into a comprehensive, well-structured answer for '{query}'",
                expected_output="Coherent, comprehensive response addressing all aspects of the query with context and insights",
                context={
                    "query": query,
                    "intent": query_analysis.get("intent", "informational"),
                    "complexity": query_analysis.get("complexity", "moderate"),
                    "domain": query_analysis.get("domain", "general"),
                },
                dependencies={
                    "content_retrieval",
                    "quality_assurance",
                    "result_enrichment",
                },
                priority=6,
                estimated_duration=35.0,
                workflow_type=workflow_type,
            )
        )

        return tasks

    def _intelligent_task_selection(
        self, tasks: List[AgentTask], max_agents: int, query_analysis: Dict[str, Any]
    ) -> List[AgentTask]:
        """Intelligently select tasks based on query analysis and dependencies"""
        selected = []
        complexity = query_analysis.get("complexity", "moderate")
        workflow_type = query_analysis.get("workflow_type", WorkflowType.FACTUAL_LOOKUP)

        # Always include core tasks
        core_tasks = {
            "context_analysis": AgentType.CONTEXT_ANALYSIS,
            "query_understanding": AgentType.QUERY_UNDERSTANDING,
            "content_retrieval": AgentType.RETRIEVAL,
        }

        for task in tasks:
            if task.task_id in core_tasks:
                selected.append(task)

        # Add workflow-specific tasks
        if workflow_type == WorkflowType.REASONING or complexity == "complex":
            # Add graph navigation for complex reasoning
            graph_task = next(
                (t for t in tasks if t.agent_type == AgentType.GRAPH_NAVIGATION), None
            )
            if graph_task:
                selected.append(graph_task)

        # Add quality assurance for critical workflows
        if workflow_type in [WorkflowType.REASONING, WorkflowType.COMPARATIVE]:
            qa_task = next(
                (t for t in tasks if t.agent_type == AgentType.QUALITY_ASSURANCE), None
            )
            if qa_task:
                selected.append(qa_task)

        # Fill remaining slots with highest priority tasks
        remaining_slots = max_agents - len(selected)
        if remaining_slots > 0:
            available_tasks = [t for t in tasks if t not in selected]
            available_tasks.sort(key=lambda x: (x.priority, -x.estimated_duration))
            selected.extend(available_tasks[:remaining_slots])

        return selected

    async def _execute_agent_tasks_v2(
        self, tasks: List[AgentTask], timeout: float
    ) -> List[AgentExecution]:
        """Enhanced agent task execution with better error handling and performance tracking"""
        if not CREWAI_AVAILABLE:
            return []

        executions = []
        completed_tasks = set()
        task_queue = tasks.copy()
        execution_start_time = time.time()

        # Execute tasks respecting dependencies with parallel execution where possible
        while task_queue and (time.time() - execution_start_time) < timeout:
            # Find ready tasks
            ready_tasks = []
            for task in task_queue:
                if not task.dependencies or all(
                    dep in completed_tasks for dep in task.dependencies
                ):
                    ready_tasks.append(task)

            if not ready_tasks:
                logger.warning("No ready tasks found - possible circular dependency")
                break

            # Execute ready tasks in parallel (up to 3 at a time)
            batch_size = min(3, len(ready_tasks))
            batches = [
                ready_tasks[i : i + batch_size]
                for i in range(0, len(ready_tasks), batch_size)
            ]

            for batch in batches:
                batch_executions = await asyncio.gather(
                    *[self._execute_enhanced_task(task) for task in batch],
                    return_exceptions=True,
                )

                for result in batch_executions:
                    if isinstance(result, Exception):
                        logger.error(f"Batch execution error: {result}")
                        # Create failed execution for unknown task
                        execution = AgentExecution(
                            task_id="unknown",
                            agent_type=AgentType.RETRIEVAL,
                            execution_time=0.0,
                            success=False,
                            result={},
                            error_message=str(result),
                        )
                        executions.append(execution)
                    else:
                        executions.append(result)
                        if result.success:
                            completed_tasks.add(result.task_id)
                        # Remove from queue
                        task_queue = [
                            t for t in task_queue if t.task_id != result.task_id
                        ]

        # Mark incomplete tasks as failed
        for task in task_queue:
            execution = AgentExecution(
                task_id=task.task_id,
                agent_type=task.agent_type,
                execution_time=0.0,
                success=False,
                result={},
                error_message="Task not executed due to timeout or dependency issues",
                metadata={
                    "timeout": True,
                    "estimated_duration": task.estimated_duration,
                },
            )
            executions.append(execution)

        return executions

    async def _execute_enhanced_task(self, task: AgentTask) -> AgentExecution:
        """Execute a single enhanced agent task with better tracking"""
        start_time = time.time()
        execution_id = str(uuid.uuid4())

        try:
            # Get agent for task type
            agent = self._get_agent_for_type(task.agent_type)
            if not agent:
                raise ValueError(f"No agent configured for type {task.agent_type}")

            # Create enhanced CrewAI task
            crew_task = Task(
                description=self._enhance_task_description(task),
                expected_output=task.expected_output,
                agent=agent,
                tools=self._get_tools_for_task(task),
                async_execution=True,
            )

            # Create optimized crew
            crew = Crew(
                agents=[agent],
                tasks=[crew_task],
                verbose=2,
                process=Process.sequential,
                memory=True,  # Enable memory for better context
                cache=True,  # Enable caching
                embedder={
                    "provider": "openai",
                    "config": {"model": "text-embedding-3-small"},
                },
            )

            # Execute with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(crew.kickoff),
                timeout=task.estimated_duration * 2,  # Allow 2x estimated time
            )

            execution_time = time.time() - start_time

            # Parse execution metadata
            metadata = {
                "task_id": task.task_id,
                "workflow_type": task.workflow_type.value,
                "estimated_duration": task.estimated_duration,
                "priority": task.priority,
                "agent_role": agent.role,
                "tools_used": [tool.name for tool in self._get_tools_for_task(task)],
            }

            # Calculate confidence score based on execution metrics
            confidence = min(
                1.0,
                (task.estimated_duration / execution_time)
                if execution_time > 0
                else 0.5,
            )

            # Quality indicators
            quality_indicators = {
                "execution_efficiency": min(
                    1.0, task.estimated_duration / execution_time
                )
                if execution_time > 0
                else 0,
                "timeout_compliance": 1.0
                if execution_time <= task.estimated_duration * 1.5
                else 0.5,
                "output_length_score": 1.0 if 100 <= len(str(result)) <= 2000 else 0.7,
            }

            return AgentExecution(
                execution_id=execution_id,
                task_id=task.task_id,
                agent_type=task.agent_type,
                execution_time=execution_time,
                success=True,
                result={"output": str(result), "raw_output": result},
                metadata=metadata,
                confidence_score=confidence,
                quality_indicators=quality_indicators,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )

        except asyncio.TimeoutError:
            execution_time = time.time() - start_time
            logger.error(f"Task {task.task_id} timed out after {execution_time:.2f}s")

            return AgentExecution(
                execution_id=execution_id,
                task_id=task.task_id,
                agent_type=task.agent_type,
                execution_time=execution_time,
                success=False,
                result={},
                error_message=f"Task timed out after {execution_time:.2f}s",
                metadata={
                    "timeout": True,
                    "estimated_duration": task.estimated_duration,
                },
                confidence_score=0.0,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Task {task.task_id} execution failed: {e}")

            return AgentExecution(
                execution_id=execution_id,
                task_id=task.task_id,
                agent_type=task.agent_type,
                execution_time=execution_time,
                success=False,
                result={},
                error_message=str(e),
                metadata={
                    "error_type": type(e).__name__,
                    "estimated_duration": task.estimated_duration,
                },
                confidence_score=0.0,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )

    def _enhance_task_description(self, task: AgentTask) -> str:
        """Enhance task description with context and constraints"""
        enhanced = task.description

        # Add constraints
        enhanced += f"\n\nConstraints and Guidelines:\n"
        enhanced += f"- Focus on accuracy and relevance\n"
        enhanced += f"- Provide specific, actionable information\n"
        enhanced += f"- Acknowledge uncertainty when appropriate\n"
        enhanced += f"- Keep response concise yet comprehensive\n"
        enhanced += f"- Estimated time: {task.estimated_duration}s\n"

        # Add workflow-specific guidance
        if task.workflow_type == WorkflowType.REASONING:
            enhanced += f"- Provide step-by-step reasoning\n"
        elif task.workflow_type == WorkflowType.COMPARATIVE:
            enhanced += f"- Include clear comparisons and contrasts\n"
        elif task.workflow_type == WorkflowType.MULTIMODAL:
            enhanced += f"- Consider multiple data types and sources\n"

        return enhanced

    async def _enhanced_fallback_search(
        self, query: str, user_id: str, organization_id: str
    ) -> MultiAgentSearchResult:
        """Enhanced fallback implementation with better results"""
        start_time = time.time()

        try:
            # Perform enhanced search
            search_query = SearchQuery(
                query=query, search_type=SearchType.HYBRID, limit=15
            )

            search_response = hybrid_search_service.search(
                search_request=search_query,
                user_id=user_id,
                organization_id=organization_id,
            )

            # Create enhanced mock execution
            execution = AgentExecution(
                execution_id=str(uuid.uuid4()),
                task_id="enhanced_fallback_search",
                agent_type=AgentType.RETRIEVAL,
                execution_time=time.time() - start_time,
                success=True,
                result={
                    "output": f"Enhanced search completed for '{query}'",
                    "results_count": len(search_response.results),
                    "search_type": "hybrid_fallback",
                },
                metadata={"fallback_mode": True, "enhanced": True},
                confidence_score=0.75,
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )

            # Generate enhanced answer
            synthesized_answer = self._generate_enhanced_answer(
                query, search_response.results
            )

            execution_time = time.time() - start_time

            return MultiAgentSearchResult(
                original_query=query,
                refined_query=query,
                expanded_queries=[],
                search_results=search_response.results,
                agent_executions=[execution],
                synthesized_answer=synthesized_answer,
                confidence_score=0.75,
                execution_time=execution_time,
                quality_metrics={
                    "relevancy": 0.75,
                    "completeness": 0.65,
                    "source_diversity": 0.8,
                },
                recommendations=[
                    "Consider using multi-agent mode for more comprehensive results",
                    "Try more specific queries for better precision",
                ],
                metadata={
                    "fallback_mode": True,
                    "enhanced_fallback": True,
                    "agents_used": 1,
                    "workflow_type": WorkflowType.FACTUAL_LOOKUP.value,
                },
                workflow_type=WorkflowType.FACTUAL_LOOKUP,
            )

        except Exception as e:
            logger.error(f"Enhanced fallback search failed: {e}")
            execution_time = time.time() - start_time

            return MultiAgentSearchResult(
                original_query=query,
                refined_query=query,
                expanded_queries=[],
                search_results=[],
                agent_executions=[],
                synthesized_answer=f"I encountered an error while searching for '{query}': {str(e)}",
                confidence_score=0.0,
                execution_time=execution_time,
                quality_metrics={},
                recommendations=["Please try rephrasing your query or contact support"],
                metadata={
                    "error": str(e),
                    "fallback_mode": True,
                    "enhanced_fallback": True,
                },
                workflow_type=WorkflowType.FACTUAL_LOOKUP,
            )

    def _generate_enhanced_answer(self, query: str, results: List[SearchResult]) -> str:
        """Generate enhanced answer from search results"""
        if not results:
            return f"I couldn't find relevant information for '{query}'. Please try different search terms or check your spelling."

        # Analyze results
        answer_parts = [f"## Search Results for '{query}'\n"]

        # Group by source type if available
        source_groups = {}
        for result in results[:10]:
            source_type = getattr(result, "source_type", "document")
            if source_type not in source_groups:
                source_groups[source_type] = []
            source_groups[source_type].append(result)

        # Generate organized answer
        for source_type, items in source_groups.items():
            answer_parts.append(f"\n### {source_type.title()} Results ({len(items)})")

            for i, result in enumerate(items[:3], 1):
                answer_parts.append(f"\n{i}. **{result.title}**")

                # Add relevance score if available
                if hasattr(result, "relevance_score") and result.relevance_score:
                    answer_parts.append(f"   - Relevance: {result.relevance_score:.2%}")

                # Add content preview
                if result.content_preview:
                    preview = (
                        result.content_preview[:300] + "..."
                        if len(result.content_preview) > 300
                        else result.content_preview
                    )
                    answer_parts.append(f"   - Preview: {preview}")

                # Add metadata if available
                if hasattr(result, "metadata") and result.metadata:
                    key_info = []
                    if "entities" in result.metadata:
                        key_info.append(f"Entities: {len(result.metadata['entities'])}")
                    if "date" in result.metadata:
                        key_info.append(f"Date: {result.metadata['date']}")
                    if key_info:
                        answer_parts.append(f"   - Info: {', '.join(key_info)}")

        answer_parts.append(f"\n---\n**Total Results Found**: {len(results)}")
        answer_parts.append(
            f"\n**Tip**: Use more specific terms or filters to refine your search."
        )

        return "\n".join(answer_parts)

    # Additional helper methods would continue here...
    # For brevity, I'll implement the key remaining methods:

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
            AgentType.CONTEXT_ANALYSIS: getattr(self, "context_agent", None),
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

    def _update_agent_metrics(self, executions: List[AgentExecution]):
        """Update performance metrics for agents"""
        for execution in executions:
            agent_type = execution.agent_type
            if agent_type in self.agent_metrics:
                metrics = self.agent_metrics[agent_type]
                metrics.total_executions += 1

                if execution.success:
                    metrics.successful_executions += 1

                # Update average execution time
                if metrics.total_executions == 1:
                    metrics.average_execution_time = execution.execution_time
                else:
                    metrics.average_execution_time = (
                        metrics.average_execution_time * (metrics.total_executions - 1)
                        + execution.execution_time
                    ) / metrics.total_executions

                # Update confidence score
                if metrics.total_executions == 1:
                    metrics.confidence_score = execution.confidence_score
                else:
                    metrics.confidence_score = (
                        metrics.confidence_score * (metrics.total_executions - 1)
                        + execution.confidence_score
                    ) / metrics.total_executions

                metrics.last_execution = datetime.now(timezone.utc)

                # Update token usage if available
                if execution.token_usage:
                    metrics.token_usage += sum(execution.token_usage.values())

                # Update error count
                if not execution.success:
                    metrics.error_count += 1

    async def _update_learning(
        self,
        query: str,
        analysis: Dict[str, Any],
        executions: List[AgentExecution],
        execution_time: float,
    ):
        """Update learning from query execution"""
        learning_data = {
            "query": query,
            "analysis": analysis,
            "execution_time": execution_time,
            "success_rate": len([e for e in executions if e.success]) / len(executions)
            if executions
            else 0,
            "timestamp": datetime.now(timezone.utc),
            "agent_performance": {
                e.agent_type.value: {
                    "success": e.success,
                    "time": e.execution_time,
                    "confidence": e.confidence_score,
                }
                for e in executions
            },
        }

        # Add to history (keep last 1000)
        self.query_history.append(learning_data)
        if len(self.query_history) > 1000:
            self.query_history = self.query_history[-1000:]

    def _extract_and_enhance_results(
        self, executions: List[AgentExecution]
    ) -> List[SearchResult]:
        """Extract and enhance search results from agent executions"""
        # Look for retrieval and enrichment agent results
        relevant_executions = [
            e
            for e in executions
            if e.agent_type in [AgentType.RETRIEVAL, AgentType.RESULT_ENRICHMENT]
            and e.success
        ]

        # Combine results from multiple executions
        all_results = []
        seen_ids = set()

        for execution in relevant_executions:
            output = execution.result.get("output", "")
            # This would need proper parsing based on actual output format
            # For now, return empty list
            pass

        return all_results

    async def _enhanced_synthesis(
        self, query: str, executions: List[AgentExecution], analysis: Dict[str, Any]
    ) -> str:
        """Enhanced answer synthesis with better context integration"""
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
            return synthesis_execution.result.get("output", "")

        # Fallback: create enhanced synthesis from other agents
        successful_executions = [e for e in executions if e.success]

        if successful_executions:
            # Organize by agent type
            agent_outputs = {}
            for execution in successful_executions:
                if execution.agent_type != AgentType.ANSWER_SYNTHESIS:
                    agent_outputs[execution.agent_type.value] = execution.result.get(
                        "output", ""
                    )

            # Create structured answer
            answer_parts = [f"## Analysis for '{query}'\n"]

            if AgentType.CONTEXT_ANALYSIS.value in agent_outputs:
                answer_parts.append("### Context Analysis")
                answer_parts.append(
                    agent_outputs[AgentType.CONTEXT_ANALYSIS.value][:300] + "..."
                )

            if AgentType.RETRIEVAL.value in agent_outputs:
                answer_parts.append("\n### Key Findings")
                answer_parts.append(
                    agent_outputs[AgentType.RETRIEVAL.value][:400] + "..."
                )

            if AgentType.QUALITY_ASSURANCE.value in agent_outputs:
                answer_parts.append("\n### Quality Assessment")
                answer_parts.append(
                    agent_outputs[AgentType.QUALITY_ASSURANCE.value][:300] + "..."
                )

            return "\n".join(answer_parts)

        return f"Unable to provide comprehensive results for '{query}' at this time."

    async def _generate_enhanced_quality_metrics(
        self, executions: List[AgentExecution], analysis: Dict[str, Any]
    ) -> Dict[str, float]:
        """Generate comprehensive quality metrics"""
        metrics = {}

        # Success metrics
        successful = len([e for e in executions if e.success])
        metrics["agent_success_rate"] = (
            successful / len(executions) if executions else 0.0
        )
        metrics["total_agents_used"] = len(executions)
        metrics["successful_agents"] = successful

        # Execution efficiency
        if executions:
            total_estimated = sum(
                e.metadata.get("estimated_duration", 30) for e in executions
            )
            total_actual = sum(e.execution_time for e in executions)
            metrics["execution_efficiency"] = (
                min(total_estimated / total_actual, 2.0) if total_actual > 0 else 1.0
            )
            metrics["average_agent_time"] = total_actual / len(executions)

        # Collaboration score
        metrics["collaboration_score"] = self._calculate_enhanced_collaboration_score(
            executions
        )

        # Quality indicators
        if executions:
            avg_confidence = sum(e.confidence_score for e in executions) / len(
                executions
            )
            metrics["average_confidence"] = avg_confidence

        # Query-specific metrics
        metrics["query_complexity_score"] = {
            "simple": 0.3,
            "moderate": 0.6,
            "complex": 0.9,
        }.get(analysis.get("complexity", "moderate"), 0.6)

        # Workflow effectiveness
        workflow_type = analysis.get("workflow_type", WorkflowType.FACTUAL_LOOKUP)
        metrics["workflow_effectiveness"] = (
            0.8 if successful == len(executions) else 0.5
        )

        return metrics

    def _calculate_enhanced_confidence_score(
        self, executions: List[AgentExecution], analysis: Dict[str, Any]
    ) -> float:
        """Calculate enhanced confidence score"""
        if not executions:
            return 0.0

        # Base confidence from success rate
        successful_executions = [e for e in executions if e.success]
        base_confidence = len(successful_executions) / len(executions)

        # Factor in agent quality
        avg_agent_confidence = sum(e.confidence_score for e in executions) / len(
            executions
        )

        # Factor in execution quality
        quality_scores = []
        for execution in executions:
            if execution.quality_indicators:
                quality_scores.append(
                    sum(execution.quality_indicators.values())
                    / len(execution.quality_indicators)
                )

        avg_quality = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 0.5
        )

        # Combine factors
        enhanced_confidence = (
            base_confidence * 0.4
            + avg_agent_confidence * 0.3  # 40% weight on success
            + avg_quality  # 30% weight on agent confidence
            * 0.3  # 30% weight on execution quality
        )

        # Apply complexity modifier
        complexity_modifier = {"simple": 1.1, "moderate": 1.0, "complex": 0.9}.get(
            analysis.get("complexity", "moderate"), 1.0
        )

        return min(enhanced_confidence * complexity_modifier, 1.0)

    def _calculate_enhanced_collaboration_score(
        self, executions: List[AgentExecution]
    ) -> float:
        """Calculate enhanced collaboration score"""
        if len(executions) <= 1:
            return 0.5

        # Agent type diversity
        successful_types = set(e.agent_type for e in executions if e.success)
        diversity_score = len(successful_types) / len(set(AgentType))

        # Success rate
        success_rate = len([e for e in executions if e.success]) / len(executions)

        # Execution harmony (executions completing close to estimated times)
        harmony_scores = []
        for execution in executions:
            if execution.success:
                estimated = execution.metadata.get("estimated_duration", 30)
                actual = execution.execution_time
                harmony = 1.0 - abs(estimated - actual) / estimated
                harmony_scores.append(max(0, harmony))

        avg_harmony = (
            sum(harmony_scores) / len(harmony_scores) if harmony_scores else 0.5
        )

        # Combine factors
        collaboration_score = (
            diversity_score * 0.3 + success_rate * 0.4 + avg_harmony * 0.3
        )

        return collaboration_score

    def _generate_enhanced_recommendations(
        self, executions: List[AgentExecution], analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate enhanced recommendations based on execution analysis"""
        recommendations = []

        # Analyze failures
        failed_executions = [e for e in executions if not e.success]
        if failed_executions:
            failed_types = [e.agent_type.value for e in failed_executions]
            recommendations.append(
                f"Failed agents: {', '.join(failed_types)}. Consider retrying with different parameters."
            )

        # Analyze performance
        slow_executions = [
            e
            for e in executions
            if e.execution_time > e.metadata.get("estimated_duration", 30) * 1.5
        ]
        if slow_executions:
            recommendations.append(
                "Some agents exceeded time estimates - consider query simplification or increased timeouts."
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
        if qa_execution:
            recommendations.append(
                "Quality assessment completed - results have been validated for accuracy."
            )

        # Complexity-based recommendations
        complexity = analysis.get("complexity", "moderate")
        if complexity == "complex":
            recommendations.append(
                "Complex query detected - consider breaking down into simpler questions for better results."
            )
        elif complexity == "simple":
            recommendations.append(
                "Query appears simple - consider using direct search for faster responses."
            )

        # Coverage recommendations
        successful_executions = len([e for e in executions if e.success])
        if successful_executions < len(executions) * 0.8:
            recommendations.append(
                "Not all agents completed successfully - try rephrasing your query for better compatibility."
            )

        return recommendations

    def get_agent_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive agent performance report"""
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "crewai_available": CREWAI_AVAILABLE,
            "agents_configured": len(
                [
                    a
                    for a in [
                        self.retrieval_agent,
                        self.graph_agent,
                        self.qa_agent,
                        self.synthesis_agent,
                        self.query_agent,
                        self.enrichment_agent,
                        self.context_agent,
                    ]
                    if a
                ]
            ),
            "total_queries_processed": len(self.query_history),
            "agent_metrics": {},
        }

        # Add detailed metrics for each agent
        for agent_type, metrics in self.agent_metrics.items():
            report["agent_metrics"][agent_type.value] = {
                "total_executions": metrics.total_executions,
                "success_rate": metrics.successful_executions / metrics.total_executions
                if metrics.total_executions > 0
                else 0,
                "average_execution_time": metrics.average_execution_time,
                "confidence_score": metrics.confidence_score,
                "last_execution": metrics.last_execution.isoformat()
                if metrics.last_execution
                else None,
                "error_rate": metrics.error_count / metrics.total_executions
                if metrics.total_executions > 0
                else 0,
            }

        return report

    def get_workflow_recommendations(self, query: str) -> Dict[str, Any]:
        """Get workflow recommendations for a query"""
        return {
            "query": query,
            "recommended_workflow": self._recommend_workflow(query),
            "suggested_agents": self._suggest_agents(query),
            "estimated_duration": self._estimate_execution_time(query),
            "optimization_tips": self._get_optimization_tips(query),
        }

    def _recommend_workflow(self, query: str) -> WorkflowType:
        """Recommend best workflow for query"""
        query_lower = query.lower()

        if any(
            word in query_lower for word in ["compare", "difference", "versus", "vs"]
        ):
            return WorkflowType.COMPARATIVE
        elif any(
            word in query_lower
            for word in ["explain why", "how does", "analyze", "reason"]
        ):
            return WorkflowType.REASONING
        elif any(
            word in query_lower for word in ["explore", "discover", "find related"]
        ):
            return WorkflowType.EXPLORATORY
        elif any(
            word in query_lower for word in ["image", "video", "audio", "multimodal"]
        ):
            return WorkflowType.MULTIMODAL
        else:
            return WorkflowType.FACTUAL_LOOKUP

    def _suggest_agents(self, query: str) -> List[AgentType]:
        """Suggest optimal agents for query"""
        suggested = [
            AgentType.CONTEXT_ANALYSIS,
            AgentType.QUERY_UNDERSTANDING,
            AgentType.RETRIEVAL,
        ]

        query_lower = query.lower()

        if any(
            word in query_lower
            for word in ["entity", "relationship", "connected", "related to"]
        ):
            suggested.append(AgentType.GRAPH_NAVIGATION)

        if len(query.split()) > 10:
            suggested.append(AgentType.QUALITY_ASSURANCE)

        return suggested

    def _estimate_execution_time(self, query: str) -> float:
        """Estimate execution time for query"""
        base_time = 60.0  # Base time in seconds
        word_count = len(query.split())

        # Add time based on complexity
        if word_count > 15:
            base_time *= 1.5
        elif word_count > 8:
            base_time *= 1.2

        return base_time

    def _get_optimization_tips(self, query: str) -> List[str]:
        """Get optimization tips for query"""
        tips = []

        word_count = len(query.split())

        if word_count > 20:
            tips.append(
                "Consider breaking this complex query into multiple simpler questions"
            )
        elif word_count < 5:
            tips.append("Add more context or specific terms for better results")

        if "?" not in query and not any(
            word in query.lower() for word in ["what", "how", "why", "when"]
        ):
            tips.append("Consider rephrasing as a question for more targeted results")

        if not any(word.isupper() for word in query.split()):
            tips.append(
                "Include proper nouns or specific terms for better entity recognition"
            )

        return tips


# Global enhanced multi-agent search service instance
multi_agent_search_service_v2 = MultiAgentSearchServiceV2()
