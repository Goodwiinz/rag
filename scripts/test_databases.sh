#!/bin/bash
# Quick database connection test using Docker commands
# No Python packages required!

echo "============================================================"
echo "🔍 Database Connection Test (Docker Edition)"
echo "⏰ Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success_count=0
total_count=4

# Test PostgreSQL
echo "Testing PostgreSQL..."
if docker exec -it rag-postgres-1 psql -U raguser -d ragdb -c "SELECT version();" > /dev/null 2>&1; then
    version=$(docker exec -it rag-postgres-1 psql -U raguser -d ragdb -t -c "SELECT version();" 2>/dev/null | head -1 | xargs)
    tables=$(docker exec -it rag-postgres-1 psql -U raguser -d ragdb -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';" 2>/dev/null | xargs)
    echo -e "${GREEN}✅ PostgreSQL: Connected${NC}"
    echo "   Version: ${version:0:50}..."
    echo "   Tables: $tables"
    ((success_count++))
else
    echo -e "${RED}❌ PostgreSQL: Failed${NC}"
fi
echo ""

# Test Redis
echo "Testing Redis..."
if docker exec -it rag-redis-1 redis-cli -a redis_password_123 PING > /dev/null 2>&1; then
    version=$(docker exec -it rag-redis-1 redis-cli -a redis_password_123 INFO server 2>/dev/null | grep redis_version | cut -d: -f2 | tr -d '\r\n')
    memory=$(docker exec -it rag-redis-1 redis-cli -a redis_password_123 INFO memory 2>/dev/null | grep used_memory_human | cut -d: -f2 | tr -d '\r\n')
    echo -e "${GREEN}✅ Redis: Connected${NC}"
    echo "   Version: $version"
    echo "   Memory Used: $memory"
    ((success_count++))
else
    echo -e "${RED}❌ Redis: Failed${NC}"
fi
echo ""

# Test Neo4j
echo "Testing Neo4j..."
if docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p neo4j_password_123 "RETURN 1;" > /dev/null 2>&1; then
    version=$(docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p neo4j_password_123 "CALL dbms.components() YIELD versions RETURN versions[0];" 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    nodes=$(docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p neo4j_password_123 "MATCH (n) RETURN count(n);" 2>/dev/null | grep -oE '[0-9]+' | head -1)
    rels=$(docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p neo4j_password_123 "MATCH ()-[r]->() RETURN count(r);" 2>/dev/null | grep -oE '[0-9]+' | head -1)
    echo -e "${GREEN}✅ Neo4j: Connected${NC}"
    echo "   Version: $version"
    echo "   Nodes: ${nodes:-0}"
    echo "   Relationships: ${rels:-0}"
    ((success_count++))
else
    echo -e "${RED}❌ Neo4j: Failed${NC}"
fi
echo ""

# Summary
echo "============================================================"
echo "📊 Summary"
echo "============================================================"

if docker exec -it rag-postgres-1 psql -U raguser -d ragdb -c "SELECT 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL: Connected${NC}"
else
    echo -e "${RED}❌ PostgreSQL: Failed${NC}"
fi

if docker exec -it rag-redis-1 redis-cli -a redis_password_123 PING > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis: Connected${NC}"
else
    echo -e "${RED}❌ Redis: Failed${NC}"
fi

if docker exec -it rag-neo4j-1 cypher-shell -u neo4j -p neo4j_password_123 "RETURN 1;" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Neo4j: Connected${NC}"
else
    echo -e "${RED}❌ Neo4j: Failed${NC}"
fi


echo ""
echo "Total: $success_count/$total_count databases connected"

if [ $success_count -eq $total_count ]; then
    echo -e "${GREEN}🎉 All databases are working!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some databases failed to connect${NC}"
    exit 1
fi
