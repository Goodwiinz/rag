"""
Draft Generation Service
Generates literature review drafts from project documents using AI
"""

import asyncio
import hashlib
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.citation import Citation
from src.models.document import Document
from src.models.draft_citation import DraftCitation
from src.models.generated_draft import GeneratedDraft

logger = structlog.get_logger(__name__)


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
_draft_metrics_initialized = False
_draft_metrics_disabled = False


def _ensure_draft_metrics() -> None:
    """Create draft generation metrics once."""
    global _draft_metrics_initialized, _draft_metrics_disabled

    if _draft_metrics_initialized or _draft_metrics_disabled:
        return

    try:
        from src.observability.metrics import MetricConfig, create_metrics

        create_metrics(
            [
                MetricConfig(
                    name="draft_generation_duration_seconds",
                    description="Draft generation duration in seconds",
                    unit="seconds",
                ),
                MetricConfig(
                    name="draft_generation_total",
                    description="Total number of draft generations by status",
                    unit="requests",
                ),
            ]
        )
        _draft_metrics_initialized = True
    except Exception as exc:  # pragma: no cover - defensive observability guard
        _draft_metrics_disabled = True
        logger.warning("draft_metrics_init_failed", error=str(exc))


class DraftGenerationService:
    """Service for generating literature review drafts"""

    _background_tasks: set[asyncio.Task] = set()

    @staticmethod
    def _fire_and_forget(coro):
        task = asyncio.create_task(coro)
        DraftGenerationService._background_tasks.add(task)
        task.add_done_callback(DraftGenerationService._background_tasks.discard)
        return task

    TERMINAL_STATUSES = {
        DraftGenerationStatus.COMPLETED,
        DraftGenerationStatus.FAILED,
        DraftGenerationStatus.CANCELLED,
    }

    _STYLE_PROMPTS = {
        "academic": (
            "Use a formal academic tone. Passive voice is acceptable. "
            "Use field-specific terminology and cite sources precisely."
        ),
        "technical": (
            "Focus on technical detail. Include methodology and implementation "
            "specifics. Use precise technical language."
        ),
        "summary": (
            "Write in a concise executive summary style. Focus on key findings "
            "and implications. Keep language accessible."
        ),
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self._openai_client = self._init_openai_client()

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

        Args:
            project_id: Project to generate draft for
            user_id: User requesting the draft
            themes: List of themes/topics to focus on
            document_ids: Specific documents to include (optional, uses all if not specified)
            style: Writing style (academic/technical/summary)
            max_sections: Maximum number of sections
            include_abstract: Whether to include an abstract

        Returns:
            Generation status with task ID
        """
        # Use MD5 for non-security task ID generation (usedforsecurity=False)
        task_id = hashlib.md5(f"{project_id}:{time.time()}".encode(), usedforsecurity=False).hexdigest()[:12]

        # Initialize status
        _generation_status[task_id] = {
            "status": DraftGenerationStatus.PENDING,
            "progress": 0,
            "current_step": "Initializing",
            "started_at": datetime.utcnow().isoformat(),
            "estimated_remaining": None,
            "project_id": str(project_id),
            "user_id": str(user_id),
        }

        # Start generation in background
        self._fire_and_forget(
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
        """Background task for draft generation"""
        start_time = time.time()
        document_count = 0

        try:
            # Phase 1: Analyzing documents
            self._update_status(
                task_id, DraftGenerationStatus.ANALYZING, 10, "Analyzing documents"
            )

            # Get documents for the project
            if document_ids:
                docs_query = select(Document).where(Document.id.in_(document_ids))
            else:
                # Get all documents in project through collection_documents
                from src.models.collection import CollectionDocument

                docs_query = (
                    select(Document)
                    .join(CollectionDocument, Document.id == CollectionDocument.document_id)
                    .where(CollectionDocument.collection_id == project_id)
                )

            result = await self.db.execute(docs_query)
            documents = result.scalars().all()
            document_count = len(documents)

            if not documents:
                self._update_status(
                    task_id, DraftGenerationStatus.FAILED, 0, "No documents found"
                )
                self._record_generation_metrics(
                    status=DraftGenerationStatus.FAILED,
                    num_documents=document_count,
                )
                return

            await asyncio.sleep(0.5)  # Simulate processing

            # Phase 2: Generating content
            self._update_status(
                task_id, DraftGenerationStatus.GENERATING, 30, "Generating content"
            )

            # Build draft content
            draft_content = await self._build_draft_content(
                documents=documents,
                themes=themes,
                style=style,
                max_sections=max_sections,
                include_abstract=include_abstract,
            )

            self._update_status(
                task_id, DraftGenerationStatus.GENERATING, 60, "Building sections"
            )
            await asyncio.sleep(0.3)

            # Phase 3: Adding citations
            self._update_status(
                task_id, DraftGenerationStatus.CITING, 80, "Adding citations"
            )

            # Extract citations
            citations_data = self._extract_citations_from_content(
                draft_content, documents
            )

            # Phase 4: Finalizing
            self._update_status(
                task_id, DraftGenerationStatus.FINALIZING, 90, "Finalizing draft"
            )

            # Get next version number
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

            # Create the draft
            draft = GeneratedDraft(
                project_id=project_id,
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
                    "document_count": len(documents),
                },
                is_current=True,
            )

            self.db.add(draft)
            await self.db.flush()

            # Create draft citations
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

            # Mark complete
            duration = time.time() - start_time
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
                duration_seconds=duration,
            )
            self._record_generation_metrics(
                status=DraftGenerationStatus.COMPLETED,
                duration=duration,
                num_documents=document_count,
            )

        except asyncio.CancelledError:
            self._update_status(
                task_id, DraftGenerationStatus.CANCELLED, 0, "Generation cancelled"
            )
            logger.info("draft_generation_cancelled", task_id=task_id)
            self._record_generation_metrics(
                status=DraftGenerationStatus.CANCELLED,
                duration=time.time() - start_time,
                num_documents=document_count,
            )

        except Exception as e:
            self._update_status(
                task_id, DraftGenerationStatus.FAILED, 0, f"Error: {str(e)}"
            )
            logger.error("draft_generation_failed", task_id=task_id, error=str(e))
            self._record_generation_metrics(
                status=DraftGenerationStatus.FAILED,
                duration=time.time() - start_time,
                num_documents=document_count,
            )

    @staticmethod
    def _init_openai_client() -> Optional[Any]:
        """Initialize OpenAI client if API key is available."""
        try:
            from src.core.config import settings

            api_key = getattr(settings, "OPENAI_API_KEY", None)
            if not api_key:
                return None
            import openai

            return openai.AsyncOpenAI(api_key=api_key)
        except Exception as exc:
            logger.warning("openai_client_init_failed", error=str(exc))
            return None

    async def _build_draft_content(
        self,
        documents: List[Document],
        themes: List[str],
        style: str,
        max_sections: int,
        include_abstract: bool,
    ) -> str:
        """Build draft content using LLM, falling back to template on failure."""
        if self._openai_client is not None:
            try:
                return await self._build_draft_with_llm(
                    documents=documents,
                    themes=themes,
                    style=style,
                    max_sections=max_sections,
                    include_abstract=include_abstract,
                )
            except Exception as exc:
                logger.warning(
                    "llm_draft_generation_failed",
                    error=str(exc),
                    fallback="template",
                )

        return self._build_draft_template(
            documents=documents,
            themes=themes,
            style=style,
            max_sections=max_sections,
            include_abstract=include_abstract,
        )

    async def _build_draft_with_llm(
        self,
        documents: List[Document],
        themes: List[str],
        style: str,
        max_sections: int,
        include_abstract: bool,
    ) -> str:
        """Generate draft content via OpenAI LLM."""
        # Gather document context
        doc_contexts: List[str] = []
        for idx, doc in enumerate(documents, start=1):
            snippet = ""
            if doc.content_summary:
                snippet = doc.content_summary[:500]
            elif doc.content_text:
                snippet = doc.content_text[:500]

            title = doc.title or f"Untitled Document {idx}"
            doc_contexts.append(f'[Doc {idx}] "{title}" — {snippet}')

        style_instruction = self._STYLE_PROMPTS.get(style, self._STYLE_PROMPTS["academic"])
        abstract_instruction = (
            "Include an Abstract section at the beginning."
            if include_abstract
            else "Do not include an abstract."
        )

        system_prompt = (
            "You are an academic writing assistant generating a literature review.\n"
            f"Style: {style}\n"
            "Rules:\n"
            "- Use [Doc N] citations to reference source documents\n"
            f"- Write {max_sections} sections maximum\n"
            f"- {abstract_instruction}\n"
            "- Use proper markdown with ## headers for sections and ### for subsections\n"
            "- Synthesize findings across documents, don't just summarize each one individually\n"
            "- Be specific about findings, methods, and contributions from the documents\n"
            f"- {style_instruction}\n"
        )

        user_prompt = (
            f"Write a literature review covering these themes: {', '.join(themes)}\n\n"
            "Documents available:\n"
            + "\n".join(doc_contexts)
            + "\n\nGenerate the literature review now."
        )

        response = await asyncio.wait_for(
            self._openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            ),
            timeout=60.0,
        )

        content = response.choices[0].message.content
        if not content or not content.strip():
            raise ValueError("LLM returned empty content")

        logger.info(
            "llm_draft_generated",
            document_count=len(documents),
            theme_count=len(themes),
            style=style,
            word_count=len(content.split()),
        )

        return content.strip()

    @staticmethod
    def _build_draft_template(
        documents: List[Document],
        themes: List[str],
        style: str,
        max_sections: int,
        include_abstract: bool,
    ) -> str:
        """Fallback template-based draft generation."""
        sections = []

        if include_abstract:
            abstract = f"""## Abstract

This literature review synthesizes research from {len(documents)} documents, focusing on the themes of {', '.join(themes)}. The review provides a comprehensive analysis of current research and identifies key findings and trends in the field.

"""
            sections.append(abstract)

        intro = f"""## 1. Introduction

The field encompassing {themes[0] if themes else 'this research area'} has seen significant developments in recent years. This literature review examines {len(documents)} key publications to understand the current state of research and identify emerging trends.

"""
        sections.append(intro)

        for i, theme in enumerate(themes[: max_sections - 2], start=2):
            doc_refs = []
            for j, doc in enumerate(documents[:3], start=1):
                doc_refs.append(f"[Doc {j}]")

            section = f"""## {i}. {theme.title()}

Research on {theme} has been extensively documented in the literature {' '.join(doc_refs)}. Studies have shown various approaches to understanding and addressing challenges in this area.

Key findings indicate that {theme} plays a significant role in the broader context of the research domain. Multiple researchers have contributed to our understanding of these phenomena, each building upon previous work to advance the field.

"""
            sections.append(section)

        conclusion = f"""## {len(themes) + 2 if len(themes) < max_sections else max_sections}. Conclusion

This review has synthesized findings from {len(documents)} publications across the themes of {', '.join(themes)}. The literature demonstrates significant progress in understanding these interconnected areas, while also highlighting opportunities for future research.

Key takeaways include the importance of continued investigation and the potential for cross-disciplinary collaboration to address remaining challenges in the field.

"""
        sections.append(conclusion)

        return "\n".join(sections)

    def _extract_citations_from_content(
        self,
        content: str,
        documents: List[Document],
    ) -> List[Dict[str, Any]]:
        """Extract citation references from the generated content"""
        import re

        citations = []
        pattern = r"\[Doc (\d+)\]"
        matches = re.findall(pattern, content)

        seen = set()
        for match in matches:
            doc_idx = int(match) - 1
            if doc_idx < len(documents) and doc_idx not in seen:
                seen.add(doc_idx)
                doc = documents[doc_idx]
                citations.append(
                    {
                        "document_id": doc.id,
                        "citation_id": None,
                        "snippet": doc.title[:200] if doc.title else "",
                        "context": f"Referenced as [Doc {match}]",
                    }
                )

        return citations

    def _update_status(
        self,
        task_id: str,
        status: str,
        progress: int,
        step: str,
        **extra: Any,
    ) -> None:
        """Update generation status"""
        if task_id in _generation_status:
            _generation_status[task_id].update(
                {
                    "status": status,
                    "progress": progress,
                    "current_step": step,
                    "updated_at": datetime.utcnow().isoformat(),
                    **extra,
                }
            )

    @staticmethod
    def get_status(task_id: str) -> Optional[Dict[str, Any]]:
        """Get generation status for a task"""
        status = _generation_status.get(task_id)
        if not status:
            return None
        return {**status, "task_id": task_id}

    @staticmethod
    def _status_timestamp(payload: Dict[str, Any]) -> datetime:
        """Parse status timestamps safely for sorting."""
        for key in ("updated_at", "started_at"):
            raw = payload.get(key)
            if not raw:
                continue
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                continue
        return datetime.min

    @staticmethod
    def _status_matches_scope(
        payload: Dict[str, Any],
        project_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> bool:
        """Check whether a status belongs to a project/user scope."""
        if payload.get("project_id") != str(project_id):
            return False
        if user_id and payload.get("user_id") != str(user_id):
            return False
        return True

    @classmethod
    def get_latest_status(
        cls,
        project_id: UUID,
        user_id: Optional[UUID] = None,
        active_only: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent status for a project (optionally active-only)."""
        scoped_statuses: List[Tuple[str, Dict[str, Any]]] = []
        for task_id, payload in _generation_status.items():
            if not cls._status_matches_scope(payload, project_id, user_id):
                continue
            if active_only and payload.get("status") in cls.TERMINAL_STATUSES:
                continue
            scoped_statuses.append((task_id, payload))

        if not scoped_statuses:
            return None

        task_id, payload = max(
            scoped_statuses,
            key=lambda item: cls._status_timestamp(item[1]),
        )
        return {**payload, "task_id": task_id}

    @staticmethod
    def cancel_generation(task_id: str) -> bool:
        """Cancel an ongoing generation"""
        if task_id in _generation_status:
            status = _generation_status[task_id]
            if status["status"] not in [
                DraftGenerationStatus.COMPLETED,
                DraftGenerationStatus.FAILED,
                DraftGenerationStatus.CANCELLED,
            ]:
                _generation_status[task_id]["status"] = DraftGenerationStatus.CANCELLED
                _generation_status[task_id]["current_step"] = "Cancelled by user"
                _generation_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
                return True
        return False

    @classmethod
    def cancel_latest_generation(
        cls,
        project_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> Optional[str]:
        """Cancel the latest in-progress generation for a project scope."""
        latest_status = cls.get_latest_status(
            project_id=project_id,
            user_id=user_id,
            active_only=True,
        )
        if not latest_status:
            return None

        task_id = latest_status["task_id"]
        if cls.cancel_generation(task_id):
            return task_id
        return None

    def _record_generation_metrics(
        self,
        status: str,
        duration: Optional[float] = None,
        num_documents: Optional[int] = None,
    ) -> None:
        """Record generation success/failure duration and totals."""
        _ensure_draft_metrics()
        if _draft_metrics_disabled:
            return

        attributes: Dict[str, str] = {"status": status}
        if num_documents is not None:
            attributes["num_documents"] = str(num_documents)

        try:
            from src.observability.metrics import increment_counter, record_histogram

            increment_counter("draft_generation_total", attributes=attributes)
            if duration is not None:
                histogram_attributes = {}
                if num_documents is not None:
                    histogram_attributes["num_documents"] = str(num_documents)
                record_histogram(
                    "draft_generation_duration_seconds",
                    duration,
                    histogram_attributes,
                )
        except Exception as exc:  # pragma: no cover - defensive observability guard
            logger.warning(
                "draft_metrics_record_failed",
                error=str(exc),
                status=status,
            )

    async def get_draft(
        self,
        project_id: UUID,
        draft_id: Optional[UUID] = None,
        current_only: bool = False,
    ) -> Optional[GeneratedDraft]:
        """Get a specific draft or current draft"""
        if draft_id:
            query = select(GeneratedDraft).where(
                GeneratedDraft.id == draft_id,
                GeneratedDraft.project_id == project_id,
            )
        elif current_only:
            query = select(GeneratedDraft).where(
                GeneratedDraft.project_id == project_id,
                GeneratedDraft.is_current == True,
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
        """List all drafts for a project"""
        # Count total
        count_query = select(func.count(GeneratedDraft.id)).where(
            GeneratedDraft.project_id == project_id
        )
        result = await self.db.execute(count_query)
        total = result.scalar() or 0

        # Get drafts
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
        """Delete a specific draft"""
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
        """Get citations for a specific draft"""
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
        """Compare two draft versions"""
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

        # Calculate similarity (simple word overlap)
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
                "created_at": draft_a.created_at.isoformat()
                if draft_a.created_at
                else None,
            },
            "version_b": {
                "version": draft_b.version,
                "word_count": draft_b.word_count,
                "citation_count": draft_b.citation_count,
                "created_at": draft_b.created_at.isoformat()
                if draft_b.created_at
                else None,
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
        """Export draft to specified format"""
        draft = await self.get_draft(project_id, draft_id)
        if not draft:
            return {"error": "Draft not found"}

        if format == "markdown":
            content = draft.content
            if include_bibliography:
                # Add bibliography section
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
            # Convert to LaTeX
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
        """Convert markdown to LaTeX"""
        import re

        latex = markdown_content

        # Convert headers
        latex = re.sub(
            r"^## (\d+\.\s)?(.+)$", r"\\section{\2}", latex, flags=re.MULTILINE
        )
        latex = re.sub(r"^### (.+)$", r"\\subsection{\1}", latex, flags=re.MULTILINE)

        # Convert [Doc N] to \cite{docN}
        latex = re.sub(r"\[Doc (\d+)\]", r"\\cite{doc\1}", latex)

        # Extract title (avoid backslash in f-string)
        title_text = markdown_content.split("\n")[0].replace("## ", "")

        # Wrap in document
        latex = f"""\\documentclass{{article}}
\\usepackage{{natbib}}
\\usepackage{{hyperref}}

\\title{{{title_text}}}
\\author{{Generated by Research Assistant}}
\\date{{\\today}}

\\begin{{document}}

\\maketitle

{latex}

\\bibliographystyle{{plain}}
\\bibliography{{references}}

\\end{{document}}
"""
        return latex

    def _generate_bib_entries(self, citations: List[DraftCitation]) -> str:
        """Generate BibTeX entries for citations"""
        entries = []
        for c in citations:
            entry = f"""@misc{{doc{c.citation_index},
  title = {{{c.snippet[:100]}}},
  note = {{{c.context}}},
}}
"""
            entries.append(entry)
        return "\n".join(entries)
