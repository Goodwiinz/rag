
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neo4jpassword")

def inspect_schema():
    driver = GraphDatabase.driver(URI, auth=AUTH)
    with driver.session() as session:
        result = session.run("MATCH (c:CONCEPT) RETURN c LIMIT 1")
        record = result.single()
        if record:
            node = record['c']
            print("Concept Properties:")
            print(node.keys())
            for k in node.keys():
                val = node[k]
                if isinstance(val, str) and len(val) > 200:
                    val = val[:200] + "..."
                print(f"  {k}: {val}")
        else:
            print("No CONCEPT nodes found.")

    driver.close()

if __name__ == "__main__":
    inspect_schema()
