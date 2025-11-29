// Neo4j performance optimization queries for the Multimodal Enterprise RAG system
// These queries optimize the graph database for entity and relationship queries

// 1. Index creation for performance
// Create indexes for frequently queried properties

// Document nodes
CREATE INDEX document_id_index IF NOT EXISTS FOR (d:Document) ON (d.id);
CREATE INDEX document_title_index IF NOT EXISTS FOR (d:Document) ON (d.title);
CREATE INDEX document_type_index IF NOT EXISTS FOR (d:Document) ON (d.document_type);
CREATE INDEX document_tenant_index IF NOT EXISTS FOR (d:Document) ON (d.tenant_id);
CREATE INDEX document_created_index IF NOT EXISTS FOR (d:Document) ON (d.created_at);

// Entity nodes
CREATE INDEX entity_id_index IF NOT EXISTS FOR (e:Entity) ON (e.id);
CREATE INDEX entity_name_index IF NOT EXISTS FOR (e:Entity) ON (e.name);
CREATE INDEX entity_type_index IF NOT EXISTS FOR (e:Entity) ON (e.type);
CREATE INDEX entity_tenant_index IF NOT EXISTS FOR (e:Entity) ON (e.tenant_id);
CREATE COMPOSITE INDEX entity_name_type_index IF NOT EXISTS FOR (e:Entity) ON (e.name, e.type);

// Text content nodes
CREATE INDEX text_content_id_index IF NOT EXISTS FOR (t:TextContent) ON (t.id);
CREATE INDEX text_content_document_index IF NOT EXISTS FOR (t:TextContent) ON (t.document_id);

// 2. Full-text search indexes
// Create full-text search indexes for content

CALL db.index.fulltext.createNodeIndex(
    "documentFulltext",
    ["Document", "TextContent"],
    ["title", "content", "summary"]
);

CALL db.index.fulltext.createNodeIndex(
    "entityFulltext",
    ["Entity"],
    ["name", "description", "aliases"]
);

// 3. Relationship indexes for performance
// Create constraints for relationship properties

CREATE CONSTRAINT entity_rel_id_unique IF NOT EXISTS FOR ()-[r:RELATED_TO]-() REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT contains_rel_id_unique IF NOT EXISTS FOR ()-[r:CONTAINS]-() REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT mentions_rel_id_unique IF NOT EXISTS FOR ()-[r:MENTIONS]-() REQUIRE r.id IS UNIQUE;

// 4. Performance monitoring queries

// Query execution plan analysis
EXPLAIN
MATCH (d:Document {tenant_id: $tenant_id})
WHERE d.document_type = $doc_type
RETURN d ORDER BY d.created_at DESC LIMIT 10;

// Index usage statistics
CALL db.indexes();

// Query performance profiling
PROFILE
MATCH (d:Document {tenant_id: $tenant_id})-[:CONTAINS]->(t:TextContent)
WHERE t.content CONTAINS $search_term
RETURN d, t LIMIT 20;

// 5. Optimized query patterns

// Efficient document retrieval with pagination
MATCH (d:Document {tenant_id: $tenant_id})
WHERE d.document_type = $doc_type
RETURN d
ORDER BY d.created_at DESC
SKIP $skip
LIMIT $limit;

// Efficient entity search with relationship counts
MATCH (e:Entity {tenant_id: $tenant_id})
WHERE e.type = $entity_type
OPTIONAL MATCH (e)-[r:RELATED_TO]-()
RETURN e, count(r) as relationship_count
ORDER BY e.name
LIMIT $limit;

// Efficient graph traversal with depth control
MATCH path = (d:Document {tenant_id: $tenant_id})-[:CONTAINS|MENTIONS*1..3]-(related)
WHERE d.id = $document_id
RETURN path
LIMIT 100;

// Optimized full-text search
CALL db.index.fulltext.queryNodes("documentFulltext", $search_query) YIELD node, score
WHERE node.tenant_id = $tenant_id
RETURN node, score
ORDER BY score DESC
LIMIT $limit;

// 6. Memory and cache optimization queries

// Warm up caches with frequent queries
MATCH (d:Document {tenant_id: $tenant_id})
RETURN d LIMIT 1000;

// Pre-load frequently accessed entities
MATCH (e:Entity {tenant_id: $tenant_id})
WHERE e.type IN ['Person', 'Organization', 'Location']
RETURN e LIMIT 500;

// 7. Batch operations for better performance

// Batch document creation (example)
// UNWIND $documents AS doc
// CREATE (d:Document {
//     id: doc.id,
//     title: doc.title,
//     document_type: doc.type,
//     tenant_id: doc.tenant_id,
//     created_at: timestamp(),
//     file_size: doc.file_size
// });

// Batch relationship creation
// UNWIND $relationships AS rel
// MATCH (a), (b)
// WHERE a.id = rel.source_id AND b.id = rel.target_id
// CREATE (a)-[r:RELATED_TO {type: rel.type, confidence: rel.confidence}]->(b);

// 8. Cleanup and maintenance queries

// Remove duplicate entities (example)
MATCH (e1:Entity), (e2:Entity)
WHERE e1.name = e2.name AND e1.type = e2.type AND e1.tenant_id = e2.tenant_id AND id(e1) < id(e2)
WITH e1, e2
MATCH (e2)-[r]-()
MERGE (e1)-[r]-(())
DELETE e2;

// Remove orphaned nodes
MATCH (n)
WHERE NOT (n)--()
DELETE n;

// Update statistics
CALL db.stats.retrieve('GRAPH COUNTS');

// 9. Query optimization examples

// Optimized document-entity relationship query
MATCH (d:Document {tenant_id: $tenant_id})-[:MENTIONS]->(e:Entity)
WHERE d.document_type = $doc_type AND e.type = $entity_type
RETURN d.title as document, e.name as entity
ORDER BY d.created_at DESC
LIMIT $limit;

// Optimized path finding with weight
MATCH (d1:Document {id: $doc1_id})-[:RELATED_TO]-(intermediate)-[:RELATED_TO]-(d2:Document {id: $doc2_id})
WHERE d1.tenant_id = $tenant_id AND d2.tenant_id = $tenant_id
RETURN d1, d2, length(intermediate) as path_length
ORDER BY path_length
LIMIT $limit;

// Optimized aggregation queries
MATCH (d:Document {tenant_id: $tenant_id})
OPTIONAL MATCH (d)-[:MENTIONS]->(e:Entity)
WITH d, count(e) as entity_count
RETURN d.document_type, avg(entity_count) as avg_entities_per_doc
ORDER BY avg_entities_per_doc DESC;

// 10. Neo4j configuration recommendations
// These should be set in neo4j.conf

// Memory settings (adjust based on available RAM)
// dbms.memory.heap.initial_size=512m
// dbms.memory.heap.max_size=2G
// dbms.memory.pagecache.size=1G

// Transaction settings
// dbms.transaction.timeout=60s
// dbms.transaction.concurrent.maximum=1000

// Query settings
// dbms.cypher.forbid_exhaustive_shortestpath=true
// dbms.cypher.forbid_shortestpath_common_nodes=true

// Log settings
// dbms.logs.query.enabled=INFO
// dbms.logs.query.threshold=1s
// dbms.logs.query.runtime=INFO

// Performance monitoring
// dbms.monitor.bolt.messages=true
// dbms.metrics.enabled=true

// 11. APOC procedures for performance
// These require APOC plugin to be installed

// Periodic commit for large operations
// CALL apoc.periodic.iterate(
//   'MATCH (d:Document) WHERE d.tenant_id = $tenant_id RETURN d',
//   'SET d.last_updated = timestamp()',
//   {batchSize:1000, parallel:true, params:{tenant_id:$tenant_id}}
// );

// Data warmup
// CALL apoc.warmup.run();

// Schema optimization
// CALL apoc.schema.assert({}, {});

// 12. Graph Data Science (GDS) for performance
// These require GDS plugin to be installed

// Create graph projection for faster analytics
// CALL gds.graph.project(
//     'documentEntityGraph',
//     ['Document', 'Entity'],
//     {
//         MENTIONS: {orientation: 'UNDIRECTED'},
//         RELATED_TO: {orientation: 'UNDIRECTED'}
//     }
// );

// Run similarity analysis
// CALL gds.nodeSimilarity.stream('documentEntityGraph')
// YIELD node1, node2, similarity
// RETURN gds.util.asNode(node1).name AS Entity1, gds.util.asNode(node2).name AS Entity2, similarity
// ORDER BY similarity DESC
// LIMIT 100;

// Community detection for performance insights
// CALL gds.louvain.stream('documentEntityGraph')
// YIELD nodeId, communityId
// RETURN communityId, count(*) as size
// ORDER BY size DESC
// LIMIT 10;