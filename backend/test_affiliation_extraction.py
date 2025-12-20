import asyncio
import logging
from src.services.arxiv_kg_integration import ArXivKnowledgeGraphIntegration
from src.services.arxiv_service import ArXivIngestionService

logging.basicConfig(level=logging.INFO)

async def test_extraction():
    config = {}
    integration = ArXivKnowledgeGraphIntegration(config)
    service = ArXivIngestionService(config)
    
    # "Attention Is All You Need" - likely has Google Brain / Google Research affiliation
    paper_id = "1706.03762" 
    
    # Extract Entities (including LLM based)
    print("Extracting entities...")
    async with integration:
        print(f"Fetching paper {paper_id}...")
        # We use search_papers with id_list
        papers = await integration.arxiv_service.search_papers(query=paper_id, max_results=1)
        
        if not papers:
            print("Paper not found.")
            return

        paper = papers[0]
        print(f"Title: {paper['title']}")
        
        # Check Metadata Affiliations
        if 'authors_detailed' in paper:
            print(f"Metadata Affiliations found: {len([a for a in paper['authors_detailed'] if a.get('affiliations')])}")
            for a in paper['authors_detailed']:
                if a.get('affiliations'):
                    print(f" - {a['name']}: {a['affiliations']}")
        else:
            print("No 'authors_detailed' field.")

        entities = await integration._extract_entities_from_paper(paper)
    
    print(f"Total Entities: {len(entities)}")
    print("--- Institutions ---")
    for e in entities:
        if e['type'] == 'institution' or e['type'] == 'ORGANIZATION':
            print(f" - {e['text']} (Source: {e.get('source')})")
            
    print("--- Topics ---")
    for e in entities:
        if e['type'] == 'topic':
            print(f" - {e['text']}")

if __name__ == "__main__":
    asyncio.run(test_extraction())
