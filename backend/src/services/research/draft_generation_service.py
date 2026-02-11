"""
Draft Generation Service
Generates literature review drafts from project documents using AI

Uses CrewAI multi-agent pipeline when available, with direct LLM fallback.
Agents: Document Analyzer, Literature Synthesizer, Citation Validator.
"""

import asyncio
import hashlib
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from prometheus_client import Counter, Histogram
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.collection import CollectionDocument
from src.models.document import Document
from src.models.draft_citation import DraftCitation
from src.models.generated_draft import GeneratedDraft

# CrewAI imports (optional)
try:
    from crewai import Agent, Crew, Process, Task

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False

# Direct LLM fallback imports
try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Prometheus Metrics (T088)
# ---------------------------------------------------------------------------

draft_generation_duration = Histogram(
    "draft_generation_duration_seconds",
    "Duration of draft generation",
    ["num_documents"],
)
draft_generation_total = Counter(
    "draft_generation_total",
    "Total draft generations",
    ["status"],
)


class DraftGenerationStatus:
    """Tracks draft generation progress"""

    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    CITING = "citing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# In-memory store for generation status (would use Redis in production)
_generation_status: Dict[str, Dict[str, Any]] = {}


class DraftGenerationService:
    """Service for generating literature review drafts"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm: Optional[str] = None
        self._openai_client: Optional[Any] = None
        self._anthropic_client: Optional[Any] = None
        self._initialize_llm()

    # ------------------------------------------------------------------
    # LLM Initialization
    # ------------------------------------------------------------------

    def _initialize_llm(self) -> None:
        """Configure LLM backend — Azure OpenAI > OpenAI > Anthropic."""
        # Azure OpenAI
        if settings.AZURE_OPENAI_API_KEY and (
            settings.AZURE_OPENAI_ENDPOINT
            or settings.AZURE_OPENAI_CHAT_ENDPOINT
        ):
            try:
                os.environ["AZURE_OPENAI_API_KEY"] = (
                    settings.AZURE_OPENAI_CHAT_API_KEY
                    or settings.AZURE_OPENAI_API_KEY
                )
                os.environ["AZURE_OPENAI_ENDPOINT"] = (
                    settings.AZURE_OPENAI_CHAT_ENDPOINT
                    or settings.AZURE_OPENAI_ENDPOINT
                )
                os.environ["OPENAI_API_VERSION"] = (
                    settings.AZURE_OPENAI_CHAT_API_VERSION
                )
                os.environ["OPENAI_API_TYPE"] = "azure"
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
                logger.info("draft_llm_initialized", provider="azure", model=self.llm)
                return
            except Exception as e:
                logger.error("draft_azure_init_failed", error=str(e))

        # Standard OpenAI
        if settings.OPENAI_API_KEY and OPENAI_AVAILABLE:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
            self.llm = "gpt-4o-mini"
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("draft_llm_initialized", provider="openai", model=self.llm)
            return

        # Anthropic
        if settings.ANTHROPIC_API_KEY and ANTHROPIC_AVAILABLE:
            self._anthropic_client = anthropic.AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY,
            )
            logger.info("draft_llm_initialized", provider="anthropic")
            return

        logger.warning("draft_no_llm_configured")

    # ------------------------------------------------------------------
    # CrewAI Agent Setup
    # ------------------------------------------------------------------

    def _create_crew_agents(self) -> Dict[str, "Agent"]:
        """Create CrewAI agents for the literature review pipeline."""
        if not CREWAI_AVAILABLE or not self.llm:
            return {}

        analyzer = Agent(
            role="Document Analyzer",
            goal="Extract key themes, findings, and methodologies from research documents",
            backstory=(
                "You are an expert research analyst who reads academic papers "
                "and extracts structured information about themes, key findings, "
                "methodologies, and conclusions."
            ),
            verbose=False,
            allow_delegation=False,
            llm=self.llm,
        )

        synthesizer = Agent(
            role="Literature Synthesizer",
            goal="Write cohesive literature review sections organized by theme with [Doc N] citations",
            backstory=(
                "You are an accomplished academic writer who synthesizes research "
                "from multiple sources into coherent literature review sections. "
                "You always cite sources using [Doc N] notation."
            ),
            verbose=False,
            allow_delegation=False,
            llm=self.llm,
        )

        validator = Agent(
            role="Citation Validator",
            goal="Verify all [Doc N] references map to actual documents and fix orphaned citations",
            backstory=(
                "You are a meticulous editor who checks every citation reference "
                "in a literature review to ensure accuracy and completeness."
            ),
            verbose=False,
            allow_delegation=False,
            llm=self.llm,
        )

        return {
            "analyzer": analyzer,
            "synthesizer": synthesizer,
            "validator": validator,
        }

    # ------------------------------------------------------------------
    # Document Content Retrieval
    # ------------------------------------------------------------------

    async def _get_project_documents(
        self,
        project_id: UUID,
        document_ids: Optional[List[UUID]] = None,
    ) -> List[Document]:
        """Get documents for a project, optionally filtered by IDs."""
        if document_ids:
            # Filter by specific IDs, but verify they belong to the project
            docs_query = (
                select(Document)
                .join(
                    CollectionDocument,
                    Document.id == CollectionDocument.document_id,
                )
                .where(
                    CollectionDocument.collection_id == project_id,
                    Document.id.in_(document_ids),
                )
            )
        else:
            docs_query = (
                select(Document)
                .join(
                    CollectionDocument,
                    Document.id == CollectionDocument.document_id,
                )
                .where(CollectionDocument.collection_id == project_id)
            )

        result = await self.db.execute(docs_query)
        return list(result.scalars().all())

    def _build_document_context(
        self,
        documents: List[Document],
    ) -> Dict[int, Dict[str, Any]]:
        """Build a numbered context map for [Doc N] referencing."""
        context: Dict[int, Dict[str, Any]] = {}
        for idx, doc in enumerate(documents, start=1):
            content = getattr(doc, "content_text", None) or ""
            summary = getattr(doc, "content_summary", None) or ""
            title = doc.title or doc.filename or f"Document {idx}"

            # Truncate content for LLM context window
            max_chars = 4000
            if len(content) > max_chars:
                content = content[:max_chars] + "..."

            context[idx] = {
                "id": doc.id,
                "title": title,
                "content": content,
                "summary": summary,
            }
        return context

    # ------------------------------------------------------------------
    # LLM Content Generation
    # ------------------------------------------------------------------

    async def _generate_with_crew(
        self,
        doc_context: Dict[int, Dict[str, Any]],
        themes: List[str],
        style: str,
        max_sections: int,
        include_abstract: bool,
    ) -> str:
        """Generate draft content using CrewAI multi-agent pipeline."""
        agents = self._create_crew_agents()
        if not agents:
            return await self._generate_with_direct_llm(
                doc_context, themes, style, max_sections, include_abstract
            )

        doc_summaries = self._format_doc_summaries(doc_context)

        # Task 1: Analyze documents
        analyze_task = Task(
            description=(
                f"Analyze the following documents and extract key themes, findings, "
                f"and methodologies relevant to: {', '.join(themes)}.\n\n"
                f"Documents:\n{doc_summaries}\n\n"
                f"For each document, identify the most relevant passages and how they "
                f"relate to the requested themes. Output structured notes."
            ),
            expected_output="Structured analysis notes with relevant passages per theme per document",
            agent=agents["analyzer"],
        )

        # Task 2: Synthesize into review
        synthesize_task = Task(
            description=(
                f"Using the document analysis, write a {style} literature review "
                f"with up to {max_sections} sections covering these themes: "
                f"{', '.join(themes)}.\n\n"
                f"{'Include an Abstract section. ' if include_abstract else ''}"
                f"Use [Doc N] notation for inline citations (e.g., [Doc 1], [Doc 3]). "
                f"Each section should synthesize findings from multiple documents. "
                f"Write in markdown format with ## headers for sections."
            ),
            expected_output="Complete literature review in markdown with [Doc N] citations",
            agent=agents["synthesizer"],
        )

        # Task 3: Validate citations
        num_docs = len(doc_context)
        validate_task = Task(
            description=(
                f"Review the literature review and verify that every [Doc N] reference "
                f"uses a valid N between 1 and {num_docs}. Remove or fix any "
                f"references to documents that don't exist. Ensure every section "
                f"has at least one citation. Return the corrected review."
            ),
            expected_output="Validated literature review with all citations verified",
            agent=agents["validator"],
        )

        crew = Crew(
            agents=list(agents.values()),
            tasks=[analyze_task, synthesize_task, validate_task],
            process=Process.sequential,
            verbose=False,
        )

        # Run crew in thread pool (CrewAI is sync)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, crew.kickoff)

        return str(result)

    async def _generate_with_direct_llm(
        self,
        doc_context: Dict[int, Dict[str, Any]],
        themes: List[str],
        style: str,
        max_sections: int,
        include_abstract: bool,
    ) -> str:
        """Fallback: generate using direct OpenAI or Anthropic API calls."""
        doc_summaries = self._format_doc_summaries(doc_context)

        system_prompt = (
            "You are an expert academic writer specializing in literature reviews. "
            "You synthesize research from multiple documents into coherent, "
            "well-structured reviews with proper citations."
        )

        user_prompt = (
            f"Write a {style} literature review based on the following documents. "
            f"Organize it into up to {max_sections} sections covering these themes: "
            f"{', '.join(themes)}.\n\n"
            f"{'Include an Abstract section at the beginning. ' if include_abstract else ''}"
            f"Use [Doc N] notation for inline citations (e.g., [Doc 1], [Doc 3]). "
            f"Write in markdown format with ## headers.\n\n"
            f"Documents:\n{doc_summaries}"
        )

        # Try OpenAI first
        if self._openai_client:
            try:
                response = await self._openai_client.chat.completions.create(
                    model=self.llm or "gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.7,
                    max_tokens=4000,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.error("openai_generation_failed", error=str(e))

        # Try Anthropic
        if self._anthropic_client:
            try:
                response = await self._anthropic_client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=4000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return response.content[0].text
            except Exception as e:
                logger.error("anthropic_generation_failed", error=str(e))

        # Final fallback: template-based generation
        logger.warning("draft_using_template_fallback")
        return self._build_template_content(
            doc_context, themes, style, max_sections, include_abstract
        )

    def _format_doc_summaries(
        self,
        doc_context: Dict[int, Dict[str, Any]],
    ) -> str:
        """Format document context for LLM prompts."""
        parts = []
        for idx, doc in doc_context.items():
            text = doc["summary"] or doc["content"]
            if len(text) > 2000:
                text = text[:2000] + "..."
            parts.append(f"[Doc {idx}] {doc['title']}\n{text}\n")
        return "\n---\n".join(parts)

    def _build_template_content(
        self,
        doc_context: Dict[int, Dict[str, Any]],
        themes: List[str],
        style: str,
        max_sections: int,
        include_abstract: bool,
    ) -> str:
        """Template-based fallback when no LLM is available."""
        num_docs = len(doc_context)
        sections = []

        if include_abstract:
            sections.append(
                f"## Abstract\n\n"
                f"This literature review synthesizes research from {num_docs} documents, "
                f"focusing on the themes of {', '.join(themes)}. The review provides "
                f"a comprehensive analysis of current research and identifies key "
                f"findings and trends in the field.\n"
            )

        sections.append(
            f"## 1. Introduction\n\n"
            f"The field encompassing {themes[0] if themes else 'this research area'} "
            f"has seen significant developments in recent years. This literature review "
            f"examines {num_docs} key publications to understand the current state of "
            f"research and identify emerging trends.\n"
        )

        for i, theme in enumerate(themes[: max_sections - 2], start=2):
            doc_refs = " ".join(
                f"[Doc {j}]" for j in list(doc_context.keys())[:3]
            )
            sections.append(
                f"## {i}. {theme.title()}\n\n"
                f"Research on {theme} has been extensively documented in the literature "
                f"{doc_refs}. Studies have shown various approaches to understanding "
                f"and addressing challenges in this area.\n\n"
                f"Key findings indicate that {theme} plays a significant role in the "
                f"broader context of the research domain. Multiple researchers have "
                f"contributed to our understanding of these phenomena, each building "
                f"upon previous work to advance the field.\n"
            )

        section_num = min(len(themes) + 2, max_sections)
        sections.append(
            f"## {section_num}. Conclusion\n\n"
            f"This review has synthesized findings from {num_docs} publications "
            f"across the themes of {', '.join(themes)}. The literature demonstrates "
            f"significant progress in understanding these interconnected areas, while "
            f"also highlighting opportunities for future research.\n"
        )

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Citation Extraction
    # ------------------------------------------------------------------

    def _extract_citations_from_content(
        self,
        content: str,
        doc_context: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Extract [Doc N] citations from generated content and map to documents."""
        citations: List[Dict[str, Any]] = []
        pattern = r"\[Doc (\d+)\]"

        seen: set[int] = set()
        for match in re.finditer(pattern, content):
            doc_num = int(match.group(1))
            if doc_num in seen or doc_num not in doc_context:
                continue
            seen.add(doc_num)

            doc = doc_context[doc_num]

            # Extract the sentence containing the citation for snippet
            start = max(0, match.start() - 200)
            end = min(len(content), match.end() + 200)
            context_text = content[start:end].strip()

            citations.append({
                "document_id": doc["id"],
                "citation_id": None,
                "snippet": doc["title"][:200],
                "context": context_text,
            })

        return citations

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_draft(
        self,
        project_id: UUID,
        user_id: UUID,
        themes: List[str],
        document_ids: Optional[List[UUID]] = None,
        style: str = "academic",
        max_sections: int = 5,
        include_abstract: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a literature review draft from project documents.

        Returns generation status with task ID for polling.
        """
        task_id = hashlib.md5(
            f"{project_id}:{time.time()}".encode(), usedforsecurity=False
        ).hexdigest()[:12]

        _generation_status[task_id] = {
            "status": DraftGenerationStatus.PENDING,
            "progress": 0,
            "current_step": "Initializing",
            "started_at": datetime.utcnow().isoformat(),
            "estimated_remaining": None,
            "project_id": str(project_id),
            "user_id": str(user_id),
        }

        asyncio.create_task(
            self._generate_draft_async(
                task_id=task_id,
                project_id=project_id,
                user_id=user_id,
                themes=themes,
                document_ids=document_ids,
                style=style,
                max_sections=max_sections,
                include_abstract=include_abstract,
            )
        )

        return {
            "task_id": task_id,
            "status": DraftGenerationStatus.PENDING,
            "message": "Draft generation started",
        }

    async def _generate_draft_async(
        self,
        task_id: str,
        project_id: UUID,
        user_id: UUID,
        themes: List[str],
        document_ids: Optional[List[UUID]],
        style: str,
        max_sections: int,
        include_abstract: bool,
    ) -> None:
        """Background task for draft generation."""
        start_time = time.time()
        num_documents = 0

        try:
            # Phase 1: Analyzing documents
            self._update_status(
                task_id, DraftGenerationStatus.ANALYZING, 10,
                "Retrieving project documents",
            )

            documents = await self._get_project_documents(
                project_id, document_ids
            )
            num_documents = len(documents)

            if not documents:
                self._update_status(
                    task_id, DraftGenerationStatus.FAILED, 0,
                    "No documents found in project",
                )
                draft_generation_total.labels(status="failed").inc()
                return

            doc_context = self._build_document_context(documents)

            self._update_status(
                task_id, DraftGenerationStatus.ANALYZING, 20,
                f"Analyzing {num_documents} documents",
            )

            # Check for cancellation
            if self._is_cancelled(task_id):
                return

            # Phase 2: Generate content via CrewAI or direct LLM
            self._update_status(
                task_id, DraftGenerationStatus.GENERATING, 30,
                "Generating literature review",
            )

            if CREWAI_AVAILABLE and self.llm:
                draft_content = await self._generate_with_crew(
                    doc_context, themes, style, max_sections, include_abstract,
                )
            else:
                draft_content = await self._generate_with_direct_llm(
                    doc_context, themes, style, max_sections, include_abstract,
                )

            if self._is_cancelled(task_id):
                return

            self._update_status(
                task_id, DraftGenerationStatus.GENERATING, 60,
                "Building sections",
            )

            # Phase 3: Extract and validate citations
            self._update_status(
                task_id, DraftGenerationStatus.CITING, 80,
                "Validating citations",
            )

            citations_data = self._extract_citations_from_content(
                draft_content, doc_context,
            )

            if self._is_cancelled(task_id):
                return

            # Phase 4: Finalize and persist
            self._update_status(
                task_id, DraftGenerationStatus.FINALIZING, 90,
                "Saving draft",
            )

            version_query = select(func.max(GeneratedDraft.version)).where(
                GeneratedDraft.project_id == project_id
            )
            result = await self.db.execute(version_query)
            max_version = result.scalar() or 0
            new_version = max_version + 1

            # Mark previous drafts as not current
            await self.db.execute(
                GeneratedDraft.__table__.update()
                .where(GeneratedDraft.project_id == project_id)
                .values(is_current=False)
            )

            duration_ms = int((time.time() - start_time) * 1000)

            draft = GeneratedDraft(
                project_id=project_id,
                user_id=user_id,
                version=new_version,
                title=f"Literature Review - {', '.join(themes[:3])}",
                content=draft_content,
                themes=themes,
                word_count=len(draft_content.split()),
                citation_count=len(citations_data),
                generation_params={
                    "style": style,
                    "max_sections": max_sections,
                    "include_abstract": include_abstract,
                    "document_count": num_documents,
                    "llm_provider": self._get_provider_name(),
                },
                generation_time_ms=duration_ms,
                is_current=True,
            )

            self.db.add(draft)
            await self.db.flush()

            for idx, citation_data in enumerate(citations_data):
                draft_citation = DraftCitation(
                    draft_id=draft.id,
                    citation_index=idx + 1,
                    document_id=citation_data.get("document_id"),
                    citation_id=citation_data.get("citation_id"),
                    snippet=citation_data.get("snippet", ""),
                    context=citation_data.get("context", ""),
                )
                self.db.add(draft_citation)

            await self.db.commit()

            # Record metrics
            duration = time.time() - start_time
            bucket = str(min(num_documents, 50))
            draft_generation_duration.labels(num_documents=bucket).observe(duration)
            draft_generation_total.labels(status="completed").inc()

            self._update_status(
                task_id,
                DraftGenerationStatus.COMPLETED,
                100,
                "Draft completed",
                draft_id=str(draft.id),
                duration=duration,
            )

            logger.info(
                "draft_generated",
                project_id=str(project_id),
                draft_id=str(draft.id),
                version=new_version,
                word_count=draft.word_count,
                citation_count=len(citations_data),
                duration_seconds=round(duration, 2),
                provider=self._get_provider_name(),
            )

        except asyncio.CancelledError:
            self._update_status(
                task_id, DraftGenerationStatus.CANCELLED, 0,
                "Generation cancelled",
            )
            draft_generation_total.labels(status="cancelled").inc()
            logger.info("draft_generation_cancelled", task_id=task_id)

        except Exception as e:
            self._update_status(
                task_id, DraftGenerationStatus.FAILED, 0,
                f"Error: {str(e)}",
            )
            draft_generation_total.labels(status="failed").inc()
            logger.error(
                "draft_generation_failed", task_id=task_id, error=str(e),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_provider_name(self) -> str:
        """Return the name of the active LLM provider."""
        if self.llm and self.llm.startswith("azure/"):
            return "azure_openai"
        if self._openai_client:
            return "openai"
        if self._anthropic_client:
            return "anthropic"
        return "template"

    def _is_cancelled(self, task_id: str) -> bool:
        """Check if the generation was cancelled."""
        status_info = _generation_status.get(task_id)
        if status_info and status_info["status"] == DraftGenerationStatus.CANCELLED:
            logger.info("draft_generation_cancelled", task_id=task_id)
            draft_generation_total.labels(status="cancelled").inc()
            return True
        return False

    def _update_status(
        self,
        task_id: str,
        status: str,
        progress: int,
        step: str,
        **extra: Any,
    ) -> None:
        """Update generation status."""
        if task_id in _generation_status:
            _generation_status[task_id].update({
                "status": status,
                "progress": progress,
                "current_step": step,
                "updated_at": datetime.utcnow().isoformat(),
                **extra,
            })

    @staticmethod
    def get_status(task_id: str) -> Optional[Dict[str, Any]]:
        """Get generation status for a task."""
        return _generation_status.get(task_id)

    @staticmethod
    def cancel_generation(task_id: str) -> bool:
        """Cancel an ongoing generation."""
        if task_id in _generation_status:
            info = _generation_status[task_id]
            if info["status"] not in [
                DraftGenerationStatus.COMPLETED,
                DraftGenerationStatus.FAILED,
                DraftGenerationStatus.CANCELLED,
            ]:
                _generation_status[task_id]["status"] = (
                    DraftGenerationStatus.CANCELLED
                )
                _generation_status[task_id]["current_step"] = "Cancelled by user"
                return True
        return False

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    async def get_draft(
        self,
        project_id: UUID,
        draft_id: Optional[UUID] = None,
        current_only: bool = False,
    ) -> Optional[GeneratedDraft]:
        """Get a specific draft or current draft."""
        if draft_id:
            query = select(GeneratedDraft).where(
                GeneratedDraft.id == draft_id,
                GeneratedDraft.project_id == project_id,
            )
        elif current_only:
            query = select(GeneratedDraft).where(
                GeneratedDraft.project_id == project_id,
                GeneratedDraft.is_current == True,  # noqa: E712
            )
        else:
            return None

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_drafts(
        self,
        project_id: UUID,
        include_content: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """List all drafts for a project."""
        count_query = select(func.count(GeneratedDraft.id)).where(
            GeneratedDraft.project_id == project_id
        )
        result = await self.db.execute(count_query)
        total = result.scalar() or 0

        query = (
            select(GeneratedDraft)
            .where(GeneratedDraft.project_id == project_id)
            .order_by(GeneratedDraft.version.desc())
            .offset(skip)
            .limit(limit)
        )

        result = await self.db.execute(query)
        drafts = result.scalars().all()

        return {
            "drafts": drafts,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    async def delete_draft(self, project_id: UUID, draft_id: UUID) -> bool:
        """Delete a specific draft."""
        query = select(GeneratedDraft).where(
            GeneratedDraft.id == draft_id,
            GeneratedDraft.project_id == project_id,
        )
        result = await self.db.execute(query)
        draft = result.scalar_one_or_none()

        if not draft:
            return False

        await self.db.delete(draft)
        await self.db.commit()
        return True

    async def get_draft_citations(
        self,
        project_id: UUID,
        draft_id: UUID,
    ) -> List[DraftCitation]:
        """Get citations for a specific draft."""
        query = (
            select(DraftCitation)
            .join(GeneratedDraft, DraftCitation.draft_id == GeneratedDraft.id)
            .where(
                GeneratedDraft.project_id == project_id,
                DraftCitation.draft_id == draft_id,
            )
            .order_by(DraftCitation.citation_index)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def compare_drafts(
        self,
        project_id: UUID,
        version_a: int,
        version_b: int,
    ) -> Dict[str, Any]:
        """Compare two draft versions."""
        query_a = select(GeneratedDraft).where(
            GeneratedDraft.project_id == project_id,
            GeneratedDraft.version == version_a,
        )
        query_b = select(GeneratedDraft).where(
            GeneratedDraft.project_id == project_id,
            GeneratedDraft.version == version_b,
        )

        result_a = await self.db.execute(query_a)
        result_b = await self.db.execute(query_b)

        draft_a = result_a.scalar_one_or_none()
        draft_b = result_b.scalar_one_or_none()

        if not draft_a or not draft_b:
            return {"error": "One or both drafts not found"}

        words_a = set(draft_a.content.lower().split())
        words_b = set(draft_b.content.lower().split())
        intersection = len(words_a & words_b)
        union = len(words_a | words_b)
        similarity = intersection / union if union > 0 else 0

        return {
            "version_a": {
                "version": draft_a.version,
                "word_count": draft_a.word_count,
                "citation_count": draft_a.citation_count,
                "created_at": (
                    draft_a.created_at.isoformat() if draft_a.created_at else None
                ),
            },
            "version_b": {
                "version": draft_b.version,
                "word_count": draft_b.word_count,
                "citation_count": draft_b.citation_count,
                "created_at": (
                    draft_b.created_at.isoformat() if draft_b.created_at else None
                ),
            },
            "word_count_diff": draft_b.word_count - draft_a.word_count,
            "citation_count_diff": draft_b.citation_count - draft_a.citation_count,
            "similarity_score": round(similarity, 3),
        }

    async def export_draft(
        self,
        project_id: UUID,
        draft_id: UUID,
        format: str = "markdown",
        include_bibliography: bool = True,
        bib_format: str = "bibtex",
    ) -> Dict[str, Any]:
        """Export draft to specified format."""
        draft = await self.get_draft(project_id, draft_id)
        if not draft:
            return {"error": "Draft not found"}

        if format == "markdown":
            content = draft.content
            if include_bibliography:
                citations = await self.get_draft_citations(project_id, draft_id)
                if citations:
                    content += "\n\n## References\n\n"
                    for c in citations:
                        content += f"[Doc {c.citation_index}] {c.snippet}\n\n"

            return {
                "format": "markdown",
                "filename": f"{draft.title.replace(' ', '_')}.md",
                "content": content,
                "mime_type": "text/markdown",
            }

        elif format == "latex":
            latex_content = self._convert_to_latex(draft.content)
            bib_content = ""

            if include_bibliography:
                citations = await self.get_draft_citations(project_id, draft_id)
                bib_content = self._generate_bib_entries(citations)

            return {
                "format": "latex",
                "files": [
                    {
                        "filename": f"{draft.title.replace(' ', '_')}.tex",
                        "content": latex_content,
                        "mime_type": "application/x-tex",
                    },
                    {
                        "filename": "references.bib",
                        "content": bib_content,
                        "mime_type": "application/x-bibtex",
                    },
                ],
            }

        return {"error": f"Unsupported format: {format}"}

    def _convert_to_latex(self, markdown_content: str) -> str:
        """Convert markdown to LaTeX."""
        latex = markdown_content

        latex = re.sub(
            r"^## (\d+\.\s)?(.+)$", r"\\section{\2}", latex, flags=re.MULTILINE
        )
        latex = re.sub(
            r"^### (.+)$", r"\\subsection{\1}", latex, flags=re.MULTILINE
        )
        latex = re.sub(r"\[Doc (\d+)\]", r"\\cite{doc\1}", latex)

        title_text = markdown_content.split("\n")[0].replace("## ", "")

        latex = (
            "\\documentclass{article}\n"
            "\\usepackage{natbib}\n"
            "\\usepackage{hyperref}\n\n"
            f"\\title{{{title_text}}}\n"
            "\\author{Generated by Research Assistant}\n"
            "\\date{\\today}\n\n"
            "\\begin{document}\n\n"
            "\\maketitle\n\n"
            f"{latex}\n\n"
            "\\bibliographystyle{plain}\n"
            "\\bibliography{references}\n\n"
            "\\end{document}\n"
        )
        return latex

    def _generate_bib_entries(self, citations: List[DraftCitation]) -> str:
        """Generate BibTeX entries for citations."""
        entries = []
        for c in citations:
            entry = (
                f"@misc{{doc{c.citation_index},\n"
                f"  title = {{{c.snippet[:100]}}},\n"
                f"  note = {{{c.context[:200] if c.context else ''}}},\n"
                f"}}\n"
            )
            entries.append(entry)
        return "\n".join(entries)
