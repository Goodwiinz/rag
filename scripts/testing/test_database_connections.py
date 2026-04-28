#!/usr/bin/env python3
"""
Quick test script to verify all database connections
Tests: PostgreSQL, Redis, Neo4j, and Qdrant

Credentials are read from environment variables — see issue #379. Set
DB_PASSWORD / REDIS_PASSWORD / NEO4J_PASSWORD / QDRANT_API_KEY before running.
"""

import os
import sys
from datetime import datetime


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)

def test_postgresql():
    """Test PostgreSQL connection"""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=_env("DB_HOST", "localhost"),
            port=int(_env("DB_PORT", "5432")),
            database=_env("DB_NAME", "ragdb"),
            user=_env("DB_USER", "raguser"),
            password=_env("DB_PASSWORD"),
        )
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';")
        tables = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        print("✅ PostgreSQL: Connected")
        print(f"   Version: {version.split(',')[0]}")
        print(f"   Tables: {tables}")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL: Failed - {e}")
        return False

def test_redis():
    """Test Redis connection"""
    try:
        import redis
        
        r = redis.Redis(
            host=_env("REDIS_HOST", "localhost"),
            port=int(_env("REDIS_PORT", "6379")),
            password=_env("REDIS_PASSWORD") or None,
            decode_responses=True,
        )
        
        # Test ping
        r.ping()
        
        # Get info
        info = r.info()
        
        print("✅ Redis: Connected")
        print(f"   Version: {info['redis_version']}")
        print(f"   Used Memory: {info['used_memory_human']}")
        print(f"   Connected Clients: {info['connected_clients']}")
        return True
    except Exception as e:
        print(f"❌ Redis: Failed - {e}")
        return False

def test_neo4j():
    """Test Neo4j connection"""
    try:
        from neo4j import GraphDatabase
        
        driver = GraphDatabase.driver(
            _env("NEO4J_URI", "bolt://localhost:7687"),
            auth=(_env("NEO4J_USER", "neo4j"), _env("NEO4J_PASSWORD")),
        )
        
        with driver.session() as session:
            # Get version
            result = session.run(
                "CALL dbms.components() YIELD name, versions, edition "
                "RETURN name, versions[0] as version, edition"
            )
            record = result.single()
            
            # Count nodes
            count_result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = count_result.single()["count"]
            
            # Count relationships
            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = rel_result.single()["count"]
        
        driver.close()
        
        print("✅ Neo4j: Connected")
        print(f"   Version: {record['version']} ({record['edition']})")
        print(f"   Nodes: {node_count}")
        print(f"   Relationships: {rel_count}")
        return True
    except Exception as e:
        print(f"❌ Neo4j: Failed - {e}")
        return False

def test_qdrant():
    """Test Qdrant connection"""
    try:
        from qdrant_client import QdrantClient
        
        client = QdrantClient(
            url=_env("QDRANT_URL", "http://localhost:6333"),
            api_key=_env("QDRANT_API_KEY") or None,
        )
        
        # Get collections
        collections = client.get_collections()
        
        # Get cluster info (if available)
        try:
            info = client.cluster_info()
            version = "Unknown"
        except:
            version = "Unknown"
        
        print("✅ Qdrant: Connected")
        print(f"   Collections: {len(collections.collections)}")
        if collections.collections:
            for col in collections.collections:
                print(f"   - {col.name}: {col.vectors_count} vectors")
        return True
    except Exception as e:
        print(f"❌ Qdrant: Failed - {e}")
        return False

def main():
    """Run all database tests"""
    print("=" * 60)
    print("🔍 Database Connection Test")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    results = {
        "PostgreSQL": test_postgresql(),
        "Redis": test_redis(),
        "Neo4j": test_neo4j(),
        "Qdrant": test_qdrant()
    }
    
    print()
    print("=" * 60)
    print("📊 Summary")
    print("=" * 60)
    
    success_count = sum(results.values())
    total_count = len(results)
    
    for db, status in results.items():
        status_icon = "✅" if status else "❌"
        print(f"{status_icon} {db}: {'Connected' if status else 'Failed'}")
    
    print()
    print(f"Total: {success_count}/{total_count} databases connected")
    
    if success_count == total_count:
        print("🎉 All databases are working!")
        return 0
    else:
        print("⚠️  Some databases failed to connect")
        return 1

if __name__ == "__main__":
    sys.exit(main())
