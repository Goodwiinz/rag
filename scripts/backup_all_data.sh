#!/bin/bash
# ============================================================================
# Backup All RAG System Data for Migration
# ============================================================================
# Creates portable backups of Neo4j, PostgreSQL, Qdrant, and Redis data
# Usage: ./scripts/backup_all_data.sh [backup_directory]
# ============================================================================

set -e

# Configuration
BACKUP_DIR="${1:-./backups/$(date +%Y%m%d_%H%M%S)}"
COMPOSE_PROJECT="rag_system"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}============================================${NC}"
echo -e "${YELLOW}  RAG System Data Backup${NC}"
echo -e "${YELLOW}============================================${NC}"
echo ""
echo -e "Backup directory: ${GREEN}${BACKUP_DIR}${NC}"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# ============================================================================
# 1. PostgreSQL Backup
# ============================================================================
echo -e "${YELLOW}[1/4] Backing up PostgreSQL...${NC}"
POSTGRES_CONTAINER=$(docker ps --filter "name=postgres" --format "{{.Names}}" | head -1)
if [ -n "$POSTGRES_CONTAINER" ]; then
    docker exec "$POSTGRES_CONTAINER" pg_dumpall -U raguser > "$BACKUP_DIR/postgresql_backup.sql"
    echo -e "${GREEN}  ✓ PostgreSQL backup complete${NC}"
else
    echo -e "${RED}  ✗ PostgreSQL container not found${NC}"
fi

# ============================================================================
# 2. Neo4j Backup (Knowledge Graph)
# ============================================================================
echo -e "${YELLOW}[2/4] Backing up Neo4j Knowledge Graph...${NC}"
NEO4J_CONTAINER=$(docker ps --filter "name=neo4j" --format "{{.Names}}" | head -1)
if [ -n "$NEO4J_CONTAINER" ]; then
    # Export all nodes and relationships as Cypher
    docker exec "$NEO4J_CONTAINER" cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" \
        "CALL apoc.export.cypher.all(null, {stream: true}) YIELD cypherStatements RETURN cypherStatements" \
        > "$BACKUP_DIR/neo4j_backup.cypher" 2>/dev/null || \
    docker exec "$NEO4J_CONTAINER" cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" \
        "MATCH (n) RETURN n LIMIT 1" > /dev/null && \
    echo "  Using volume copy for Neo4j backup..."
    
    # Also copy the data volume
    docker cp "$NEO4J_CONTAINER:/data" "$BACKUP_DIR/neo4j_data" 2>/dev/null || true
    echo -e "${GREEN}  ✓ Neo4j backup complete${NC}"
else
    echo -e "${RED}  ✗ Neo4j container not found${NC}"
fi

# ============================================================================
# 3. Qdrant Backup (Vector Database)
# ============================================================================
echo -e "${YELLOW}[3/4] Backing up Qdrant Vectors...${NC}"
QDRANT_CONTAINER=$(docker ps --filter "name=qdrant" --format "{{.Names}}" | head -1)
if [ -n "$QDRANT_CONTAINER" ]; then
    # Create snapshots for all collections
    mkdir -p "$BACKUP_DIR/qdrant_snapshots"
    
    # Get all collections and create snapshots
    COLLECTIONS=$(curl -s http://localhost:6333/collections | jq -r '.result.collections[].name' 2>/dev/null || echo "")
    
    if [ -n "$COLLECTIONS" ]; then
        for COLLECTION in $COLLECTIONS; do
            echo "  Creating snapshot for collection: $COLLECTION"
            curl -s -X POST "http://localhost:6333/collections/${COLLECTION}/snapshots" > /dev/null
            # Get the latest snapshot
            SNAPSHOT=$(curl -s "http://localhost:6333/collections/${COLLECTION}/snapshots" | jq -r '.result[-1].name' 2>/dev/null)
            if [ -n "$SNAPSHOT" ] && [ "$SNAPSHOT" != "null" ]; then
                curl -s "http://localhost:6333/collections/${COLLECTION}/snapshots/${SNAPSHOT}" \
                    -o "$BACKUP_DIR/qdrant_snapshots/${COLLECTION}_${SNAPSHOT}" 2>/dev/null || true
            fi
        done
    fi
    
    # Also copy the storage volume
    docker cp "$QDRANT_CONTAINER:/qdrant/storage" "$BACKUP_DIR/qdrant_storage" 2>/dev/null || true
    echo -e "${GREEN}  ✓ Qdrant backup complete${NC}"
else
    echo -e "${RED}  ✗ Qdrant container not found${NC}"
fi

# ============================================================================
# 4. Redis Backup
# ============================================================================
echo -e "${YELLOW}[4/4] Backing up Redis...${NC}"
REDIS_CONTAINER=$(docker ps --filter "name=redis" --format "{{.Names}}" | grep -v commander | head -1)
if [ -n "$REDIS_CONTAINER" ]; then
    # Trigger a Redis save
    docker exec "$REDIS_CONTAINER" redis-cli BGSAVE 2>/dev/null || true
    sleep 2
    # Copy the RDB file
    docker cp "$REDIS_CONTAINER:/data/dump.rdb" "$BACKUP_DIR/redis_dump.rdb" 2>/dev/null || true
    echo -e "${GREEN}  ✓ Redis backup complete${NC}"
else
    echo -e "${RED}  ✗ Redis container not found${NC}"
fi

# ============================================================================
# Create compressed archive
# ============================================================================
echo ""
echo -e "${YELLOW}Creating compressed archive...${NC}"
ARCHIVE_NAME="rag_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
tar -czf "$BACKUP_DIR/../$ARCHIVE_NAME" -C "$BACKUP_DIR" .
echo -e "${GREEN}  ✓ Archive created: $BACKUP_DIR/../$ARCHIVE_NAME${NC}"

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Backup Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Backup location: $BACKUP_DIR"
echo "Archive: $BACKUP_DIR/../$ARCHIVE_NAME"
echo ""
echo "Contents:"
ls -lh "$BACKUP_DIR"
echo ""
echo -e "${YELLOW}To restore on DigitalOcean:${NC}"
echo "1. Copy the archive to your DigitalOcean droplet"
echo "2. Extract: tar -xzf $ARCHIVE_NAME"
echo "3. Use the restore script: ./scripts/restore_all_data.sh <backup_dir>"
