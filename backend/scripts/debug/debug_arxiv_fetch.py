
import asyncio
import logging
from src.services.arxiv import ArxivService as ArXivIngestionService

# Setup logging
logging.basicConfig(level=logging.INFO)

async def check_paper_title():
    service = ArXivIngestionService()
    async with service:
        # Search for the specific paper ID mentioned in the export
        query = "id:2512.15687v1" 
        # Note: Arxiv query syntax for ID usually doesn't include version, but let's try strict ID
        # or just "2512.15687". The export said 'paper_id': '2512.15687v1'.
        # The split('/')[-1] in parser might keep the v1 if present.
        
        print(f"Searching for {query}...")
        papers = await service.search_papers(query=query, max_results=1)
        
        if papers:
            print("\n--- Paper Metadata ---")
            print(f"ID: {papers[0]['id']}")
            print(f"Title: '{papers[0]['title']}'")
            print(f"Authors: {papers[0]['authors']}")
        else:
            print("No paper found.")

            # Try without version
            query = "id:2512.15687"
            print(f"\nSearching for {query}...")
            papers = await service.search_papers(query=query, max_results=1)
            if papers:
                print("\n--- Paper Metadata ---")
                print(f"ID: {papers[0]['id']}")
                print(f"Title: '{papers[0]['title']}'")
            else:
                print("Still no paper.")

if __name__ == "__main__":
    asyncio.run(check_paper_title())
