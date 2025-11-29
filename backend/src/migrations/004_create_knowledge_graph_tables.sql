-- Migration 004: Create knowledge graph and entity extraction tables
-- Supports comprehensive entity extraction and relationship mapping

BEGIN;

-- Entities extracted from documents
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Entity information
    entity_type VARCHAR(100) NOT NULL, -- person, organization, location, concept, product, date, etc.
    entity_name VARCHAR(500) NOT NULL,
    canonical_name VARCHAR(500),
    aliases JSONB DEFAULT '[]',

    -- Extraction details
    extraction_method VARCHAR(100), -- spacy, openai, regex, manual, graph_extraction
    extraction_confidence DECIMAL(5,4) CHECK (extraction_confidence >= 0 AND extraction_confidence <= 1),
    extraction_model VARCHAR(100),

    -- Entity properties
    properties JSONB DEFAULT '{}',
    description TEXT,

    -- Graph integration
    graph_node_id VARCHAR(255), -- Neo4j node ID
    is_in_knowledge_graph BOOLEAN DEFAULT FALSE,

    -- Context
    text_span_start INTEGER,
    text_span_end INTEGER,
    context_window TEXT,

    -- Quality metrics
    relevance_score DECIMAL(5,4) DEFAULT 1.0,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Entity relationships
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Relationship information
    relationship_type VARCHAR(100) NOT NULL, -- works_for, located_in, related_to, part_of, etc.
    relationship_description TEXT,

    -- Confidence and relevance
    confidence DECIMAL(5,4) CHECK (confidence >= 0 AND confidence <= 1),
    relevance_score DECIMAL(5,4) DEFAULT 1.0,

    -- Graph integration
    graph_relationship_id VARCHAR(255), -- Neo4j relationship ID

    -- Source and context
    source_context TEXT,
    extraction_method VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT no_self_relationship CHECK (source_entity_id != target_entity_id),
    CONSTRAINT valid_confidence CHECK (confidence >= 0 AND confidence <= 1)
);

-- Concepts and topics for knowledge organization
CREATE TABLE concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Concept information
    name VARCHAR(255) NOT NULL,
    concept_type VARCHAR(100) NOT NULL, -- topic, category, domain, technology, methodology
    description TEXT,
    parent_concept_id UUID REFERENCES concepts(id),

    -- Hierarchy and structure
    level INTEGER DEFAULT 0,
    path TEXT[], -- Hierarchy path
    children JSONB DEFAULT '[]',

    -- Usage statistics
    document_frequency INTEGER DEFAULT 0,
    total_mentions INTEGER DEFAULT 0,
    avg_confidence DECIMAL(5,4),

    -- AI-generated content
    ai_summary TEXT,
    related_concepts JSONB DEFAULT '[]',

    -- Metadata
    is_system_generated BOOLEAN DEFAULT FALSE,
    created_by_user_id UUID REFERENCES users(id),
    verified_by_user_id UUID REFERENCES users(id),
    is_verified BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, name, concept_type)
);

-- Document-concept relationships
CREATE TABLE document_concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Relationship details
    relevance_score DECIMAL(5,4) CHECK (relevance_score >= 0 AND relevance_score <= 1),
    confidence DECIMAL(5,4) CHECK (confidence >= 0 AND confidence <= 1),

    -- Evidence and context
    evidence_snippets JSONB DEFAULT '[]',
    mention_count INTEGER DEFAULT 1,

    -- Extraction information
    extraction_method VARCHAR(100),
    extraction_model VARCHAR(100),

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(document_id, concept_id)
);

-- Entity canonicalization (merging duplicates)
CREATE TABLE entity_canonical_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Canonical entity information
    canonical_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    canonical_name VARCHAR(500) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,

    -- Merged entities (these will be soft-deleted)
    merged_entity_ids JSONB DEFAULT '[]',

    -- Merging metadata
    merge_confidence DECIMAL(5,4),
    merge_method VARCHAR(100), -- manual, automatic, ml_model
    merge_criteria JSONB DEFAULT '{}',

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    reviewed_by_user_id UUID REFERENCES users(id),
    reviewed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(organization_id, canonical_entity_id)
);

-- Knowledge graph analytics
CREATE TABLE knowledge_graph_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Graph metrics
    metric_type VARCHAR(100) NOT NULL, -- centrality, clustering, connectivity, etc.
    metric_name VARCHAR(255) NOT NULL,
    metric_value DECIMAL(15,6) NOT NULL,

    -- Entity context
    entity_id UUID REFERENCES entities(id),
    entity_type VARCHAR(100),
    concept_id UUID REFERENCES concepts(id),

    -- Calculation metadata
    calculation_method VARCHAR(100),
    calculation_date DATE,
    graph_version VARCHAR(50),

    -- Additional data
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Entity embeddings for semantic similarity
CREATE TABLE entity_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Embedding information
    embedding_model VARCHAR(100) NOT NULL,
    embedding_version VARCHAR(50),
    embedding_dimensions INTEGER NOT NULL,
    embedding_vector DECIMAL[] NOT NULL,

    -- Quality metrics
    embedding_quality_score DECIMAL(5,4),
    semantic_coherence DECIMAL(5,4),

    -- Usage
    similarity_calculated_at TIMESTAMPTZ,
    similar_entities JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(entity_id, embedding_model, embedding_version)
);

-- Create indexes for knowledge graph tables
CREATE INDEX idx_entities_document ON entities(document_id, entity_type);
CREATE INDEX idx_entities_organization ON entities(organization_id, entity_type);
CREATE INDEX idx_entities_name ON entities(entity_name, entity_type);
CREATE INDEX idx_entities_canonical ON entities(canonical_name, entity_type);
CREATE INDEX idx_entities_graph ON entities(graph_node_id) WHERE graph_node_id IS NOT NULL;
CREATE INDEX idx_entities_extraction ON entities(extraction_method, extraction_confidence DESC);
CREATE INDEX idx_entities_relevance ON entities(relevance_score DESC);
CREATE INDEX idx_entities_context ON entities USING GIN(to_tsvector('english', context_window));

CREATE INDEX idx_entity_relationships_source ON entity_relationships(source_entity_id, relationship_type);
CREATE INDEX idx_entity_relationships_target ON entity_relationships(target_entity_id, relationship_type);
CREATE INDEX idx_entity_relationships_org ON entity_relationships(organization_id, relationship_type);
CREATE INDEX idx_entity_relationships_graph ON entity_relationships(graph_relationship_id) WHERE graph_relationship_id IS NOT NULL;
CREATE INDEX idx_entity_relationships_confidence ON entity_relationships(confidence DESC);

CREATE INDEX idx_concepts_organization ON concepts(organization_id, concept_type);
CREATE INDEX idx_concepts_parent ON concepts(parent_concept_id, level);
CREATE INDEX idx_concepts_path ON concepts USING GIN(path);
CREATE INDEX idx_concepts_frequency ON concepts(document_frequency DESC);
CREATE INDEX idx_concepts_name_fts ON concepts USING GIN(to_tsvector('english', name || ' ' || COALESCE(description, '')));

CREATE INDEX idx_document_concepts_document ON document_concepts(document_id, relevance_score DESC);
CREATE INDEX idx_document_concepts_concept ON document_concepts(concept_id, relevance_score DESC);
CREATE INDEX idx_document_concepts_org ON document_concepts(organization_id, relevance_score DESC);

CREATE INDEX idx_entity_canonical_canonical ON entity_canonical_mapping(canonical_entity_id);
CREATE INDEX idx_entity_canonical_org ON entity_canonical_mapping(organization_id, is_active);
CREATE INDEX idx_entity_canonical_name ON entity_canonical_mapping(canonical_name, entity_type);

CREATE INDEX idx_kg_analytics_metric ON knowledge_graph_analytics(metric_type, metric_value DESC);
CREATE INDEX idx_kg_analytics_entity ON knowledge_graph_analytics(entity_id, metric_type);
CREATE INDEX idx_kg_analytics_concept ON knowledge_graph_analytics(concept_id, metric_type);
CREATE INDEX idx_kg_analytics_org ON knowledge_graph_analytics(organization_id, calculation_date DESC);

CREATE INDEX idx_entity_embeddings_entity ON entity_embeddings(entity_id);
CREATE INDEX idx_entity_embeddings_model ON entity_embeddings(embedding_model, embedding_version);
CREATE INDEX idx_entity_embeddings_quality ON entity_embeddings(embedding_quality_score DESC);

-- Enable Row Level Security
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_concepts ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_canonical_mapping ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_graph_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_embeddings ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for knowledge graph tables
CREATE POLICY entities_org_policy ON entities
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY entity_relationships_org_policy ON entity_relationships
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

CREATE POLICY concepts_org_policy ON concepts
    FOR ALL TO authenticated_users
    USING (organization_id = current_setting('app.current_organization_id', true)::UUID);

-- Triggers for automatic updates
CREATE OR REPLACE FUNCTION update_concept_usage()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Update concept usage statistics
        UPDATE concepts
        SET
            document_frequency = document_frequency + 1,
            total_mentions = total_mentions + NEW.mention_count,
            avg_confidence = CASE
                WHEN avg_confidence IS NULL THEN NEW.confidence
                ELSE ROUND((avg_confidence * document_frequency + NEW.confidence) / (document_frequency + 1), 4)
            END,
            updated_at = NOW()
        WHERE id = NEW.concept_id;

        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER concept_usage_trigger
    AFTER INSERT ON document_concepts
    FOR EACH ROW
    EXECUTE FUNCTION update_concept_usage();

CREATE OR REPLACE FUNCTION update_entity_graph_sync()
RETURNS TRIGGER AS $$
BEGIN
    -- Mark entity as needing graph synchronization
    UPDATE entities
    SET
        is_in_knowledge_graph = FALSE,
        updated_at = NOW()
    WHERE id = NEW.id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER entity_graph_sync_trigger
    AFTER INSERT OR UPDATE ON entities
    FOR EACH ROW
    WHEN (NEW.graph_node_id IS NULL OR NEW.graph_node_id != OLD.graph_node_id)
    EXECUTE FUNCTION update_entity_graph_sync();

-- Function for entity canonicalization
CREATE OR REPLACE FUNCTION canonicalize_entity(
    p_organization_id UUID,
    p_entity_type VARCHAR(100),
    p_entity_name VARCHAR(100)
) RETURNS UUID AS $$
DECLARE
    canonical_id UUID;
BEGIN
    -- Check if canonical mapping exists
    SELECT canonical_entity_id INTO canonical_id
    FROM entity_canonical_mapping
    WHERE organization_id = p_organization_id
      AND canonical_name = p_entity_name
      AND entity_type = p_entity_type
      AND is_active = TRUE;

    IF canonical_id IS NULL THEN
        -- Create new canonical entity
        canonical_id := gen_random_uuid();

        INSERT INTO entity_canonical_mapping (
            organization_id,
            canonical_entity_id,
            canonical_name,
            entity_type,
            is_active
        ) VALUES (
            p_organization_id,
            canonical_id,
            p_entity_name,
            p_entity_type,
            TRUE
        );
    END IF;

    RETURN canonical_id;
END;
$$ LANGUAGE plpgsql;

COMMIT;