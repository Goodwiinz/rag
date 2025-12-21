#!/usr/bin/env python3
"""
Test ArXiv CLI with Neo4j
"""

import subprocess
import sys
import time

def run_command(cmd):
    """Run command and return output"""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd="/Users/goodwiinz/development/RAG_system"
    )
    return result.stdout, result.stderr, result.returncode

def test_cli():
    """Test arXiv CLI"""
    print("=" * 60)
    print("ArXiv CLI Neo4j Test")
    print("=" * 60)

    # Test 1: Search for papers
    print("\n1. Searching for arXiv papers...")
    stdout, stderr, code = run_command(
        "python scripts/arxiv_cli.py search --query 'quantum computing' --max-results 3"
    )

    if code == 0:
        print("✓ Search successful")
        lines = stdout.strip().split('\n')
        for line in lines[-5:]:  # Show last 5 lines
            if line.strip():
                print(f"  {line}")
    else:
        print(f"✗ Search failed: {stderr}")
        return

    # Test 2: Ingest papers with KG
    print("\n2. Ingesting papers with knowledge graph...")
    stdout, stderr, code = run_command(
        "python scripts/arxiv_cli.py ingest --query 'quantum computing' --max-results 2 --extract-entities"
    )

    if code == 0:
        print("✓ Ingestion successful")
        # Show last few lines
        lines = stdout.strip().split('\n')
        for line in lines[-10:]:
            if 'Created' in line or 'Extracted' in line or 'Processed' in line:
                print(f"  {line}")
    else:
        print(f"✗ Ingestion failed: {stderr}")

    # Wait for processing
    print("\n3. Waiting for processing...")
    time.sleep(3)

    # Test 3: Check Neo4j directly
    print("\n4. Checking Neo4j...")
    stdout, stderr, code = run_command(
        'docker exec rag_system-neo4j-1 cypher-shell -u neo4j -p neo4j123 "MATCH (n) RETURN count(n) as total_nodes"'
    )

    if code == 0:
        print(f"✓ Neo4j connected")
        print(f"  Total nodes: {stdout.strip()}")
    else:
        print(f"✗ Neo4j connection failed")

    # Check for ArXiv entities
    print("\n5. Checking for ArXiv entities...")
    stdout, stderr, code = run_command(
        'docker exec rag_system-neo4j-1 cypher-shell -u neo4j -p neo4j123 "MATCH (e) WHERE e.name CONTAINS \'quantum\' RETURN count(e) as quantum_nodes"'
    )

    if code == 0:
        count = stdout.strip()
        print(f"✓ Found {count} entities containing 'quantum'")
    else:
        print(f"✗ Query failed")

    # Show sample entities
    print("\n6. Sample entities...")
    stdout, stderr, code = run_command(
        'docker exec rag_system-neo4j-1 cypher-shell -u neo4j -p neo4j123 "MATCH (e) RETURN e.name as name, labels(e) as labels LIMIT 5" --format plain'
    )

    if code == 0:
        print("✓ Sample entities from Neo4j:")
        lines = stdout.strip().split('\n')
        for line in lines[2:]:  # Skip header
            if line.strip():
                print(f"  {line}")

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print("\nTo view in Neo4j Browser:")
    print("1. Open http://localhost:7474")
    print("2. Login with neo4j/neo4j123")
    print("3. Run: MATCH (n) RETURN n LIMIT 25")

if __name__ == "__main__":
    test_cli()