
import asyncio
import json
import ast
from neo4j import GraphDatabase

# Connection details
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "neo4jpassword")

def get_mapped_label(original_type):
    """Map original entity types to Neo4j Labels"""
    original_type = original_type.lower().strip()
    
    # Map these to CONCEPT
    concept_types = [
        'model', 'method', 'methodology', 'metric', 'task', 
        'technique', 'algorithm', 'framework', 'architecture',
        'dataset', 'benchmark', 'concept', 'field', 'mechanism', 
        'optimizer', 'activation', 'loss'
    ]
    
    if original_type in concept_types:
        return 'CONCEPT'
        
    return None

def reclassify_nodes():
    try:
        driver = GraphDatabase.driver(URI, auth=AUTH)
        with driver.session() as session:
            # 1. Fetch all OTHER nodes with metadata
            query = """
            MATCH (n:OTHER)
            WHERE n.metadata IS NOT NULL
            RETURN elementId(n) as id, n.metadata as metadata
            """
            result = session.run(query)
            
            updates = []
            
            for record in result:
                node_id = record["id"]
                metadata_str = record["metadata"]
                
                try:
                    # Metadata might be a JSON string or Python dictionary string representation
                    # based on the user's previous output "{'source': ...}" implies Python dict string
                    # But could be JSON. strict=False for json might not work for single quotes.
                    # We'll try ast.literal_eval for python-dict style strings first.
                    try:
                        metadata = json.loads(metadata_str)
                    except json.JSONDecodeError:
                        try:
                            metadata = ast.literal_eval(metadata_str)
                        except:
                            continue
                            
                    if not isinstance(metadata, dict):
                        continue
                        
                    original_type = metadata.get('entity_type_original')
                    if not original_type:
                        # Fallback to checking 'type' specific field if exists
                        original_type = metadata.get('type')
                        
                    if original_type:
                        new_label = get_mapped_label(original_type)
                        if new_label:
                            updates.append({
                                "id": node_id,
                                "new_label": new_label,
                                "original_type": original_type
                            })
                            
                except Exception as e:
                    print(f"Error parsing metadata for node {node_id}: {e}")
                    continue

            print(f"Found {len(updates)} nodes to reclassify out of {len(list(result)) if isinstance(result, list) else 'many'}.")
            
            # 2. Apply updates
            # We do this in batches or one by one. One by one is safer for a script.
            updated_count = 0
            for update in updates:
                node_id = update["id"]
                new_label = update["new_label"]
                
                # Cypher to remove OTHER and add New Label
                # Also update the 'type' property to reflect the new label (e.g. CONCEPT)
                update_query = f"""
                MATCH (n)
                WHERE elementId(n) = $id
                REMOVE n:OTHER
                SET n:{new_label}
                SET n.type = $new_label
                RETURN count(n) as c
                """
                
                session.run(update_query, id=node_id, new_label=new_label)
                updated_count += 1
                
            print(f"Successfully reclassified {updated_count} nodes.")

        driver.close()
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")

if __name__ == "__main__":
    reclassify_nodes()
