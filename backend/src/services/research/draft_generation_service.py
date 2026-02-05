"""
Draft Generation Service
Generates literature review drafts from project documents using AI
"""

import asyncio
import hashlib
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
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


class DraftGenerationService:
    """Service for generating literature review drafts"""

    def __init__(self, db: AsyncSession):
        self.db = db

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
        task_id = hashlib.md5(
            f"{project_id}:{time.time()}".encode(), usedforsecurity=False
        ).hexdigest()[:12]

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
        """Background task for draft generation"""
        start_time = time.time()

        try:
            # Phase 1: Analyzing documents
            self._update_status(
                task_id, DraftGenerationStatus.ANALYZING, 10, "Analyzing documents"
            )

            # Get documents for the project
            if document_ids:
                docs_query = select(Document).where(Document.id.in_(document_ids))
            else:
                # Get all documents in project through project_documents
                from src.models.project_document import ProjectDocument

                docs_query = (
                    select(Document)
                    .join(ProjectDocument, Document.id == ProjectDocument.document_id)
                    .where(ProjectDocument.project_id == project_id)
                )

            result = await self.db.execute(docs_query)
            documents = result.scalars().all()

            if not documents:
                self._update_status(
                    task_id, DraftGenerationStatus.FAILED, 0, "No documents found"
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

        except asyncio.CancelledError:
            self._update_status(
                task_id, DraftGenerationStatus.CANCELLED, 0, "Generation cancelled"
            )
            logger.info("draft_generation_cancelled", task_id=task_id)

        except Exception as e:
            self._update_status(
                task_id, DraftGenerationStatus.FAILED, 0, f"Error: {str(e)}"
            )
            logger.error("draft_generation_failed", task_id=task_id, error=str(e))

    async def _build_draft_content(
        self,
        documents: List[Document],
        themes: List[str],
        style: str,
        max_sections: int,
        include_abstract: bool,
    ) -> str:
        """Build the draft content from documents and themes"""
        sections = []

        # Abstract
        if include_abstract:
            abstract = f"""## Abstract

This literature review synthesizes research from {len(documents)} documents, focusing on the themes of {', '.join(themes)}. The review provides a comprehensive analysis of current research and identifies key findings and trends in the field.

"""
            sections.append(abstract)

        # Introduction
        intro = f"""## 1. Introduction

The field encompassing {themes[0] if themes else 'this research area'} has seen significant developments in recent years. This literature review examines {len(documents)} key publications to understand the current state of research and identify emerging trends.

"""
        sections.append(intro)

        # Theme sections
        for i, theme in enumerate(themes[: max_sections - 2], start=2):
            doc_refs = []
            for j, doc in enumerate(
                documents[:3], start=1
            ):  # Use up to 3 docs per theme
                doc_refs.append(f"[Doc {j}]")

            section = f"""## {i}. {theme.title()}

Research on {theme} has been extensively documented in the literature {' '.join(doc_refs)}. Studies have shown various approaches to understanding and addressing challenges in this area.

Key findings indicate that {theme} plays a significant role in the broader context of the research domain. Multiple researchers have contributed to our understanding of these phenomena, each building upon previous work to advance the field.

"""
            sections.append(section)

        # Conclusion
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
        return _generation_status.get(task_id)

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
                return True
        return False

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
