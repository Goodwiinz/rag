# Neo4j Graph Database Connection Guide

## 🎯 Your Neo4j Connection Details

**Connection Information:**
- **Host**: `localhost` (or `neo4j` from within Docker containers)
- **Bolt Port**: `7687` (for programmatic access)
- **HTTP Port**: `7474` (for web browser interface)
- **Username**: `neo4j`
- **Password**: `REDACTED`

**Connection URIs:**
```
bolt://neo4j:REDACTED@localhost:7687
neo4j://neo4j:REDACTED@localhost:7687
http://localhost:7474/browser/
```

---

## 🌐 Web Browser Interface (Easiest!)

### Neo4j Browser
1. Open your web browser
2. Go to: **http://localhost:7474**
3. Login with:
   - **Connect URL**: `bolt://localhost:7687`
   - **Username**: `neo4j`
   - **Password**: `REDACTED`
4. Click **Connect**

### Quick Cypher Queries to Try:
```cypher
// Show Neo4j version
CALL dbms.components() YIELD name, versions
RETURN name, versions[0] as version;

// Count all nodes
MATCH (n) RETURN count(n) as total_nodes;

// Count all relationships
MATCH ()-[r]->() RETURN count(r) as total_relationships;

// Show node labels
CALL db.labels() YIELD label RETURN label;

// Show relationship types
CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType;

// Show sample data (first 25 nodes)
MATCH (n) RETURN n LIMIT 25;
```

---

## 💻 Command Line Access

### Using Cypher Shell (Inside Container)

```bash
# Interactive mode
docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p REDACTED

# Single query
docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p REDACTED \
  "MATCH (n) RETURN count(n) as nodes;"

# With database selection
docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p REDACTED -d neo4j \
  "RETURN 'Hello Neo4j!' as greeting;"
```

### Cypher Shell Commands
Once connected, you can use these commands:
```
:help          - Show help
:exit          - Exit cypher-shell
:use neo4j     - Switch database
:param name => value  - Set parameter
:params        - Show all parameters
```

---

## 🐍 Python Connection

### Using py2neo

```python
from py2neo import Graph

# Connect to Neo4j
graph = Graph(
    "bolt://localhost:7687",
    auth=("neo4j", "REDACTED")
)

# Test connection
result = graph.run("RETURN 'Connected!' as status").data()
print(result[0]['status'])

# Create a node
graph.run("""
    CREATE (p:Person {name: 'Alice', age: 30})
    RETURN p
""")

# Query nodes
people = graph.run("MATCH (p:Person) RETURN p.name as name, p.age as age").data()
for person in people:
    print(f"{person['name']}: {person['age']}")
```

### Using neo4j Official Driver (Recommended)

```python
from neo4j import GraphDatabase

class Neo4jConnection:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]

# Initialize connection
conn = Neo4jConnection(
    "bolt://localhost:7687",
    "neo4j",
    "REDACTED"
)

# Run query
result = conn.query("MATCH (n) RETURN count(n) as total")
print(f"Total nodes: {result[0]['total']}")

# Create nodes
conn.query("""
    CREATE (a:Article {title: $title, date: $date})
    RETURN a
""", parameters={"title": "My Article", "date": "2025-10-19"})

# Close connection
conn.close()
```

### Using Your Backend Configuration

Your backend already has Neo4j configured in `/backend/src/core/config.py`:

```python
from backend.src.core.config import settings
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    settings.NEO4J_URI,  # bolt://neo4j:7687
    auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
)

with driver.session() as session:
    result = session.run("MATCH (n) RETURN count(n) as total")
    print(result.single()["total"])
```

---

## 🔧 GUI Tools

### 1. **Neo4j Desktop** (Official, Free)
- Download: https://neo4j.com/download/
- Features: Built-in browser, graph visualization, APOC plugins
- Setup:
  1. Install Neo4j Desktop
  2. Add "Remote Connection"
  3. Connect URL: `bolt://localhost:7687`
  4. Username: `neo4j`, Password: `REDACTED`

### 2. **Neo4j Bloom** (Visual Exploration)
- Included with Neo4j Desktop
- Great for visual graph exploration
- Drag-and-drop interface

### 3. **Arrows.app** (Graph Modeling)
- URL: https://arrows.app/
- Create graph models visually
- Export to Cypher

---

## 📊 Common Cypher Queries

### Data Exploration

```cypher
// Show database info
CALL dbms.components() YIELD name, versions, edition
RETURN name, versions[0] as version, edition;

// List all databases
SHOW DATABASES;

// Show current database
CALL db.info() YIELD name RETURN name;

// Show indexes
SHOW INDEXES;

// Show constraints
SHOW CONSTRAINTS;
```

### Node Operations

```cypher
// Create a node
CREATE (n:Person {name: 'John', age: 25})
RETURN n;

// Create multiple nodes
CREATE 
  (a:Person {name: 'Alice'}),
  (b:Person {name: 'Bob'}),
  (c:Person {name: 'Charlie'})
RETURN a, b, c;

// Find nodes
MATCH (p:Person {name: 'Alice'})
RETURN p;

// Find all nodes of a type
MATCH (p:Person)
RETURN p
LIMIT 10;

// Update a node
MATCH (p:Person {name: 'Alice'})
SET p.age = 31, p.email = 'alice@example.com'
RETURN p;

// Delete a node
MATCH (p:Person {name: 'Alice'})
DELETE p;
```

### Relationship Operations

```cypher
// Create relationship
MATCH (a:Person {name: 'Alice'}), (b:Person {name: 'Bob'})
CREATE (a)-[r:KNOWS {since: 2020}]->(b)
RETURN a, r, b;

// Find relationships
MATCH (a:Person)-[r:KNOWS]->(b:Person)
RETURN a.name, type(r), b.name, r.since;

// Delete relationship
MATCH (a:Person)-[r:KNOWS]->(b:Person)
WHERE a.name = 'Alice' AND b.name = 'Bob'
DELETE r;
```

### Advanced Queries

```cypher
// Find paths between nodes
MATCH path = (a:Person {name: 'Alice'})-[*..3]-(b:Person {name: 'Charlie'})
RETURN path
LIMIT 5;

// Count nodes by label
MATCH (n)
RETURN labels(n) as label, count(n) as count
ORDER BY count DESC;

// Find nodes with most connections
MATCH (n)
RETURN n, size((n)--()) as degree
ORDER BY degree DESC
LIMIT 10;

// Aggregate data
MATCH (p:Person)
RETURN 
  count(p) as total,
  avg(p.age) as avg_age,
  min(p.age) as min_age,
  max(p.age) as max_age;
```

---

## 🔍 Knowledge Graph Queries (For Your RAG System)

### Entity Queries

```cypher
// Find all entities
MATCH (e:Entity)
RETURN e.name, e.type, e.confidence
LIMIT 25;

// Find entities by type
MATCH (e:Entity {type: 'PERSON'})
RETURN e.name, e.mentions
ORDER BY e.mentions DESC;

// Find related entities
MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
WHERE e1.name = 'specific_entity'
RETURN e1.name, type(r), e2.name, r.confidence;
```

### Document-Entity Relationships

```cypher
// Find documents containing an entity
MATCH (d:Document)-[r:CONTAINS_ENTITY]->(e:Entity)
WHERE e.name = 'entity_name'
RETURN d.title, d.id, e.name;

// Find co-occurring entities
MATCH (e1:Entity)<-[:CONTAINS_ENTITY]-(d:Document)-[:CONTAINS_ENTITY]->(e2:Entity)
WHERE e1.name = 'entity_1' AND id(e1) < id(e2)
RETURN e2.name, count(d) as co_occurrences
ORDER BY co_occurrences DESC
LIMIT 10;
```

---

## 🛠️ Troubleshooting

### Connection Refused

```bash
# Check if Neo4j is running
docker ps | grep neo4j

# Check Neo4j logs
docker logs rag-neo4j-1 --tail 50

# Restart Neo4j
docker restart rag-neo4j-1

# Wait for startup (takes 5-10 seconds)
sleep 10

# Test connection
docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p REDACTED \
  "RETURN 'OK' as status;"
```

### Authentication Failed

If you get authentication errors:

```bash
# Option 1: Reset Neo4j with new password
docker stop rag-neo4j-1
docker rm rag-neo4j-1
docker volume rm rag_neo4j_data
docker run -d \
  --name rag-neo4j-1 \
  --network rag_multimodal-rag-network \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/REDACTED \
  -v rag_neo4j_data:/data \
  neo4j:5.15-community

# Option 2: Disable authentication (NOT for production!)
docker run -d \
  --name rag-neo4j-1 \
  --network rag_multimodal-rag-network \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=none \
  neo4j:5.15-community
```

### Check Memory Usage

```cypher
// Show memory usage
CALL dbms.queryJmx("java.lang:type=Memory")
YIELD attributes
RETURN attributes.HeapMemoryUsage.value as heap;

// Show cache statistics
CALL dbms.queryJmx("org.neo4j:*")
YIELD attributes, name
WHERE name CONTAINS 'Cache'
RETURN name, attributes;
```

### Performance Issues

```cypher
// Show slow queries
CALL dbms.listQueries()
YIELD queryId, elapsedTimeMillis, query
WHERE elapsedTimeMillis > 1000
RETURN queryId, elapsedTimeMillis, query
ORDER BY elapsedTimeMillis DESC;

// Kill a query
CALL dbms.killQuery('query-123');

// Show transaction statistics
CALL dbms.listTransactions()
YIELD transactionId, currentQuery, elapsedTimeMillis
RETURN transactionId, currentQuery, elapsedTimeMillis
ORDER BY elapsedTimeMillis DESC;
```

---

## 📦 Backup and Restore

### Backup Database

```bash
# Stop Neo4j (recommended for consistent backup)
docker stop rag-neo4j-1

# Create backup
docker run --rm \
  -v rag_neo4j_data:/data \
  -v $(pwd)/backups:/backup \
  neo4j:5.15-community \
  neo4j-admin database dump neo4j --to=/backup/neo4j-backup-$(date +%Y%m%d_%H%M%S).dump

# Start Neo4j
docker start rag-neo4j-1
```

### Restore Database

```bash
# Stop Neo4j
docker stop rag-neo4j-1

# Restore backup
docker run --rm \
  -v rag_neo4j_data:/data \
  -v $(pwd)/backups:/backup \
  neo4j:5.15-community \
  neo4j-admin database load neo4j --from=/backup/your-backup.dump --overwrite-destination=true

# Start Neo4j
docker start rag-neo4j-1
```

### Export to Cypher

```bash
# Export all data to Cypher statements
docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p REDACTED \
  "CALL apoc.export.cypher.all('/var/lib/neo4j/import/export.cypher', {format: 'cypher-shell'});"

# Copy export file to host
docker cp rag-neo4j-1:/var/lib/neo4j/import/export.cypher ./neo4j_export.cypher
```

---

## 🔐 Security Best Practices

### Change Default Password (Production)

```cypher
// Change password (after first login)
ALTER CURRENT USER SET PASSWORD FROM 'REDACTED' TO 'new_strong_password';
```

### Create Additional Users

```cypher
// Create new user
CREATE USER alice SET PASSWORD 'secure_password' CHANGE NOT REQUIRED;

// Grant privileges
GRANT ROLE reader TO alice;
GRANT ROLE publisher TO alice;

// Show users
SHOW USERS;

// Revoke privileges
REVOKE ROLE publisher FROM alice;

// Delete user
DROP USER alice;
```

### Enable SSL/TLS (Production)

In your docker-compose.yml:
```yaml
neo4j:
  environment:
    - NEO4J_dbms_connector_bolt_tls__level=REQUIRED
    - NEO4J_dbms_ssl_policy_bolt_enabled=true
  volumes:
    - ./certificates:/ssl
```

---

## 📈 Performance Optimization

### Create Indexes

```cypher
// Create index on Entity name
CREATE INDEX entity_name FOR (e:Entity) ON (e.name);

// Create composite index
CREATE INDEX entity_type_name FOR (e:Entity) ON (e.type, e.name);

// Create full-text index
CREATE FULLTEXT INDEX entity_search FOR (e:Entity) ON EACH [e.name, e.description];

// Use full-text search
CALL db.index.fulltext.queryNodes('entity_search', 'search term')
YIELD node, score
RETURN node.name, score
ORDER BY score DESC;
```

### Create Constraints

```cypher
// Unique constraint
CREATE CONSTRAINT entity_id_unique FOR (e:Entity) REQUIRE e.id IS UNIQUE;

// Property existence constraint
CREATE CONSTRAINT entity_name_exists FOR (e:Entity) REQUIRE e.name IS NOT NULL;

// Show constraints
SHOW CONSTRAINTS;
```

---

## 📚 Resources

- **Neo4j Documentation**: https://neo4j.com/docs/
- **Cypher Manual**: https://neo4j.com/docs/cypher-manual/current/
- **GraphAcademy** (Free Courses): https://graphacademy.neo4j.com/
- **Neo4j Community**: https://community.neo4j.com/
- **Awesome Neo4j**: https://github.com/neueda/awesome-neo4j

---

## ✅ Quick Connection Test

**Test your connection now:**

```bash
# Command line test
docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p REDACTED \
  "RETURN 'Neo4j is ready!' as status, datetime() as time;"
```

**Or open in browser:**
- URL: http://localhost:7474
- Username: `neo4j`
- Password: `REDACTED`

---

**Status**: ✅ Your Neo4j graph database is running and ready!

**Connection URI**: `bolt://localhost:7687`
**Web Interface**: http://localhost:7474
