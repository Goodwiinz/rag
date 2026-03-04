-- Initial schema migration from existing multimodal_rag_dev database
-- Generated: 2026-03-03

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: uuid-ossp; Type: EXTENSION; Schema: -; Owner: -
--

-- Using gen_random_uuid() (built-in PostgreSQL 13+) instead of uuid-ossp




--
-- Name: connectionstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.connectionstatus AS ENUM (
    'CONNECTING',
    'CONNECTED',
    'DISCONNECTING',
    'DISCONNECTED',
    'ERROR',
    'TIMEOUT'
);


--
-- Name: contenttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.contenttype AS ENUM (
    'TEXT',
    'IMAGE',
    'AUDIO',
    'VIDEO',
    'METADATA'
);


--
-- Name: documenttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.documenttype AS ENUM (
    'TEXT',
    'IMAGE',
    'AUDIO',
    'VIDEO',
    'PDF',
    'SPREADSHEET',
    'PRESENTATION',
    'MULTIMODAL'
);


--
-- Name: entitytype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.entitytype AS ENUM (
    'PERSON',
    'ORGANIZATION',
    'LOCATION',
    'PRODUCT',
    'CONCEPT',
    'DATE',
    'NUMBER',
    'EMAIL',
    'PHONE',
    'URL',
    'CUSTOM'
);


--
-- Name: evaluationtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.evaluationtype AS ENUM (
    'AUTOMATED',
    'HUMAN',
    'HYBRID',
    'A_B_TEST',
    'CONTINUOUS'
);


--
-- Name: eventseverity; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.eventseverity AS ENUM (
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL'
);


--
-- Name: eventtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.eventtype AS ENUM (
    'SEARCH_QUERY',
    'DOCUMENT_VIEW',
    'DOCUMENT_DOWNLOAD',
    'USER_LOGIN',
    'USER_LOGOUT',
    'SESSION_START',
    'SESSION_END',
    'CLICK_EVENT',
    'PAGE_VIEW',
    'ERROR_OCCURRED',
    'PERFORMANCE_METRIC',
    'QUALITY_METRIC',
    'RECOMMENDATION_SHOWN',
    'RECOMMENDATION_CLICKED',
    'FEEDBACK_SUBMITTED',
    'FILTER_APPLIED',
    'SORT_CHANGED'
);


--
-- Name: experimentstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.experimentstatus AS ENUM (
    'DRAFT',
    'SCHEDULED',
    'RUNNING',
    'PAUSED',
    'COMPLETED',
    'ANALYZED',
    'ARCHIVED',
    'CANCELLED'
);


--
-- Name: experimenttype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.experimenttype AS ENUM (
    'SEARCH_ALGORITHM',
    'RANKING_MODEL',
    'QUERY_PROCESSING',
    'FILTER_CONFIGURATION',
    'MULTIMODAL_WEIGHTING',
    'RESPONSE_FORMAT',
    'PERFORMANCE_OPTIMIZATION',
    'UI_EXPERIENCE'
);


--
-- Name: extractionmethod; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.extractionmethod AS ENUM (
    'SPACY',
    'OPENAI',
    'REGEX',
    'MANUAL',
    'GRAPH_EXTRACTION'
);


--
-- Name: jobpriority; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.jobpriority AS ENUM (
    'LOW',
    'NORMAL',
    'HIGH',
    'URGENT'
);


--
-- Name: jobstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.jobstatus AS ENUM (
    'PENDING',
    'QUEUED',
    'RUNNING',
    'COMPLETED',
    'FAILED',
    'CANCELLED',
    'RETRYING'
);


--
-- Name: jobtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.jobtype AS ENUM (
    'DOCUMENT_INGESTION',
    'TEXT_EXTRACTION',
    'EMBEDDING_GENERATION',
    'ENTITY_EXTRACTION',
    'GRAPH_INDEXING',
    'QUALITY_EVALUATION',
    'BATCH_PROCESSING',
    'CLEANUP'
);


--
-- Name: messagerole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.messagerole AS ENUM (
    'user',
    'assistant',
    'system',
    'tool'
);


--
-- Name: metriccategory; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.metriccategory AS ENUM (
    'SYSTEM',
    'DATABASE',
    'API',
    'SEARCH',
    'CACHE',
    'MEMORY',
    'NETWORK',
    'STORAGE',
    'EXTERNAL_SERVICE'
);


--
-- Name: metricscope; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.metricscope AS ENUM (
    'SYSTEM',
    'ORGANIZATION',
    'USER',
    'DOCUMENT',
    'SEARCH_QUERY',
    'PROCESSING_JOB'
);


--
-- Name: metrictype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.metrictype AS ENUM (
    'PRECISION',
    'RECALL',
    'F1_SCORE',
    'ACCURACY',
    'RELEVANCE',
    'COHERENCE',
    'LATENCY',
    'THROUGHPUT',
    'ERROR_RATE',
    'USER_SATISFACTION',
    'BUSINESS_IMPACT'
);


--
-- Name: performancelevel; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.performancelevel AS ENUM (
    'EXCELLENT',
    'GOOD',
    'FAIR',
    'POOR',
    'CRITICAL'
);


--
-- Name: priority; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.priority AS ENUM (
    'LOW',
    'NORMAL',
    'HIGH',
    'CRITICAL'
);


--
-- Name: processingstage; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.processingstage AS ENUM (
    'UPLOADED',
    'VALIDATED',
    'EXTRACTED',
    'ANALYZED',
    'INDEXED',
    'EMBEDDED',
    'COMPLETED'
);


--
-- Name: processingstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.processingstatus AS ENUM (
    'PENDING',
    'PROCESSING',
    'COMPLETED',
    'FAILED',
    'RETRYING'
);


--
-- Name: qualitymetrictype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.qualitymetrictype AS ENUM (
    'TEXT_CLARITY',
    'IMAGE_RESOLUTION',
    'AUDIO_CLARITY',
    'VIDEO_QUALITY',
    'CONTENT_RICHNESS',
    'EXTRACTION_ACCURACY'
);


--
-- Name: searchtype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.searchtype AS ENUM (
    'SEMANTIC',
    'KEYWORD',
    'HYBRID',
    'GRAPH',
    'MULTIMODAL'
);


--
-- Name: sessionstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.sessionstatus AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'EXPIRED',
    'TERMINATED'
);


--
-- Name: stanceenum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.stanceenum AS ENUM (
    'SUPPORTING',
    'OPPOSING',
    'NEUTRAL',
    'NOT_ADDRESSED'
);


--
-- Name: statisticaltest; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.statisticaltest AS ENUM (
    'Z_TEST',
    'T_TEST',
    'CHI_SQUARE',
    'MANN_WHITNEY',
    'WELCH_T_TEST',
    'BAYESIAN_AB'
);


--
-- Name: storagetier; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.storagetier AS ENUM (
    'FREE',
    'PROFESSIONAL',
    'ENTERPRISE'
);


--
-- Name: successcriterion; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.successcriterion AS ENUM (
    'HIGHER_IS_BETTER',
    'LOWER_IS_BETTER',
    'TARGET_RANGE',
    'STATISTICAL_SIGNIFICANCE'
);


--
-- Name: threadstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.threadstatus AS ENUM (
    'active',
    'resolved',
    'archived'
);


--
-- Name: trafficsplittype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.trafficsplittype AS ENUM (
    'UNIFORM',
    'WEIGHTED',
    'GRADUAL_ROLLOUT',
    'BANDIT'
);


--
-- Name: updatetype; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.updatetype AS ENUM (
    'DOCUMENT_PROCESSING',
    'JOB_STATUS',
    'SYSTEM_STATUS',
    'USER_NOTIFICATION',
    'QUOTA_ALERT',
    'EVALUATION_RESULT',
    'SEARCH_PROGRESS',
    'BATCH_OPERATION'
);


--
-- Name: userrole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.userrole AS ENUM (
    'ADMIN',
    'CONTENT_MANAGER',
    'USER',
    'ANALYST'
);


--
-- Name: workspacerole; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.workspacerole AS ENUM (
    'owner',
    'admin',
    'editor',
    'viewer'
);


--
-- Name: get_user_websocket_connections(uuid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_user_websocket_connections(p_user_id uuid) RETURNS TABLE(connection_id character varying, session_id character varying, connected_at timestamp with time zone, last_activity timestamp with time zone, subscription_channels text[])
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT
        wc.connection_id,
        wc.session_id,
        wc.connected_at,
        wc.last_activity,
        wc.subscription_channels
    FROM websocket_connections wc
    WHERE wc.user_id = p_user_id
    AND wc.is_active = TRUE;
END;
$$;


--
-- Name: refresh_realtime_views(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.refresh_realtime_views() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_document_dashboard;
    REFRESH MATERIALIZED VIEW CONCURRENTLY realtime_system_status;
END;
$$;


--
-- Name: update_document_realtime_status(uuid, character varying, numeric, character varying, character varying, text, boolean); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_document_realtime_status(p_document_id uuid, p_new_status character varying, p_progress numeric DEFAULT NULL::numeric, p_stage character varying DEFAULT NULL::character varying, p_worker_id character varying DEFAULT NULL::character varying, p_message text DEFAULT NULL::text, p_broadcast boolean DEFAULT false) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_old_status VARCHAR(50);
    v_user_id UUID;
    v_update_id UUID;
BEGIN
    -- Get old status and user info
    SELECT status, uploaded_by INTO v_old_status, v_user_id
    FROM documents
    WHERE id = p_document_id;

    -- Update document status
    UPDATE documents
    SET
        status = p_new_status,
        processing_progress = COALESCE(p_progress, processing_progress),
        current_processing_stage = COALESCE(p_stage, current_processing_stage),
        worker_assignment_id = COALESCE(p_worker_id, worker_assignment_id),
        last_status_update = NOW()
    WHERE id = p_document_id;

    -- Create real-time status update
    INSERT INTO realtime_status_updates (
        document_id,
        update_type,
        previous_status,
        new_status,
        progress_percentage,
        current_stage,
        message_content,
        target_user_id,
        broadcast_all
    ) VALUES (
        p_document_id,
        'status_change',
        v_old_status,
        p_new_status,
        p_progress,
        p_stage,
        p_message,
        v_user_id,
        p_broadcast
    ) RETURNING id INTO v_update_id;

    RETURN TRUE;
END;
$$;


--
-- Name: update_last_status_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_last_status_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.last_status_update = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ab_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ab_assignments (
    user_id uuid NOT NULL,
    session_id character varying(255),
    experiment_id uuid NOT NULL,
    variant_id uuid NOT NULL,
    assigned_at timestamp with time zone NOT NULL,
    assignment_source character varying(100),
    user_segment jsonb,
    query_context jsonb,
    device_info jsonb,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: ab_experiment_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ab_experiment_metrics (
    experiment_id uuid NOT NULL,
    variant_id uuid NOT NULL,
    metric_type public.metrictype NOT NULL,
    metric_value double precision NOT NULL,
    user_id uuid,
    session_id character varying(255),
    query_id uuid,
    metric_metadata jsonb,
    "timestamp" timestamp with time zone NOT NULL,
    date_hour character varying(13) NOT NULL,
    date_day character varying(10) NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: ab_experiment_segments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ab_experiment_segments (
    experiment_id uuid NOT NULL,
    segment_id uuid NOT NULL,
    traffic_percentage double precision,
    variant_weights jsonb,
    custom_success_criteria jsonb,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT valid_segment_traffic_percentage CHECK (((traffic_percentage IS NULL) OR ((traffic_percentage > (0)::double precision) AND (traffic_percentage <= (100)::double precision))))
);


--
-- Name: ab_experiments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ab_experiments (
    name character varying(255) NOT NULL,
    description text,
    hypothesis text NOT NULL,
    experiment_type public.experimenttype NOT NULL,
    status public.experimentstatus NOT NULL,
    start_time timestamp with time zone,
    end_time timestamp with time zone,
    scheduled_start timestamp with time zone,
    scheduled_end timestamp with time zone,
    traffic_split_type public.trafficsplittype NOT NULL,
    traffic_percentage double precision NOT NULL,
    max_participants integer,
    confidence_level double precision NOT NULL,
    minimum_sample_size integer NOT NULL,
    statistical_test public.statisticaltest NOT NULL,
    expected_effect_size double precision,
    target_user_segments jsonb,
    target_query_patterns jsonb,
    target_organization_ids uuid[],
    primary_metric public.metrictype NOT NULL,
    success_criteria public.successcriterion NOT NULL,
    target_improvement double precision,
    minimum_duration_days integer NOT NULL,
    winning_variant_id uuid,
    statistical_significance double precision,
    effect_size double precision,
    confidence_interval_lower double precision,
    confidence_interval_upper double precision,
    organization_id uuid NOT NULL,
    created_by uuid NOT NULL,
    tags character varying[],
    external_references jsonb,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT valid_confidence_level CHECK (((confidence_level > (0)::double precision) AND (confidence_level < (1)::double precision))),
    CONSTRAINT valid_duration CHECK ((minimum_duration_days > 0)),
    CONSTRAINT valid_sample_size CHECK ((minimum_sample_size > 0)),
    CONSTRAINT valid_target_improvement CHECK (((target_improvement IS NULL) OR (target_improvement > (0)::double precision))),
    CONSTRAINT valid_traffic_percentage CHECK (((traffic_percentage > (0)::double precision) AND (traffic_percentage <= (100)::double precision)))
);


--
-- Name: ab_query_routing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ab_query_routing (
    query_id uuid NOT NULL,
    user_id uuid,
    session_id character varying(255),
    experiment_id uuid NOT NULL,
    variant_id uuid NOT NULL,
    routing_decision_at timestamp with time zone NOT NULL,
    routing_reason character varying(255),
    routing_confidence double precision,
    alternative_variants jsonb,
    processing_overhead_ms integer,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: ab_user_segment_memberships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ab_user_segment_memberships (
    user_id uuid NOT NULL,
    segment_id uuid NOT NULL,
    is_active boolean NOT NULL,
    joined_at timestamp with time zone NOT NULL,
    left_at timestamp with time zone,
    membership_criteria jsonb,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: ab_user_segments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ab_user_segments (
    name character varying(255) NOT NULL,
    description text,
    organization_id uuid NOT NULL,
    segment_criteria jsonb NOT NULL,
    segment_type character varying(100),
    user_count integer NOT NULL,
    active_user_count integer NOT NULL,
    created_by uuid NOT NULL,
    is_dynamic boolean NOT NULL,
    last_updated timestamp with time zone NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT valid_active_user_count CHECK ((active_user_count >= 0)),
    CONSTRAINT valid_user_count CHECK ((user_count >= 0))
);


--
-- Name: ab_variants; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ab_variants (
    name character varying(255) NOT NULL,
    description text,
    is_control boolean NOT NULL,
    experiment_id uuid NOT NULL,
    config jsonb NOT NULL,
    weight double precision NOT NULL,
    participant_count integer NOT NULL,
    query_count integer NOT NULL,
    primary_metric_value double precision,
    conversion_count integer NOT NULL,
    click_count integer NOT NULL,
    total_response_time_ms integer NOT NULL,
    user_satisfaction_score double precision,
    standard_error double precision,
    confidence_interval_lower double precision,
    confidence_interval_upper double precision,
    p_value double precision,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT valid_participant_count CHECK ((participant_count >= 0)),
    CONSTRAINT valid_weight CHECK ((weight > (0)::double precision))
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: analytics_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.analytics_events (
    id uuid NOT NULL,
    event_type public.eventtype NOT NULL,
    event_category character varying(100),
    severity public.eventseverity NOT NULL,
    user_id uuid,
    session_id character varying(255),
    organization_id uuid NOT NULL,
    event_name character varying(255) NOT NULL,
    description text,
    event_data jsonb,
    user_agent text,
    ip_address character varying(45),
    referrer text,
    page_url text,
    api_endpoint character varying(500),
    response_time_ms integer,
    memory_usage_mb double precision,
    cpu_usage_percent double precision,
    value double precision,
    unit character varying(50),
    tags jsonb,
    event_timestamp timestamp with time zone NOT NULL,
    date_hour character varying(13) NOT NULL,
    date_day character varying(10) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    processed boolean NOT NULL,
    batch_id character varying(100),
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: api_key_usage_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_key_usage_log (
    id uuid NOT NULL,
    api_key_id character varying NOT NULL,
    endpoint character varying(255) NOT NULL,
    method character varying(10) NOT NULL,
    client_ip character varying(45),
    user_agent text,
    request_size_bytes integer,
    response_status integer,
    response_time_ms integer,
    search_query text,
    results_count integer,
    error_message text,
    accessed_at timestamp without time zone NOT NULL
);


--
-- Name: api_keys; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_keys (
    id uuid NOT NULL,
    name character varying NOT NULL,
    key_hash character varying NOT NULL,
    key_prefix character varying(8) NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp without time zone NOT NULL,
    last_used_at timestamp without time zone,
    usage_count integer NOT NULL,
    rate_limit_per_hour integer NOT NULL,
    allowed_endpoints text,
    created_by character varying,
    description text,
    expires_at timestamp without time zone
);


--
-- Name: audit_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_events (
    id uuid NOT NULL,
    event_type character varying(50) NOT NULL,
    severity character varying(20) NOT NULL,
    user_id uuid,
    organization_id uuid NOT NULL,
    session_id character varying(255),
    action character varying(255) NOT NULL,
    resource_type character varying(100),
    resource_id character varying(255),
    ip_address character varying(45),
    user_agent text,
    endpoint character varying(255),
    http_method character varying(10),
    details json,
    old_values json,
    new_values json,
    success boolean NOT NULL,
    error_message text,
    error_code character varying(100),
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: chat_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chat_messages (
    id uuid NOT NULL,
    thread_id uuid NOT NULL,
    user_id uuid,
    role public.messagerole NOT NULL,
    content text NOT NULL,
    token_count integer NOT NULL,
    latency_ms integer,
    model_name character varying(100),
    model_version character varying(50),
    tool_name character varying(100),
    tool_call_id character varying(255),
    feedback_rating integer,
    feedback_text text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: citation_relationships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.citation_relationships (
    source_citation_id uuid NOT NULL,
    target_citation_id uuid NOT NULL,
    relationship_type character varying(50) DEFAULT 'cites'::character varying NOT NULL,
    citation_context text,
    confidence double precision,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_citation_no_self_reference CHECK ((source_citation_id <> target_citation_id))
);


--
-- Name: citations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.citations (
    id uuid NOT NULL,
    message_id uuid,
    document_id uuid,
    chunk_index integer,
    chunk_id character varying(255),
    snippet text,
    page_number integer,
    score double precision,
    rerank_score double precision,
    start_char integer,
    end_char integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    external_reference_id character varying(255),
    document_title character varying(500),
    document_type character varying(100),
    authors jsonb,
    year integer,
    venue character varying(500),
    doi character varying(255),
    arxiv_id character varying(100),
    abstract text,
    metadata_source character varying(100),
    needs_review boolean DEFAULT false NOT NULL
);


--
-- Name: collection_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.collection_documents (
    id uuid NOT NULL,
    collection_id uuid NOT NULL,
    document_id uuid NOT NULL,
    sort_order integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: collections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.collections (
    id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    color character varying(7),
    icon character varying(50),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    project_type character varying(50) DEFAULT 'research'::character varying NOT NULL,
    research_status character varying(50) DEFAULT 'active'::character varying NOT NULL,
    research_goals text,
    deadline timestamp with time zone,
    tags jsonb DEFAULT '[]'::jsonb NOT NULL,
    is_private boolean DEFAULT true NOT NULL
);


--
-- Name: compliance_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.compliance_reports (
    id uuid NOT NULL,
    report_type character varying(100) NOT NULL,
    report_name character varying(255) NOT NULL,
    description text,
    organization_id uuid NOT NULL,
    generated_by uuid NOT NULL,
    period_start timestamp with time zone NOT NULL,
    period_end timestamp with time zone NOT NULL,
    data json NOT NULL,
    metrics json NOT NULL,
    summary text,
    file_path character varying(500),
    file_size_bytes integer,
    file_format character varying(20),
    status character varying(20) NOT NULL,
    error_message text,
    created_at timestamp with time zone DEFAULT now(),
    generated_at timestamp with time zone,
    expires_at timestamp with time zone
);


--
-- Name: connection_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.connection_events (
    connection_id uuid NOT NULL,
    event_type character varying(50) NOT NULL,
    event_data json,
    event_timestamp timestamp with time zone NOT NULL,
    session_id character varying(255),
    client_info json,
    server_info json,
    latency_ms double precision,
    message_size_bytes integer,
    processing_time_ms double precision,
    error_code character varying(50),
    error_message text,
    error_stack text,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: conversations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conversations (
    id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    title character varying(500) NOT NULL,
    description text,
    is_archived boolean NOT NULL,
    is_pinned boolean NOT NULL,
    last_activity_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by_id uuid NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: data_retention_policies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.data_retention_policies (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    policy_type character varying(100) NOT NULL,
    retention_days integer NOT NULL,
    retention_period character varying(50) NOT NULL,
    conditions json,
    action character varying(50) NOT NULL,
    is_active boolean NOT NULL,
    organization_id uuid,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    last_run_at timestamp with time zone
);


--
-- Name: document_access_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_access_log (
    document_id uuid NOT NULL,
    document_version_id uuid,
    access_type character varying(50) NOT NULL,
    access_result character varying(20) NOT NULL,
    user_id uuid,
    session_id character varying(255),
    api_key_id character varying(255),
    request_method character varying(10),
    request_path character varying(1000),
    request_query_params jsonb,
    ip_address character varying(45),
    user_agent text,
    referer character varying(1000),
    response_status_code integer,
    response_size_bytes integer,
    response_time_ms double precision,
    is_suspicious boolean NOT NULL,
    threat_score double precision,
    security_flags jsonb,
    access_metadata jsonb,
    error_message text,
    organization_id uuid NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT check_response_size_positive CHECK ((response_size_bytes >= 0)),
    CONSTRAINT check_response_time_positive CHECK ((response_time_ms >= (0)::double precision)),
    CONSTRAINT check_threat_score_range CHECK (((threat_score >= (0)::double precision) AND (threat_score <= (1)::double precision)))
);


--
-- Name: document_processing_stages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_processing_stages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    stage_name character varying(100) NOT NULL,
    stage_order integer NOT NULL,
    stage_type character varying(50) NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    estimated_duration_seconds integer,
    actual_duration_seconds integer,
    progress_percentage numeric(5,2) DEFAULT 0.0,
    worker_id character varying(100),
    error_message text,
    stage_metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT document_processing_stages_progress_percentage_check CHECK (((progress_percentage >= (0)::numeric) AND (progress_percentage <= (100)::numeric))),
    CONSTRAINT document_processing_stages_stage_type_check CHECK (((stage_type)::text = ANY ((ARRAY['upload'::character varying, 'validation'::character varying, 'ocr'::character varying, 'transcription'::character varying, 'entity_extraction'::character varying, 'embedding'::character varying, 'indexing'::character varying, 'quality_check'::character varying, 'completion'::character varying])::text[]))),
    CONSTRAINT document_processing_stages_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'running'::character varying, 'completed'::character varying, 'failed'::character varying, 'skipped'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT processing_stages_duration_positive CHECK (((actual_duration_seconds IS NULL) OR (actual_duration_seconds >= 0)))
);


--
-- Name: TABLE document_processing_stages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.document_processing_stages IS 'Detailed tracking of multi-stage document processing pipeline';


--
-- Name: document_quality_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_quality_metrics (
    document_id uuid NOT NULL,
    content_id character varying(255),
    metric_type public.qualitymetrictype NOT NULL,
    metric_value double precision NOT NULL,
    metric_unit character varying(50),
    assessment_method character varying(100),
    assessment_version character varying(50),
    confidence_score double precision,
    threshold_min double precision,
    threshold_max double precision,
    threshold_target double precision,
    meets_threshold boolean,
    metric_details jsonb,
    comparison_baseline jsonb,
    assessed_by_user_id uuid,
    assessment_config jsonb,
    organization_id uuid NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT check_confidence_score_range CHECK (((confidence_score >= (0)::double precision) AND (confidence_score <= (1)::double precision))),
    CONSTRAINT check_metric_value_positive CHECK ((metric_value >= (0)::double precision))
);


--
-- Name: document_versions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.document_versions (
    document_id uuid NOT NULL,
    version_number integer NOT NULL,
    version_label character varying(100),
    change_description text,
    is_major_version boolean NOT NULL,
    is_current_version boolean NOT NULL,
    file_path character varying(1000) NOT NULL,
    file_size_bytes integer NOT NULL,
    file_hash character varying(64),
    mime_type character varying(100) NOT NULL,
    content_diff jsonb,
    changed_sections character varying[],
    version_metadata jsonb,
    created_by_user_id uuid NOT NULL,
    parent_version_id uuid,
    organization_id uuid NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT check_file_size_positive CHECK ((file_size_bytes >= 0)),
    CONSTRAINT check_version_positive CHECK ((version_number > 0))
);


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    title character varying(500) NOT NULL,
    filename character varying(500) NOT NULL,
    file_path character varying(1000) NOT NULL,
    file_size_bytes integer NOT NULL,
    mime_type character varying(100) NOT NULL,
    document_type public.documenttype NOT NULL,
    content_text text,
    content_summary text,
    document_metadata json,
    search_vector tsvector,
    processing_status public.processingstatus NOT NULL,
    processing_started_at timestamp with time zone,
    processing_completed_at timestamp with time zone,
    processing_error text,
    processing_retry_count integer NOT NULL,
    embedding_id character varying(255),
    is_embedded boolean NOT NULL,
    is_indexed boolean NOT NULL,
    is_public boolean NOT NULL,
    tags character varying[],
    organization_id uuid NOT NULL,
    uploaded_by_user_id uuid NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    current_processing_stage character varying(100) DEFAULT 'queued'::character varying,
    processing_progress numeric(5,2) DEFAULT 0.0,
    estimated_completion_time timestamp with time zone,
    worker_assignment_id character varying(100),
    queue_priority integer DEFAULT 5,
    processing_metadata jsonb DEFAULT '{}'::jsonb,
    real_time_status jsonb DEFAULT '{}'::jsonb,
    last_status_update timestamp with time zone DEFAULT now(),
    concurrent_processing_id uuid,
    retry_attempt integer DEFAULT 0,
    max_retry_attempts integer DEFAULT 3,
    processing_session_id uuid DEFAULT gen_random_uuid(),
    CONSTRAINT documents_processing_progress_check CHECK (((processing_progress >= (0)::numeric) AND (processing_progress <= (100)::numeric))),
    CONSTRAINT documents_queue_priority_check CHECK (((queue_priority >= 1) AND (queue_priority <= 10)))
);


--
-- Name: draft_citations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.draft_citations (
    draft_id uuid NOT NULL,
    citation_index integer NOT NULL,
    document_id uuid,
    citation_id uuid,
    snippet text,
    context text,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: encrypted_organization_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.encrypted_organization_profiles (
    id uuid NOT NULL,
    organization_id uuid NOT NULL,
    legal_business_name text,
    dba_name text,
    tax_id text,
    duns_number text,
    billing_address text,
    shipping_address text,
    billing_phone text,
    billing_email text,
    bank_account_number text,
    bank_routing_number text,
    payment_method text,
    legal_contact_name text,
    legal_contact_email text,
    legal_contact_phone text,
    business_notes text,
    custom_attributes text,
    created_at timestamp with time zone DEFAULT '2025-11-15 21:35:47.581729+00'::timestamp with time zone,
    updated_at timestamp with time zone,
    last_encryption_rotation timestamp with time zone
);


--
-- Name: encrypted_user_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.encrypted_user_profiles (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    first_name text,
    last_name text,
    middle_name text,
    email_personal text,
    phone_mobile text,
    phone_work text,
    address_home text,
    address_work text,
    ssn text,
    passport_number text,
    driver_license text,
    emergency_contact_name text,
    emergency_contact_phone text,
    emergency_contact_relationship text,
    personal_notes text,
    preferences text,
    job_title text,
    department text,
    employee_id text,
    created_at timestamp with time zone DEFAULT '2025-11-15 21:35:47.581729+00'::timestamp with time zone,
    updated_at timestamp with time zone,
    last_encryption_rotation timestamp with time zone
);


--
-- Name: encryption_audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.encryption_audit_logs (
    id uuid NOT NULL,
    operation_type character varying(50) NOT NULL,
    resource_type character varying(50) NOT NULL,
    resource_id uuid NOT NULL,
    key_id character varying(64),
    key_version integer,
    performed_by uuid,
    organization_id uuid,
    operation_details text,
    ip_address character varying(45),
    user_agent text,
    success boolean,
    error_message text,
    created_at timestamp with time zone DEFAULT '2025-11-15 21:35:47.581729+00'::timestamp with time zone
);


--
-- Name: entities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entities (
    entity_type public.entitytype NOT NULL,
    name character varying(500) NOT NULL,
    canonical_name character varying(500),
    aliases character varying[],
    description text,
    properties json,
    confidence double precision NOT NULL,
    relevance_score double precision NOT NULL,
    extraction_method public.extractionmethod NOT NULL,
    extracted_at timestamp with time zone NOT NULL,
    extraction_model character varying(100),
    graph_id character varying(255),
    is_in_knowledge_graph boolean NOT NULL,
    document_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: entity_relationships; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_relationships (
    source_entity_id uuid NOT NULL,
    target_entity_id uuid NOT NULL,
    relationship_type character varying(100) NOT NULL,
    confidence double precision NOT NULL,
    relationship_metadata json,
    created_at timestamp with time zone DEFAULT '2025-11-15 21:35:47.581729+00'::timestamp with time zone NOT NULL
);


--
-- Name: evaluation_comparisons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evaluation_comparisons (
    name character varying(255) NOT NULL,
    description text,
    baseline_job_id uuid,
    comparison_job_id uuid,
    baseline_score double precision,
    comparison_score double precision,
    improvement_percentage double precision,
    statistical_significance double precision,
    metric_comparisons json,
    summary text,
    recommendation text,
    user_id uuid,
    organization_id uuid NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: evaluation_datasets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evaluation_datasets (
    job_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    dataset_type character varying(50) NOT NULL,
    questions json NOT NULL,
    reference_answers json,
    contexts json,
    source_type character varying(100),
    domain character varying(100),
    difficulty_level character varying(50),
    language character varying(10),
    is_processed boolean,
    processed_at timestamp with time zone,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: evaluation_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evaluation_jobs (
    name character varying(255) NOT NULL,
    description text,
    evaluation_type character varying(50) NOT NULL,
    status character varying(50) NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    duration_seconds double precision,
    parameters json NOT NULL,
    dataset_size integer,
    processed_count integer,
    user_id uuid,
    organization_id uuid NOT NULL,
    overall_score double precision,
    success_rate double precision,
    error_message text,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: evaluation_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evaluation_metrics (
    job_id uuid NOT NULL,
    metric_type character varying(100) NOT NULL,
    metric_name character varying(255) NOT NULL,
    value double precision NOT NULL,
    min_value double precision,
    max_value double precision,
    mean_value double precision,
    std_deviation double precision,
    threshold_min double precision,
    threshold_max double precision,
    is_threshold_violation boolean,
    query text NOT NULL,
    generated_answer text,
    reference_answer text,
    retrieved_context text,
    metric_metadata json,
    calculation_method character varying(100),
    model_used character varying(255),
    additional_data json,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: evaluation_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evaluation_reports (
    title character varying(255) NOT NULL,
    report_type character varying(50) NOT NULL,
    job_id uuid NOT NULL,
    content text NOT NULL,
    executive_summary text,
    key_findings json,
    recommendations json,
    format_type character varying(20),
    template_used character varying(100),
    generated_by_model character varying(255),
    file_path character varying(500),
    file_size_bytes integer,
    user_id uuid,
    organization_id uuid NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: evaluation_thresholds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evaluation_thresholds (
    metric_type character varying(100) NOT NULL,
    threshold_min double precision,
    threshold_max double precision,
    organization_id uuid,
    search_type character varying(50),
    document_type character varying(50),
    is_enabled boolean,
    description text,
    severity_level character varying(20),
    alert_on_violation boolean,
    alert_cooldown_minutes integer,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: extraction_cells; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_cells (
    matrix_id uuid NOT NULL,
    document_id uuid NOT NULL,
    column_name character varying(100) NOT NULL,
    value text,
    citation_snippet text,
    confidence double precision,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_cell_confidence_range CHECK (((confidence IS NULL) OR ((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision))))
);


--
-- Name: extraction_matrices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.extraction_matrices (
    project_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    columns jsonb DEFAULT '[]'::jsonb NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: generated_drafts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.generated_drafts (
    project_id uuid NOT NULL,
    version integer NOT NULL,
    title character varying(255) NOT NULL,
    content text NOT NULL,
    themes jsonb DEFAULT '[]'::jsonb NOT NULL,
    word_count integer,
    citation_count integer,
    generation_params jsonb,
    generation_time_ms integer,
    is_current boolean DEFAULT true NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: integrity_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.integrity_scores (
    document_id uuid NOT NULL,
    ai_probability double precision NOT NULL,
    human_probability double precision NOT NULL,
    method character varying(100) NOT NULL,
    analyzed_at timestamp with time zone,
    segment_scores jsonb DEFAULT '[]'::jsonb NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: message_attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.message_attachments (
    id uuid NOT NULL,
    message_id uuid NOT NULL,
    document_id uuid NOT NULL,
    display_name character varying(255),
    thumbnail_url character varying(1000),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: metric_aggregations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metric_aggregations (
    id uuid NOT NULL,
    metric_type character varying(50) NOT NULL,
    aggregation_type character varying(20) NOT NULL,
    aggregation_period_start timestamp without time zone NOT NULL,
    aggregation_period_end timestamp without time zone NOT NULL,
    avg_value double precision NOT NULL,
    min_value double precision NOT NULL,
    max_value double precision NOT NULL,
    count_values integer NOT NULL,
    sum_values double precision NOT NULL,
    std_deviation double precision,
    organization_id uuid NOT NULL,
    search_type character varying(20),
    percentiles jsonb,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: multimodal_content; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.multimodal_content (
    document_id uuid NOT NULL,
    document_version_id uuid,
    content_type public.contenttype NOT NULL,
    content_id character varying(255) NOT NULL,
    sequence_order integer NOT NULL,
    raw_content text,
    processed_content text,
    content_metadata jsonb,
    quality_score double precision,
    extraction_method character varying(100),
    extraction_confidence double precision,
    media_duration_seconds double precision,
    media_dimensions jsonb,
    media_format character varying(50),
    language_code character varying(10),
    word_count integer,
    character_count integer,
    is_indexed boolean NOT NULL,
    embedding_id character varying(255),
    search_vector text,
    organization_id uuid NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT check_character_count_positive CHECK ((character_count >= 0)),
    CONSTRAINT check_extraction_confidence_range CHECK (((extraction_confidence >= (0)::double precision) AND (extraction_confidence <= (1)::double precision))),
    CONSTRAINT check_media_duration_positive CHECK ((media_duration_seconds >= (0)::double precision)),
    CONSTRAINT check_quality_score_range CHECK (((quality_score >= (0)::double precision) AND (quality_score <= (1)::double precision))),
    CONSTRAINT check_sequence_order_positive CHECK ((sequence_order >= 0)),
    CONSTRAINT check_word_count_positive CHECK ((word_count >= 0))
);


--
-- Name: notification_templates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notification_templates (
    template_name character varying(100) NOT NULL,
    update_type public.updatetype NOT NULL,
    priority public.priority NOT NULL,
    title_template character varying(255) NOT NULL,
    message_template text,
    data_schema json,
    default_ttl_minutes integer,
    requires_acknowledgment boolean NOT NULL,
    is_dismissible boolean NOT NULL,
    action_required boolean NOT NULL,
    default_action_url character varying(500),
    supported_languages json,
    translations json,
    usage_count integer NOT NULL,
    last_used_at timestamp with time zone,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: organizations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organizations (
    name character varying(255) NOT NULL,
    storage_tier public.storagetier NOT NULL,
    storage_used_bytes bigint NOT NULL,
    storage_limit_bytes bigint NOT NULL,
    is_active boolean NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: performance_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.performance_logs (
    id uuid NOT NULL,
    metric_name character varying(255) NOT NULL,
    metric_category public.metriccategory NOT NULL,
    performance_level public.performancelevel NOT NULL,
    organization_id uuid,
    value double precision NOT NULL,
    unit character varying(50),
    baseline_value double precision,
    threshold_warning double precision,
    threshold_critical double precision,
    cpu_usage_percent double precision,
    memory_usage_mb double precision,
    memory_usage_percent double precision,
    disk_usage_gb double precision,
    disk_usage_percent double precision,
    network_io_mb double precision,
    response_time_ms integer,
    request_count integer,
    error_count integer,
    active_connections integer,
    queue_size integer,
    db_connections integer,
    db_query_time_ms integer,
    db_slow_queries integer,
    db_cache_hit_rate double precision,
    search_query_time_ms integer,
    index_size_mb double precision,
    search_results_count integer,
    component character varying(100),
    environment character varying(50),
    version character varying(50),
    node_id character varying(100),
    tags jsonb,
    event_metadata jsonb,
    alert_triggered boolean NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    date_hour character varying(13) NOT NULL,
    date_day character varying(10) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    batch_id character varying(100),
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permissions (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    display_name character varying(255) NOT NULL,
    description text,
    category character varying(50) NOT NULL,
    scope character varying(50) NOT NULL,
    resource character varying(100),
    is_system boolean NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: processing_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.processing_history (
    document_id uuid NOT NULL,
    stage public.processingstage NOT NULL,
    status character varying(20) NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    duration_seconds double precision,
    processor_id character varying(255),
    processing_config jsonb,
    processing_metadata jsonb,
    error_message text,
    error_type character varying(100),
    retry_count integer NOT NULL,
    cpu_time_seconds double precision,
    memory_peak_mb double precision,
    progress_percentage double precision NOT NULL,
    current_step character varying(255),
    organization_id uuid NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT check_duration_positive CHECK ((duration_seconds >= (0)::double precision)),
    CONSTRAINT check_progress_range CHECK (((progress_percentage >= (0)::double precision) AND (progress_percentage <= (100)::double precision))),
    CONSTRAINT check_retry_non_negative CHECK ((retry_count >= 0))
);


--
-- Name: processing_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.processing_jobs (
    job_type public.jobtype NOT NULL,
    status public.jobstatus NOT NULL,
    priority public.jobpriority NOT NULL,
    parameters json,
    config json,
    requirements json,
    celery_task_id character varying(255),
    worker_id character varying(255),
    queue_name character varying(100),
    queued_at timestamp with time zone,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    duration_seconds double precision,
    cpu_time_seconds double precision,
    memory_peak_mb double precision,
    progress_percentage double precision NOT NULL,
    current_step character varying(255),
    total_steps integer,
    completed_steps integer NOT NULL,
    error_message text,
    error_type character varying(100),
    retry_count integer NOT NULL,
    max_retries integer NOT NULL,
    result json,
    artifacts json,
    metrics json,
    document_id uuid,
    organization_id uuid NOT NULL,
    created_by_user_id uuid,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: project_notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_notes (
    project_id uuid NOT NULL,
    user_id uuid NOT NULL,
    title character varying(255) NOT NULL,
    content text NOT NULL,
    linked_document_ids jsonb DEFAULT '[]'::jsonb NOT NULL,
    tags jsonb DEFAULT '[]'::jsonb NOT NULL,
    is_pinned boolean DEFAULT false NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: project_threads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.project_threads (
    project_id uuid NOT NULL,
    thread_id uuid NOT NULL,
    link_type character varying(50) NOT NULL,
    linked_at timestamp with time zone NOT NULL,
    linked_by_id uuid,
    context_note text,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: COLUMN project_threads.context_note; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.project_threads.context_note IS 'Optional note about why this thread was linked to this project';


--
-- Name: quality_alerts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quality_alerts (
    id uuid NOT NULL,
    metric_id uuid NOT NULL,
    severity character varying(20) NOT NULL,
    title character varying(200) NOT NULL,
    message text NOT NULL,
    status character varying(20) NOT NULL,
    acknowledged_at timestamp without time zone,
    acknowledged_by uuid,
    resolved_at timestamp without time zone,
    resolved_by uuid,
    organization_id uuid NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: quality_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quality_metrics (
    metric_type public.metrictype NOT NULL,
    metric_name character varying(255) NOT NULL,
    value double precision NOT NULL,
    unit character varying(50),
    evaluation_type public.evaluationtype NOT NULL,
    scope public.metricscope NOT NULL,
    scope_id uuid,
    evaluation_parameters json,
    ground_truth json,
    predictions json,
    evaluation_metadata json,
    threshold_min double precision,
    threshold_max double precision,
    target_value double precision,
    quality_score double precision,
    passes_threshold boolean,
    confidence_interval json,
    evaluation_period_start timestamp with time zone,
    evaluation_period_end timestamp with time zone,
    sample_size integer,
    organization_id uuid NOT NULL,
    created_by_user_id uuid,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: quality_thresholds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.quality_thresholds (
    id uuid NOT NULL,
    metric_type character varying(50) NOT NULL,
    threshold_min double precision,
    threshold_max double precision,
    threshold_target double precision,
    alert_severity character varying(20) NOT NULL,
    is_enabled boolean NOT NULL,
    alert_cooldown_minutes integer NOT NULL,
    organization_id uuid,
    search_type character varying(20),
    description text,
    created_by uuid NOT NULL,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    role public.userrole NOT NULL,
    is_active boolean NOT NULL,
    organization_id uuid NOT NULL,
    last_login timestamp with time zone,
    login_count integer NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: realtime_document_dashboard; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.realtime_document_dashboard AS
 SELECT d.id,
    d.title,
    d.filename,
    d.document_type AS file_type,
    d.processing_status AS status,
    d.current_processing_stage,
    d.processing_progress,
    d.queue_priority,
    d.worker_assignment_id,
    d.last_status_update,
    d.created_at AS uploaded_at,
    d.processing_started_at,
    u.email AS uploaded_by_email,
    (((u.first_name)::text || ' '::text) || (COALESCE(u.last_name, ''::character varying))::text) AS uploaded_by_name,
    count(DISTINCT ps.id) AS total_stages,
    count(
        CASE
            WHEN ((ps.status)::text = 'completed'::text) THEN 1
            ELSE NULL::integer
        END) AS completed_stages,
    count(
        CASE
            WHEN ((ps.status)::text = 'running'::text) THEN 1
            ELSE NULL::integer
        END) AS running_stages,
    count(
        CASE
            WHEN ((ps.status)::text = 'failed'::text) THEN 1
            ELSE NULL::integer
        END) AS failed_stages,
        CASE
            WHEN (d.processing_status = 'PROCESSING'::public.processingstatus) THEN
            CASE
                WHEN (count(ps.id) = 0) THEN (0)::numeric
                ELSE round((((count(
                CASE
                    WHEN ((ps.status)::text = 'completed'::text) THEN 1
                    ELSE NULL::integer
                END))::numeric * 100.0) / (count(ps.id))::numeric), 2)
            END
            WHEN (d.processing_status = 'COMPLETED'::public.processingstatus) THEN (100)::numeric
            WHEN (d.processing_status = 'FAILED'::public.processingstatus) THEN (0)::numeric
            ELSE d.processing_progress
        END AS calculated_progress,
        CASE
            WHEN (d.processing_started_at IS NOT NULL) THEN (EXTRACT(epoch FROM (now() - d.processing_started_at)))::integer
            ELSE NULL::integer
        END AS processing_duration_seconds
   FROM ((public.documents d
     JOIN public.users u ON ((d.uploaded_by_user_id = u.id)))
     LEFT JOIN public.document_processing_stages ps ON ((d.id = ps.document_id)))
  WHERE (d.is_deleted = false)
  GROUP BY d.id, d.title, d.filename, d.document_type, d.processing_status, d.current_processing_stage, d.processing_progress, d.queue_priority, d.worker_assignment_id, d.last_status_update, d.created_at, d.processing_started_at, u.email, u.first_name, u.last_name
  WITH NO DATA;


--
-- Name: realtime_performance_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.realtime_performance_metrics (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    metric_name character varying(100) NOT NULL,
    metric_value numeric NOT NULL,
    metric_unit character varying(50),
    metric_type character varying(50) DEFAULT 'gauge'::character varying,
    tags jsonb DEFAULT '{}'::jsonb,
    "timestamp" timestamp with time zone DEFAULT now(),
    source_service character varying(100),
    user_id uuid,
    document_id uuid,
    session_id character varying(255),
    expiration_time timestamp with time zone DEFAULT (now() + '24:00:00'::interval),
    CONSTRAINT performance_metrics_name_not_empty CHECK ((length(TRIM(BOTH FROM metric_name)) > 0)),
    CONSTRAINT realtime_performance_metrics_metric_type_check CHECK (((metric_type)::text = ANY ((ARRAY['gauge'::character varying, 'counter'::character varying, 'histogram'::character varying, 'timer'::character varying])::text[])))
);


--
-- Name: TABLE realtime_performance_metrics; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.realtime_performance_metrics IS 'Time-series metrics for system performance monitoring';


--
-- Name: realtime_status_updates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.realtime_status_updates (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    update_type character varying(50) NOT NULL,
    previous_status character varying(50),
    new_status character varying(50) NOT NULL,
    progress_percentage numeric(5,2),
    current_stage character varying(100),
    message_content text,
    update_metadata jsonb DEFAULT '{}'::jsonb,
    priority integer DEFAULT 5,
    target_user_id uuid,
    target_channels text[] DEFAULT '{}'::text[],
    broadcast_all boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    processed_at timestamp with time zone,
    delivery_status character varying(20) DEFAULT 'pending'::character varying,
    retry_count integer DEFAULT 0,
    max_retries integer DEFAULT 3,
    expires_at timestamp with time zone DEFAULT (now() + '01:00:00'::interval),
    CONSTRAINT realtime_status_updates_delivery_status_check CHECK (((delivery_status)::text = ANY ((ARRAY['pending'::character varying, 'processing'::character varying, 'delivered'::character varying, 'failed'::character varying, 'expired'::character varying])::text[]))),
    CONSTRAINT realtime_status_updates_priority_check CHECK (((priority >= 1) AND (priority <= 10))),
    CONSTRAINT realtime_status_updates_progress_percentage_check CHECK (((progress_percentage >= (0)::numeric) AND (progress_percentage <= (100)::numeric))),
    CONSTRAINT realtime_status_updates_update_type_check CHECK (((update_type)::text = ANY ((ARRAY['status_change'::character varying, 'progress_update'::character varying, 'stage_change'::character varying, 'error'::character varying, 'completion'::character varying, 'queue_update'::character varying])::text[]))),
    CONSTRAINT realtime_updates_message_content_required CHECK ((((update_type)::text <> ALL ((ARRAY['status_change'::character varying, 'progress_update'::character varying, 'stage_change'::character varying, 'completion'::character varying])::text[])) OR (message_content IS NOT NULL)))
);


--
-- Name: TABLE realtime_status_updates; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.realtime_status_updates IS 'Queue for real-time status update messages to be delivered via WebSocket';


--
-- Name: websocket_connections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.websocket_connections (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    connection_id character varying(255) NOT NULL,
    user_id uuid NOT NULL,
    session_id character varying(255),
    socket_id character varying(255),
    connected_at timestamp with time zone DEFAULT now(),
    last_activity timestamp with time zone DEFAULT now(),
    last_heartbeat timestamp with time zone DEFAULT now(),
    client_ip inet,
    user_agent text,
    connection_metadata jsonb DEFAULT '{}'::jsonb,
    subscription_channels text[] DEFAULT '{}'::text[],
    is_active boolean DEFAULT true,
    disconnect_reason character varying(100),
    disconnected_at timestamp with time zone,
    message_count_sent integer DEFAULT 0,
    message_count_received integer DEFAULT 0,
    bytes_sent bigint DEFAULT 0,
    bytes_received bigint DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT websocket_connections_bytes_valid CHECK (((bytes_sent >= 0) AND (bytes_received >= 0))),
    CONSTRAINT websocket_connections_connection_id_not_empty CHECK ((length(TRIM(BOTH FROM connection_id)) > 0)),
    CONSTRAINT websocket_connections_counts_valid CHECK (((message_count_sent >= 0) AND (message_count_received >= 0)))
);


--
-- Name: TABLE websocket_connections; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.websocket_connections IS 'Tracks active WebSocket connections for real-time communication';


--
-- Name: realtime_system_status; Type: MATERIALIZED VIEW; Schema: public; Owner: -
--

CREATE MATERIALIZED VIEW public.realtime_system_status AS
 SELECT ( SELECT count(*) AS count
           FROM public.documents
          WHERE (documents.is_deleted = false)) AS total_documents,
    ( SELECT count(*) AS count
           FROM public.documents
          WHERE ((documents.is_deleted = false) AND (documents.processing_status = 'PENDING'::public.processingstatus))) AS queued_documents,
    ( SELECT count(*) AS count
           FROM public.documents
          WHERE ((documents.is_deleted = false) AND (documents.processing_status = 'PROCESSING'::public.processingstatus))) AS processing_documents,
    ( SELECT count(*) AS count
           FROM public.documents
          WHERE ((documents.is_deleted = false) AND (documents.processing_status = 'COMPLETED'::public.processingstatus))) AS processed_documents,
    ( SELECT count(*) AS count
           FROM public.documents
          WHERE ((documents.is_deleted = false) AND (documents.processing_status = 'FAILED'::public.processingstatus))) AS failed_documents,
    ( SELECT count(*) AS count
           FROM public.websocket_connections
          WHERE (websocket_connections.is_active = true)) AS active_websocket_connections,
    ( SELECT count(DISTINCT websocket_connections.user_id) AS count
           FROM public.websocket_connections
          WHERE (websocket_connections.is_active = true)) AS connected_users,
    ( SELECT avg(realtime_performance_metrics.metric_value) AS avg
           FROM public.realtime_performance_metrics
          WHERE (((realtime_performance_metrics.metric_name)::text = 'document_processing_duration'::text) AND (realtime_performance_metrics."timestamp" >= (now() - '00:05:00'::interval)))) AS avg_processing_time_5min,
    ( SELECT count(*) AS count
           FROM public.realtime_status_updates
          WHERE (realtime_status_updates.created_at >= (now() - '00:05:00'::interval))) AS updates_last_5min,
    ( SELECT count(*) AS count
           FROM public.processing_jobs
          WHERE (processing_jobs.status = 'RUNNING'::public.jobstatus)) AS active_jobs,
    now() AS status_timestamp
  WITH NO DATA;


--
-- Name: research_blueprints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_blueprints (
    project_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    template_source character varying(100),
    version integer NOT NULL,
    steps jsonb,
    parameters jsonb,
    is_immutable boolean NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: research_evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_evidence (
    step_id uuid NOT NULL,
    source_id uuid NOT NULL,
    claim_text text NOT NULL,
    confidence double precision,
    grounding_status character varying(50) NOT NULL,
    page_reference character varying(100),
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: research_pipelines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_pipelines (
    project_id uuid NOT NULL,
    current_step integer DEFAULT 0 NOT NULL,
    completed_steps integer[] DEFAULT '{}'::integer[] NOT NULL,
    skipped_steps integer[] DEFAULT '{}'::integer[] NOT NULL,
    step_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    invalidated_steps integer[] DEFAULT '{}'::integer[] NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: research_projects; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_projects (
    name character varying(255) NOT NULL,
    description text,
    owner_id uuid NOT NULL,
    status character varying(50) NOT NULL,
    settings jsonb,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: research_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_runs (
    blueprint_id uuid NOT NULL,
    blueprint_version integer NOT NULL,
    status character varying(50) NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    reproducibility_manifest jsonb,
    total_tokens integer NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: research_sources; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_sources (
    run_id uuid NOT NULL,
    connector_type character varying(50) NOT NULL,
    external_id character varying(255),
    title character varying(500) NOT NULL,
    authors jsonb,
    abstract text,
    url character varying(2048),
    metadata jsonb,
    content_hash character varying(64),
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: research_steps; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.research_steps (
    run_id uuid NOT NULL,
    step_index integer NOT NULL,
    step_type character varying(50) NOT NULL,
    mode character varying(50) NOT NULL,
    inputs_hash character varying(64),
    outputs_hash character varying(64),
    full_prompt text,
    model_id character varying(100),
    model_version character varying(100),
    temperature double precision NOT NULL,
    seed integer,
    output jsonb,
    quality_marks jsonb,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    token_count integer NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_permissions (
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL,
    granted_at timestamp with time zone DEFAULT now(),
    granted_by uuid
);


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    display_name character varying(255) NOT NULL,
    description text,
    organization_id uuid NOT NULL,
    is_system boolean NOT NULL,
    is_active boolean NOT NULL,
    priority integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: search_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.search_events (
    id uuid NOT NULL,
    session_id uuid NOT NULL,
    search_query_id uuid,
    query text NOT NULL,
    search_type character varying(20) NOT NULL,
    results_count integer NOT NULL,
    response_time double precision NOT NULL,
    clicked_results integer NOT NULL,
    clicked_result_ids jsonb,
    time_to_first_click double precision,
    dwell_time double precision,
    user_rating integer,
    feedback_text text,
    is_bookmarked boolean,
    user_id uuid,
    organization_id uuid NOT NULL,
    page_number integer NOT NULL,
    filters_applied jsonb,
    sort_order character varying(20),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: search_queries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.search_queries (
    query_text text NOT NULL,
    search_type public.searchtype NOT NULL,
    filters json,
    query_parameters json,
    total_results integer NOT NULL,
    search_duration_ms integer,
    vector_search_duration_ms integer,
    graph_search_duration_ms integer,
    reranking_duration_ms integer,
    user_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    session_id character varying(255),
    user_agent text,
    ip_address character varying(45),
    user_satisfaction integer,
    feedback_text text,
    clicked_results integer NOT NULL,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: search_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.search_results (
    document_id uuid NOT NULL,
    search_query_id uuid NOT NULL,
    rank_position integer NOT NULL,
    relevance_score double precision NOT NULL,
    confidence double precision NOT NULL,
    matching_text text,
    match_type character varying(50),
    highlight_spans json,
    context_before text,
    context_after text,
    context_window_size integer NOT NULL,
    matched_modalities character varying[],
    modality_scores json,
    was_clicked boolean NOT NULL,
    clicked_at timestamp with time zone,
    dwell_time_ms integer,
    user_rating integer,
    feedback_text text,
    id uuid NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: search_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.search_sessions (
    id uuid NOT NULL,
    session_id character varying(100) NOT NULL,
    user_id uuid,
    organization_id uuid NOT NULL,
    start_time timestamp without time zone NOT NULL,
    end_time timestamp without time zone,
    search_count integer NOT NULL,
    total_response_time double precision NOT NULL,
    user_agent text,
    ip_address character varying(45),
    referrer text,
    avg_response_time double precision,
    session_duration double precision,
    bounce_rate boolean,
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone
);


--
-- Name: security_incidents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.security_incidents (
    id uuid NOT NULL,
    incident_id character varying(100) NOT NULL,
    title character varying(255) NOT NULL,
    description text NOT NULL,
    severity character varying(20) NOT NULL,
    category character varying(100) NOT NULL,
    status character varying(20) NOT NULL,
    organization_id uuid NOT NULL,
    detected_at timestamp with time zone NOT NULL,
    source character varying(100),
    source_details json,
    affected_users json,
    affected_resources json,
    impact_assessment text,
    assigned_to uuid,
    response_actions json,
    resolution text,
    resolution_time_hours integer,
    damage_assessment character varying(50),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone,
    resolved_at timestamp with time zone
);


--
-- Name: stance_classifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stance_classifications (
    id uuid NOT NULL,
    claim_hash character varying(64) NOT NULL,
    source_id uuid NOT NULL,
    stance public.stanceenum NOT NULL,
    confidence double precision NOT NULL,
    justification_excerpt text,
    model_version character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_stance_classifications_confidence CHECK (((confidence >= (0.0)::double precision) AND (confidence <= (1.0)::double precision)))
);


--
-- Name: status_updates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.status_updates (
    update_id character varying(255) NOT NULL,
    connection_id uuid NOT NULL,
    update_type public.updatetype NOT NULL,
    priority public.priority NOT NULL,
    title character varying(255) NOT NULL,
    message text,
    update_data json,
    progress_percentage double precision,
    target_users json,
    target_organizations json,
    broadcast_channel character varying(100),
    created_at timestamp with time zone NOT NULL,
    sent_at timestamp with time zone,
    delivered_at timestamp with time zone,
    read_at timestamp with time zone,
    acknowledged_at timestamp with time zone,
    delivery_status character varying(50) NOT NULL,
    delivery_attempts integer NOT NULL,
    max_delivery_attempts integer NOT NULL,
    delivery_error text,
    expires_at timestamp with time zone,
    requires_acknowledgment boolean NOT NULL,
    is_dismissible boolean NOT NULL,
    action_required boolean NOT NULL,
    action_url character varying(500),
    was_clicked boolean NOT NULL,
    clicked_at timestamp with time zone,
    user_response json,
    id uuid NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: system_metrics; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_metrics (
    id uuid NOT NULL,
    metric_name character varying(100) NOT NULL,
    metric_value double precision NOT NULL,
    metric_unit character varying(20),
    component_name character varying(100) NOT NULL,
    component_instance character varying(100),
    organization_id uuid,
    metadata jsonb,
    measured_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone NOT NULL
);


--
-- Name: system_status_broadcasts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.system_status_broadcasts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    broadcast_type character varying(50) NOT NULL,
    title character varying(200) NOT NULL,
    message_content text NOT NULL,
    severity character varying(20) DEFAULT 'info'::character varying,
    is_active boolean DEFAULT true,
    target_audience character varying(50) DEFAULT 'all'::character varying,
    start_time timestamp with time zone DEFAULT now(),
    end_time timestamp with time zone DEFAULT (now() + '24:00:00'::interval),
    broadcast_metadata jsonb DEFAULT '{}'::jsonb,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now(),
    delivery_count integer DEFAULT 0,
    read_count integer DEFAULT 0,
    CONSTRAINT system_broadcasts_counts_valid CHECK (((delivery_count >= 0) AND (read_count >= 0))),
    CONSTRAINT system_broadcasts_message_not_empty CHECK ((length(TRIM(BOTH FROM message_content)) > 0)),
    CONSTRAINT system_broadcasts_time_valid CHECK (((end_time IS NULL) OR (end_time >= start_time))),
    CONSTRAINT system_broadcasts_title_not_empty CHECK ((length(TRIM(BOTH FROM title)) > 0)),
    CONSTRAINT system_status_broadcasts_broadcast_type_check CHECK (((broadcast_type)::text = ANY ((ARRAY['system_maintenance'::character varying, 'feature_update'::character varying, 'emergency'::character varying, 'performance_alert'::character varying, 'capacity_warning'::character varying])::text[]))),
    CONSTRAINT system_status_broadcasts_severity_check CHECK (((severity)::text = ANY ((ARRAY['info'::character varying, 'warning'::character varying, 'error'::character varying, 'critical'::character varying])::text[]))),
    CONSTRAINT system_status_broadcasts_target_audience_check CHECK (((target_audience)::text = ANY ((ARRAY['all'::character varying, 'administrators'::character varying, 'users'::character varying, 'premium_users'::character varying])::text[])))
);


--
-- Name: TABLE system_status_broadcasts; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.system_status_broadcasts IS 'System-wide announcements and alerts';


--
-- Name: threads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.threads (
    id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    title character varying(500),
    summary text,
    status public.threadstatus NOT NULL,
    last_message_at timestamp with time zone DEFAULT now() NOT NULL,
    message_count integer NOT NULL,
    token_count integer NOT NULL,
    created_by_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone,
    source_project_id uuid,
    rag_document_scope jsonb
);


--
-- Name: user_realtime_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_realtime_subscriptions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    subscription_type character varying(50) NOT NULL,
    subscription_target jsonb DEFAULT '{}'::jsonb,
    filters jsonb DEFAULT '{}'::jsonb,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    last_notification_at timestamp with time zone,
    notification_count integer DEFAULT 0,
    CONSTRAINT user_realtime_subscriptions_subscription_type_check CHECK (((subscription_type)::text = ANY ((ARRAY['document_updates'::character varying, 'system_status'::character varying, 'processing_queue'::character varying, 'error_alerts'::character varying, 'performance_metrics'::character varying])::text[]))),
    CONSTRAINT user_subscriptions_count_valid CHECK ((notification_count >= 0))
);


--
-- Name: TABLE user_realtime_subscriptions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.user_realtime_subscriptions IS 'User preferences for real-time notifications and updates';


--
-- Name: user_role_assignments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_role_assignments (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    role_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    assigned_by uuid,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone,
    is_active boolean NOT NULL
);


--
-- Name: user_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_sessions (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    organization_id uuid NOT NULL,
    session_id character varying(255) NOT NULL,
    session_token character varying(512),
    status public.sessionstatus NOT NULL,
    user_agent text,
    ip_address character varying(45),
    device_type character varying(50),
    browser character varying(100),
    os character varying(100),
    location_country character varying(2),
    location_city character varying(100),
    started_at timestamp with time zone NOT NULL,
    last_activity timestamp with time zone NOT NULL,
    ended_at timestamp with time zone,
    duration_seconds integer,
    total_searches integer NOT NULL,
    total_documents_viewed integer NOT NULL,
    total_downloads integer NOT NULL,
    total_clicks integer NOT NULL,
    engagement_score double precision NOT NULL,
    search_queries jsonb,
    viewed_documents jsonb,
    clicked_results jsonb,
    navigation_path jsonb,
    bounce_rate double precision NOT NULL,
    conversion_events jsonb,
    satisfaction_rating integer,
    avg_response_time double precision,
    error_count integer NOT NULL,
    page_load_time double precision,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: workspace_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workspace_members (
    id uuid NOT NULL,
    workspace_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role public.workspacerole NOT NULL,
    joined_at timestamp with time zone DEFAULT now() NOT NULL,
    invited_by_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: workspaces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.workspaces (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    is_archived boolean NOT NULL,
    is_public boolean NOT NULL,
    owner_id uuid NOT NULL,
    organization_id uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    is_deleted boolean NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: ab_assignments ab_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_assignments
    ADD CONSTRAINT ab_assignments_pkey PRIMARY KEY (id);


--
-- Name: ab_experiment_metrics ab_experiment_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiment_metrics
    ADD CONSTRAINT ab_experiment_metrics_pkey PRIMARY KEY (id);


--
-- Name: ab_experiment_segments ab_experiment_segments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiment_segments
    ADD CONSTRAINT ab_experiment_segments_pkey PRIMARY KEY (id);


--
-- Name: ab_experiments ab_experiments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiments
    ADD CONSTRAINT ab_experiments_pkey PRIMARY KEY (id);


--
-- Name: ab_query_routing ab_query_routing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_query_routing
    ADD CONSTRAINT ab_query_routing_pkey PRIMARY KEY (id);


--
-- Name: ab_user_segment_memberships ab_user_segment_memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_user_segment_memberships
    ADD CONSTRAINT ab_user_segment_memberships_pkey PRIMARY KEY (id);


--
-- Name: ab_user_segments ab_user_segments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_user_segments
    ADD CONSTRAINT ab_user_segments_pkey PRIMARY KEY (id);


--
-- Name: ab_variants ab_variants_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_variants
    ADD CONSTRAINT ab_variants_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: analytics_events analytics_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analytics_events
    ADD CONSTRAINT analytics_events_pkey PRIMARY KEY (id);


--
-- Name: api_key_usage_log api_key_usage_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_key_usage_log
    ADD CONSTRAINT api_key_usage_log_pkey PRIMARY KEY (id);


--
-- Name: api_keys api_keys_key_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_key_hash_key UNIQUE (key_hash);


--
-- Name: api_keys api_keys_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_keys
    ADD CONSTRAINT api_keys_pkey PRIMARY KEY (id);


--
-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--
-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);


--
-- Name: citation_relationships citation_relationships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citation_relationships
    ADD CONSTRAINT citation_relationships_pkey PRIMARY KEY (id);


--
-- Name: citations citations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citations
    ADD CONSTRAINT citations_pkey PRIMARY KEY (id);


--
-- Name: collection_documents collection_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collection_documents
    ADD CONSTRAINT collection_documents_pkey PRIMARY KEY (id);


--
-- Name: collections collections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collections
    ADD CONSTRAINT collections_pkey PRIMARY KEY (id);


--
-- Name: compliance_reports compliance_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_reports
    ADD CONSTRAINT compliance_reports_pkey PRIMARY KEY (id);


--
-- Name: connection_events connection_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connection_events
    ADD CONSTRAINT connection_events_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: data_retention_policies data_retention_policies_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_retention_policies
    ADD CONSTRAINT data_retention_policies_name_key UNIQUE (name);


--
-- Name: data_retention_policies data_retention_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_retention_policies
    ADD CONSTRAINT data_retention_policies_pkey PRIMARY KEY (id);


--
-- Name: document_access_log document_access_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_access_log
    ADD CONSTRAINT document_access_log_pkey PRIMARY KEY (id);


--
-- Name: document_processing_stages document_processing_stages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_processing_stages
    ADD CONSTRAINT document_processing_stages_pkey PRIMARY KEY (id);


--
-- Name: document_quality_metrics document_quality_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_quality_metrics
    ADD CONSTRAINT document_quality_metrics_pkey PRIMARY KEY (id);


--
-- Name: document_versions document_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT document_versions_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: draft_citations draft_citations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.draft_citations
    ADD CONSTRAINT draft_citations_pkey PRIMARY KEY (id);


--
-- Name: encrypted_organization_profiles encrypted_organization_profiles_organization_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_organization_profiles
    ADD CONSTRAINT encrypted_organization_profiles_organization_id_key UNIQUE (organization_id);


--
-- Name: encrypted_organization_profiles encrypted_organization_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_organization_profiles
    ADD CONSTRAINT encrypted_organization_profiles_pkey PRIMARY KEY (id);


--
-- Name: encrypted_user_profiles encrypted_user_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_user_profiles
    ADD CONSTRAINT encrypted_user_profiles_pkey PRIMARY KEY (id);


--
-- Name: encrypted_user_profiles encrypted_user_profiles_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_user_profiles
    ADD CONSTRAINT encrypted_user_profiles_user_id_key UNIQUE (user_id);


--
-- Name: encryption_audit_logs encryption_audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encryption_audit_logs
    ADD CONSTRAINT encryption_audit_logs_pkey PRIMARY KEY (id);


--
-- Name: entities entities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT entities_pkey PRIMARY KEY (id);


--
-- Name: entity_relationships entity_relationships_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_relationships
    ADD CONSTRAINT entity_relationships_pkey PRIMARY KEY (source_entity_id, target_entity_id);


--
-- Name: evaluation_comparisons evaluation_comparisons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_comparisons
    ADD CONSTRAINT evaluation_comparisons_pkey PRIMARY KEY (id);


--
-- Name: evaluation_datasets evaluation_datasets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_datasets
    ADD CONSTRAINT evaluation_datasets_pkey PRIMARY KEY (id);


--
-- Name: evaluation_jobs evaluation_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_jobs
    ADD CONSTRAINT evaluation_jobs_pkey PRIMARY KEY (id);


--
-- Name: evaluation_metrics evaluation_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_metrics
    ADD CONSTRAINT evaluation_metrics_pkey PRIMARY KEY (id);


--
-- Name: evaluation_reports evaluation_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_reports
    ADD CONSTRAINT evaluation_reports_pkey PRIMARY KEY (id);


--
-- Name: evaluation_thresholds evaluation_thresholds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_thresholds
    ADD CONSTRAINT evaluation_thresholds_pkey PRIMARY KEY (id);


--
-- Name: extraction_cells extraction_cells_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_cells
    ADD CONSTRAINT extraction_cells_pkey PRIMARY KEY (id);


--
-- Name: extraction_matrices extraction_matrices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_matrices
    ADD CONSTRAINT extraction_matrices_pkey PRIMARY KEY (id);


--
-- Name: generated_drafts generated_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generated_drafts
    ADD CONSTRAINT generated_drafts_pkey PRIMARY KEY (id);


--
-- Name: integrity_scores integrity_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integrity_scores
    ADD CONSTRAINT integrity_scores_pkey PRIMARY KEY (id);


--
-- Name: message_attachments message_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_attachments
    ADD CONSTRAINT message_attachments_pkey PRIMARY KEY (id);


--
-- Name: metric_aggregations metric_aggregations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_aggregations
    ADD CONSTRAINT metric_aggregations_pkey PRIMARY KEY (id);


--
-- Name: multimodal_content multimodal_content_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.multimodal_content
    ADD CONSTRAINT multimodal_content_pkey PRIMARY KEY (id);


--
-- Name: notification_templates notification_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notification_templates
    ADD CONSTRAINT notification_templates_pkey PRIMARY KEY (id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: performance_logs performance_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_logs
    ADD CONSTRAINT performance_logs_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: processing_history processing_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_history
    ADD CONSTRAINT processing_history_pkey PRIMARY KEY (id);


--
-- Name: processing_jobs processing_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_jobs
    ADD CONSTRAINT processing_jobs_pkey PRIMARY KEY (id);


--
-- Name: document_processing_stages processing_stages_unique_order; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_processing_stages
    ADD CONSTRAINT processing_stages_unique_order UNIQUE (document_id, stage_order);


--
-- Name: project_notes project_notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_notes
    ADD CONSTRAINT project_notes_pkey PRIMARY KEY (id);


--
-- Name: project_threads project_threads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_threads
    ADD CONSTRAINT project_threads_pkey PRIMARY KEY (id);


--
-- Name: quality_alerts quality_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_alerts
    ADD CONSTRAINT quality_alerts_pkey PRIMARY KEY (id);


--
-- Name: quality_metrics quality_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_metrics
    ADD CONSTRAINT quality_metrics_pkey PRIMARY KEY (id);


--
-- Name: quality_thresholds quality_thresholds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_thresholds
    ADD CONSTRAINT quality_thresholds_pkey PRIMARY KEY (id);


--
-- Name: realtime_performance_metrics realtime_performance_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.realtime_performance_metrics
    ADD CONSTRAINT realtime_performance_metrics_pkey PRIMARY KEY (id);


--
-- Name: realtime_status_updates realtime_status_updates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.realtime_status_updates
    ADD CONSTRAINT realtime_status_updates_pkey PRIMARY KEY (id);


--
-- Name: research_blueprints research_blueprints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_blueprints
    ADD CONSTRAINT research_blueprints_pkey PRIMARY KEY (id);


--
-- Name: research_evidence research_evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_evidence
    ADD CONSTRAINT research_evidence_pkey PRIMARY KEY (id);


--
-- Name: research_pipelines research_pipelines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_pipelines
    ADD CONSTRAINT research_pipelines_pkey PRIMARY KEY (id);


--
-- Name: research_projects research_projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_projects
    ADD CONSTRAINT research_projects_pkey PRIMARY KEY (id);


--
-- Name: research_runs research_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_runs
    ADD CONSTRAINT research_runs_pkey PRIMARY KEY (id);


--
-- Name: research_sources research_sources_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_sources
    ADD CONSTRAINT research_sources_pkey PRIMARY KEY (id);


--
-- Name: research_steps research_steps_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_steps
    ADD CONSTRAINT research_steps_pkey PRIMARY KEY (id);


--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (role_id, permission_id);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);


--
-- Name: search_events search_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_events
    ADD CONSTRAINT search_events_pkey PRIMARY KEY (id);


--
-- Name: search_queries search_queries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_queries
    ADD CONSTRAINT search_queries_pkey PRIMARY KEY (id);


--
-- Name: search_results search_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_results
    ADD CONSTRAINT search_results_pkey PRIMARY KEY (id);


--
-- Name: search_sessions search_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_sessions
    ADD CONSTRAINT search_sessions_pkey PRIMARY KEY (id);


--
-- Name: search_sessions search_sessions_session_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_sessions
    ADD CONSTRAINT search_sessions_session_id_key UNIQUE (session_id);


--
-- Name: security_incidents security_incidents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_incidents
    ADD CONSTRAINT security_incidents_pkey PRIMARY KEY (id);


--
-- Name: stance_classifications stance_classifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stance_classifications
    ADD CONSTRAINT stance_classifications_pkey PRIMARY KEY (id);


--
-- Name: status_updates status_updates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.status_updates
    ADD CONSTRAINT status_updates_pkey PRIMARY KEY (id);


--
-- Name: system_metrics system_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_metrics
    ADD CONSTRAINT system_metrics_pkey PRIMARY KEY (id);


--
-- Name: system_status_broadcasts system_status_broadcasts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_status_broadcasts
    ADD CONSTRAINT system_status_broadcasts_pkey PRIMARY KEY (id);


--
-- Name: threads threads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threads
    ADD CONSTRAINT threads_pkey PRIMARY KEY (id);


--
-- Name: ab_experiments unique_experiment_name_per_org; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiments
    ADD CONSTRAINT unique_experiment_name_per_org UNIQUE (organization_id, name);


--
-- Name: ab_experiment_segments unique_experiment_segment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiment_segments
    ADD CONSTRAINT unique_experiment_segment UNIQUE (experiment_id, segment_id);


--
-- Name: ab_user_segments unique_segment_name_per_org; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_user_segments
    ADD CONSTRAINT unique_segment_name_per_org UNIQUE (organization_id, name);


--
-- Name: ab_assignments unique_session_experiment_assignment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_assignments
    ADD CONSTRAINT unique_session_experiment_assignment UNIQUE (session_id, experiment_id);


--
-- Name: ab_assignments unique_user_experiment_assignment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_assignments
    ADD CONSTRAINT unique_user_experiment_assignment UNIQUE (user_id, experiment_id);


--
-- Name: ab_user_segment_memberships unique_user_segment_membership; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_user_segment_memberships
    ADD CONSTRAINT unique_user_segment_membership UNIQUE (user_id, segment_id);


--
-- Name: ab_variants unique_variant_name_per_experiment; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_variants
    ADD CONSTRAINT unique_variant_name_per_experiment UNIQUE (experiment_id, name);


--
-- Name: extraction_cells uq_cell_matrix_doc_col; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_cells
    ADD CONSTRAINT uq_cell_matrix_doc_col UNIQUE (matrix_id, document_id, column_name);


--
-- Name: citation_relationships uq_citation_relationship; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citation_relationships
    ADD CONSTRAINT uq_citation_relationship UNIQUE (source_citation_id, target_citation_id);


--
-- Name: collection_documents uq_collection_documents; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collection_documents
    ADD CONSTRAINT uq_collection_documents UNIQUE (collection_id, document_id);


--
-- Name: integrity_scores uq_integrity_doc_method; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integrity_scores
    ADD CONSTRAINT uq_integrity_doc_method UNIQUE (document_id, method);


--
-- Name: message_attachments uq_message_attachments; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_attachments
    ADD CONSTRAINT uq_message_attachments UNIQUE (message_id, document_id);


--
-- Name: research_pipelines uq_pipeline_project; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_pipelines
    ADD CONSTRAINT uq_pipeline_project UNIQUE (project_id);


--
-- Name: workspace_members uq_workspace_members_workspace_user; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT uq_workspace_members_workspace_user UNIQUE (workspace_id, user_id);


--
-- Name: user_realtime_subscriptions user_realtime_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_realtime_subscriptions
    ADD CONSTRAINT user_realtime_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: user_role_assignments user_role_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_role_assignments
    ADD CONSTRAINT user_role_assignments_pkey PRIMARY KEY (id);


--
-- Name: user_sessions user_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_pkey PRIMARY KEY (id);


--
-- Name: user_realtime_subscriptions user_subscriptions_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_realtime_subscriptions
    ADD CONSTRAINT user_subscriptions_unique UNIQUE (user_id, subscription_type, subscription_target);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: websocket_connections websocket_connections_connection_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.websocket_connections
    ADD CONSTRAINT websocket_connections_connection_id_key UNIQUE (connection_id);


--
-- Name: websocket_connections websocket_connections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.websocket_connections
    ADD CONSTRAINT websocket_connections_pkey PRIMARY KEY (id);


--
-- Name: workspace_members workspace_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_pkey PRIMARY KEY (id);


--
-- Name: workspaces workspaces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_pkey PRIMARY KEY (id);


--
-- Name: idx_analytics_events_batch; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_batch ON public.analytics_events USING btree (batch_id);


--
-- Name: idx_analytics_events_composite; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_composite ON public.analytics_events USING btree (organization_id, event_type, date_day);


--
-- Name: idx_analytics_events_date_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_date_day ON public.analytics_events USING btree (date_day);


--
-- Name: idx_analytics_events_date_hour; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_date_hour ON public.analytics_events USING btree (date_hour);


--
-- Name: idx_analytics_events_org_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_org_time ON public.analytics_events USING btree (organization_id, event_timestamp);


--
-- Name: idx_analytics_events_processed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_processed ON public.analytics_events USING btree (processed);


--
-- Name: idx_analytics_events_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_session ON public.analytics_events USING btree (session_id, event_timestamp);


--
-- Name: idx_analytics_events_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_severity ON public.analytics_events USING btree (severity, event_timestamp);


--
-- Name: idx_analytics_events_type_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_type_org ON public.analytics_events USING btree (event_type, organization_id);


--
-- Name: idx_analytics_events_user_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_analytics_events_user_time ON public.analytics_events USING btree (user_id, event_timestamp);


--
-- Name: idx_assignments_experiment_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assignments_experiment_time ON public.ab_assignments USING btree (experiment_id, assigned_at);


--
-- Name: idx_assignments_user_experiment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assignments_user_experiment ON public.ab_assignments USING btree (user_id, experiment_id);


--
-- Name: idx_assignments_variant_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_assignments_variant_time ON public.ab_assignments USING btree (variant_id, assigned_at);


--
-- Name: idx_audit_events_org_user_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_events_org_user_date ON public.audit_events USING btree (organization_id, user_id, created_at);


--
-- Name: idx_audit_events_resource; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_events_resource ON public.audit_events USING btree (resource_type, resource_id);


--
-- Name: idx_audit_events_type_success; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_events_type_success ON public.audit_events USING btree (event_type, success);


--
-- Name: idx_compliance_reports_org_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_compliance_reports_org_type ON public.compliance_reports USING btree (organization_id, report_type);


--
-- Name: idx_documents_current_stage; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_current_stage ON public.documents USING btree (current_processing_stage);


--
-- Name: idx_documents_last_status_update; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_last_status_update ON public.documents USING btree (last_status_update DESC);


--
-- Name: idx_documents_processing_progress; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_processing_progress ON public.documents USING btree (processing_progress);


--
-- Name: idx_documents_queue_priority; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_queue_priority ON public.documents USING btree (queue_priority DESC);


--
-- Name: idx_documents_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_session_id ON public.documents USING btree (processing_session_id);


--
-- Name: idx_documents_worker_assignment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documents_worker_assignment ON public.documents USING btree (worker_assignment_id);


--
-- Name: idx_experiments_creator; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_creator ON public.ab_experiments USING btree (created_by);


--
-- Name: idx_experiments_org_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_org_status ON public.ab_experiments USING btree (organization_id, status);


--
-- Name: idx_experiments_timing; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_timing ON public.ab_experiments USING btree (start_time, end_time);


--
-- Name: idx_experiments_type_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_experiments_type_status ON public.ab_experiments USING btree (experiment_type, status);


--
-- Name: idx_metric_agg_org_type_period; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metric_agg_org_type_period ON public.metric_aggregations USING btree (organization_id, metric_type, aggregation_type);


--
-- Name: idx_metric_agg_period_start; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metric_agg_period_start ON public.metric_aggregations USING btree (aggregation_period_start);


--
-- Name: idx_metric_agg_search_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metric_agg_search_type ON public.metric_aggregations USING btree (search_type);


--
-- Name: idx_metrics_experiment_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_experiment_day ON public.ab_experiment_metrics USING btree (experiment_id, date_day);


--
-- Name: idx_metrics_experiment_variant_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_experiment_variant_type ON public.ab_experiment_metrics USING btree (experiment_id, variant_id, metric_type);


--
-- Name: idx_metrics_type_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_type_time ON public.ab_experiment_metrics USING btree (metric_type, "timestamp");


--
-- Name: idx_metrics_user_experiment; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_user_experiment ON public.ab_experiment_metrics USING btree (user_id, experiment_id);


--
-- Name: idx_metrics_variant_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_metrics_variant_time ON public.ab_experiment_metrics USING btree (variant_id, "timestamp");


--
-- Name: idx_performance_logs_alert; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_logs_alert ON public.performance_logs USING btree (alert_triggered, "timestamp");


--
-- Name: idx_performance_logs_category_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_logs_category_time ON public.performance_logs USING btree (metric_category, "timestamp");


--
-- Name: idx_performance_logs_component_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_logs_component_time ON public.performance_logs USING btree (component, "timestamp");


--
-- Name: idx_performance_logs_composite; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_logs_composite ON public.performance_logs USING btree (metric_category, organization_id, date_day);


--
-- Name: idx_performance_logs_date_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_logs_date_day ON public.performance_logs USING btree (date_day);


--
-- Name: idx_performance_logs_date_hour; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_logs_date_hour ON public.performance_logs USING btree (date_hour);


--
-- Name: idx_performance_logs_level_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_logs_level_time ON public.performance_logs USING btree (performance_level, "timestamp");


--
-- Name: idx_performance_logs_metric_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_logs_metric_time ON public.performance_logs USING btree (metric_name, "timestamp");


--
-- Name: idx_performance_logs_org_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_logs_org_time ON public.performance_logs USING btree (organization_id, "timestamp");


--
-- Name: idx_performance_metrics_document; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_metrics_document ON public.realtime_performance_metrics USING btree (document_id);


--
-- Name: idx_performance_metrics_expiration; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_metrics_expiration ON public.realtime_performance_metrics USING btree (expiration_time) WHERE (expiration_time IS NOT NULL);


--
-- Name: idx_performance_metrics_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_metrics_name ON public.realtime_performance_metrics USING btree (metric_name);


--
-- Name: idx_performance_metrics_tags_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_metrics_tags_gin ON public.realtime_performance_metrics USING gin (tags);


--
-- Name: idx_performance_metrics_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_metrics_timestamp ON public.realtime_performance_metrics USING btree ("timestamp" DESC);


--
-- Name: idx_performance_metrics_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_performance_metrics_user ON public.realtime_performance_metrics USING btree (user_id);


--
-- Name: idx_processing_stages_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processing_stages_document_id ON public.document_processing_stages USING btree (document_id);


--
-- Name: idx_processing_stages_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processing_stages_order ON public.document_processing_stages USING btree (document_id, stage_order);


--
-- Name: idx_processing_stages_progress; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processing_stages_progress ON public.document_processing_stages USING btree (progress_percentage);


--
-- Name: idx_processing_stages_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processing_stages_status ON public.document_processing_stages USING btree (status);


--
-- Name: idx_processing_stages_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processing_stages_type ON public.document_processing_stages USING btree (stage_type);


--
-- Name: idx_processing_stages_updated_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processing_stages_updated_at ON public.document_processing_stages USING btree (updated_at DESC);


--
-- Name: idx_processing_stages_worker; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processing_stages_worker ON public.document_processing_stages USING btree (worker_id);


--
-- Name: idx_quality_alerts_org_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quality_alerts_org_status ON public.quality_alerts USING btree (organization_id, status);


--
-- Name: idx_quality_alerts_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quality_alerts_severity ON public.quality_alerts USING btree (severity, created_at);


--
-- Name: idx_quality_thresholds_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quality_thresholds_enabled ON public.quality_thresholds USING btree (is_enabled);


--
-- Name: idx_quality_thresholds_org_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_quality_thresholds_org_type ON public.quality_thresholds USING btree (organization_id, metric_type);


--
-- Name: idx_realtime_document_dashboard_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_document_dashboard_id ON public.realtime_document_dashboard USING btree (id);


--
-- Name: idx_realtime_document_dashboard_progress; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_document_dashboard_progress ON public.realtime_document_dashboard USING btree (processing_progress);


--
-- Name: idx_realtime_document_dashboard_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_document_dashboard_status ON public.realtime_document_dashboard USING btree (status);


--
-- Name: idx_realtime_document_dashboard_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_document_dashboard_user ON public.realtime_document_dashboard USING btree (uploaded_by_email);


--
-- Name: idx_realtime_system_status_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_system_status_timestamp ON public.realtime_system_status USING btree (status_timestamp);


--
-- Name: idx_realtime_updates_broadcast_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_updates_broadcast_target ON public.realtime_status_updates USING btree (broadcast_all, target_user_id) WHERE (broadcast_all = true);


--
-- Name: idx_realtime_updates_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_updates_created_at ON public.realtime_status_updates USING btree (created_at DESC);


--
-- Name: idx_realtime_updates_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_updates_document_id ON public.realtime_status_updates USING btree (document_id);


--
-- Name: idx_realtime_updates_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_updates_expires_at ON public.realtime_status_updates USING btree (expires_at);


--
-- Name: idx_realtime_updates_priority; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_updates_priority ON public.realtime_status_updates USING btree (priority DESC);


--
-- Name: idx_realtime_updates_target_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_updates_target_user ON public.realtime_status_updates USING btree (target_user_id);


--
-- Name: idx_realtime_updatestatus; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_realtime_updatestatus ON public.realtime_status_updates USING btree (delivery_status);


--
-- Name: idx_routing_experiment_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routing_experiment_time ON public.ab_query_routing USING btree (experiment_id, routing_decision_at);


--
-- Name: idx_routing_session_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routing_session_time ON public.ab_query_routing USING btree (session_id, routing_decision_at);


--
-- Name: idx_routing_user_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routing_user_time ON public.ab_query_routing USING btree (user_id, routing_decision_at);


--
-- Name: idx_routing_variant_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_routing_variant_time ON public.ab_query_routing USING btree (variant_id, routing_decision_at);


--
-- Name: idx_search_events_org_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_search_events_org_time ON public.search_events USING btree (organization_id, created_at);


--
-- Name: idx_search_events_query; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_search_events_query ON public.search_events USING btree (query);


--
-- Name: idx_search_events_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_search_events_session ON public.search_events USING btree (session_id);


--
-- Name: idx_search_events_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_search_events_user ON public.search_events USING btree (user_id);


--
-- Name: idx_search_sessions_org_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_search_sessions_org_user ON public.search_sessions USING btree (organization_id, user_id);


--
-- Name: idx_search_sessions_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_search_sessions_session_id ON public.search_sessions USING btree (session_id);


--
-- Name: idx_search_sessions_start_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_search_sessions_start_time ON public.search_sessions USING btree (start_time);


--
-- Name: idx_security_incidents_org_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_security_incidents_org_status ON public.security_incidents USING btree (organization_id, status);


--
-- Name: idx_segment_memberships_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_segment_memberships_active ON public.ab_user_segment_memberships USING btree (segment_id, is_active);


--
-- Name: idx_segment_memberships_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_segment_memberships_user ON public.ab_user_segment_memberships USING btree (user_id, is_active);


--
-- Name: idx_segments_org_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_segments_org_type ON public.ab_user_segments USING btree (organization_id, segment_type);


--
-- Name: idx_status_updates_connection_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_status_updates_connection_type ON public.status_updates USING btree (connection_id, update_type);


--
-- Name: idx_status_updates_expires; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_status_updates_expires ON public.status_updates USING btree (expires_at);


--
-- Name: idx_status_updates_priority_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_status_updates_priority_created ON public.status_updates USING btree (priority, created_at);


--
-- Name: idx_status_updates_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_status_updates_status ON public.status_updates USING btree (delivery_status);


--
-- Name: idx_system_broadcasts_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_broadcasts_active ON public.system_status_broadcasts USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_system_broadcasts_audience; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_broadcasts_audience ON public.system_status_broadcasts USING btree (target_audience);


--
-- Name: idx_system_broadcasts_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_broadcasts_severity ON public.system_status_broadcasts USING btree (severity);


--
-- Name: idx_system_broadcasts_time_range; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_broadcasts_time_range ON public.system_status_broadcasts USING btree (start_time, end_time);


--
-- Name: idx_system_broadcasts_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_broadcasts_type ON public.system_status_broadcasts USING btree (broadcast_type);


--
-- Name: idx_system_metrics_component_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_metrics_component_time ON public.system_metrics USING btree (component_name, measured_at);


--
-- Name: idx_system_metrics_name_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_metrics_name_time ON public.system_metrics USING btree (metric_name, measured_at);


--
-- Name: idx_system_metrics_org_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_system_metrics_org_time ON public.system_metrics USING btree (organization_id, measured_at);


--
-- Name: idx_threads_source_project; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_threads_source_project ON public.threads USING btree (source_project_id);


--
-- Name: idx_user_sessions_active_sessions; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_active_sessions ON public.user_sessions USING btree (user_id, status, last_activity);


--
-- Name: idx_user_sessions_last_activity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_last_activity ON public.user_sessions USING btree (last_activity);


--
-- Name: idx_user_sessions_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_organization_id ON public.user_sessions USING btree (organization_id);


--
-- Name: idx_user_sessions_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_session_id ON public.user_sessions USING btree (session_id);


--
-- Name: idx_user_sessions_started_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_started_at ON public.user_sessions USING btree (started_at);


--
-- Name: idx_user_sessions_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_status ON public.user_sessions USING btree (status);


--
-- Name: idx_user_sessions_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_user_id ON public.user_sessions USING btree (user_id);


--
-- Name: idx_user_sessions_user_org; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_sessions_user_org ON public.user_sessions USING btree (user_id, organization_id);


--
-- Name: idx_user_subscriptions_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_subscriptions_active ON public.user_realtime_subscriptions USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_user_subscriptions_last_notification; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_subscriptions_last_notification ON public.user_realtime_subscriptions USING btree (last_notification_at DESC);


--
-- Name: idx_user_subscriptions_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_subscriptions_type ON public.user_realtime_subscriptions USING btree (subscription_type);


--
-- Name: idx_user_subscriptions_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_subscriptions_user ON public.user_realtime_subscriptions USING btree (user_id);


--
-- Name: idx_variants_experiment_control; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variants_experiment_control ON public.ab_variants USING btree (experiment_id, is_control);


--
-- Name: idx_variants_experiment_participants; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_variants_experiment_participants ON public.ab_variants USING btree (experiment_id, participant_count);


--
-- Name: idx_websocket_connections_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_websocket_connections_active ON public.websocket_connections USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_websocket_connections_channels_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_websocket_connections_channels_gin ON public.websocket_connections USING gin (subscription_channels);


--
-- Name: idx_websocket_connections_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_websocket_connections_created_at ON public.websocket_connections USING btree (created_at DESC);


--
-- Name: idx_websocket_connections_last_activity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_websocket_connections_last_activity ON public.websocket_connections USING btree (last_activity DESC);


--
-- Name: idx_websocket_connections_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_websocket_connections_session_id ON public.websocket_connections USING btree (session_id);


--
-- Name: idx_websocket_connections_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_websocket_connections_user_id ON public.websocket_connections USING btree (user_id);


--
-- Name: ix_ab_assignments_assigned_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_assignments_assigned_at ON public.ab_assignments USING btree (assigned_at);


--
-- Name: ix_ab_assignments_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_assignments_experiment_id ON public.ab_assignments USING btree (experiment_id);


--
-- Name: ix_ab_assignments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_assignments_id ON public.ab_assignments USING btree (id);


--
-- Name: ix_ab_assignments_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_assignments_session_id ON public.ab_assignments USING btree (session_id);


--
-- Name: ix_ab_assignments_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_assignments_user_id ON public.ab_assignments USING btree (user_id);


--
-- Name: ix_ab_assignments_variant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_assignments_variant_id ON public.ab_assignments USING btree (variant_id);


--
-- Name: ix_ab_experiment_metrics_date_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_date_day ON public.ab_experiment_metrics USING btree (date_day);


--
-- Name: ix_ab_experiment_metrics_date_hour; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_date_hour ON public.ab_experiment_metrics USING btree (date_hour);


--
-- Name: ix_ab_experiment_metrics_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_experiment_id ON public.ab_experiment_metrics USING btree (experiment_id);


--
-- Name: ix_ab_experiment_metrics_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_id ON public.ab_experiment_metrics USING btree (id);


--
-- Name: ix_ab_experiment_metrics_metric_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_metric_type ON public.ab_experiment_metrics USING btree (metric_type);


--
-- Name: ix_ab_experiment_metrics_query_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_query_id ON public.ab_experiment_metrics USING btree (query_id);


--
-- Name: ix_ab_experiment_metrics_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_session_id ON public.ab_experiment_metrics USING btree (session_id);


--
-- Name: ix_ab_experiment_metrics_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_timestamp ON public.ab_experiment_metrics USING btree ("timestamp");


--
-- Name: ix_ab_experiment_metrics_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_user_id ON public.ab_experiment_metrics USING btree (user_id);


--
-- Name: ix_ab_experiment_metrics_variant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_metrics_variant_id ON public.ab_experiment_metrics USING btree (variant_id);


--
-- Name: ix_ab_experiment_segments_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_segments_experiment_id ON public.ab_experiment_segments USING btree (experiment_id);


--
-- Name: ix_ab_experiment_segments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_segments_id ON public.ab_experiment_segments USING btree (id);


--
-- Name: ix_ab_experiment_segments_segment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiment_segments_segment_id ON public.ab_experiment_segments USING btree (segment_id);


--
-- Name: ix_ab_experiments_end_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiments_end_time ON public.ab_experiments USING btree (end_time);


--
-- Name: ix_ab_experiments_experiment_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiments_experiment_type ON public.ab_experiments USING btree (experiment_type);


--
-- Name: ix_ab_experiments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiments_id ON public.ab_experiments USING btree (id);


--
-- Name: ix_ab_experiments_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiments_name ON public.ab_experiments USING btree (name);


--
-- Name: ix_ab_experiments_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiments_organization_id ON public.ab_experiments USING btree (organization_id);


--
-- Name: ix_ab_experiments_primary_metric; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiments_primary_metric ON public.ab_experiments USING btree (primary_metric);


--
-- Name: ix_ab_experiments_start_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiments_start_time ON public.ab_experiments USING btree (start_time);


--
-- Name: ix_ab_experiments_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_experiments_status ON public.ab_experiments USING btree (status);


--
-- Name: ix_ab_query_routing_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_query_routing_experiment_id ON public.ab_query_routing USING btree (experiment_id);


--
-- Name: ix_ab_query_routing_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_query_routing_id ON public.ab_query_routing USING btree (id);


--
-- Name: ix_ab_query_routing_query_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_ab_query_routing_query_id ON public.ab_query_routing USING btree (query_id);


--
-- Name: ix_ab_query_routing_routing_decision_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_query_routing_routing_decision_at ON public.ab_query_routing USING btree (routing_decision_at);


--
-- Name: ix_ab_query_routing_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_query_routing_session_id ON public.ab_query_routing USING btree (session_id);


--
-- Name: ix_ab_query_routing_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_query_routing_user_id ON public.ab_query_routing USING btree (user_id);


--
-- Name: ix_ab_query_routing_variant_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_query_routing_variant_id ON public.ab_query_routing USING btree (variant_id);


--
-- Name: ix_ab_user_segment_memberships_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_user_segment_memberships_id ON public.ab_user_segment_memberships USING btree (id);


--
-- Name: ix_ab_user_segment_memberships_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_user_segment_memberships_is_active ON public.ab_user_segment_memberships USING btree (is_active);


--
-- Name: ix_ab_user_segment_memberships_segment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_user_segment_memberships_segment_id ON public.ab_user_segment_memberships USING btree (segment_id);


--
-- Name: ix_ab_user_segment_memberships_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_user_segment_memberships_user_id ON public.ab_user_segment_memberships USING btree (user_id);


--
-- Name: ix_ab_user_segments_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_user_segments_id ON public.ab_user_segments USING btree (id);


--
-- Name: ix_ab_user_segments_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_user_segments_name ON public.ab_user_segments USING btree (name);


--
-- Name: ix_ab_user_segments_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_user_segments_organization_id ON public.ab_user_segments USING btree (organization_id);


--
-- Name: ix_ab_user_segments_segment_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_user_segments_segment_type ON public.ab_user_segments USING btree (segment_type);


--
-- Name: ix_ab_variants_experiment_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_variants_experiment_id ON public.ab_variants USING btree (experiment_id);


--
-- Name: ix_ab_variants_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_variants_id ON public.ab_variants USING btree (id);


--
-- Name: ix_ab_variants_is_control; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_variants_is_control ON public.ab_variants USING btree (is_control);


--
-- Name: ix_ab_variants_participant_count; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_variants_participant_count ON public.ab_variants USING btree (participant_count);


--
-- Name: ix_ab_variants_primary_metric_value; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ab_variants_primary_metric_value ON public.ab_variants USING btree (primary_metric_value);


--
-- Name: ix_analytics_events_batch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_batch_id ON public.analytics_events USING btree (batch_id);


--
-- Name: ix_analytics_events_date_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_date_day ON public.analytics_events USING btree (date_day);


--
-- Name: ix_analytics_events_date_hour; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_date_hour ON public.analytics_events USING btree (date_hour);


--
-- Name: ix_analytics_events_event_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_event_category ON public.analytics_events USING btree (event_category);


--
-- Name: ix_analytics_events_event_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_event_name ON public.analytics_events USING btree (event_name);


--
-- Name: ix_analytics_events_event_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_event_timestamp ON public.analytics_events USING btree (event_timestamp);


--
-- Name: ix_analytics_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_event_type ON public.analytics_events USING btree (event_type);


--
-- Name: ix_analytics_events_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_organization_id ON public.analytics_events USING btree (organization_id);


--
-- Name: ix_analytics_events_processed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_processed ON public.analytics_events USING btree (processed);


--
-- Name: ix_analytics_events_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_session_id ON public.analytics_events USING btree (session_id);


--
-- Name: ix_analytics_events_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_analytics_events_user_id ON public.analytics_events USING btree (user_id);


--
-- Name: ix_audit_events_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_created_at ON public.audit_events USING btree (created_at);


--
-- Name: ix_audit_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_event_type ON public.audit_events USING btree (event_type);


--
-- Name: ix_audit_events_ip_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_ip_address ON public.audit_events USING btree (ip_address);


--
-- Name: ix_audit_events_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_organization_id ON public.audit_events USING btree (organization_id);


--
-- Name: ix_audit_events_resource_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_resource_id ON public.audit_events USING btree (resource_id);


--
-- Name: ix_audit_events_resource_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_resource_type ON public.audit_events USING btree (resource_type);


--
-- Name: ix_audit_events_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_session_id ON public.audit_events USING btree (session_id);


--
-- Name: ix_audit_events_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_severity ON public.audit_events USING btree (severity);


--
-- Name: ix_audit_events_success; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_success ON public.audit_events USING btree (success);


--
-- Name: ix_audit_events_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_user_id ON public.audit_events USING btree (user_id);


--
-- Name: ix_chat_messages_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_messages_role ON public.chat_messages USING btree (role);


--
-- Name: ix_chat_messages_thread_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_messages_thread_created ON public.chat_messages USING btree (thread_id, created_at);


--
-- Name: ix_chat_messages_thread_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_chat_messages_thread_id ON public.chat_messages USING btree (thread_id);


--
-- Name: ix_citation_relationships_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citation_relationships_id ON public.citation_relationships USING btree (id);


--
-- Name: ix_citation_relationships_source_citation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citation_relationships_source_citation_id ON public.citation_relationships USING btree (source_citation_id);


--
-- Name: ix_citation_relationships_target_citation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citation_relationships_target_citation_id ON public.citation_relationships USING btree (target_citation_id);


--
-- Name: ix_citations_arxiv_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_citations_arxiv_id ON public.citations USING btree (arxiv_id) WHERE (arxiv_id IS NOT NULL);


--
-- Name: ix_citations_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citations_document_id ON public.citations USING btree (document_id);


--
-- Name: ix_citations_doi; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_citations_doi ON public.citations USING btree (doi) WHERE (doi IS NOT NULL);


--
-- Name: ix_citations_external_reference_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citations_external_reference_id ON public.citations USING btree (external_reference_id);


--
-- Name: ix_citations_message_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_citations_message_id ON public.citations USING btree (message_id);


--
-- Name: ix_collection_documents_collection_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_collection_documents_collection_id ON public.collection_documents USING btree (collection_id);


--
-- Name: ix_collection_documents_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_collection_documents_document_id ON public.collection_documents USING btree (document_id);


--
-- Name: ix_collections_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_collections_name ON public.collections USING btree (name);


--
-- Name: ix_collections_research_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_collections_research_status ON public.collections USING btree (research_status);


--
-- Name: ix_collections_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_collections_workspace_id ON public.collections USING btree (workspace_id);


--
-- Name: ix_compliance_reports_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compliance_reports_organization_id ON public.compliance_reports USING btree (organization_id);


--
-- Name: ix_compliance_reports_period_end; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compliance_reports_period_end ON public.compliance_reports USING btree (period_end);


--
-- Name: ix_compliance_reports_period_start; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compliance_reports_period_start ON public.compliance_reports USING btree (period_start);


--
-- Name: ix_compliance_reports_report_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compliance_reports_report_type ON public.compliance_reports USING btree (report_type);


--
-- Name: ix_compliance_reports_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_compliance_reports_status ON public.compliance_reports USING btree (status);


--
-- Name: ix_connection_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_connection_events_id ON public.connection_events USING btree (id);


--
-- Name: ix_conversations_last_activity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversations_last_activity ON public.conversations USING btree (last_activity_at);


--
-- Name: ix_conversations_title; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversations_title ON public.conversations USING btree (title);


--
-- Name: ix_conversations_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_conversations_workspace_id ON public.conversations USING btree (workspace_id);


--
-- Name: ix_data_retention_policies_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_data_retention_policies_is_active ON public.data_retention_policies USING btree (is_active);


--
-- Name: ix_data_retention_policies_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_data_retention_policies_organization_id ON public.data_retention_policies USING btree (organization_id);


--
-- Name: ix_data_retention_policies_policy_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_data_retention_policies_policy_type ON public.data_retention_policies USING btree (policy_type);


--
-- Name: ix_document_access_log_access_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_access_log_access_type ON public.document_access_log USING btree (access_type);


--
-- Name: ix_document_access_log_api_key_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_access_log_api_key_id ON public.document_access_log USING btree (api_key_id);


--
-- Name: ix_document_access_log_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_access_log_document_id ON public.document_access_log USING btree (document_id);


--
-- Name: ix_document_access_log_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_access_log_id ON public.document_access_log USING btree (id);


--
-- Name: ix_document_access_log_ip_address; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_access_log_ip_address ON public.document_access_log USING btree (ip_address);


--
-- Name: ix_document_access_log_is_suspicious; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_access_log_is_suspicious ON public.document_access_log USING btree (is_suspicious);


--
-- Name: ix_document_access_log_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_access_log_session_id ON public.document_access_log USING btree (session_id);


--
-- Name: ix_document_quality_metrics_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_quality_metrics_content_id ON public.document_quality_metrics USING btree (content_id);


--
-- Name: ix_document_quality_metrics_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_quality_metrics_document_id ON public.document_quality_metrics USING btree (document_id);


--
-- Name: ix_document_quality_metrics_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_quality_metrics_id ON public.document_quality_metrics USING btree (id);


--
-- Name: ix_document_quality_metrics_meets_threshold; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_quality_metrics_meets_threshold ON public.document_quality_metrics USING btree (meets_threshold);


--
-- Name: ix_document_quality_metrics_metric_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_quality_metrics_metric_type ON public.document_quality_metrics USING btree (metric_type);


--
-- Name: ix_document_versions_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_versions_document_id ON public.document_versions USING btree (document_id);


--
-- Name: ix_document_versions_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_document_versions_id ON public.document_versions USING btree (id);


--
-- Name: ix_documents_document_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_document_type ON public.documents USING btree (document_type);


--
-- Name: ix_documents_embedding_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_embedding_id ON public.documents USING btree (embedding_id);


--
-- Name: ix_documents_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_id ON public.documents USING btree (id);


--
-- Name: ix_documents_title; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_documents_title ON public.documents USING btree (title);


--
-- Name: ix_draft_citations_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_draft_citations_document_id ON public.draft_citations USING btree (document_id);


--
-- Name: ix_draft_citations_draft_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_draft_citations_draft_id ON public.draft_citations USING btree (draft_id);


--
-- Name: ix_draft_citations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_draft_citations_id ON public.draft_citations USING btree (id);


--
-- Name: ix_entities_canonical_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entities_canonical_name ON public.entities USING btree (canonical_name);


--
-- Name: ix_entities_entity_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entities_entity_type ON public.entities USING btree (entity_type);


--
-- Name: ix_entities_graph_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entities_graph_id ON public.entities USING btree (graph_id);


--
-- Name: ix_entities_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entities_id ON public.entities USING btree (id);


--
-- Name: ix_entities_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entities_name ON public.entities USING btree (name);


--
-- Name: ix_evaluation_comparisons_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_comparisons_id ON public.evaluation_comparisons USING btree (id);


--
-- Name: ix_evaluation_comparisons_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_comparisons_organization_id ON public.evaluation_comparisons USING btree (organization_id);


--
-- Name: ix_evaluation_comparisons_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_comparisons_user_id ON public.evaluation_comparisons USING btree (user_id);


--
-- Name: ix_evaluation_datasets_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_datasets_id ON public.evaluation_datasets USING btree (id);


--
-- Name: ix_evaluation_datasets_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_datasets_job_id ON public.evaluation_datasets USING btree (job_id);


--
-- Name: ix_evaluation_jobs_evaluation_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_jobs_evaluation_type ON public.evaluation_jobs USING btree (evaluation_type);


--
-- Name: ix_evaluation_jobs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_jobs_id ON public.evaluation_jobs USING btree (id);


--
-- Name: ix_evaluation_jobs_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_jobs_name ON public.evaluation_jobs USING btree (name);


--
-- Name: ix_evaluation_jobs_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_jobs_organization_id ON public.evaluation_jobs USING btree (organization_id);


--
-- Name: ix_evaluation_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_jobs_status ON public.evaluation_jobs USING btree (status);


--
-- Name: ix_evaluation_jobs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_jobs_user_id ON public.evaluation_jobs USING btree (user_id);


--
-- Name: ix_evaluation_metrics_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_metrics_id ON public.evaluation_metrics USING btree (id);


--
-- Name: ix_evaluation_metrics_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_metrics_job_id ON public.evaluation_metrics USING btree (job_id);


--
-- Name: ix_evaluation_metrics_metric_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_metrics_metric_type ON public.evaluation_metrics USING btree (metric_type);


--
-- Name: ix_evaluation_reports_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_reports_id ON public.evaluation_reports USING btree (id);


--
-- Name: ix_evaluation_reports_job_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_reports_job_id ON public.evaluation_reports USING btree (job_id);


--
-- Name: ix_evaluation_reports_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_reports_organization_id ON public.evaluation_reports USING btree (organization_id);


--
-- Name: ix_evaluation_reports_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_reports_user_id ON public.evaluation_reports USING btree (user_id);


--
-- Name: ix_evaluation_thresholds_document_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_thresholds_document_type ON public.evaluation_thresholds USING btree (document_type);


--
-- Name: ix_evaluation_thresholds_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_thresholds_id ON public.evaluation_thresholds USING btree (id);


--
-- Name: ix_evaluation_thresholds_is_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_thresholds_is_enabled ON public.evaluation_thresholds USING btree (is_enabled);


--
-- Name: ix_evaluation_thresholds_metric_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_thresholds_metric_type ON public.evaluation_thresholds USING btree (metric_type);


--
-- Name: ix_evaluation_thresholds_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_thresholds_organization_id ON public.evaluation_thresholds USING btree (organization_id);


--
-- Name: ix_evaluation_thresholds_search_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evaluation_thresholds_search_type ON public.evaluation_thresholds USING btree (search_type);


--
-- Name: ix_extraction_cells_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_extraction_cells_document_id ON public.extraction_cells USING btree (document_id);


--
-- Name: ix_extraction_cells_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_extraction_cells_id ON public.extraction_cells USING btree (id);


--
-- Name: ix_extraction_cells_matrix_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_extraction_cells_matrix_id ON public.extraction_cells USING btree (matrix_id);


--
-- Name: ix_extraction_matrices_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_extraction_matrices_id ON public.extraction_matrices USING btree (id);


--
-- Name: ix_extraction_matrices_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_extraction_matrices_project_id ON public.extraction_matrices USING btree (project_id);


--
-- Name: ix_generated_drafts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_generated_drafts_id ON public.generated_drafts USING btree (id);


--
-- Name: ix_generated_drafts_is_current; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_generated_drafts_is_current ON public.generated_drafts USING btree (is_current);


--
-- Name: ix_generated_drafts_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_generated_drafts_project_id ON public.generated_drafts USING btree (project_id);


--
-- Name: ix_integrity_scores_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integrity_scores_document_id ON public.integrity_scores USING btree (document_id);


--
-- Name: ix_integrity_scores_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_integrity_scores_id ON public.integrity_scores USING btree (id);


--
-- Name: ix_message_attachments_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_message_attachments_document_id ON public.message_attachments USING btree (document_id);


--
-- Name: ix_message_attachments_message_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_message_attachments_message_id ON public.message_attachments USING btree (message_id);


--
-- Name: ix_multimodal_content_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_multimodal_content_content_id ON public.multimodal_content USING btree (content_id);


--
-- Name: ix_multimodal_content_content_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_multimodal_content_content_type ON public.multimodal_content USING btree (content_type);


--
-- Name: ix_multimodal_content_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_multimodal_content_document_id ON public.multimodal_content USING btree (document_id);


--
-- Name: ix_multimodal_content_embedding_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_multimodal_content_embedding_id ON public.multimodal_content USING btree (embedding_id);


--
-- Name: ix_multimodal_content_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_multimodal_content_id ON public.multimodal_content USING btree (id);


--
-- Name: ix_notification_templates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notification_templates_id ON public.notification_templates USING btree (id);


--
-- Name: ix_notification_templates_template_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_notification_templates_template_name ON public.notification_templates USING btree (template_name);


--
-- Name: ix_organizations_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_organizations_id ON public.organizations USING btree (id);


--
-- Name: ix_organizations_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_organizations_name ON public.organizations USING btree (name);


--
-- Name: ix_performance_logs_alert_triggered; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_alert_triggered ON public.performance_logs USING btree (alert_triggered);


--
-- Name: ix_performance_logs_batch_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_batch_id ON public.performance_logs USING btree (batch_id);


--
-- Name: ix_performance_logs_component; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_component ON public.performance_logs USING btree (component);


--
-- Name: ix_performance_logs_date_day; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_date_day ON public.performance_logs USING btree (date_day);


--
-- Name: ix_performance_logs_date_hour; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_date_hour ON public.performance_logs USING btree (date_hour);


--
-- Name: ix_performance_logs_metric_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_metric_category ON public.performance_logs USING btree (metric_category);


--
-- Name: ix_performance_logs_metric_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_metric_name ON public.performance_logs USING btree (metric_name);


--
-- Name: ix_performance_logs_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_organization_id ON public.performance_logs USING btree (organization_id);


--
-- Name: ix_performance_logs_performance_level; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_performance_level ON public.performance_logs USING btree (performance_level);


--
-- Name: ix_performance_logs_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_performance_logs_timestamp ON public.performance_logs USING btree ("timestamp");


--
-- Name: ix_permissions_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_permissions_category ON public.permissions USING btree (category);


--
-- Name: ix_permissions_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_permissions_name ON public.permissions USING btree (name);


--
-- Name: ix_permissions_resource; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_permissions_resource ON public.permissions USING btree (resource);


--
-- Name: ix_permissions_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_permissions_scope ON public.permissions USING btree (scope);


--
-- Name: ix_processing_history_document_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_processing_history_document_id ON public.processing_history USING btree (document_id);


--
-- Name: ix_processing_history_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_processing_history_id ON public.processing_history USING btree (id);


--
-- Name: ix_processing_history_stage; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_processing_history_stage ON public.processing_history USING btree (stage);


--
-- Name: ix_processing_jobs_celery_task_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_processing_jobs_celery_task_id ON public.processing_jobs USING btree (celery_task_id);


--
-- Name: ix_processing_jobs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_processing_jobs_id ON public.processing_jobs USING btree (id);


--
-- Name: ix_processing_jobs_job_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_processing_jobs_job_type ON public.processing_jobs USING btree (job_type);


--
-- Name: ix_processing_jobs_priority; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_processing_jobs_priority ON public.processing_jobs USING btree (priority);


--
-- Name: ix_processing_jobs_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_processing_jobs_status ON public.processing_jobs USING btree (status);


--
-- Name: ix_project_notes_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_notes_id ON public.project_notes USING btree (id);


--
-- Name: ix_project_notes_is_pinned; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_notes_is_pinned ON public.project_notes USING btree (is_pinned);


--
-- Name: ix_project_notes_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_notes_project_id ON public.project_notes USING btree (project_id);


--
-- Name: ix_project_notes_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_notes_user_id ON public.project_notes USING btree (user_id);


--
-- Name: ix_project_threads_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_threads_id ON public.project_threads USING btree (id);


--
-- Name: ix_project_threads_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_threads_project_id ON public.project_threads USING btree (project_id);


--
-- Name: ix_project_threads_thread_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_project_threads_thread_id ON public.project_threads USING btree (thread_id);


--
-- Name: ix_quality_metrics_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quality_metrics_id ON public.quality_metrics USING btree (id);


--
-- Name: ix_quality_metrics_metric_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quality_metrics_metric_name ON public.quality_metrics USING btree (metric_name);


--
-- Name: ix_quality_metrics_metric_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quality_metrics_metric_type ON public.quality_metrics USING btree (metric_type);


--
-- Name: ix_quality_metrics_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quality_metrics_scope ON public.quality_metrics USING btree (scope);


--
-- Name: ix_quality_metrics_scope_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_quality_metrics_scope_id ON public.quality_metrics USING btree (scope_id);


--
-- Name: ix_research_blueprints_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_research_blueprints_id ON public.research_blueprints USING btree (id);


--
-- Name: ix_research_evidence_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_research_evidence_id ON public.research_evidence USING btree (id);


--
-- Name: ix_research_pipelines_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_research_pipelines_id ON public.research_pipelines USING btree (id);


--
-- Name: ix_research_pipelines_project_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_research_pipelines_project_id ON public.research_pipelines USING btree (project_id);


--
-- Name: ix_research_projects_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_research_projects_id ON public.research_projects USING btree (id);


--
-- Name: ix_research_runs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_research_runs_id ON public.research_runs USING btree (id);


--
-- Name: ix_research_sources_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_research_sources_id ON public.research_sources USING btree (id);


--
-- Name: ix_research_steps_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_research_steps_id ON public.research_steps USING btree (id);


--
-- Name: ix_roles_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_roles_name ON public.roles USING btree (name);


--
-- Name: ix_roles_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_roles_organization_id ON public.roles USING btree (organization_id);


--
-- Name: ix_search_queries_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_search_queries_id ON public.search_queries USING btree (id);


--
-- Name: ix_search_queries_search_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_search_queries_search_type ON public.search_queries USING btree (search_type);


--
-- Name: ix_search_queries_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_search_queries_session_id ON public.search_queries USING btree (session_id);


--
-- Name: ix_search_results_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_search_results_id ON public.search_results USING btree (id);


--
-- Name: ix_search_results_relevance_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_search_results_relevance_score ON public.search_results USING btree (relevance_score);


--
-- Name: ix_security_incidents_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_security_incidents_category ON public.security_incidents USING btree (category);


--
-- Name: ix_security_incidents_detected_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_security_incidents_detected_at ON public.security_incidents USING btree (detected_at);


--
-- Name: ix_security_incidents_incident_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_security_incidents_incident_id ON public.security_incidents USING btree (incident_id);


--
-- Name: ix_security_incidents_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_security_incidents_organization_id ON public.security_incidents USING btree (organization_id);


--
-- Name: ix_security_incidents_severity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_security_incidents_severity ON public.security_incidents USING btree (severity);


--
-- Name: ix_security_incidents_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_security_incidents_status ON public.security_incidents USING btree (status);


--
-- Name: ix_stance_classifications_claim_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_stance_classifications_claim_hash ON public.stance_classifications USING btree (claim_hash);


--
-- Name: ix_stance_classifications_source_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_stance_classifications_source_id ON public.stance_classifications USING btree (source_id);


--
-- Name: ix_status_updates_connection_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_status_updates_connection_id ON public.status_updates USING btree (connection_id);


--
-- Name: ix_status_updates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_status_updates_id ON public.status_updates USING btree (id);


--
-- Name: ix_status_updates_priority; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_status_updates_priority ON public.status_updates USING btree (priority);


--
-- Name: ix_status_updates_update_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_status_updates_update_id ON public.status_updates USING btree (update_id);


--
-- Name: ix_status_updates_update_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_status_updates_update_type ON public.status_updates USING btree (update_type);


--
-- Name: ix_threads_conversation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_threads_conversation_id ON public.threads USING btree (conversation_id);


--
-- Name: ix_threads_last_message_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_threads_last_message_at ON public.threads USING btree (last_message_at);


--
-- Name: ix_threads_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_threads_status ON public.threads USING btree (status);


--
-- Name: ix_user_role_assignments_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_role_assignments_organization_id ON public.user_role_assignments USING btree (organization_id);


--
-- Name: ix_user_role_assignments_role_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_role_assignments_role_id ON public.user_role_assignments USING btree (role_id);


--
-- Name: ix_user_role_assignments_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_user_role_assignments_user_id ON public.user_role_assignments USING btree (user_id);


--
-- Name: ix_user_sessions_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_user_sessions_session_id ON public.user_sessions USING btree (session_id);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_id ON public.users USING btree (id);


--
-- Name: ix_workspace_members_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_members_user_id ON public.workspace_members USING btree (user_id);


--
-- Name: ix_workspace_members_workspace_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspace_members_workspace_id ON public.workspace_members USING btree (workspace_id);


--
-- Name: ix_workspaces_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspaces_name ON public.workspaces USING btree (name);


--
-- Name: ix_workspaces_organization_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspaces_organization_id ON public.workspaces USING btree (organization_id);


--
-- Name: ix_workspaces_owner_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_workspaces_owner_id ON public.workspaces USING btree (owner_id);


--
-- Name: documents update_documents_last_status_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER update_documents_last_status_update BEFORE UPDATE ON public.documents FOR EACH ROW EXECUTE FUNCTION public.update_last_status_update();


--
-- Name: ab_assignments ab_assignments_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_assignments
    ADD CONSTRAINT ab_assignments_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.ab_experiments(id);


--
-- Name: ab_assignments ab_assignments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_assignments
    ADD CONSTRAINT ab_assignments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ab_assignments ab_assignments_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_assignments
    ADD CONSTRAINT ab_assignments_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.ab_variants(id);


--
-- Name: ab_experiment_metrics ab_experiment_metrics_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiment_metrics
    ADD CONSTRAINT ab_experiment_metrics_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.ab_experiments(id);


--
-- Name: ab_experiment_metrics ab_experiment_metrics_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiment_metrics
    ADD CONSTRAINT ab_experiment_metrics_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ab_experiment_metrics ab_experiment_metrics_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiment_metrics
    ADD CONSTRAINT ab_experiment_metrics_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.ab_variants(id);


--
-- Name: ab_experiment_segments ab_experiment_segments_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiment_segments
    ADD CONSTRAINT ab_experiment_segments_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.ab_experiments(id);


--
-- Name: ab_experiment_segments ab_experiment_segments_segment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiment_segments
    ADD CONSTRAINT ab_experiment_segments_segment_id_fkey FOREIGN KEY (segment_id) REFERENCES public.ab_user_segments(id);


--
-- Name: ab_experiments ab_experiments_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiments
    ADD CONSTRAINT ab_experiments_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: ab_experiments ab_experiments_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiments
    ADD CONSTRAINT ab_experiments_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: ab_experiments ab_experiments_winning_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_experiments
    ADD CONSTRAINT ab_experiments_winning_variant_id_fkey FOREIGN KEY (winning_variant_id) REFERENCES public.ab_variants(id);


--
-- Name: ab_query_routing ab_query_routing_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_query_routing
    ADD CONSTRAINT ab_query_routing_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.ab_experiments(id);


--
-- Name: ab_query_routing ab_query_routing_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_query_routing
    ADD CONSTRAINT ab_query_routing_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ab_query_routing ab_query_routing_variant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_query_routing
    ADD CONSTRAINT ab_query_routing_variant_id_fkey FOREIGN KEY (variant_id) REFERENCES public.ab_variants(id);


--
-- Name: ab_user_segment_memberships ab_user_segment_memberships_segment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_user_segment_memberships
    ADD CONSTRAINT ab_user_segment_memberships_segment_id_fkey FOREIGN KEY (segment_id) REFERENCES public.ab_user_segments(id);


--
-- Name: ab_user_segment_memberships ab_user_segment_memberships_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_user_segment_memberships
    ADD CONSTRAINT ab_user_segment_memberships_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: ab_user_segments ab_user_segments_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_user_segments
    ADD CONSTRAINT ab_user_segments_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: ab_user_segments ab_user_segments_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_user_segments
    ADD CONSTRAINT ab_user_segments_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: ab_variants ab_variants_experiment_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ab_variants
    ADD CONSTRAINT ab_variants_experiment_id_fkey FOREIGN KEY (experiment_id) REFERENCES public.ab_experiments(id);


--
-- Name: analytics_events analytics_events_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analytics_events
    ADD CONSTRAINT analytics_events_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: analytics_events analytics_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.analytics_events
    ADD CONSTRAINT analytics_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: audit_events audit_events_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: audit_events audit_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: chat_messages chat_messages_thread_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.threads(id) ON DELETE CASCADE;


--
-- Name: chat_messages chat_messages_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: citation_relationships citation_relationships_source_citation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citation_relationships
    ADD CONSTRAINT citation_relationships_source_citation_id_fkey FOREIGN KEY (source_citation_id) REFERENCES public.citations(id) ON DELETE CASCADE;


--
-- Name: citation_relationships citation_relationships_target_citation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citation_relationships
    ADD CONSTRAINT citation_relationships_target_citation_id_fkey FOREIGN KEY (target_citation_id) REFERENCES public.citations(id) ON DELETE CASCADE;


--
-- Name: citations citations_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citations
    ADD CONSTRAINT citations_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: citations citations_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.citations
    ADD CONSTRAINT citations_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.chat_messages(id) ON DELETE CASCADE;


--
-- Name: collection_documents collection_documents_collection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collection_documents
    ADD CONSTRAINT collection_documents_collection_id_fkey FOREIGN KEY (collection_id) REFERENCES public.collections(id) ON DELETE CASCADE;


--
-- Name: collection_documents collection_documents_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collection_documents
    ADD CONSTRAINT collection_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: collections collections_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.collections
    ADD CONSTRAINT collections_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: compliance_reports compliance_reports_generated_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_reports
    ADD CONSTRAINT compliance_reports_generated_by_fkey FOREIGN KEY (generated_by) REFERENCES public.users(id);


--
-- Name: compliance_reports compliance_reports_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.compliance_reports
    ADD CONSTRAINT compliance_reports_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: connection_events connection_events_connection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.connection_events
    ADD CONSTRAINT connection_events_connection_id_fkey FOREIGN KEY (connection_id) REFERENCES public.websocket_connections(id);


--
-- Name: conversations conversations_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.users(id);


--
-- Name: conversations conversations_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: data_retention_policies data_retention_policies_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.data_retention_policies
    ADD CONSTRAINT data_retention_policies_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: document_access_log document_access_log_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_access_log
    ADD CONSTRAINT document_access_log_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: document_access_log document_access_log_document_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_access_log
    ADD CONSTRAINT document_access_log_document_version_id_fkey FOREIGN KEY (document_version_id) REFERENCES public.document_versions(id);


--
-- Name: document_access_log document_access_log_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_access_log
    ADD CONSTRAINT document_access_log_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: document_access_log document_access_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_access_log
    ADD CONSTRAINT document_access_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: document_processing_stages document_processing_stages_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_processing_stages
    ADD CONSTRAINT document_processing_stages_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: document_quality_metrics document_quality_metrics_assessed_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_quality_metrics
    ADD CONSTRAINT document_quality_metrics_assessed_by_user_id_fkey FOREIGN KEY (assessed_by_user_id) REFERENCES public.users(id);


--
-- Name: document_quality_metrics document_quality_metrics_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_quality_metrics
    ADD CONSTRAINT document_quality_metrics_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: document_quality_metrics document_quality_metrics_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_quality_metrics
    ADD CONSTRAINT document_quality_metrics_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: document_versions document_versions_created_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT document_versions_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES public.users(id);


--
-- Name: document_versions document_versions_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT document_versions_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: document_versions document_versions_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT document_versions_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: document_versions document_versions_parent_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT document_versions_parent_version_id_fkey FOREIGN KEY (parent_version_id) REFERENCES public.document_versions(id);


--
-- Name: documents documents_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: documents documents_uploaded_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_uploaded_by_user_id_fkey FOREIGN KEY (uploaded_by_user_id) REFERENCES public.users(id);


--
-- Name: draft_citations draft_citations_citation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.draft_citations
    ADD CONSTRAINT draft_citations_citation_id_fkey FOREIGN KEY (citation_id) REFERENCES public.citations(id) ON DELETE SET NULL;


--
-- Name: draft_citations draft_citations_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.draft_citations
    ADD CONSTRAINT draft_citations_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: draft_citations draft_citations_draft_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.draft_citations
    ADD CONSTRAINT draft_citations_draft_id_fkey FOREIGN KEY (draft_id) REFERENCES public.generated_drafts(id) ON DELETE CASCADE;


--
-- Name: encrypted_organization_profiles encrypted_organization_profiles_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_organization_profiles
    ADD CONSTRAINT encrypted_organization_profiles_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE;


--
-- Name: encrypted_user_profiles encrypted_user_profiles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encrypted_user_profiles
    ADD CONSTRAINT encrypted_user_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: encryption_audit_logs encryption_audit_logs_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encryption_audit_logs
    ADD CONSTRAINT encryption_audit_logs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: encryption_audit_logs encryption_audit_logs_performed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.encryption_audit_logs
    ADD CONSTRAINT encryption_audit_logs_performed_by_fkey FOREIGN KEY (performed_by) REFERENCES public.users(id);


--
-- Name: entities entities_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT entities_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: entities entities_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT entities_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: entity_relationships entity_relationships_source_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_relationships
    ADD CONSTRAINT entity_relationships_source_entity_id_fkey FOREIGN KEY (source_entity_id) REFERENCES public.entities(id);


--
-- Name: entity_relationships entity_relationships_target_entity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_relationships
    ADD CONSTRAINT entity_relationships_target_entity_id_fkey FOREIGN KEY (target_entity_id) REFERENCES public.entities(id);


--
-- Name: evaluation_comparisons evaluation_comparisons_baseline_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_comparisons
    ADD CONSTRAINT evaluation_comparisons_baseline_job_id_fkey FOREIGN KEY (baseline_job_id) REFERENCES public.evaluation_jobs(id);


--
-- Name: evaluation_comparisons evaluation_comparisons_comparison_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_comparisons
    ADD CONSTRAINT evaluation_comparisons_comparison_job_id_fkey FOREIGN KEY (comparison_job_id) REFERENCES public.evaluation_jobs(id);


--
-- Name: evaluation_comparisons evaluation_comparisons_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_comparisons
    ADD CONSTRAINT evaluation_comparisons_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: evaluation_comparisons evaluation_comparisons_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_comparisons
    ADD CONSTRAINT evaluation_comparisons_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: evaluation_datasets evaluation_datasets_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_datasets
    ADD CONSTRAINT evaluation_datasets_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.evaluation_jobs(id);


--
-- Name: evaluation_jobs evaluation_jobs_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_jobs
    ADD CONSTRAINT evaluation_jobs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: evaluation_jobs evaluation_jobs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_jobs
    ADD CONSTRAINT evaluation_jobs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: evaluation_metrics evaluation_metrics_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_metrics
    ADD CONSTRAINT evaluation_metrics_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.evaluation_jobs(id);


--
-- Name: evaluation_reports evaluation_reports_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_reports
    ADD CONSTRAINT evaluation_reports_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.evaluation_jobs(id);


--
-- Name: evaluation_reports evaluation_reports_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_reports
    ADD CONSTRAINT evaluation_reports_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: evaluation_reports evaluation_reports_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_reports
    ADD CONSTRAINT evaluation_reports_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: evaluation_thresholds evaluation_thresholds_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evaluation_thresholds
    ADD CONSTRAINT evaluation_thresholds_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: extraction_cells extraction_cells_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_cells
    ADD CONSTRAINT extraction_cells_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: extraction_cells extraction_cells_matrix_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_cells
    ADD CONSTRAINT extraction_cells_matrix_id_fkey FOREIGN KEY (matrix_id) REFERENCES public.extraction_matrices(id) ON DELETE CASCADE;


--
-- Name: extraction_matrices extraction_matrices_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.extraction_matrices
    ADD CONSTRAINT extraction_matrices_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.collections(id) ON DELETE CASCADE;


--
-- Name: generated_drafts generated_drafts_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.generated_drafts
    ADD CONSTRAINT generated_drafts_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.collections(id) ON DELETE CASCADE;


--
-- Name: integrity_scores integrity_scores_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.integrity_scores
    ADD CONSTRAINT integrity_scores_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: message_attachments message_attachments_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_attachments
    ADD CONSTRAINT message_attachments_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: message_attachments message_attachments_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.message_attachments
    ADD CONSTRAINT message_attachments_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.chat_messages(id) ON DELETE CASCADE;


--
-- Name: metric_aggregations metric_aggregations_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metric_aggregations
    ADD CONSTRAINT metric_aggregations_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: multimodal_content multimodal_content_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.multimodal_content
    ADD CONSTRAINT multimodal_content_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: multimodal_content multimodal_content_document_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.multimodal_content
    ADD CONSTRAINT multimodal_content_document_version_id_fkey FOREIGN KEY (document_version_id) REFERENCES public.document_versions(id);


--
-- Name: multimodal_content multimodal_content_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.multimodal_content
    ADD CONSTRAINT multimodal_content_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: performance_logs performance_logs_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.performance_logs
    ADD CONSTRAINT performance_logs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: processing_history processing_history_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_history
    ADD CONSTRAINT processing_history_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: processing_history processing_history_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_history
    ADD CONSTRAINT processing_history_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: processing_jobs processing_jobs_created_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_jobs
    ADD CONSTRAINT processing_jobs_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES public.users(id);


--
-- Name: processing_jobs processing_jobs_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_jobs
    ADD CONSTRAINT processing_jobs_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: processing_jobs processing_jobs_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processing_jobs
    ADD CONSTRAINT processing_jobs_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: project_notes project_notes_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_notes
    ADD CONSTRAINT project_notes_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.collections(id) ON DELETE CASCADE;


--
-- Name: project_notes project_notes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_notes
    ADD CONSTRAINT project_notes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: project_threads project_threads_linked_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_threads
    ADD CONSTRAINT project_threads_linked_by_id_fkey FOREIGN KEY (linked_by_id) REFERENCES public.users(id);


--
-- Name: project_threads project_threads_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_threads
    ADD CONSTRAINT project_threads_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.collections(id) ON DELETE CASCADE;


--
-- Name: project_threads project_threads_thread_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.project_threads
    ADD CONSTRAINT project_threads_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.threads(id) ON DELETE CASCADE;


--
-- Name: quality_alerts quality_alerts_acknowledged_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_alerts
    ADD CONSTRAINT quality_alerts_acknowledged_by_fkey FOREIGN KEY (acknowledged_by) REFERENCES public.users(id);


--
-- Name: quality_alerts quality_alerts_metric_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_alerts
    ADD CONSTRAINT quality_alerts_metric_id_fkey FOREIGN KEY (metric_id) REFERENCES public.quality_metrics(id);


--
-- Name: quality_alerts quality_alerts_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_alerts
    ADD CONSTRAINT quality_alerts_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: quality_alerts quality_alerts_resolved_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_alerts
    ADD CONSTRAINT quality_alerts_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.users(id);


--
-- Name: quality_metrics quality_metrics_created_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_metrics
    ADD CONSTRAINT quality_metrics_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES public.users(id);


--
-- Name: quality_metrics quality_metrics_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_metrics
    ADD CONSTRAINT quality_metrics_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: quality_thresholds quality_thresholds_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_thresholds
    ADD CONSTRAINT quality_thresholds_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: quality_thresholds quality_thresholds_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.quality_thresholds
    ADD CONSTRAINT quality_thresholds_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: realtime_performance_metrics realtime_performance_metrics_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.realtime_performance_metrics
    ADD CONSTRAINT realtime_performance_metrics_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE SET NULL;


--
-- Name: realtime_performance_metrics realtime_performance_metrics_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.realtime_performance_metrics
    ADD CONSTRAINT realtime_performance_metrics_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: realtime_status_updates realtime_status_updates_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.realtime_status_updates
    ADD CONSTRAINT realtime_status_updates_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: realtime_status_updates realtime_status_updates_target_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.realtime_status_updates
    ADD CONSTRAINT realtime_status_updates_target_user_id_fkey FOREIGN KEY (target_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: research_blueprints research_blueprints_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_blueprints
    ADD CONSTRAINT research_blueprints_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.research_projects(id);


--
-- Name: research_evidence research_evidence_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_evidence
    ADD CONSTRAINT research_evidence_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.research_sources(id);


--
-- Name: research_evidence research_evidence_step_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_evidence
    ADD CONSTRAINT research_evidence_step_id_fkey FOREIGN KEY (step_id) REFERENCES public.research_steps(id);


--
-- Name: research_pipelines research_pipelines_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_pipelines
    ADD CONSTRAINT research_pipelines_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.collections(id) ON DELETE CASCADE;


--
-- Name: research_projects research_projects_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_projects
    ADD CONSTRAINT research_projects_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id);


--
-- Name: research_runs research_runs_blueprint_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_runs
    ADD CONSTRAINT research_runs_blueprint_id_fkey FOREIGN KEY (blueprint_id) REFERENCES public.research_blueprints(id);


--
-- Name: research_sources research_sources_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_sources
    ADD CONSTRAINT research_sources_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.research_runs(id);


--
-- Name: research_steps research_steps_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.research_steps
    ADD CONSTRAINT research_steps_run_id_fkey FOREIGN KEY (run_id) REFERENCES public.research_runs(id);


--
-- Name: role_permissions role_permissions_granted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_granted_by_fkey FOREIGN KEY (granted_by) REFERENCES public.users(id);


--
-- Name: role_permissions role_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id);


--
-- Name: role_permissions role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: roles roles_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: search_events search_events_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_events
    ADD CONSTRAINT search_events_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: search_events search_events_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_events
    ADD CONSTRAINT search_events_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.search_sessions(id);


--
-- Name: search_events search_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_events
    ADD CONSTRAINT search_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: search_queries search_queries_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_queries
    ADD CONSTRAINT search_queries_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: search_queries search_queries_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_queries
    ADD CONSTRAINT search_queries_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: search_results search_results_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_results
    ADD CONSTRAINT search_results_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: search_results search_results_search_query_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_results
    ADD CONSTRAINT search_results_search_query_id_fkey FOREIGN KEY (search_query_id) REFERENCES public.search_queries(id);


--
-- Name: search_sessions search_sessions_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_sessions
    ADD CONSTRAINT search_sessions_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: search_sessions search_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.search_sessions
    ADD CONSTRAINT search_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: security_incidents security_incidents_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_incidents
    ADD CONSTRAINT security_incidents_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.users(id);


--
-- Name: security_incidents security_incidents_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.security_incidents
    ADD CONSTRAINT security_incidents_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: status_updates status_updates_connection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.status_updates
    ADD CONSTRAINT status_updates_connection_id_fkey FOREIGN KEY (connection_id) REFERENCES public.websocket_connections(id);


--
-- Name: system_metrics system_metrics_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_metrics
    ADD CONSTRAINT system_metrics_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: system_status_broadcasts system_status_broadcasts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.system_status_broadcasts
    ADD CONSTRAINT system_status_broadcasts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: threads threads_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threads
    ADD CONSTRAINT threads_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: threads threads_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threads
    ADD CONSTRAINT threads_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public.users(id);


--
-- Name: threads threads_source_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.threads
    ADD CONSTRAINT threads_source_project_id_fkey FOREIGN KEY (source_project_id) REFERENCES public.collections(id) ON DELETE SET NULL;


--
-- Name: user_realtime_subscriptions user_realtime_subscriptions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_realtime_subscriptions
    ADD CONSTRAINT user_realtime_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: user_role_assignments user_role_assignments_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_role_assignments
    ADD CONSTRAINT user_role_assignments_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.users(id);


--
-- Name: user_role_assignments user_role_assignments_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_role_assignments
    ADD CONSTRAINT user_role_assignments_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: user_role_assignments user_role_assignments_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_role_assignments
    ADD CONSTRAINT user_role_assignments_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id);


--
-- Name: user_role_assignments user_role_assignments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_role_assignments
    ADD CONSTRAINT user_role_assignments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: user_sessions user_sessions_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: user_sessions user_sessions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_sessions
    ADD CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: users users_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: websocket_connections websocket_connections_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.websocket_connections
    ADD CONSTRAINT websocket_connections_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: workspace_members workspace_members_invited_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_invited_by_id_fkey FOREIGN KEY (invited_by_id) REFERENCES public.users(id);


--
-- Name: workspace_members workspace_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: workspace_members workspace_members_workspace_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspace_members
    ADD CONSTRAINT workspace_members_workspace_id_fkey FOREIGN KEY (workspace_id) REFERENCES public.workspaces(id) ON DELETE CASCADE;


--
-- Name: workspaces workspaces_organization_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_organization_id_fkey FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: workspaces workspaces_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.workspaces
    ADD CONSTRAINT workspaces_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id);


--
-- Name: document_processing_stages; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.document_processing_stages ENABLE ROW LEVEL SECURITY;

--
-- Name: realtime_performance_metrics; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.realtime_performance_metrics ENABLE ROW LEVEL SECURITY;

--
-- Name: realtime_status_updates; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.realtime_status_updates ENABLE ROW LEVEL SECURITY;

--
-- Name: user_realtime_subscriptions; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.user_realtime_subscriptions ENABLE ROW LEVEL SECURITY;

--
-- Name: websocket_connections; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.websocket_connections ENABLE ROW LEVEL SECURITY;

--
-- PostgreSQL database dump complete
--

