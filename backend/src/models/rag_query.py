"""
Enhanced RAG Query model with comprehensive answer tracking and 30-day retention
"""

import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Enum, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship, selectinload, joinedload
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from enum import Enum as PyEnum
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, List, Dict, Any

from .base import BaseModel, GUID

class QueryType(PyEnum):
    """Types of RAG queries"""
    FACTUAL_LOOKUP = "factual_lookup"
    REASONING = "reasoning"
    COMPARISON = "comparison"
    SUMMARY = "summary"
    ANALYSIS = "analysis"
    RECOMMENDATION = "recommendation"
    MULTIMODAL = "multimodal"
    CONVERSATIONAL = "conversational"

class AnswerType(PyEnum):
    """Types of RAG answers"""
    DIRECT = "direct"               # Direct answer from sources
    SYNTHESIZED = "synthesized"     # Synthesized from multiple sources
    EXTRAPOLATED = "extrapolated"   # Inferred beyond sources
    UNCERTAIN = "uncertain"         # Low confidence answer
    NO_ANSWER = "no_answer"         # No relevant information found

class RAGQualityScore(PyEnum):
    """RAG quality rating levels"""
    EXCELLENT = "excellent"    # >90% quality
    GOOD = "good"             # 70-90% quality
    FAIR = "fair"             # 50-70% quality
    POOR = "poor"             # <50% quality

class RAGQuery(BaseModel):
    """Enhanced RAG Query model with comprehensive answer tracking"""

    __tablename__ = "rag_queries"

    # Query information
    query_text = Column(Text, nullable=False)
    query_type = Column(Enum(QueryType), nullable=False, index=True)
    query_intent = Column(String(100), nullable=True, index=True)  # information, navigation, transaction
    query_complexity = Column(String(20), nullable=True)  # simple, moderate, complex

    # Query preprocessing
    cleaned_query = Column(Text, nullable=True)  # Preprocessed query
    query_embeddings = Column(JSON, nullable=True)  # Query vector embeddings
    extracted_entities = Column(JSON, nullable=True)  # Entities extracted from query
    query_language = Column(String(10), nullable=True, default="en")
    query_sentiment = Column(String(20), nullable=True)  # positive, negative, neutral

    # User context
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    organization_id = Column(GUID(), ForeignKey("organizations.id"), nullable=False, index=True)
    session_id = Column(String(255), nullable=True, index=True)
    conversation_id = Column(String(255), nullable=True, index=True)  # For conversation tracking

    # Search configuration
    search_strategy = Column(String(50), nullable=False, default="hybrid")  # semantic, keyword, hybrid, graph
    search_filters = Column(JSON, nullable=True)  # Document type, date range, etc.
    retrieval_limit = Column(Integer, nullable=False, default=5)
    similarity_threshold = Column(Float, nullable=False, default=0.7)

    # Performance metrics
    total_duration_ms = Column(Integer, nullable=True, index=True)
    retrieval_duration_ms = Column(Integer, nullable=True)
    ranking_duration_ms = Column(Integer, nullable=True)
    generation_duration_ms = Column(Integer, nullable=True)
    total_tokens_used = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)

    # Search results context
    retrieved_documents = Column(JSON, nullable=True)  # Retrieved document IDs and scores
    context_snippets = Column(JSON, nullable=True)  # Context used for answer generation
    context_length = Column(Integer, nullable=True)  # Characters in context
    context_quality_score = Column(Float, nullable=True)  # Quality of retrieved context

    # Answer information
    answer_text = Column(Text, nullable=True)
    answer_type = Column(Enum(AnswerType), nullable=True, index=True)
    answer_confidence = Column(Float, nullable=True, index=True)  # 0.0 to 1.0
    answer_sources = Column(JSON, nullable=True)  # Source document references
    source_count = Column(Integer, nullable=False, default=0)

    # Answer quality metrics
    faithfulness_score = Column(Float, nullable=True, index=True)  # Grounded in sources
    relevance_score = Column(Float, nullable=True, index=True)  # Relevant to query
    completeness_score = Column(Float, nullable=True)  # Complete answer
    clarity_score = Column(Float, nullable=True)  # Clear and understandable
    overall_quality_score = Column(Float, nullable=True, index=True)
    quality_rating = Column(Enum(RAGQualityScore), nullable=True, index=True)

    # Multimodal information
    modalities_used = Column(JSON, nullable=True)  # text, image, audio, video
    modality_scores = Column(JSON, nullable=True)  # Contribution scores per modality
    cross_modal_references = Column(JSON, nullable=True)  # Cross-modal citations

    # Entity and knowledge graph
    query_entities = Column(JSON, nullable=True)  # Entities in query
    answer_entities = Column(JSON, nullable=True)  # Entities in answer
    graph_traversal_path = Column(JSON, nullable=True)  # Knowledge graph path used
    entity_relationships_used = Column(JSON, nullable=True)

    # User interaction and feedback
    user_rating = Column(Integer, nullable=True, index=True)  # 1-5 rating
    user_feedback = Column(Text, nullable=True)
    feedback_category = Column(String(50), nullable=True)  # helpful, incorrect, incomplete
    was_helpful = Column(Boolean, nullable=True)
    was_shared = Column(Boolean, default=False, nullable=False)
    was_bookmarked = Column(Boolean, default=False, nullable=False)

    # Follow-up actions
    follow_up_queries = Column(JSON, nullable=True)  # Related follow-up questions
    suggested_questions = Column(JSON, nullable=True)  # AI-suggested follow-ups
    refinement_count = Column(Integer, default=0, nullable=False)  # Number of query refinements

    # Error handling
    error_occurred = Column(Boolean, default=False, nullable=False)
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    fallback_used = Column(Boolean, default=False, nullable=False)
    fallback_answer = Column(Text, nullable=True)

    # Caching and optimization
    cache_hit = Column(Boolean, default=False, nullable=False)
    cache_key = Column(String(255), nullable=True, index=True)
    similarity_cluster_id = Column(String(100), nullable=True)  # Cluster of similar queries

    # Data retention and cleanup
    expires_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.utcnow() + timedelta(days=30))
    retention_days = Column(Integer, nullable=False, default=30)
    marked_for_deletion = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="rag_queries")
    organization = relationship("Organization")
    quality_metrics = relationship("RAGQualityMetrics", back_populates="query", cascade="all, delete-orphan")
    answer_versions = relationship("RAGAnswerVersion", back_populates="query", cascade="all, delete-orphan")
    feedback_events = relationship("RAGFeedbackEvent", back_populates="query", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index('idx_rag_queries_user_session', 'user_id', 'session_id'),
        Index('idx_rag_queries_org_type', 'organization_id', 'query_type'),
        Index('idx_rag_queries_quality', 'overall_quality_score', 'faithfulness_score'),
        Index('idx_rag_queries_created', 'created_at'),
        Index('idx_rag_queries_expires', 'expires_at'),
        Index('idx_rag_queries_cache', 'cache_key', 'cache_hit'),
        # Additional performance indexes
        Index('idx_rag_queries_user_created', 'user_id', 'created_at'),
        Index('idx_rag_queries_org_created', 'organization_id', 'created_at'),
        Index('idx_rag_queries_rating_helpful', 'user_rating', 'was_helpful'),
        Index('idx_rag_queries_confidence_type', 'answer_confidence', 'answer_type'),
        Index('idx_rag_queries_performance', 'total_duration_ms', 'cache_hit'),
    )

    def __repr__(self):
        return f"<RAGQuery(id={self.id}, type={self.query_type.value}, quality={self.quality_rating.value if self.quality_rating else 'N/A'})>"

    @property
    def is_expired(self) -> bool:
        """Check if query has expired"""
        return datetime.utcnow() > self.expires_at

    @property
    def days_until_expiry(self) -> int:
        """Get days until expiry"""
        if self.is_expired:
            return 0
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)

    @property
    def answer_quality_summary(self) -> Dict[str, Any]:
        """Get summary of answer quality metrics"""
        return {
            'overall_score': self.overall_quality_score,
            'faithfulness': self.faithfulness_score,
            'relevance': self.relevance_score,
            'completeness': self.completeness_score,
            'clarity': self.clarity_score,
            'rating': self.quality_rating.value if self.quality_rating else None,
            'confidence': self.answer_confidence,
            'source_count': self.source_count
        }

    @property
    def performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary"""
        return {
            'total_duration_ms': self.total_duration_ms,
            'retrieval_duration_ms': self.retrieval_duration_ms,
            'generation_duration_ms': self.generation_duration_ms,
            'total_tokens': self.total_tokens_used,
            'cache_hit': self.cache_hit,
            'error_occurred': self.error_occurred
        }

    @property
    def user_engagement_summary(self) -> Dict[str, Any]:
        """Get user engagement summary"""
        return {
            'rating': self.user_rating,
            'feedback': self.user_feedback,
            'was_helpful': self.was_helpful,
            'was_shared': self.was_shared,
            'was_bookmarked': self.was_bookmarked,
            'refinement_count': self.refinement_count
        }

    def calculate_quality_scores(self):
        """Calculate quality scores based on various metrics"""
        if not all([self.faithfulness_score, self.relevance_score]):
            return

        # Weighted average for overall quality
        weights = {
            'faithfulness': 0.4,
            'relevance': 0.3,
            'completeness': 0.2,
            'clarity': 0.1
        }

        self.overall_quality_score = (
            (self.faithfulness_score * weights['faithfulness']) +
            (self.relevance_score * weights['relevance']) +
            (self.completeness_score or 0.5 * weights['completeness']) +
            (self.clarity_score or 0.5 * weights['clarity'])
        )

        # Determine quality rating
        if self.overall_quality_score >= 0.9:
            self.quality_rating = RAGQualityScore.EXCELLENT
        elif self.overall_quality_score >= 0.7:
            self.quality_rating = RAGQualityScore.GOOD
        elif self.overall_quality_score >= 0.5:
            self.quality_rating = RAGQualityScore.FAIR
        else:
            self.quality_rating = RAGQualityScore.POOR

    def add_source_reference(self, document_id: str, title: str, snippet: str, relevance_score: float):
        """Add a source reference to the answer"""
        if not self.answer_sources:
            self.answer_sources = []

        self.answer_sources.append({
            'document_id': str(document_id),
            'title': title,
            'snippet': snippet,
            'relevance_score': relevance_score
        })
        self.source_count = len(self.answer_sources)

    def add_context_snippet(self, document_id: str, text: str, score: float):
        """Add context snippet used for answer generation"""
        if not self.context_snippets:
            self.context_snippets = []

        self.context_snippets.append({
            'document_id': str(document_id),
            'text': text,
            'score': score
        })

    def record_user_feedback(self, rating: int, feedback: str = None, category: str = None):
        """Record user feedback for the answer"""
        self.user_rating = rating
        self.user_feedback = feedback
        self.feedback_category = category
        self.was_helpful = rating >= 3

        # Create feedback event
        feedback_event = RAGFeedbackEvent(
            query_id=self.id,
            user_id=self.user_id,
            event_type="rating",
            rating=rating,
            feedback_text=feedback,
            feedback_category=category
        )
        self.feedback_events.append(feedback_event)

    def record_refinement(self, original_query: str, refined_query: str):
        """Record a query refinement"""
        self.refinement_count += 1
        if not self.follow_up_queries:
            self.follow_up_queries = []
        self.follow_up_queries.append({
            'original': original_query,
            'refined': refined_query,
            'timestamp': datetime.utcnow().isoformat()
        })

    def extend_retention(self, days: int = 30):
        """Extend retention period for this query"""
        self.expires_at = datetime.utcnow() + timedelta(days=days)
        self.retention_days = days
        self.marked_for_deletion = False

    def mark_for_archival(self):
        """Mark query for archival (not deletion)"""
        self.archived_at = datetime.utcnow()

    def to_dict(self, include_context: bool = False, include_sources: bool = True) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = super().to_dict()

        # Convert enum values
        data.update({
            'query_type': self.query_type.value if self.query_type else None,
            'answer_type': self.answer_type.value if self.answer_type else None,
            'quality_rating': self.quality_rating.value if self.quality_rating else None
        })

        # Add computed properties
        data.update({
            'is_expired': self.is_expired,
            'days_until_expiry': self.days_until_expiry,
            'answer_quality_summary': self.answer_quality_summary,
            'performance_summary': self.performance_summary,
            'user_engagement_summary': self.user_engagement_summary
        })

        # Include/exclude context based on parameter
        if not include_context:
            data.pop('context_snippets', None)
            data.pop('retrieved_documents', None)

        # Always include sources unless explicitly excluded
        if not include_sources:
            data.pop('answer_sources', None)

        # Remove sensitive fields
        data.pop('cache_key', None)

        return data

    @classmethod
    def get_with_user_and_org(cls, query_id):
        """Get query with user and organization eagerly loaded"""
        return cls.query.options(
            joinedload(cls.user),
            joinedload(cls.organization)
        ).filter(cls.id == query_id).first()

    @classmethod
    def get_with_feedback(cls, query_id):
        """Get query with feedback events and metrics loaded"""
        return cls.query.options(
            joinedload(cls.user),
            selectinload(cls.feedback_events),
            selectinload(cls.quality_metrics)
        ).filter(cls.id == query_id).first()

    @classmethod
    def get_user_queries_with_details(cls, user_id, limit=50):
        """Get user queries with organization loaded to avoid N+1"""
        return cls.query.options(
            joinedload(cls.organization),
            selectinload(cls.quality_metrics)
        ).filter(
            cls.user_id == user_id,
            cls.is_deleted == False
        ).order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def get_active_queries(cls, organization_id: Optional[uuid.UUID] = None, limit: int = 100) -> List:
        """Get active (non-expired) queries with user info loaded"""
        query = cls.query.options(
            joinedload(cls.user),
            joinedload(cls.organization)
        ).filter(
            cls.expires_at > datetime.utcnow(),
            cls.marked_for_deletion == False,
            cls.is_deleted == False
        ).order_by(cls.created_at.desc())

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.limit(limit).all()

    @classmethod
    def get_expired_queries(cls, organization_id: Optional[uuid.UUID] = None) -> List:
        """Get expired queries for cleanup"""
        query = cls.query.filter(
            cls.expires_at <= datetime.utcnow(),
            cls.marked_for_deletion == False,
            cls.is_deleted == False
        )

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.all()

    @classmethod
    def get_high_quality_queries(cls, organization_id: Optional[uuid.UUID] = None, min_score: float = 0.8) -> List:
        """Get high-quality queries"""
        query = cls.query.filter(
            cls.overall_quality_score >= min_score,
            cls.is_deleted == False
        ).order_by(cls.overall_quality_score.desc())

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.all()

    @classmethod
    def get_queries_with_low_rating(cls, organization_id: Optional[uuid.UUID] = None, max_rating: int = 2) -> List:
        """Get queries with low user ratings"""
        query = cls.query.filter(
            cls.user_rating <= max_rating,
            cls.user_rating.isnot(None),
            cls.is_deleted == False
        ).order_by(cls.user_rating.asc())

        if organization_id:
            query = query.filter(cls.organization_id == organization_id)

        return query.all()


class RAGQualityMetrics(BaseModel):
    """Detailed quality metrics for RAG queries"""

    __tablename__ = "rag_quality_metrics"

    query_id = Column(GUID(), ForeignKey("rag_queries.id"), nullable=False)

    # Faithfulness metrics
    factual_consistency = Column(Float, nullable=True)  # Answer consistent with sources
    contradiction_score = Column(Float, nullable=True)  # Contradictions in answer
    source_support_ratio = Column(Float, nullable=True)  # Proportion of answer supported by sources

    # Relevance metrics
    query_answer_alignment = Column(Float, nullable=True)  # How well answer addresses query
    semantic_similarity = Column(Float, nullable=True)  # Semantic similarity between query and answer
    topic_coherence = Column(Float, nullable=True)  # Answer stays on topic

    # Completeness metrics
    coverage_score = Column(Float, nullable=True)  # How completely answer addresses query
    missing_information = Column(JSON, nullable=True)  # Topics not covered
    information_density = Column(Float, nullable=True)  # Information per word

    # Clarity metrics
    readability_score = Column(Float, nullable=True)  # Reading ease
    coherence_score = Column(Float, nullable=True)  # Logical flow
    ambiguity_score = Column(Float, nullable=True)  # Lower is better

    # Multimodal metrics
    modality_integration = Column(Float, nullable=True)  # How well modalities are integrated
    cross_modal_consistency = Column(Float, nullable=True)  # Consistency across modalities

    # User engagement metrics
    click_through_rate = Column(Float, nullable=True)  # Source link clicks
    dwell_time_average = Column(Float, nullable=True)  # Time spent on answer
    refinement_rate = Column(Float, nullable=True)  # Query refinement frequency

    # System metrics
    retrieval_precision = Column(Float, nullable=True)  # Precision of retrieved documents
    retrieval_recall = Column(Float, nullable=True)  # Recall of relevant documents
    answer_length_words = Column(Integer, nullable=True)
    answer_length_chars = Column(Integer, nullable=True)

    # Relationships
    query = relationship("RAGQuery", back_populates="quality_metrics")

    def calculate_composite_score(self) -> float:
        """Calculate composite quality score"""
        weights = {
            'factual_consistency': 0.25,
            'query_answer_alignment': 0.20,
            'coverage_score': 0.15,
            'readability_score': 0.10,
            'modality_integration': 0.10,
            'user_engagement': 0.20
        }

        scores = {
            'factual_consistency': self.factual_consistency or 0.5,
            'query_answer_alignment': self.query_answer_alignment or 0.5,
            'coverage_score': self.coverage_score or 0.5,
            'readability_score': self.readability_score or 0.5,
            'modality_integration': self.modality_integration or 0.5,
            'user_engagement': (self.click_through_rate or 0.5) * 0.5 + (self.dwell_time_average or 0.5) * 0.5
        }

        return sum(scores[key] * weights[key] for key in weights)


class RAGAnswerVersion(BaseModel):
    """Version history of RAG answers for tracking improvements"""

    __tablename__ = "rag_answer_versions"

    query_id = Column(GUID(), ForeignKey("rag_queries.id"), nullable=False)
    version_number = Column(Integer, nullable=False)

    # Version content
    answer_text = Column(Text, nullable=False)
    answer_type = Column(Enum(AnswerType), nullable=False)
    answer_sources = Column(JSON, nullable=True)
    context_snippets = Column(JSON, nullable=True)

    # Version metrics
    confidence_score = Column(Float, nullable=False)
    quality_score = Column(Float, nullable=True)

    # Change information
    change_reason = Column(String(255), nullable=True)  # user_feedback, auto_improvement, new_sources
    change_description = Column(Text, nullable=True)
    changed_by_user_id = Column(GUID(), ForeignKey("users.id"), nullable=True)

    # Relationships
    query = relationship("RAGQuery", back_populates="answer_versions")
    changed_by_user = relationship("User")


class RAGFeedbackEvent(BaseModel):
    """Detailed feedback events for RAG queries"""

    __tablename__ = "rag_feedback_events"

    query_id = Column(GUID(), ForeignKey("rag_queries.id"), nullable=False)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)

    # Event details
    event_type = Column(String(50), nullable=False)  # rating, feedback, share, bookmark, refinement
    event_data = Column(JSON, nullable=True)  # Event-specific data

    # Feedback specifics
    rating = Column(Integer, nullable=True)
    feedback_text = Column(Text, nullable=True)
    feedback_category = Column(String(50), nullable=True)
    helpful = Column(Boolean, nullable=True)

    # Event context
    session_id = Column(String(255), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Relationships
    query = relationship("RAGQuery", back_populates="feedback_events")
    user = relationship("User")