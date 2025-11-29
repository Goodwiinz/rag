# AI-Powered Document Analysis and Q&A System - Data Access Patterns

## Overview

This document outlines the comprehensive data access patterns for optimal performance when interacting with the AI-Powered Document Analysis and Q&A System. These patterns are designed to leverage PostgreSQL-specific optimizations and ensure scalability.

## Core Data Access Patterns

### 1. Conversation Retrieval Patterns

#### Pattern 1: User's Conversations with Pagination
```sql
-- Optimized for user dashboard with keyset pagination
WITH user_conversations AS (
    SELECT
        cs.*,
        d.title as document_title,
        u.email as created_by_email,
        u.first_name || ' ' || COALESCE(u.last_name, '') as created_by_name
    FROM conversation_summary cs
    LEFT JOIN documents d ON cs.document_id = d.id
    LEFT JOIN users u ON cs.created_by_user_id = u.id
    WHERE cs.created_by_user_id = $user_id
    AND cs.organization_id = $org_id
    AND cs.status = ANY($statuses)
    AND ($document_id IS NULL OR cs.document_id = $document_id)
    AND ($search_term IS NULL OR
         cs.title ILIKE '%' || $search_term || '%' OR
         cs.document_title ILIKE '%' || $search_term || '%'
    )
)
SELECT * FROM user_conversations
WHERE cs.last_activity_at < $cursor
ORDER BY cs.last_activity_at DESC
LIMIT $limit;
```

**Performance Optimizations**:
- Uses materialized view `conversation_summary` for pre-aggregated data
- Keyset pagination instead of OFFSET for better performance
- Conditional filters using parameterized queries
- Full-text search with ILIKE for title matching

#### Pattern 2: Conversation Detail with Messages
```sql
-- Single query to get conversation with all messages and participants
WITH conversation_detail AS (
    SELECT
        dc.*,
        d.title as document_title,
        d.content_text as document_content,
        u.email as created_by_email,
        u.first_name || ' ' || COALESCE(u.last_name, '') as created_by_name
    FROM document_conversations dc
    JOIN documents d ON dc.document_id = d.id
    JOIN users u ON dc.created_by_user_id = u.id
    WHERE dc.id = $conversation_id
    AND dc.organization_id = $org_id
),
conversation_messages AS (
    SELECT
        cm.*,
        u.email as created_by_email,
        u.first_name || ' ' || COALESCE(u.last_name, '') as created_by_name
    FROM conversation_messages cm
    LEFT JOIN users u ON cm.created_by_user_id = u.id
    WHERE cm.conversation_id = $conversation_id
    AND cm.is_deleted = false
    ORDER BY cm.message_sequence
),
conversation_participants AS (
    SELECT
        cp.*,
        u.email as user_email,
        u.first_name || ' ' || COALESCE(u.last_name, '') as user_name
    FROM conversation_participants cp
    JOIN users u ON cp.user_id = u.id
    WHERE cp.conversation_id = $conversation_id
    AND cp.is_deleted = false
)
SELECT
    cd.*,
    jsonb_agg(jsonb_build_object(
        'id', cm.id,
        'message_sequence', cm.message_sequence,
        'message_type', cm.message_type,
        'content', cm.content,
        'content_type', cm.content_type,
        'source_type', cm.source_type,
        'confidence_score', cm.confidence_score,
        'processing_time_ms', cm.processing_time_ms,
        'user_rating', cm.user_rating,
        'is_helpful', cm.is_helpful,
        'created_at', cm.created_at,
        'created_by_email', cm.created_by_email,
        'created_by_name', cm.created_by_name
    ) ORDER BY cm.message_sequence) as messages,
    jsonb_agg(jsonb_build_object(
        'id', cp.id,
        'user_id', cp.user_id,
        'role', cp.role,
        'status', cp.status,
        'joined_at', cp.joined_at,
        'user_email', cp.user_email,
        'user_name', cp.user_name
    )) as participants
FROM conversation_detail cd
CROSS JOIN LATERAL (SELECT 1) dummy
LEFT JOIN conversation_messages cm ON true
LEFT JOIN conversation_participants cp ON true
GROUP BY cd.id, cd.title, cd.description, cd.conversation_type, cd.status,
         cd.document_id, cd.document_title, cd.document_content,
         cd.created_by_email, cd.created_by_name,
         dc.created_at, dc.updated_at, dc.last_activity_at;
```

### 2. Q&A Cache Optimization Patterns

#### Pattern 3: High-Performance Cache Lookup
```sql
-- Function-based cache lookup with context matching
SELECT * FROM get_or_create_cached_answer(
    $normalized_question,
    $original_question,
    $context_document_ids,
    $organization_id,
    $user_id
);
```

#### Pattern 4: Cache Warming Strategy
```sql
-- Identify popular question patterns for cache warming
WITH question_patterns AS (
    SELECT
        cm.content,
        COUNT(*) as frequency,
        AVG(cm.confidence_score) as avg_confidence,
        dc.document_id
    FROM conversation_messages cm
    JOIN document_conversations dc ON cm.conversation_id = dc.id
    WHERE cm.message_type = 'question'
    AND cm.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
    AND dc.organization_id = $org_id
    GROUP BY cm.content, dc.document_id
    HAVING COUNT(*) >= 3
    ORDER BY frequency DESC
    LIMIT 100
)
SELECT
    qp.content,
    qp.frequency,
    qp.avg_confidence,
    qp.document_id,
    d.title as document_title
FROM question_patterns qp
LEFT JOIN documents d ON qp.document_id = d.id;
```

#### Pattern 5: Cache Performance Monitoring
```sql
-- Real-time cache performance analytics
SELECT
    organization_id,
    total_cache_entries,
    total_hits,
    ROUND(total_hits::DECIMAL / NULLIF(total_cache_entries, 0), 2) as hit_ratio,
    avg_hits_per_entry,
    avg_quality,
    stale_entries,
    expired_entries,
    ROUND(stale_entries::DECIMAL / NULLIF(total_cache_entries, 0) * 100, 2) as stale_percentage,
    entries_used_last_week,
    avg_generation_time
FROM qa_cache_performance
WHERE organization_id = $org_id;
```

### 3. User Analytics Patterns

#### Pattern 6: User Engagement Dashboard
```sql
-- Comprehensive user engagement with efficient joins
WITH user_metrics AS (
    SELECT
        ued.*,
        -- Calculate conversation quality score
        CASE
            WHEN ued.questions_asked > 0 THEN
                (COALESCE(ued.satisfaction_score, 0) * 0.4 +
                 COALESCE(ued.avg_question_rating, 3) / 5 * 0.3 +
                 LEAST(ued.avg_response_time_ms / 5000, 1) * 0.3)
            ELSE 0
        END as engagement_score,
        -- Categorize user activity level
        CASE
            WHEN ued.questions_asked >= 50 THEN 'power_user'
            WHEN ued.questions_asked >= 20 THEN 'active_user'
            WHEN ued.questions_asked >= 5 THEN 'regular_user'
            ELSE 'casual_user'
        END as user_category
    FROM user_engagement_dashboard ued
    WHERE ued.organization_id = $org_id
    AND ($user_category IS NULL OR
         CASE
             WHEN $user_category = 'power_user' AND ued.questions_asked >= 50 THEN true
             WHEN $user_category = 'active_user' AND ued.questions_asked >= 20 THEN true
             WHEN $user_category = 'regular_user' AND ued.questions_asked >= 5 THEN true
             WHEN $user_category = 'casual_user' AND ued.questions_asked < 5 THEN true
             ELSE false
         END
    )
    AND ($min_questions IS NULL OR ued.questions_asked >= $min_questions)
)
SELECT
    um.*,
    -- Rank users within organization
    ROW_NUMBER() OVER (ORDER BY um.engagement_score DESC) as engagement_rank,
    ROW_NUMBER() OVER (ORDER BY um.questions_asked DESC) as activity_rank,
    ROW_NUMBER() OVER (ORDER BY um.satisfaction_score DESC NULLS LAST) as satisfaction_rank
FROM user_metrics um
ORDER BY um.engagement_score DESC
LIMIT $limit OFFSET $offset;
```

#### Pattern 7: Real-time User Activity Tracking
```sql
-- Track current user activity sessions
WITH active_sessions AS (
    SELECT
        user_id,
        session_id,
        COUNT(*) as interactions_count,
        MIN(created_at) as session_start,
        MAX(created_at) as last_activity,
        STRING_AGG(DISTINCT interaction_type::TEXT, ', ') as interaction_types
    FROM user_qa_interactions
    WHERE organization_id = $org_id
    AND created_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour'
    AND success = true
    GROUP BY user_id, session_id
    HAVING COUNT(*) >= 1
),
user_activity AS (
    SELECT
        asq.user_id,
        COUNT(*) as active_sessions,
        SUM(asq.interactions_count) as total_interactions,
        MAX(asq.last_activity) as latest_activity,
        ARRAY_AGG(asq.session_id) as session_ids
    FROM active_sessions asq
    GROUP BY asq.user_id
)
SELECT
    ua.*,
        u.first_name || ' ' || COALESCE(u.last_name, '') as user_name,
        u.email,
        CASE
            WHEN ua.latest_activity >= CURRENT_TIMESTAMP - INTERVAL '5 minutes' THEN 'online'
            WHEN ua.latest_activity >= CURRENT_TIMESTAMP - INTERVAL '30 minutes' THEN 'away'
            ELSE 'offline'
        END as status
FROM user_activity ua
JOIN users u ON ua.user_id = u.id
WHERE u.organization_id = $org_id
ORDER BY ua.latest_activity DESC;
```

### 4. Document Analysis Patterns

#### Pattern 8: Document Analysis Pipeline
```sql
-- Get pending analysis jobs with priority ordering
WITH pending_analyses AS (
    SELECT
        dar.*,
        d.title as document_title,
        d.file_size_bytes,
        d.document_type,
        -- Calculate processing priority
        CASE
            WHEN d.document_type = 'pdf' AND d.file_size_bytes > 10485760 THEN 10 -- Large PDF
            WHEN d.document_type = 'video' THEN 9
            WHEN d.document_type = 'pdf' THEN 8
            WHEN d.document_type IN ('text', 'docx') THEN 7
            ELSE 5
        END +
        CASE
            WHEN d.created_at >= CURRENT_TIMESTAMP - INTERVAL '1 day' THEN 5
            WHEN d.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days' THEN 3
            ELSE 0
        END as processing_priority,
        -- Check for existing analyses
        EXISTS (
            SELECT 1 FROM document_analysis_results dar2
            WHERE dar2.document_id = dar.document_id
            AND dar2.analysis_type = dar.analysis_type
            AND dar2.status = 'completed'
            AND dar2.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
        ) as has_recent_analysis
    FROM document_analysis_results dar
    JOIN documents d ON dar.document_id = d.id
    WHERE dar.status = 'pending'
    AND dar.organization_id = $org_id
    AND NOT EXISTS (
        SELECT 1 FROM document_analysis_results dar3
        WHERE dar3.document_id = dar.document_id
        AND dar3.analysis_type = dar.analysis_type
        AND dar3.status = 'processing'
    )
)
SELECT
    pa.*,
    -- Optimize for parallel processing by document type and size
    ROW_NUMBER() OVER (PARTITION BY pa.document_id ORDER BY pa.processing_priority DESC) as type_rank
FROM pending_analyses pa
WHERE pa.has_recent_analysis = false
ORDER BY pa.processing_priority DESC, pa.file_size_bytes ASC
LIMIT $batch_size;
```

#### Pattern 9: Analysis Results Aggregation
```sql
-- Get comprehensive analysis results for a document
WITH analysis_summary AS (
    SELECT
        dar.document_id,
        jsonb_object_agg(
            dar.analysis_type,
            jsonb_build_object(
                'results', dar.results,
                'confidence_score', dar.confidence_score,
                'quality_score', dar.quality_score,
                'ai_model_used', dar.ai_model_used,
                'created_at', dar.created_at,
                'version', dar.analysis_version
            )
        ) as analyses_by_type,
        -- Aggregate quality metrics
        AVG(dar.confidence_score) as avg_confidence,
        AVG(dar.quality_score) as avg_quality,
        COUNT(*) as total_analyses,
        COUNT(CASE WHEN dar.status = 'completed' THEN 1 END) as completed_analyses,
        COUNT(CASE WHEN dar.status = 'failed' THEN 1 END) as failed_analyses,
        -- Processing metrics
        SUM(dar.processing_time_ms) as total_processing_time,
        AVG(dar.processing_time_ms) as avg_processing_time,
        SUM(dar.computational_cost) as total_cost
    FROM document_analysis_results dar
    WHERE dar.document_id = $document_id
    AND dar.organization_id = $org_id
    AND dar.is_deleted = false
    GROUP BY dar.document_id
)
SELECT
    as_.*,
    d.title as document_title,
    d.document_type,
    d.file_size_bytes,
    d.processing_status,
    -- Calculate analysis completeness
    CASE
        WHEN as_.completed_analyses >= 5 THEN 'comprehensive'
        WHEN as_.completed_analyses >= 3 THEN 'substantial'
        WHEN as_.completed_analyses >= 1 THEN 'basic'
        ELSE 'none'
    END as analysis_level,
    -- Calculate overall document score
    CASE
        WHEN as_.avg_quality IS NOT NULL THEN
            ROUND(as_.avg_quality * 100, 2)
        ELSE NULL
    END as overall_quality_score
FROM analysis_summary as_
JOIN documents d ON as_.document_id = d.id;
```

### 5. Knowledge Gap Analysis Patterns

#### Pattern 10: Automated Knowledge Gap Detection
```sql
-- Comprehensive knowledge gap analysis
WITH unanswered_patterns AS (
    -- Frequently asked questions without answers
    SELECT
        'unanswered_questions' as gap_type,
        'Questions frequently left unanswered' as gap_title,
        ARRAY_AGG(DISTINCT cm.content ORDER BY COUNT(*) DESC) as affected_questions,
        COUNT(*) as frequency,
        -- Map severity based on frequency
        CASE
            WHEN COUNT(*) >= 20 THEN 'critical'
            WHEN COUNT(*) >= 10 THEN 'high'
            WHEN COUNT(*) >= 5 THEN 'medium'
            ELSE 'low'
        END as impact_severity
    FROM conversation_messages cm
    JOIN document_conversations dc ON cm.conversation_id = dc.id
    WHERE cm.message_type = 'question'
    AND cm.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
    AND dc.organization_id = $org_id
    AND NOT EXISTS (
        SELECT 1 FROM conversation_messages cm2
        WHERE cm2.conversation_id = cm.conversation_id
        AND cm2.message_sequence > cm.message_sequence
        AND cm2.message_type = 'answer'
    )
    GROUP BY cm.conversation_id
    HAVING COUNT(*) >= 3
),
low_confidence_patterns AS (
    -- Questions receiving low-confidence answers
    SELECT
        'low_confidence_responses' as gap_type,
        'Answers with consistently low confidence' as gap_title,
        ARRAY_AGG(DISTINCT cm.content ORDER BY cm.confidence_score ASC) as affected_questions,
        COUNT(*) as frequency,
        CASE
            WHEN COUNT(*) >= 15 THEN 'critical'
            WHEN COUNT(*) >= 8 THEN 'high'
            WHEN COUNT(*) >= 3 THEN 'medium'
            ELSE 'low'
        END as impact_severity
    FROM conversation_messages cm
    JOIN document_conversations dc ON cm.conversation_id = dc.id
    WHERE cm.message_type = 'answer'
    AND cm.confidence_score < 0.6
    AND cm.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
    AND dc.organization_id = $org_id
    GROUP BY dc.document_id
    HAVING COUNT(*) >= 3
),
dissatisfaction_patterns AS (
    -- Questions with poor user ratings
    SELECT
        'poor_quality_answers' as gap_type,
        'Answers with consistently poor user ratings' as gap_title,
        ARRAY_AGG(DISTINCT cm.content ORDER BY cm.user_rating ASC) as affected_questions,
        COUNT(*) as frequency,
        CASE
            WHEN COUNT(*) >= 10 THEN 'critical'
            WHEN COUNT(*) >= 5 THEN 'high'
            WHEN COUNT(*) >= 2 THEN 'medium'
            ELSE 'low'
        END as impact_severity
    FROM conversation_messages cm
    JOIN document_conversations dc ON cm.conversation_id = dc.id
    WHERE cm.message_type = 'answer'
    AND cm.user_rating IS NOT NULL
    AND cm.user_rating <= 2
    AND cm.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
    AND dc.organization_id = $org_id
    GROUP BY dc.document_id
    HAVING COUNT(*) >= 2
)
SELECT * FROM unanswered_patterns
UNION ALL
SELECT * FROM low_confidence_patterns
UNION ALL
SELECT * FROM dissatisfaction_patterns
ORDER BY frequency DESC, impact_severity DESC
LIMIT $limit;
```

### 6. Performance Monitoring Patterns

#### Pattern 11: System Health Dashboard
```sql
-- Real-time system performance metrics
WITH conversation_metrics AS (
    SELECT
        COUNT(*) as total_conversations,
        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_conversations,
        COUNT(CASE WHEN last_activity_at >= CURRENT_TIMESTAMP - INTERVAL '1 hour' THEN 1 END) as conversations_last_hour,
        AVG(CASE
            WHEN last_activity_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
            THEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_activity_at))/60
        END) as avg_response_time_minutes
    FROM document_conversations
    WHERE organization_id = $org_id
    AND is_deleted = false
),
message_metrics AS (
    SELECT
        COUNT(*) as total_messages,
        COUNT(CASE WHEN message_type = 'question' THEN 1 END) as questions_today,
        COUNT(CASE WHEN message_type = 'answer' THEN 1 END) as answers_today,
        AVG(COALESCE(confidence_score, 0)) as avg_confidence_score,
        AVG(COALESCE(processing_time_ms, 0)) as avg_processing_time_ms
    FROM conversation_messages
    WHERE organization_id = $org_id
    AND created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
    AND is_deleted = false
),
cache_metrics AS (
    SELECT
        total_cache_entries,
        total_hits,
        ROUND(total_hits::DECIMAL / NULLIF(total_cache_entries, 0), 2) as cache_hit_ratio,
        stale_entries,
        avg_quality
    FROM qa_cache_performance
    WHERE organization_id = $org_id
),
analysis_metrics AS (
    SELECT
        COUNT(*) as pending_analyses,
        COUNT(CASE WHEN status = 'processing' THEN 1 END) as processing_analyses,
        COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_analyses,
        AVG(COALESCE(processing_time_ms, 0)) as avg_analysis_time_ms
    FROM document_analysis_results
    WHERE organization_id = $org_id
    AND created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
    AND is_deleted = false
)
SELECT
    cm.*,
    mm.*,
    cp.*,
    am.*,
    -- Calculate overall health score (0-100)
    ROUND(
        LEAST(cp.cache_hit_ratio * 20, 20) + -- Cache performance (0-20)
        LEAST(cm.avg_confidence_score * 20, 20) + -- Confidence score (0-20)
        LEAST((100 - am.failed_analyses::DECIMAL / NULLIF(am.pending_analyses + am.processing_analyses + am.failed_analyses, 1) * 100) * 0.2, 20) + -- Success rate (0-20)
        LEAST((100 - GREATEST(cm.avg_response_time_minutes - 5, 0) / 55 * 100) * 0.2, 20) + -- Response time (0-20)
        LEAST(GREATEST(cm.active_conversations::DECIMAL / NULLIF(cm.total_conversations, 1) * 100, 0), 20) -- Activity level (0-20)
    ) as health_score,
    CASE
        WHEN ROUND(
            LEAST(cp.cache_hit_ratio * 20, 20) +
            LEAST(cm.avg_confidence_score * 20, 20) +
            LEAST((100 - am.failed_analyses::DECIMAL / NULLIF(am.pending_analyses + am.processing_analyses + am.failed_analyses, 1) * 100) * 0.2, 20) +
            LEAST((100 - GREATEST(cm.avg_response_time_minutes - 5, 0) / 55 * 100) * 0.2, 20) +
            LEAST(GREATEST(cm.active_conversations::DECIMAL / NULLIF(cm.total_conversations, 1) * 100, 0), 20)
        ) >= 80 THEN 'excellent'
        WHEN ROUND(...) >= 60 THEN 'good'
        WHEN ROUND(...) >= 40 THEN 'fair'
        ELSE 'poor'
    END as health_status
FROM conversation_metrics cm
CROSS JOIN message_metrics mm
CROSS JOIN cache_metrics cp
CROSS JOIN analysis_metrics am;
```

## Advanced Query Patterns

### 1. Recursive Queries for Conversation Trees

```sql
-- Get conversation threads with reply hierarchies
WITH RECURSIVE conversation_tree AS (
    -- Base case: root messages
    SELECT
        cm.id,
        cm.conversation_id,
        cm.content,
        cm.message_type,
        cm.message_sequence,
        cm.parent_message_id,
        cm.created_at,
        cm.created_by_user_id,
        1 as thread_level,
        ARRAY[cm.id] as thread_path,
        cm.content as root_content
    FROM conversation_messages cm
    WHERE cm.conversation_id = $conversation_id
    AND (cm.parent_message_id IS NULL OR cm.message_sequence = 1)

    UNION ALL

    -- Recursive case: replies
    SELECT
        cm.id,
        cm.conversation_id,
        cm.content,
        cm.message_type,
        cm.message_sequence,
        cm.parent_message_id,
        cm.created_at,
        cm.created_by_user_id,
        ct.thread_level + 1,
        ct.thread_path || cm.id,
        ct.root_content
    FROM conversation_messages cm
    JOIN conversation_tree ct ON cm.parent_message_id = ct.id
    WHERE cm.conversation_id = $conversation_id
    AND cm.is_deleted = false
)
SELECT
    ct.*,
    u.email as created_by_email,
    u.first_name || ' ' || COALESCE(u.last_name, '') as created_by_name,
    -- Calculate reply depth statistics
        COUNT(*) OVER (PARTITION BY ct.root_content) as total_replies_in_thread,
        MAX(ct.thread_level) OVER (PARTITION BY ct.root_content) as max_thread_depth
FROM conversation_tree ct
JOIN users u ON ct.created_by_user_id = u.id
ORDER BY ct.thread_path;
```

### 2. Time-Series Analytics with Window Functions

```sql
-- User engagement trends over time
WITH daily_metrics AS (
    SELECT
        DATE(created_at) as metric_date,
        user_id,
        COUNT(CASE WHEN interaction_type = 'question_asked' THEN 1 END) as questions_asked,
        COUNT(CASE WHEN interaction_type = 'conversation_started' THEN 1 END) as conversations_started,
        AVG(CASE WHEN response_time_ms IS NOT NULL THEN response_time_ms END) as avg_response_time,
        COUNT(DISTINCT session_id) as unique_sessions
    FROM user_qa_interactions
    WHERE organization_id = $org_id
    AND created_at >= CURRENT_TIMESTAMP - INTERVAL '90 days'
    GROUP BY DATE(created_at), user_id
),
user_trends AS (
    SELECT
        dm.metric_date,
        dm.user_id,
        dm.questions_asked,
        dm.conversations_started,
        dm.avg_response_time,
        dm.unique_sessions,
        -- Calculate moving averages
        AVG(dm.questions_asked) OVER (
            PARTITION BY dm.user_id
            ORDER BY dm.metric_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as questions_7day_ma,
        AVG(dm.avg_response_time) OVER (
            PARTITION BY dm.user_id
            ORDER BY dm.metric_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) as response_time_7day_ma,
        -- Calculate trend direction
        CASE
            WHEN AVG(dm.questions_asked) OVER (
                PARTITION BY dm.user_id
                ORDER BY dm.metric_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) > AVG(dm.questions_asked) OVER (
                PARTITION BY dm.user_id
                ORDER BY dm.metric_date
                ROWS BETWEEN 13 PRECEDING AND 7 PRECEDING
            ) THEN 'increasing'
            WHEN AVG(dm.questions_asked) OVER (
                PARTITION BY dm.user_id
                ORDER BY dm.metric_date
                ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) < AVG(dm.questions_asked) OVER (
                PARTITION BY dm.user_id
                ORDER BY dm.metric_date
                ROWS BETWEEN 13 PRECEDING AND 7 PRECEDING
            ) THEN 'decreasing'
            ELSE 'stable'
        END as engagement_trend
    FROM daily_metrics dm
)
SELECT
    ut.*,
    u.email as user_email,
    u.first_name || ' ' || COALESCE(u.last_name, '') as user_name
FROM user_trends ut
JOIN users u ON ut.user_id = u.id
WHERE ut.metric_date >= CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY ut.metric_date DESC, ut.questions_asked DESC;
```

### 3. Full-Text Search with Ranking

```sql
-- Advanced document search with semantic ranking
WITH search_query AS (
    SELECT plainto_tsquery('english', $search_term) as query
),
document_scores AS (
    SELECT
        d.id,
        d.title,
        d.content_text,
        d.document_type,
        -- Full-text search score
        ts_rank(
            setweight(to_tsvector('english', COALESCE(d.title, '')), 'A') ||
            setweight(to_tsvector('english', COALESCE(d.content_text, '')), 'B') ||
            setweight(to_tsvector('english', COALESCE(d.content_summary, '')), 'C'),
            sq.query
        ) as text_rank,
        -- Recent activity boost
        CASE
            WHEN d.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days' THEN 1.5
            WHEN d.created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days' THEN 1.2
            ELSE 1.0
        END as recency_boost,
        -- Document type preferences
        CASE
            WHEN d.document_type = 'pdf' THEN 1.1
            WHEN d.document_type = 'text' THEN 1.05
            ELSE 1.0
        END as type_boost,
        -- Q&A activity boost
        COALESCE((
            SELECT COUNT(*) * 0.1
            FROM document_conversations dc
            WHERE dc.document_id = d.id
            AND dc.last_activity_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
        ), 0) as qa_activity_boost
    FROM documents d, search_query sq
    WHERE d.organization_id = $org_id
    AND d.is_deleted = false
    AND (
        to_tsvector('english', COALESCE(d.title, '') || ' ' || COALESCE(d.content_text, '') || ' ' || COALESCE(d.content_summary, '')) @@ sq.query
    )
)
SELECT
    ds.*,
    -- Calculate final relevance score
    (ds.text_rank * ds.recency_boost * ds.type_boost + ds.qa_activity_boost) as final_score,
    -- Include related conversation count
        (
            SELECT COUNT(*)
            FROM document_conversations dc
            WHERE dc.document_id = ds.id
            AND dc.is_deleted = false
        ) as conversation_count,
    -- Include analysis status
        EXISTS (
            SELECT 1 FROM document_analysis_results dar
            WHERE dar.document_id = ds.id
            AND dar.status = 'completed'
            AND dar.is_deleted = false
        ) as has_analysis
FROM document_scores ds
WHERE ds.text_rank > 0.1  -- Filter out very low relevance
ORDER BY final_score DESC
LIMIT $limit OFFSET $offset;
```

## Optimization Guidelines

### 1. Connection Pooling
- Use connection pools with appropriate sizing (typically 10-20 connections per application instance)
- Implement connection validation and retry logic
- Consider read replicas for analytics queries

### 2. Query Optimization
- Always use parameterized queries to prevent SQL injection
- Implement proper indexing strategy based on query patterns
- Use EXPLAIN ANALYZE to optimize slow queries

### 3. Caching Strategy
- Implement application-level caching for frequently accessed data
- Use materialized views for complex analytics queries
- Implement cache invalidation strategies

### 4. Batch Operations
- Use batch inserts for high-volume data ingestion
- Implement bulk updates for maintenance operations
- Consider COPY command for large data imports

### 5. Monitoring and Maintenance
- Monitor query performance with pg_stat_statements
- Implement regular vacuum and analyze operations
- Track table bloat and index usage

These data access patterns provide a comprehensive foundation for building high-performance applications on the AI-Powered Document Analysis and Q&A System while leveraging PostgreSQL-specific optimizations and ensuring scalability.