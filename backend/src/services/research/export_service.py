"""
Export service for thread/conversation export functionality.

Handles conversion of thread data to various formats:
- Markdown: Human-readable with citations
- PDF: Formatted document (requires weasyprint)
- JSON: Complete data for re-import or analysis
- HTML: Self-contained viewable file
"""

import io
import json
import zipfile
import structlog
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any, Protocol, BinaryIO
from jinja2 import Environment, BaseLoader
from jinja2.ext import loopcontrols

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models.thread import Thread
from src.models.chat_message import ChatMessage, MessageRole
from src.models.citation import Citation
from src.shared.export_schemas import (
    ExportFormat,
    ExportOptions,
    ThreadExport,
    MessageExport,
    CitationExport,
)

logger = structlog.get_logger(__name__)


# Markdown template
MARKDOWN_TEMPLATE = """# {{ thread.title or "Untitled Thread" }}

{% if thread.summary %}
> {{ thread.summary }}
{% endif %}

**Status**: {{ thread.status }}
**Created**: {{ thread.created_at.strftime(date_format) }}
**Messages**: {{ thread.message_count }}
{% if options.include_metadata %}
**Tokens**: {{ thread.token_count }}
{% endif %}

---

{% for message in thread.messages %}
{% if message.role == "system" and not options.include_system_messages %}
{% continue %}
{% endif %}
## {{ message.role | title }}
*{{ message.created_at.strftime(date_format) }}*{% if message.model_name and options.include_metadata %} | Model: {{ message.model_name }}{% endif %}

{{ message.content }}

{% if message.citations and options.include_citations %}
### Sources
{% for citation in message.citations %}
- **{{ citation.document_title or citation.external_reference_id or "Source " ~ loop.index }}**{% if citation.page_number %} (p. {{ citation.page_number }}){% endif %}{% if citation.score %} [{{ "%.2f"|format(citation.score) }}]{% endif %}
{% if citation.snippet %}
  > {{ citation.snippet | truncate(200) }}
{% endif %}
{% endfor %}
{% endif %}

{% if message.feedback_rating and options.include_feedback %}
**Feedback**: {{ "⭐" * message.feedback_rating }}{% if message.feedback_text %} - {{ message.feedback_text }}{% endif %}
{% endif %}

---

{% endfor %}

---
*Exported on {{ exported_at.strftime(date_format) }}*
"""

# HTML template
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ thread.title or "Thread Export" }}</title>
    <style>
        :root {
            --phosphor-green: #00ff9f;
            --amber: #ffb700;
            --cyan: #00d4ff;
            --bg-dark: #0a0a0a;
            --bg-card: #141414;
            --text-primary: #e4e4e7;
            --text-secondary: #a1a1aa;
        }
        body {
            font-family: 'JetBrains Mono', 'SF Mono', Monaco, monospace;
            background: var(--bg-dark);
            color: var(--text-primary);
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
            line-height: 1.6;
        }
        h1 { color: var(--phosphor-green); border-bottom: 2px solid var(--phosphor-green); padding-bottom: 0.5rem; }
        h2 { color: var(--cyan); margin-top: 2rem; }
        .metadata { color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 2rem; }
        .message { background: var(--bg-card); padding: 1.5rem; margin: 1rem 0; border-radius: 8px; border-left: 3px solid var(--cyan); }
        .message.user { border-left-color: var(--phosphor-green); }
        .message.assistant { border-left-color: var(--cyan); }
        .message.system { border-left-color: var(--amber); opacity: 0.8; }
        .message-header { display: flex; justify-content: space-between; margin-bottom: 1rem; color: var(--text-secondary); font-size: 0.85rem; }
        .role { font-weight: bold; text-transform: uppercase; }
        .role.user { color: var(--phosphor-green); }
        .role.assistant { color: var(--cyan); }
        .role.system { color: var(--amber); }
        .content { white-space: pre-wrap; word-wrap: break-word; }
        .citations { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #333; }
        .citation { background: #1a1a1a; padding: 0.75rem; margin: 0.5rem 0; border-radius: 4px; font-size: 0.85rem; }
        .citation-title { color: var(--amber); font-weight: bold; }
        .citation-snippet { color: var(--text-secondary); margin-top: 0.5rem; font-style: italic; }
        .footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #333; color: var(--text-secondary); font-size: 0.8rem; text-align: center; }
        blockquote { border-left: 3px solid var(--amber); padding-left: 1rem; margin: 1rem 0; color: var(--text-secondary); }
    </style>
</head>
<body>
    <h1>{{ thread.title or "Untitled Thread" }}</h1>
    
    {% if thread.summary %}
    <blockquote>{{ thread.summary }}</blockquote>
    {% endif %}
    
    <div class="metadata">
        <strong>Status:</strong> {{ thread.status }} | 
        <strong>Created:</strong> {{ thread.created_at.strftime(date_format) }} | 
        <strong>Messages:</strong> {{ thread.message_count }}
        {% if options.include_metadata %} | <strong>Tokens:</strong> {{ thread.token_count }}{% endif %}
    </div>
    
    {% for message in thread.messages %}
    {% if message.role == "system" and not options.include_system_messages %}
    {% continue %}
    {% endif %}
    <div class="message {{ message.role }}">
        <div class="message-header">
            <span class="role {{ message.role }}">{{ message.role }}</span>
            <span>{{ message.created_at.strftime(date_format) }}{% if message.model_name and options.include_metadata %} | {{ message.model_name }}{% endif %}</span>
        </div>
        <div class="content">{{ message.content }}</div>
        
        {% if message.citations and options.include_citations %}
        <div class="citations">
            <strong>Sources:</strong>
            {% for citation in message.citations %}
            <div class="citation">
                <span class="citation-title">{{ citation.document_title or citation.external_reference_id or "Source " ~ loop.index }}</span>
                {% if citation.page_number %} (p. {{ citation.page_number }}){% endif %}
                {% if citation.score %} [{{ "%.2f"|format(citation.score) }}]{% endif %}
                {% if citation.snippet %}
                <div class="citation-snippet">{{ citation.snippet | truncate(200) }}</div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        {% endif %}
    </div>
    {% endfor %}
    
    <div class="footer">
        Exported on {{ exported_at.strftime(date_format) }} | RAG System Thread Export v1.0
    </div>
</body>
</html>
"""


class ExportFormatter(ABC):
    """Abstract base class for export formatters."""
    
    @abstractmethod
    def format(
        self,
        thread: ThreadExport,
        options: ExportOptions
    ) -> bytes:
        """Format thread data to bytes."""
        pass
    
    @property
    @abstractmethod
    def content_type(self) -> str:
        """MIME content type."""
        pass
    
    @property
    @abstractmethod
    def file_extension(self) -> str:
        """File extension without dot."""
        pass


class MarkdownFormatter(ExportFormatter):
    """Format thread as Markdown."""
    
    def __init__(self):
        self._env = Environment(loader=BaseLoader(), extensions=[loopcontrols])
        self._template = self._env.from_string(MARKDOWN_TEMPLATE)
    
    def format(self, thread: ThreadExport, options: ExportOptions) -> bytes:
        content = self._template.render(
            thread=thread,
            options=options,
            date_format=options.date_format,
            exported_at=datetime.utcnow()
        )
        return content.encode('utf-8')
    
    @property
    def content_type(self) -> str:
        return "text/markdown; charset=utf-8"
    
    @property
    def file_extension(self) -> str:
        return "md"


class HTMLFormatter(ExportFormatter):
    """Format thread as HTML."""
    
    def __init__(self):
        self._env = Environment(loader=BaseLoader(), extensions=[loopcontrols])
        self._template = self._env.from_string(HTML_TEMPLATE)
    
    def format(self, thread: ThreadExport, options: ExportOptions) -> bytes:
        content = self._template.render(
            thread=thread,
            options=options,
            date_format=options.date_format,
            exported_at=datetime.utcnow()
        )
        return content.encode('utf-8')
    
    @property
    def content_type(self) -> str:
        return "text/html; charset=utf-8"
    
    @property
    def file_extension(self) -> str:
        return "html"


class JSONFormatter(ExportFormatter):
    """Format thread as JSON."""
    
    def format(self, thread: ThreadExport, options: ExportOptions) -> bytes:
        data = thread.model_dump(mode='json')
        data['export_options'] = options.model_dump()
        content = json.dumps(data, indent=2, default=str)
        return content.encode('utf-8')
    
    @property
    def content_type(self) -> str:
        return "application/json; charset=utf-8"
    
    @property
    def file_extension(self) -> str:
        return "json"


class PDFFormatter(ExportFormatter):
    """Format thread as PDF using WeasyPrint."""
    
    def __init__(self):
        self._html_formatter = HTMLFormatter()
        self._weasyprint_available = self._check_weasyprint()
    
    def _check_weasyprint(self) -> bool:
        try:
            import weasyprint
            return True
        except ImportError:
            logger.warning("WeasyPrint not installed, PDF export will use HTML fallback")
            return False
    
    def format(self, thread: ThreadExport, options: ExportOptions) -> bytes:
        html_content = self._html_formatter.format(thread, options)
        
        if not self._weasyprint_available:
            # Fallback: return HTML with PDF content type suggestion
            logger.warning("PDF export falling back to HTML - install weasyprint for true PDF")
            return html_content
        
        try:
            import weasyprint
            html_doc = weasyprint.HTML(string=html_content.decode('utf-8'))
            pdf_bytes = html_doc.write_pdf()
            return pdf_bytes
        except Exception as e:
            logger.error("PDF generation failed", error=str(e))
            raise RuntimeError(f"PDF generation failed: {e}")
    
    @property
    def content_type(self) -> str:
        if self._weasyprint_available:
            return "application/pdf"
        return "text/html; charset=utf-8"
    
    @property
    def file_extension(self) -> str:
        if self._weasyprint_available:
            return "pdf"
        return "html"


class ExportService:
    """Service for exporting threads to various formats."""
    
    def __init__(self, db: AsyncSession):
        self._db = db
        self._formatters: Dict[ExportFormat, ExportFormatter] = {
            ExportFormat.MARKDOWN: MarkdownFormatter(),
            ExportFormat.HTML: HTMLFormatter(),
            ExportFormat.JSON: JSONFormatter(),
            ExportFormat.PDF: PDFFormatter(),
        }
    
    async def export_thread(
        self,
        thread_id: str,
        user_id: str,
        format: ExportFormat,
        options: ExportOptions
    ) -> tuple[bytes, str, str]:
        """
        Export a single thread.
        
        Returns:
            tuple: (content_bytes, filename, content_type)
        """
        thread = await self._load_thread(thread_id, user_id, options)
        if not thread:
            raise ValueError(f"Thread {thread_id} not found or access denied")
        
        formatter = self._formatters[format]
        content = formatter.format(thread, options)
        
        # Generate filename
        title_slug = self._slugify(thread.title or "thread")
        filename = f"{title_slug}_{thread_id[:8]}.{formatter.file_extension}"
        
        logger.info(
            "Thread exported",
            thread_id=thread_id,
            format=format.value,
            size_bytes=len(content)
        )
        
        return content, filename, formatter.content_type
    
    async def export_batch(
        self,
        thread_ids: List[str],
        user_id: str,
        format: ExportFormat,
        options: ExportOptions,
        as_zip: bool = True
    ) -> tuple[bytes, str, str]:
        """
        Export multiple threads.
        
        Returns:
            tuple: (content_bytes, filename, content_type)
        """
        if not as_zip and len(thread_ids) > 1:
            raise ValueError("Multiple threads require ZIP packaging")
        
        if len(thread_ids) == 1 and not as_zip:
            return await self.export_thread(thread_ids[0], user_id, format, options)
        
        # Create ZIP archive
        zip_buffer = io.BytesIO()
        formatter = self._formatters[format]
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for thread_id in thread_ids:
                try:
                    thread = await self._load_thread(thread_id, user_id, options)
                    if not thread:
                        logger.warning("Thread not found, skipping", thread_id=thread_id)
                        continue
                    
                    content = formatter.format(thread, options)
                    title_slug = self._slugify(thread.title or "thread")
                    filename = f"{title_slug}_{thread_id[:8]}.{formatter.file_extension}"
                    
                    zf.writestr(filename, content)
                    
                except Exception as e:
                    logger.error("Failed to export thread", thread_id=thread_id, error=str(e))
                    # Add error file
                    zf.writestr(f"error_{thread_id[:8]}.txt", f"Export failed: {e}")
        
        zip_buffer.seek(0)
        zip_content = zip_buffer.read()
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"thread_export_{timestamp}.zip"
        
        logger.info(
            "Batch export completed",
            thread_count=len(thread_ids),
            format=format.value,
            size_bytes=len(zip_content)
        )
        
        return zip_content, filename, "application/zip"
    
    async def _load_thread(
        self,
        thread_id: str,
        user_id: str,
        options: ExportOptions
    ) -> Optional[ThreadExport]:
        """Load thread with messages and citations."""
        query = (
            select(Thread)
            .options(
                selectinload(Thread.messages).selectinload(ChatMessage.citations),
                selectinload(Thread.conversation)  # Load conversation for ownership check
            )
            .where(Thread.id == thread_id)
        )
        
        result = await self._db.execute(query)
        thread = result.unique().scalar_one_or_none()
        
        if not thread:
            return None

        # Authorization check: Verify user owns the thread or has admin privileges
        # Thread ownership is determined by:
        # 1. User created the thread directly (thread.created_by_id == user_id)
        # 2. User owns the parent conversation (conversation.created_by_id == user_id)
        if str(thread.created_by_id) != user_id and str(thread.conversation.created_by_id) != user_id:
            logger.warning(
                "Unauthorized thread export attempt",
                thread_id=thread_id,
                user_id=user_id,
                thread_owner=str(thread.created_by_id),
                conversation_owner=str(thread.conversation.created_by_id)
            )
            return None
        
        # Convert to export schema
        messages = []
        for msg in thread.messages:
            # Skip system messages if not requested
            if msg.role == MessageRole.SYSTEM and not options.include_system_messages:
                continue
            
            citations = []
            if options.include_citations and msg.citations:
                for cit in msg.citations:
                    citations.append(CitationExport(
                        id=str(cit.id),
                        document_id=str(cit.document_id) if cit.document_id else None,
                        external_reference_id=cit.external_reference_id,
                        document_title=cit.document_title,
                        document_type=cit.document_type,
                        snippet=cit.snippet,
                        page_number=cit.page_number,
                        score=cit.score
                    ))
            
            messages.append(MessageExport(
                id=str(msg.id),
                role=msg.role.value,
                content=msg.content,
                created_at=msg.created_at,
                model_name=msg.model_name if options.include_metadata else None,
                token_count=msg.token_count if options.include_metadata else 0,
                latency_ms=msg.latency_ms if options.include_metadata else None,
                feedback_rating=msg.feedback_rating if options.include_feedback else None,
                feedback_text=msg.feedback_text if options.include_feedback else None,
                citations=citations,
                has_attachments=msg.has_attachments if options.include_attachments else False
            ))
        
        return ThreadExport(
            id=str(thread.id),
            title=thread.title,
            summary=thread.summary,
            status=thread.status.value if thread.status else "unknown",
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            last_message_at=thread.last_message_at,
            message_count=thread.message_count,
            token_count=thread.token_count,
            conversation_id=str(thread.conversation_id),
            messages=messages,
            export_format=ExportFormat.MARKDOWN  # Will be overwritten by formatter
        )
    
    def _slugify(self, text: str, max_length: int = 50) -> str:
        """Convert text to URL-safe slug."""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '_', text)
        return text[:max_length].strip('_')


def get_export_service(db: AsyncSession) -> ExportService:
    """Factory function for ExportService."""
    return ExportService(db)
