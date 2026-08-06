
import asyncio
import logging
from src.services.arxiv_kg_integration import ArXivKnowledgeGraphIntegration
from src.services.knowledge_graph import KnowledgeGraphService
from src.services.knowledge_graph.knowledge_graph_service import knowledge_graph_service
from src.services.search.vector_service import vector_service

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def backfill_relationships():
    # Initialize Integration Service
    # We need to manually set the singleton services
    integration = ArXivKnowledgeGraphIntegration(config={})
    integration.kg_service = knowledge_graph_service
    integration.vector_service = vector_service
    
    print("Starting Backfill of Semantic Relationships...")
    
    # 1. Fetch Documents and their Concept Entities
    # We want documents that HAVE text content and HAVE extracted concepts
    query = """
    MATCH (d:DOCUMENT)
    WHERE d.content_text IS NOT NULL AND d.content_text <> ""
    OPTIONAL MATCH (c:CONCEPT)-[:EXTRACTED_FROM]->(d)
    WITH d, collect(c) as concepts
    WHERE size(concepts) > 1  // Need at least 2 concepts to find a relationship
    RETURN 
        elementId(d) as doc_id, 
        d.title as title, 
        d.content_text as text, 
        concepts
    LIMIT 20  // Limit for safety during testing/demo
    """
    
    print("Starting Backfill of Semantic Relationships...")
    
    # 1. Fetch Documents and their Concept Entities
    query = """
    MATCH (d:DOCUMENT)
    WHERE d.id IS NOT NULL
    OPTIONAL MATCH (e:Entity)-[:EXTRACTED_FROM]->(d)
    WITH d, collect(e) as entities
    RETURN 
        d.id as paper_id, 
        d.title as title, 
        collect(entities) as nested_concepts
    """

    
    import aiohttp
    import xml.etree.ElementTree as ET
    
    async with aiohttp.ClientSession() as http_session:
        try:
            results = []
            with knowledge_graph_service.get_session() as session:
                result = session.run(query)
                for record in result:
                    # flattening nested concepts list structure from cypher collect
                    flat_concepts = []
                    # record['nested_concepts'] is a list of lists of nodes
                    for sublist in record['nested_concepts']:
                        for node in sublist:
                            flat_concepts.append(dict(node.items()))
                            
                    results.append({
                        'paper_id': record['paper_id'],
                        'title': record['title'],
                        'concepts': flat_concepts
                    })
            
            print(f"Found {len(results)} candidate documents for backfilling.")
            
            total_rels_added = 0
            
            for record in results:
                paper_id = record['paper_id']
                doc_title = record['title']
                
                entities = []
                for props in record['concepts']:
                    entity_name = props.get('name')
                    entity_type = props.get('type', 'CONCEPT')
                    if entity_name:
                        entities.append({'text': entity_name, 'type': entity_type})
                
                if len(entities) < 2:
                    continue

                print(f"Processing '{doc_title}' (ID: {paper_id})...")
                
                # Fetch Abstract from Arxiv
                try:
                    url = f"http://export.arxiv.org/api/query?id_list={paper_id}"
                    async with http_session.get(url) as response:
                        if response.status == 200:
                            content = await response.text()
                            root = ET.fromstring(content)
                            # Namespaces in atom feed
                            ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
                            entry = root.find('atom:entry', ns)
                            if entry:
                                summary = entry.find('atom:summary', ns).text.strip()
                                context_text = f"{doc_title}\n{summary}"
                                print(f"  -> Fetched abstract (len: {len(summary)})")
                                
                                # Extract Authors & Affiliations
                                authors_list = []
                                authors_detailed = []
                                for author_elem in entry.findall('atom:author', ns):
                                    name_elem = author_elem.find('atom:name', ns)
                                    if name_elem is not None:
                                        name = name_elem.text
                                        authors_list.append(name)
                                        affils = [aff.text for aff in author_elem.findall('arxiv:affiliation', ns)]
                                        authors_detailed.append({'name': name, 'affiliations': affils})

                                # Step 2: Extract NEW entities using LLM
                                paper_data = {
                                    'title': doc_title, 
                                    'abstract': summary, 
                                    'categories': [], 
                                    'authors': authors_list,
                                    'authors_detailed': authors_detailed
                                }
                                new_extracted_entities = await integration._extract_entities_from_paper(paper_data)
                                print(f"  -> Extracted {len(new_extracted_entities)} new entities: {[e['text'] for e in new_extracted_entities]}")
                                
                                # Merge
                                existing_names = {e['text'].lower() for e in entities}
                                final_entities = list(entities)
                                for new_e in new_extracted_entities:
                                    if new_e['text'].lower() not in existing_names:
                                        final_entities.append(new_e)
                                        try:
                                             await integration._add_entity_to_kg(new_e, {'id': paper_id, 'title': doc_title})
                                        except Exception as ex:
                                             print(f"Failed to save entity: {ex}")

                                print(f"  -> Final entity count: {len(final_entities)}")
                                
                                # Step 3: Extract Relationships
                                new_relationships = await integration._extract_semantic_relations_with_llm(
                                    context_text,
                                    final_entities
                                )
                                    
                                if new_relationships:
                                    print(f"  -> Found {len(new_relationships)} new relationships.")
                                    
                                    for rel in new_relationships:
                                        try:
                                            source_name = rel['source']['text']
                                            target_name = rel['target']['text']
                                            rel_type = rel['relation']
                                            
                                            cypher = (
                                                f"MATCH (s:Entity {{name: $source_name}}), (t:Entity {{name: $target_name}}) "
                                                f"MERGE (s)-[r:{rel_type}]->(t) "
                                                "SET r.confidence = $confidence, r.source = 'llm_backfill'"
                                            )
                                            
                                            with knowledge_graph_service.get_session() as session:
                                                session.run(cypher, {
                                                   'source_name': source_name,
                                                   'target_name': target_name,
                                                   'confidence': rel.get('confidence', 0.8)
                                                })
                                            
                                            total_rels_added += 1
                                            
                                        except Exception as e:
                                            logger.error(f"Failed to write relationship: {e}")
                                            
                                else:
                                    print("  -> No relationships found.")
                            else:
                                print(f"  -> Abstract not found for {paper_id}")
                                continue
                        else:
                            print(f"  -> Failed to fetch arxiv data: {response.status}")
                            continue
                            
                    # Rate limit kindness
                    await asyncio.sleep(3) 
                    
                except Exception as e:
                    print(f"  -> Error fetching arxiv: {e}")
                    import traceback
                    traceback.print_exc()
                    continue


                        
        except Exception as e:
            print(f"Global Error: {e}")
            import traceback
            traceback.print_exc()
                
        print(f"\nBackfill Complete. Added {total_rels_added} semantic relationships.")
        


if __name__ == "__main__":
    asyncio.run(backfill_relationships())
