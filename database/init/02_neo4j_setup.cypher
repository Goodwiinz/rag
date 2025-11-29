// Multimodal Enterprise RAG System - Neo4j Knowledge Graph Setup
// This script sets up the Neo4j database with constraints, indexes, and sample data

// =================================================================
// CONSTRAINTS FOR DATA INTEGRITY
// =================================================================

// Entity uniqueness constraints
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;
CREATE CONSTRAINT organization_id_unique IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE;
CREATE CONSTRAINT session_id_unique IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE;

// Name uniqueness within organization
CREATE CONSTRAINT entity_name_org_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.organization_id) IS NODE KEY;
CREATE CONSTRAINT document_title_org_unique IF NOT EXISTS FOR (d:Document) REQUIRE (d.title, d.organization_id) IS NODE KEY;

// =================================================================
// INDEXES FOR PERFORMANCE OPTIMIZATION
// =================================================================

// Entity indexes
CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type);
CREATE INDEX entity_canonical_name_index IF NOT EXISTS FOR (e:Entity) ON (e.canonical_name);
CREATE INDEX entity_organization_index IF NOT EXISTS FOR (e:Entity) ON (e.organization_id);
CREATE INDEX entity_confidence_index IF NOT EXISTS FOR (e:Entity) ON (e.confidence_score);
CREATE INDEX entity_created_index IF NOT EXISTS FOR (e:Entity) ON (e.created_at);

// Document indexes
CREATE INDEX document_title_index IF NOT EXISTS FOR (d:Document) ON (d.title);
CREATE INDEX document_type_index IF NOT EXISTS FOR (d:Document) ON (d.type);
CREATE INDEX document_organization_index IF NOT EXISTS FOR (d:Document) ON (d.organization_id);
CREATE INDEX document_created_index IF NOT EXISTS FOR (d:Document) ON (d.created_at);
CREATE INDEX document_status_index IF NOT EXISTS FOR (d:Document) ON (d.processing_status);

// User indexes
CREATE INDEX user_email_index IF NOT EXISTS FOR (u:User) ON (u.email);
CREATE INDEX user_organization_index IF NOT EXISTS FOR (u:User) ON (u.organization_id);
CREATE INDEX user_role_index IF NOT EXISTS FOR (u:User) ON (u.role);

// Relationship indexes
CREATE INDEX relationship_type_index IF NOT EXISTS FOR ()-[r]-() ON (type(r));
CREATE INDEX relationship_strength_index IF NOT EXISTS FOR ()-[r]-() ON (r.strength);
CREATE INDEX relationship_created_index IF NOT EXISTS FOR ()-[r]-() ON (r.created_at);

// =================================================================
// FULL-TEXT SEARCH INDEXES
// =================================================================

// Entity content search
CREATE FULLTEXT INDEX entity_content_index IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.description, e.aliases];

// Document content search
CREATE FULLTEXT INDEX document_content_index IF NOT EXISTS FOR (d:Document) ON EACH [d.title, d.content_text, d.summary];

// Multi-modal content search
CREATE FULLTEXT INDEX multimodal_content_index IF NOT EXISTS FOR (m:MultimodalContent) ON EACH [m.content_text, m.description];

// =================================================================
// COMPOSITE INDEXES FOR COMMON QUERY PATTERNS
// =================================================================

// Entity by type and organization
CREATE INDEX entity_type_organization_index IF NOT EXISTS FOR (e:Entity) ON (e.type, e.organization_id);

// Document by type and organization
CREATE INDEX document_type_organization_index IF NOT EXISTS FOR (d:Document) ON (d.type, d.organization_id);

// Entity relationships by type and strength
CREATE INDEX relationship_type_strength_index IF NOT EXISTS FOR ()-[r:RELATED_TO|PART_OF|LOCATED_IN|WORKS_FOR|MENTIONS]-() ON (type(r), r.strength);

// =================================================================
// SAMPLE DATA SETUP (for development and testing)
// =================================================================

// Create sample organization
MERGE (o:Organization {
    id: '550e8400-e29b-41d4-a716-446655440001',
    name: 'Demo Organization',
    slug: 'demo-org',
    description: 'A demonstration organization for the RAG system',
    created_at: datetime(),
    updated_at: datetime()
});

// Create sample users
MERGE (u1:User {
    id: '550e8400-e29b-41d4-a716-446655440002',
    email: 'admin@demo.com',
    first_name: 'Admin',
    last_name: 'User',
    role: 'admin',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    created_at: datetime(),
    updated_at: datetime()
});

MERGE (u2:User {
    id: '550e8400-e29b-41d4-a716-446655440003',
    email: 'analyst@demo.com',
    first_name: 'Data',
    last_name: 'Analyst',
    role: 'analyst',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    created_at: datetime(),
    updated_at: datetime()
});

// Connect users to organization
MERGE (u1)-[:MEMBER_OF {role: 'admin', joined_at: datetime()}]->(o);
MERGE (u2)-[:MEMBER_OF {role: 'analyst', joined_at: datetime()}]->(o);

// Create sample documents
MERGE (d1:Document {
    id: '550e8400-e29b-41d4-a716-446655440004',
    title: 'AI and Machine Learning Trends 2024',
    type: 'pdf',
    content_text: 'Artificial Intelligence and Machine Learning continue to evolve rapidly in 2024...',
    summary: 'An overview of the latest AI and ML trends for 2024',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    uploaded_by: '550e8400-e29b-41d4-a716-446655440002',
    created_at: datetime(),
    updated_at: datetime()
});

MERGE (d2:Document {
    id: '550e8400-e29b-41d4-a716-446655440005',
    title: 'Cloud Infrastructure Best Practices',
    type: 'document',
    content_text: 'Cloud infrastructure requires careful planning and optimization...',
    summary: 'Best practices for designing and managing cloud infrastructure',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    uploaded_by: '550e8400-e29b-41d4-a716-446655440003',
    created_at: datetime(),
    updated_at: datetime()
});

// Connect documents to organization and users
MERGE (d1)-[:BELONGS_TO {added_at: datetime()}]->(o);
MERGE (d2)-[:BELONGS_TO {added_at: datetime()}]->(o);
MERGE (u1)-[:UPLOADED {uploaded_at: datetime()}]->(d1);
MERGE (u2)-[:UPLOADED {uploaded_at: datetime()}]->(d2);

// Create sample entities
MERGE (e1:Entity {
    id: '550e8400-e29b-41d4-a716-446655440006',
    name: 'Artificial Intelligence',
    canonical_name: 'Artificial Intelligence',
    type: 'concept',
    description: 'The simulation of human intelligence in machines',
    confidence_score: 0.95,
    source_document_id: '550e8400-e29b-41d4-a716-446655440004',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    created_at: datetime(),
    updated_at: datetime()
});

MERGE (e2:Entity {
    id: '550e8400-e29b-41d4-a716-446655440007',
    name: 'Machine Learning',
    canonical_name: 'Machine Learning',
    type: 'concept',
    description: 'A subset of AI that enables systems to learn from data',
    confidence_score: 0.92,
    source_document_id: '550e8400-e29b-41d4-a716-446655440004',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    created_at: datetime(),
    updated_at: datetime()
});

MERGE (e3:Entity {
    id: '550e8400-e29b-41d4-a716-446655440008',
    name: 'Cloud Computing',
    canonical_name: 'Cloud Computing',
    type: 'concept',
    description: 'The delivery of computing services over the internet',
    confidence_score: 0.88,
    source_document_id: '550e8400-e29b-41d4-a716-446655440005',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    created_at: datetime(),
    updated_at: datetime()
});

MERGE (e4:Entity {
    id: '550e8400-e29b-41d4-a716-446655440009',
    name: 'Amazon Web Services',
    canonical_name: 'Amazon Web Services',
    type: 'organization',
    aliases: ['AWS', 'Amazon Cloud'],
    description: 'A subsidiary of Amazon providing on-demand cloud computing platforms',
    confidence_score: 0.96,
    source_document_id: '550e8400-e29b-41d4-a716-446655440005',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    created_at: datetime(),
    updated_at: datetime()
});

// Connect entities to documents
MERGE (e1)-[:EXTRACTED_FROM {confidence: 0.95, extraction_method: 'ner'}]->(d1);
MERGE (e2)-[:EXTRACTED_FROM {confidence: 0.92, extraction_method: 'ner'}]->(d1);
MERGE (e3)-[:EXTRACTED_FROM {confidence: 0.88, extraction_method: 'ner'}]->(d2);
MERGE (e4)-[:EXTRACTED_FROM {confidence: 0.96, extraction_method: 'ner'}]->(d2);

// Create entity relationships
MERGE (e1)-[:RELATED_TO {
    type: 'subset',
    strength: 0.9,
    description: 'Machine Learning is a subset of Artificial Intelligence',
    created_at: datetime()
}]->(e2);

MERGE (e3)-[:RELATED_TO {
    type: 'example',
    strength: 0.8,
    description: 'Amazon Web Services is an example of Cloud Computing',
    created_at: datetime()
}]->(e4);

// Create sample multimodal content nodes
MERGE (m1:MultimodalContent {
    id: '550e8400-e29b-41d4-a716-446655440010',
    content_type: 'image',
    content_text: 'AI architecture diagram showing neural networks and data flow',
    description: 'Diagram showing the architecture of a modern AI system',
    confidence_score: 0.85,
    document_id: '550e8400-e29b-41d4-a716-446655440004',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    created_at: datetime()
});

MERGE (m2:MultimodalContent {
    id: '550e8400-e29b-41d4-a716-446655440011',
    content_type: 'table',
    content_text: 'Comparison table of cloud service providers and their features',
    description: 'Table comparing AWS, Azure, and Google Cloud features',
    confidence_score: 0.90,
    document_id: '550e8400-e29b-41d4-a716-446655440005',
    organization_id: '550e8400-e29b-41d4-a716-446655440001',
    created_at: datetime()
});

// Connect multimodal content to documents
MERGE (m1)-[:PART_OF {modality: 'image', extraction_method: 'ocr'}]->(d1);
MERGE (m2)-[:PART_OF {modality: 'table', extraction_method: 'table_extraction'}]->(d2);

// =================================================================
// PROCEDURES FOR COMMON OPERATIONS
// =================================================================

// Procedure to find related entities
CREATE OR REPLACE PROCEDURE findRelatedEntities(
    entityId STRING,
    maxDepth INTEGER = 2,
    minStrength FLOAT = 0.5
)
YIELD relatedEntity, relationship, path, depth
CALL {
    MATCH path = (start:Entity {id: entityId})-[*1..maxDepth]-(related:Entity)
    WHERE all(r IN relationships(path) WHERE r.strength >= minStrength)
    RETURN related, last(relationships(path)) AS relationship, path, length(path) AS depth
    ORDER BY depth, relationship.strength DESC
    LIMIT 50
}
RETURN relatedEntity, relationship, path, depth;

// Procedure to search entities by text
CREATE OR REPLACE PROCEDURE searchEntitiesByType(
    searchText STRING,
    entityType STRING = '',
    orgId STRING = '',
    limit INTEGER = 20
)
YIELD entity, score
CALL {
    WITH searchText, entityType, orgId, limit
    CALL db.index.fulltext.queryNodes('entity_content_index', searchText) YIELD node, score
    WITH node, score
    WHERE (entityType = '' OR node.type = entityType)
    AND (orgId = '' OR node.organization_id = orgId)
    RETURN node AS entity, score
    ORDER BY score DESC
    LIMIT limit
}
RETURN entity, score;

// Procedure to get document recommendations
CREATE OR REPLACE PROCEDURE getDocumentRecommendations(
    documentId STRING,
    orgId STRING,
    limit INTEGER = 10
)
YIELD recommendedDocument, similarityScore, commonEntities
CALL {
    WITH documentId, orgId, limit
    MATCH (doc:Document {id: documentId})-[:EXTRACTED_FROM]-(entities:Entity)
    MATCH (recommended:Document)-[:EXTRACTED_FROM]-(entities)
    WHERE recommended.id <> documentId
    AND recommended.organization_id = orgId
    WITH recommended, count(DISTINCT entities) AS commonEntities
    ORDER BY commonEntities DESC
    LIMIT limit
    RETURN recommended, commonEntities, (commonEntities * 1.0) AS similarityScore
}
RETURN recommendedDocument, similarityScore, commonEntities;

// Procedure to create or update entity
CREATE OR REPLACE PROCEDURE upsertEntity(
    entityId STRING,
    name STRING,
    entityType STRING,
    canonicalName STRING,
    description STRING,
    confidenceScore FLOAT,
    sourceDocumentId STRING,
    organizationId STRING,
    aliases LIST<STRING> = []
)
YIELD entity, created
MERGE (e:Entity {id: entityId})
ON CREATE SET
    e.name = name,
    e.type = entityType,
    e.canonical_name = canonicalName,
    e.description = description,
    e.confidence_score = confidenceScore,
    e.source_document_id = sourceDocumentId,
    e.organization_id = organizationId,
    e.aliases = aliases,
    e.created_at = datetime(),
    e.updated_at = datetime()
ON MATCH SET
    e.name = COALESCE(name, e.name),
    e.canonical_name = COALESCE(canonicalName, e.canonical_name),
    e.description = COALESCE(description, e.description),
    e.confidence_score = GREATEST(confidenceScore, e.confidence_score),
    e.aliases = CASE
        WHEN size(aliases) > 0 THEN aliases
        ELSE e.aliases
    END,
    e.updated_at = datetime()
RETURN e, created = (e.created_at = datetime());

// Procedure to create entity relationship
CREATE OR REPLACE PROCEDURE createEntityRelationship(
    sourceEntityId STRING,
    targetEntityId STRING,
    relationshipType STRING,
    strength FLOAT,
    description STRING,
    sourceDocumentId STRING
)
YIELD relationship, created
MATCH (source:Entity {id: sourceEntityId})
MATCH (target:Entity {id: targetEntityId})
MERGE (source)-[r:RELATED_TO]-(target)
ON CREATE SET
    r.type = relationshipType,
    r.strength = strength,
    r.description = description,
    r.source_document_id = sourceDocumentId,
    r.created_at = datetime()
ON MATCH SET
    r.strength = GREATEST(strength, r.strength),
    r.description = COALESCE(description, r.description),
    r.updated_at = datetime()
RETURN r, created = (r.created_at = datetime());

// =================================================================
// FUNCTIONS FOR GRAPH ANALYTICS
// =================================================================

// Function to calculate entity importance score
CREATE OR REPLACE FUNCTION calculateEntityImportance(entityId STRING)
RETURNS FLOAT
WITH 'gds' AS procedureName
YIELD gdsScore
CALL {
    WITH entityId
    MATCH (e:Entity {id: entityId})
    OPTIONAL MATCH (e)-[r1:RELATED_TO]-(related:Entity)
    OPTIONAL MATCH (e)-[r2:EXTRACTED_FROM]-(d:Document)
    RETURN
        // Degree centrality (number of connections)
        (count(DISTINCT related) * 0.3) +
        // Document relevance (number of documents)
        (count(DISTINCT d) * 0.2) +
        // Confidence score
        (e.confidence_score * 0.3) +
        // Relationship strength average
        (avg(r2.strength) * 0.2) AS importanceScore
}
RETURN importanceScore;

// Function to find shortest path between entities
CREATE OR REPLACE FUNCTION findEntityPath(sourceId STRING, targetId STRING)
RETURNS LIST<LIST<ANY>>
CALL {
    WITH sourceId, targetId
    MATCH path = shortestPath((start:Entity {id: sourceId})-[*]-(end:Entity {id: targetId}))
    RETURN [node IN nodes(path) | {
        id: node.id,
        name: node.name,
        type: node.type
    }] AS entityPath
}
RETURN entityPath;

// =================================================================
// TRIGGERS FOR AUTOMATIC UPDATES
// =================================================================

// Trigger to update entity timestamps
CREATE OR REPLACE TRIGGER updateEntityTimestamp
ON CREATE OR UPDATE OF Entity
SET (updated_at) = datetime();

// Trigger to update document timestamps
CREATE OR REPLACE TRIGGER updateDocumentTimestamp
ON CREATE OR UPDATE OF Document
SET (updated_at) = datetime();

// Trigger to update relationship timestamps
CREATE OR REPLACE TRIGGER updateRelationshipTimestamp
ON CREATE OR UPDATE OF RELATED_TO
SET (updated_at) = datetime();

// =================================================================
// STATISTICS AND MONITORING QUERIES
// =================================================================

// Query to get database statistics
CALL {
    // Entity statistics
    MATCH (e:Entity)
    WITH count(e) AS entityCount, count(DISTINCT e.type) AS entityTypes
    // Document statistics
    MATCH (d:Document)
    WITH entityCount, entityTypes, count(d) AS documentCount, count(DISTINCT d.type) AS documentTypes
    // Relationship statistics
    MATCH ()-[r]-()
    WITH entityCount, entityTypes, documentCount, documentTypes, count(r) AS relationshipCount, count(DISTINCT type(r)) AS relationshipTypes
    // Organization statistics
    MATCH (o:Organization)
    WITH entityCount, entityTypes, documentCount, documentTypes, relationshipCount, relationshipTypes, count(o) AS organizationCount
    RETURN {
        entities: entityCount,
        entityTypes: entityTypes,
        documents: documentCount,
        documentTypes: documentTypes,
        relationships: relationshipCount,
        relationshipTypes: relationshipTypes,
        organizations: organizationCount
    } AS stats
} YIELD stats
RETURN stats;

// =================================================================
// CLEANUP AND MAINTENANCE PROCEDURES
// =================================================================

// Procedure to clean up orphaned relationships
CREATE OR REPLACE PROCEDURE cleanupOrphanedRelationships()
CALL {
    MATCH ()-[r]-()
    WHERE NOT exists(startNode(r)) OR NOT exists(endNode(r))
    DELETE r
    RETURN count(r) AS deletedRelationships
}
YIELD deletedRelationships
RETURN deletedRelationships;

// Procedure to update entity importance scores
CREATE OR REPLACE PROCEDURE updateEntityImportanceScores()
CALL {
    MATCH (e:Entity)
    CALL gds.nodeSimilarity.stream('entitySimilarity') YIELD node1, node2, similarity
    WITH e, count(node2) AS similarNodes, avg(similarity) AS avgSimilarity
    SET e.importance_score = (similarNodes * avgSimilarity * e.confidence_score)
    RETURN count(e) AS updatedEntities
}
YIELD updatedEntities
RETURN updatedEntities;

// =================================================================
// COMPLETION MESSAGE
// =================================================================

RETURN '✅ Neo4j knowledge graph setup completed successfully!' AS message,
       '🔗 Constraints and indexes created',
       '📊 Sample data loaded',
       '⚡ Procedures and functions created',
       '🔍 Full-text search enabled',
       '📈 Graph analytics functions available';