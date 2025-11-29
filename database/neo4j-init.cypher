// Neo4j Initialization Script for Knowledge Graph
// This script initializes Neo4j for the Multimodal Enterprise RAG Knowledge Graph
// Run this after Neo4j starts to set up the graph database properly

// Enable required plugins and configure the database
CALL dbms.security.listUsers();

// Create constraints for data integrity
CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT text_content_id_unique IF NOT EXISTS FOR (t:TextContent) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT media_content_id_unique IF NOT EXISTS FOR (m:MediaContent) REQUIRE m.id IS UNIQUE;

// Create uniqueness constraints for relationships
CREATE CONSTRAINT mentions_rel_unique IF NOT EXISTS FOR ()-[r:MENTIONS]-() REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT contains_rel_unique IF NOT EXISTS FOR ()-[r:CONTAINS]-() REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT relates_to_rel_unique IF NOT EXISTS FOR ()-[r:RELATES_TO]-() REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT similar_to_rel_unique IF NOT EXISTS FOR ()-[r:SIMILAR_TO]-() REQUIRE r.id IS UNIQUE;

// Create indexes for performance
CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type);
CREATE INDEX entity_confidence_index IF NOT EXISTS FOR (e:Entity) ON (e.confidence);
CREATE INDEX entity_organization_index IF NOT EXISTS FOR (e:Entity) ON (e.organization_id);
CREATE INDEX entity_importance_index IF NOT EXISTS FOR (e:Entity) ON (e.importance_score);

CREATE INDEX document_title_index IF NOT EXISTS FOR (d:Document) ON (d.title);
CREATE INDEX document_type_index IF NOT EXISTS FOR (d:Document) ON (d.document_type);
CREATE INDEX document_organization_index IF NOT EXISTS FOR (d:Document) ON (d.organization_id);
CREATE INDEX document_created_index IF NOT EXISTS FOR (d:Document) ON (d.created_at);

CREATE INDEX text_content_document_index IF NOT EXISTS FOR (t:TextContent) ON (t.document_id);
CREATE INDEX media_content_document_index IF NOT EXISTS FOR (m:MediaContent) ON (m.document_id);

// Composite indexes for common query patterns
CREATE COMPOSITE INDEX entity_type_org_index IF NOT EXISTS FOR (e:Entity) ON (e.type, e.organization_id);
CREATE COMPOSITE INDEX entity_confidence_type_index IF NOT EXISTS FOR (e:Entity) ON (e.confidence, e.type);
CREATE COMPOSITE INDEX document_type_org_index IF NOT EXISTS FOR (d:Document) ON (d.document_type, d.organization_id);

// Full-text search indexes
CALL db.index.fulltext.createNodeIndex(
    "entityFulltext",
    ["Entity"],
    ["name", "description", "aliases", "canonical_name"]
);

CALL db.index.fulltext.createNodeIndex(
    "documentFulltext",
    ["Document"],
    ["title", "summary", "content_snippet"]
);

CALL db.index.fulltext.createNodeIndex(
    "contentFulltext",
    ["TextContent", "MediaContent"],
    ["content", "description", "transcript"]
);

// Create relationship property indexes
CREATE INDEX mentions_confidence_index IF NOT EXISTS FOR ()-[r:MENTIONS]-() ON (r.confidence);
CREATE INDEX mentions_strength_index IF NOT EXISTS FOR ()-[r:MENTIONS]-() ON (r.strength);
CREATE INDEX relates_to_confidence_index IF NOT EXISTS FOR ()-[r:RELATES_TO]-() ON (r.confidence);
CREATE INDEX relates_to_strength_index IF NOT EXISTS FOR ()-[r:RELATES_TO]-() ON (r.strength);

// Create specialized graph nodes for analytics
// Graph computation nodes for tracking algorithm results
CREATE CONSTRAINT graph_computation_id_unique IF NOT EXISTS FOR (gc:GraphComputation) REQUIRE gc.id IS UNIQUE;
CREATE INDEX graph_computation_org_index IF NOT EXISTS FOR (gc:GraphComputation) ON (gc.organization_id);
CREATE INDEX graph_computation_type_index IF NOT EXISTS FOR (gc:GraphComputation) ON (gc.computation_type);
CREATE INDEX graph_computation_status_index IF NOT EXISTS FOR (gc:GraphComputation) ON (gc.status);

// Community detection nodes
CREATE CONSTRAINT community_id_unique IF NOT EXISTS FOR (c:Community) REQUIRE c.id IS UNIQUE;
CREATE INDEX community_org_index IF NOT EXISTS FOR (c:Community) ON (c.organization_id);
CREATE INDEX community_algorithm_index IF NOT EXISTS FOR (c:Community) ON (c.algorithm);

// Graph snapshot nodes for temporal analysis
CREATE CONSTRAINT graph_snapshot_id_unique IF NOT EXISTS FOR (gs:GraphSnapshot) REQUIRE gs.id IS UNIQUE;
CREATE INDEX snapshot_org_index IF NOT EXISTS FOR (gs:GraphSnapshot) ON (gs.organization_id);
CREATE INDEX snapshot_timestamp_index IF NOT EXISTS FOR (gs:GraphSnapshot) ON (gs.timestamp);

// Create sample data structure for testing
// (Remove in production)
WITH "org123" AS default_org_id
MERGE (org:Organization {id: "org123", name: "Default Organization"})
ON CREATE SET org.created_at = timestamp(), org.updated_at = timestamp();

// Create sample entity types for validation
MERGE (person_type:EntityType {name: "Person"})
ON CREATE SET person_type.description = "Person entities like people, users, contacts";
MERGE (org_type:EntityType {name: "Organization"})
ON CREATE SET org_type.description = "Organization entities like companies, institutions";
MERGE (location_type:EntityType {name: "Location"})
ON CREATE SET location_type.description = "Location entities like places, addresses, coordinates";
MERGE (product_type:EntityType {name: "Product"})
ON CREATE SET product_type.description = "Product entities like items, services, offerings";
MERGE (concept_type:EntityType {name: "Concept"})
ON CREATE SET concept_type.description = "Abstract concepts, ideas, topics";

// Create relationship types for validation
MERGE (mentions_rel:RelationshipType {name: "MENTIONS"})
ON CREATE SET mentions_rel.description = "Document mentions an entity";
MERGE (relates_to_rel:RelationshipType {name: "RELATES_TO"})
ON CREATE SET relates_to_rel.description = "Entity is related to another entity";
MERGE (contains_rel:RelationshipType {name: "CONTAINS"})
ON CREATE SET contains_rel.description = "Document contains content";
MERGE (similar_to_rel:RelationshipType {name: "SIMILAR_TO"})
ON CREATE SET similar_to_rel.description = "Entities are similar to each other";

// Set up graph data science projections (if GDS plugin is available)
// These projections optimize graph algorithms for better performance

// Create a comprehensive graph projection for entity analysis
// Note: Uncomment when you have actual data
/*
CALL gds.graph.project(
    'knowledgeGraph',
    ['Entity', 'Document'],
    {
        MENTIONS: {
            orientation: 'UNDIRECTED',
            properties: ['confidence', 'strength']
        },
        RELATES_TO: {
            orientation: 'UNDIRECTED',
            properties: ['confidence', 'strength']
        },
        SIMILAR_TO: {
            orientation: 'UNDIRECTED',
            properties: ['similarity_score']
        }
    },
    {
        nodeProperties: ['confidence', 'importance_score', 'created_at']
    }
);

// Create a document-centric graph projection
CALL gds.graph.project(
    'documentGraph',
    ['Document'],
    {
        CONTAINS: {
            orientation: 'UNDIRECTED'
        },
        SIMILAR_TO: {
            orientation: 'UNDIRECTED',
            properties: ['similarity_score']
        }
    }
);
*/

// Create procedures for graph maintenance and analytics

// Procedure to get graph health metrics
CREATE OR REPLACE PROCEDURE getGraphHealthMetrics(
    IN orgId STRING
)
YIELD
    totalNodes INTEGER,
    totalEdges INTEGER,
    graphDensity FLOAT,
    connectedComponents INTEGER,
    averageClustering FLOAT,
    nodeTypes MAP,
    edgeTypes MAP
AS
BEGIN
    // Count nodes by type
    MATCH (n:Entity {organization_id: orgId})
    WITH count(n) AS entityCount
    MATCH (n:Document {organization_id: orgId})
    WITH entityCount, count(n) AS documentCount
    MATCH (n:TextContent)
    WITH entityCount, documentCount, count(n) AS textContentCount
    MATCH (n:MediaContent)
    WITH entityCount, documentCount, textContentCount, count(n) AS mediaContentCount

    // Count edges by type
    MATCH ()-[r:MENTIONS]-()
    WITH entityCount, documentCount, textContentCount, mediaContentCount, count(r) AS mentionsCount
    MATCH ()-[r:RELATES_TO]-()
    WITH entityCount, documentCount, textContentCount, mediaContentCount, mentionsCount, count(r) AS relatesToCount
    MATCH ()-[r:CONTAINS]-()
    WITH entityCount, documentCount, textContentCount, mediaContentCount, mentionsCount, relatesToCount, count(r) AS containsCount
    MATCH ()-[r:SIMILAR_TO]-()
    WITH entityCount, documentCount, textContentCount, mediaContentCount, mentionsCount, relatesToCount, containsCount, count(r) AS similarToCount

    // Calculate total counts
    WITH entityCount, documentCount, textContentCount, mediaContentCount,
         mentionsCount, relatesToCount, containsCount, similarToCount,
         entityCount + documentCount + textContentCount + mediaContentCount AS totalNodes,
         mentionsCount + relatesToCount + containsCount + similarToCount AS totalEdges

    // Calculate graph density
    WITH totalNodes, totalEdges,
         CASE WHEN totalNodes > 1 THEN (2.0 * totalEdges) / (totalNodes * (totalNodes - 1)) ELSE 0.0 END AS graphDensity,
         mentionsCount, relatesToCount, containsCount, similarToCount

    // Get connected components count (simplified)
    CALL {
        MATCH (n:Entity {organization_id: orgId})
        WITH collect(DISTINCT n) AS nodes
        RETURN length(nodes) AS connectedComponents
    }

    // Create result maps
    WITH totalNodes, totalEdges, graphDensity, connectedComponents,
         mentionsCount, relatesToCount, containsCount, similarToCount,
         {
             Entity: entityCount,
             Document: documentCount,
             TextContent: textContentCount,
             MediaContent: mediaContentCount
         } AS nodeTypes,
         {
             MENTIONS: mentionsCount,
             RELATES_TO: relatesToCount,
             CONTAINS: containsCount,
             SIMILAR_TO: similarToCount
         } AS edgeTypes

    // Return average clustering as placeholder (calculate properly if needed)
    RETURN totalNodes, totalEdges, graphDensity, connectedComponents, 0.0 AS averageClustering, nodeTypes, edgeTypes;
END;

// Procedure to find important entities (high centrality)
CREATE OR REPLACE PROCEDURE getImportantEntities(
    IN orgId STRING,
    IN limitCount INTEGER
)
YIELD
    entityId STRING,
    entityName STRING,
    entityType STRING,
    degree INTEGER,
    confidence FLOAT,
    importanceScore FLOAT
AS
BEGIN
    MATCH (e:Entity {organization_id: orgId})
    OPTIONAL MATCH (e)-[r]-(related)
    WITH e, count(r) AS degree
    WHERE degree > 0
    RETURN
        e.id AS entityId,
        e.name AS entityName,
        e.type AS entityType,
        degree,
        e.confidence AS confidence,
        COALESCE(e.importance_score, 0.0) AS importanceScore
    ORDER BY degree DESC, importanceScore DESC
    LIMIT limitCount;
END;

// Procedure to get entity neighborhoods
CREATE OR REPLACE PROCEDURE getEntityNeighborhood(
    IN entityId STRING,
    IN depth INTEGER,
    IN limitCount INTEGER
)
YIELD
    centerEntityId STRING,
    neighborEntityId STRING,
    neighborName STRING,
    neighborType STRING,
    relationshipType STRING,
    relationshipStrength FLOAT,
    distance INTEGER
AS
BEGIN
    MATCH (center:Entity {id: entityId})
    CALL {
        WITH center
        MATCH path = (center)-[*1..depth]-(neighbor:Entity)
        WHERE neighbor.id <> center.id
        RETURN neighbor, length(path) AS distance
        LIMIT limitCount
    }
    MATCH (center)-[rel]-(neighbor)
    RETURN
        center.id AS centerEntityId,
        neighbor.id AS neighborEntityId,
        neighbor.name AS neighborName,
        neighbor.type AS neighborType,
        type(rel) AS relationshipType,
        COALESCE(rel.strength, rel.confidence, 0.0) AS relationshipStrength,
        distance
    ORDER BY distance, relationshipStrength DESC;
END;

// Procedure to find similar entities
CREATE OR REPLACE PROCEDURE findSimilarEntities(
    IN entityId STRING,
    IN limitCount INTEGER,
    IN minSimilarity FLOAT
)
YIELD
    entityId STRING,
    similarEntityId STRING,
    similarEntityName STRING,
    similarEntityType STRING,
    similarityScore FLOAT
AS
BEGIN
    MATCH (e:Entity {id: entityId})
    MATCH (e)-[r:SIMILAR_TO]-(similar:Entity)
    WHERE r.similarity_score >= minSimilarity
    RETURN
        e.id AS entityId,
        similar.id AS similarEntityId,
        similar.name AS similarEntityName,
        similar.type AS similarEntityType,
        r.similarity_score AS similarityScore
    ORDER BY similarityScore DESC
    LIMIT limitCount;
END;

// Procedure to clean up orphaned nodes
CREATE OR REPLACE PROCEDURE cleanupOrphanedNodes()
YIELD
    nodesDeleted INTEGER,
    relationshipsDeleted INTEGER
AS
BEGIN
    // Count relationships before deletion
    MATCH ()-[r]-()
    WITH count(r) AS initialRelCount

    // Find and delete orphaned nodes
    MATCH (n)
    WHERE NOT (n)--()
    WITH count(n) AS orphanCount, initialRelCount
    CALL {
        WITH orphanCount
        MATCH (n)
        WHERE NOT (n)--()
        DETACH DELETE n
        RETURN orphanCount
    }

    // Count final relationships
    MATCH ()-[r]-()
    WITH count(r) AS finalRelCount, orphanCount, initialRelCount

    RETURN orphanCount AS nodesDeleted, initialRelCount - finalRelCount AS relationshipsDeleted;
END;

// Procedure to update graph statistics
CREATE OR REPLACE PROCEDURE updateGraphStatistics(
    IN orgId STRING
)
YIELD
    timestamp INTEGER,
    totalEntities INTEGER,
    totalDocuments INTEGER,
    totalRelationships INTEGER,
    averageConfidence FLOAT,
    highQualityEntities INTEGER
AS
BEGIN
    // Get current statistics
    MATCH (e:Entity {organization_id: orgId})
    WITH count(e) AS entityCount, avg(e.confidence) AS avgConfidence
    MATCH (d:Document {organization_id: orgId})
    WITH entityCount, avgConfidence, count(d) AS documentCount
    MATCH ()-[r]-()
    WITH entityCount, avgConfidence, documentCount, count(r) AS relationshipCount
    MATCH (e:Entity {organization_id: orgId})
    WHERE e.confidence > 0.8
    WITH entityCount, avgConfidence, documentCount, relationshipCount, count(e) AS highQualityCount

    // Create or update graph snapshot
    CREATE (snapshot:GraphSnapshot {
        id: randomUUID() + toString(timestamp()),
        organization_id: orgId,
        timestamp: timestamp(),
        total_entities: entityCount,
        total_documents: documentCount,
        total_relationships: relationshipCount,
        average_confidence: avgConfidence,
        high_quality_entities: highQualityCount
    })

    RETURN timestamp(), entityCount, documentCount, relationshipCount, avgConfidence, highQualityCount;
END;

// Set up database configuration for performance
CALL dbms.setConfigValue('dbms.memory.heap.initial_size', '512m');
CALL dbms.setConfigValue('dbms.memory.heap.max_size', '2G');
CALL dbms.setConfigValue('dbms.memory.pagecache.size', '1G');
CALL dbms.setConfigValue('dbms.transaction.timeout', '60s');
CALL dbms.setConfigValue('dbms.security.procedures.unrestricted', 'gds.*,apoc.*');

// Create a sample knowledge graph structure for testing
// (Remove or modify for production use)

// Create a sample document and entities for demonstration
WITH "doc123" AS docId, "org123" AS orgId
MERGE (doc:Document {
    id: docId,
    title: "Sample Knowledge Graph Document",
    document_type: "research_paper",
    organization_id: orgId,
    created_at: timestamp(),
    file_size: 1024000
});

// Create sample entities
WITH "org123" AS orgId
MERGE (person1:Entity {
    id: "person123",
    name: "John Doe",
    type: "Person",
    organization_id: orgId,
    confidence: 0.95,
    importance_score: 0.8,
    created_at: timestamp()
});

MERGE (org1:Entity {
    id: "org123",
    name: "Acme Corporation",
    type: "Organization",
    organization_id: orgId,
    confidence: 0.90,
    importance_score: 0.9,
    created_at: timestamp()
});

MERGE (location1:Entity {
    id: "loc123",
    name: "San Francisco",
    type: "Location",
    organization_id: orgId,
    confidence: 0.98,
    importance_score: 0.6,
    created_at: timestamp()
});

// Create relationships
MATCH (doc:Document {id: "doc123"})
MATCH (person:Entity {id: "person123"})
MERGE (doc)-[:MENTIONS {
    id: randomUUID(),
    confidence: 0.95,
    strength: 0.8,
    created_at: timestamp()
}]->(person);

MATCH (person:Entity {id: "person123"})
MATCH (org:Entity {id: "org123"})
MERGE (person)-[:RELATES_TO {
    id: randomUUID(),
    relationship_type: "WORKS_FOR",
    confidence: 0.90,
    strength: 0.9,
    created_at: timestamp()
}]->(org);

MATCH (org:Entity {id: "org123"})
MATCH (location:Entity {id: "loc123"})
MERGE (org)-[:RELATES_TO {
    id: randomUUID(),
    relationship_type: "LOCATED_IN",
    confidence: 0.85,
    strength: 0.7,
    created_at: timestamp()
}]->(location);

// Create content node
MATCH (doc:Document {id: "doc123"})
MERGE (text:TextContent {
    id: "text123",
    document_id: doc.id,
    content: "This is a sample text content for the knowledge graph demonstration...",
    content_type: "text",
    created_at: timestamp()
});

MERGE (doc)-[:CONTAINS {
    id: randomUUID(),
    created_at: timestamp()
}]->(text);

// Final setup verification
// Check that all constraints and indexes are created
CALL db.constraints() YIELD name RETURN count(*) AS constraintCount;
CALL db.indexes() YIELD name RETURN count(*) AS indexCount;

// Display initialization summary
WITH
    (SELECT count(*) FROM (:Entity)) AS entityCount,
    (SELECT count(*) FROM (:Document)) AS documentCount,
    (SELECT count(*) FROM (:TextContent)) AS textContentCount,
    (SELECT count(*) FROM (:MediaContent)) AS mediaContentCount,
    (SELECT count(*) FROM ()-[:MENTIONS]-()) AS mentionsCount,
    (SELECT count(*) FROM ()-[:RELATES_TO]-()) AS relatesToCount,
    (SELECT count(*) FROM ()-[:CONTAINS]-()) AS containsCount
RETURN
    "Neo4j Knowledge Graph Initialization Complete" AS status,
    entityCount,
    documentCount,
    textContentCount,
    mediaContentCount,
    mentionsCount,
    relatesToCount,
    containsCount,
    timestamp() AS initialization_time;

// Log successful initialization
CALL apoc.log.info("Neo4j Knowledge Graph database initialized successfully", {});

// Performance optimization tips (run these after you have data)
/*
// After loading data, run these optimizations:

// Update statistics
CALL db.stats.retrieve('GRAPH COUNTS');

// Warm up caches
CALL apoc.warmup.run();

// Create graph projections for GDS algorithms
CALL gds.graph.project('entityGraph', 'Entity', {
    MENTIONS: {orientation: 'UNDIRECTED'},
    RELATES_TO: {orientation: 'UNDIRECTED'}
});

// Run centrality algorithms
CALL gds.degree.stream('entityGraph') YIELD nodeId, score
RETURN gds.util.asNode(nodeId).name AS entity, score
ORDER BY score DESC LIMIT 10;

// Run community detection
CALL gds.louvain.stream('entityGraph') YIELD nodeId, communityId
RETURN communityId, count(*) AS size
ORDER BY size DESC LIMIT 10;
*/