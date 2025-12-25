
import os
import sys
# Add backend to path to import settings
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from src.core.config import settings
    from neo4j import GraphDatabase

    print(f"Testing Neo4j Connection...")
    print(f"URI: {settings.NEO4J_URI}")
    print(f"User: {settings.NEO4J_USER}")
    # Don't print password explicitly, but check if it's set
    print(f"Password set: {'Yes' if settings.NEO4J_PASSWORD else 'No (Empty String)'}")

    try:
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        with driver.session() as session:
            result = session.run("RETURN 1 AS num")
            record = result.single()
            print(f"Current Database Time: {record['num']}")
        print("SUCCESS: Connected to Neo4j!")
        driver.close()
    except Exception as e:
        print(f"FAILURE: Could not connect to Neo4j: {e}")

except ImportError as e:
    print(f"Import Error (run from project root): {e}")
except Exception as e:
    print(f"Unexpected Error: {e}")
