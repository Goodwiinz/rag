#!/usr/bin/env python3
"""
ArXiv CLI for RAG System

Command-line interface for managing arXiv paper ingestion and evaluation datasets.
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv(override=True)

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / "backend"))

from src.services.arxiv_service import ArXivIngestionService
from src.services.arxiv_kg_integration import ArXivKnowledgeGraphIntegration

# DocumentService import removed - not implemented yet
# from src.services.document_service import DocumentService


async def search_papers(args):
    """Search for papers on arXiv"""
    async with ArXivIngestionService() as service:
        papers = await service.search_papers(
            query=args.query,
            max_results=args.max_results,
            date_from=args.date_from,
            date_to=args.date_to,
            categories=args.categories,
            sort_by=args.sort_by,
            sort_order=args.sort_order
        )

        # Print results
        print(f"\nFound {len(papers)} papers:\n")
        for i, paper in enumerate(papers, 1):
            print(f"{i}. {paper['title']}")
            print(f"   ID: {paper['id']}")
            print(f"   Authors: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}")
            print(f"   Categories: {', '.join(paper['categories'])}")
            print(f"   Published: {paper['published'][:10]}")
            print(f"   Abstract: {paper['abstract'][:200]}...")
            print()

        # Save to file if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(papers, f, indent=2)
            print(f"Results saved to: {args.output}")


async def ingest_papers(args):
    """Ingest papers into the RAG system"""
    if args.input_file:
        # Load paper IDs from file
        with open(args.input_file, 'r') as f:
            if args.input_file.endswith('.json'):
                data = json.load(f)
                if isinstance(data, list):
                    papers = data
                else:
                    papers = data.get('papers', [])
                paper_ids = [p['id'] for p in papers]
            else:
                paper_ids = [line.strip() for line in f if line.strip()]
    elif args.query:
        # Search for papers first
        print(f"Searching for papers: {args.query}")
        async with ArXivIngestionService() as service:
            papers = await service.search_papers(
                query=args.query,
                max_results=args.max_results,
                categories=args.categories
            )
            paper_ids = [p['id'] for p in papers]
    else:
        print("Error: Either --input-file or --query must be specified")
        return

    print(f"\nIngesting {len(paper_ids)} papers...")
    print(f"Download PDFs: {args.download_pdfs}")
    print(f"Extract content: {args.extract_content}")
    print(f"Extract entities: {args.extract_entities}")
    print(f"Batch size: {args.batch_size}\n")

    # Get paper metadata
    async with ArXivIngestionService() as arxiv_service:
        all_papers = []
        for paper_id in paper_ids:
            results = await arxiv_service.search_papers(
                query=f"id:{paper_id}",
                max_results=1
            )
            if results:
                all_papers.extend(results)

        if all_papers:
            # Ingest papers
            documents = await arxiv_service.ingest_papers(
                papers=all_papers,
                download_pdfs=args.download_pdfs,
                extract_content=args.extract_content,
                batch_size=args.batch_size
            )

            # Save to database (if implemented)
            # Save to database (if implemented)
            if args.save_to_db:
                print("\nSaving documents to Vector Database...")
                try:
                    from src.services.vector_search_service import vector_search_service
                    
                    saved_count = 0
                    for doc in documents:
                        # Use asyncio.to_thread to run the sync service method (which might use asyncio.run internally)
                        # This avoids "asyncio.run() cannot be called from a running event loop" error
                        result = await asyncio.to_thread(
                            vector_search_service.index_document,
                            document_id=doc.metadata.get('arxiv_id', doc.filename),
                            text=doc.content_text,
                            organization_id="system", # Default org
                            metadata=doc.metadata
                        )
                        
                        if result.success:
                            saved_count += 1
                            print(f"✓ Indexed: {doc.metadata.get('title', 'Unknown')[:50]}...")
                        else:
                            print(f"✗ Failed to index {doc.metadata.get('id', 'unknown')}: {result.message}")
                            
                    print(f"Successfully saved {saved_count}/{len(documents)} documents to Vector DB")
                    
                except ImportError as e:
                    print(f"Error importing VectorSearchService: {e}")
                except Exception as e:
                    print(f"Error saving to database: {e}")
                    import traceback
                    traceback.print_exc()

            print(f"\nSuccessfully ingested {len(documents)}/{len(all_papers)} papers")

            # Extract entities and add to knowledge graph if requested
            if args.extract_entities:
                print("\nExtracting entities and adding to knowledge graph...")
                try:
                    async with ArXivKnowledgeGraphIntegration() as kg_integration:
                        kg_count = 0
                        for paper in all_papers:
                            result = await kg_integration.process_paper_kg_integration(paper)
                            if result:
                                kg_count += 1
                        print(f"✓ Processed {kg_count} papers for knowledge graph")
                except Exception as e:
                    print(f"✗ Knowledge graph processing failed: {e}")
        else:
            print("No papers found to ingest")


async def create_dataset(args):
    """Create evaluation dataset"""
    print(f"Creating evaluation dataset...")
    print(f"Query: {args.query}")
    print(f"Number of papers: {args.num_papers}")
    print(f"Questions per paper: {args.questions_per_paper}\n")

    async with ArXivIngestionService() as service:
        # Search for papers
        papers = await service.search_papers(
            query=args.query,
            max_results=args.num_papers,
            categories=args.categories
        )

        if papers:
            # Create evaluation dataset
            dataset = await service.create_evaluation_dataset(
                papers=papers,
                num_questions=args.questions_per_paper,
                difficulty_levels=args.difficulty_levels
            )

            print(f"\nCreated evaluation dataset:")
            print(f"  Total test cases: {len(dataset['test_cases'])}")
            print(f"  Total questions: {len(dataset['test_cases']) * args.questions_per_paper}")
            print(f"  Dataset saved to: {service.download_dir / 'evaluation_dataset.json'}")

            # Print sample questions
            print("\nSample questions:")
            for i, test_case in enumerate(dataset['test_cases'][:3]):
                print(f"\nPaper: {test_case['paper_title'][:60]}...")
                for question in test_case['questions'][:2]:
                    print(f"  Q{question['id'].split('_')[-1]}: {question['question']} [{question['difficulty']}]")
        else:
            print("No papers found for the given query")


async def show_statistics(args):
    """Show arXiv statistics"""
    date_to = datetime.now()
    date_from = date_to - timedelta(days=args.days)

    print(f"ArXiv Statistics (Last {args.days} days)")
    print(f"From: {date_from.strftime('%Y-%m-%d')}")
    print(f"To: {date_to.strftime('%Y-%m-%d')}\n")

    async with ArXivIngestionService() as service:
        # Build query with date range
        query = args.query or "all"
        papers = await service.search_papers(
            query=query,
            max_results=1000,
            date_from=date_from,
            date_to=date_to
        )

        # Get statistics
        stats = service.get_category_statistics(papers)

        print(f"Total papers: {stats['total_papers']}")
        print(f"Unique categories: {stats['unique_categories']}\n")

        print("Top 10 Categories:")
        for category, count in stats['top_categories'][:10]:
            print(f"  {category}: {count}")

        print("\nCategory Groups:")
        for group, count in stats['group_distribution'].items():
            if count > 0:
                print(f"  {group}: {count}")


async def download_pdfs(args):
    """Download PDFs for specified papers"""
    print(f"Downloading PDFs for {len(args.paper_ids)} papers...\n")

    async with ArXivIngestionService() as service:
        success_count = 0

        for paper_id in args.paper_ids:
            try:
                print(f"Downloading {paper_id}...", end=" ")
                content = await service.download_paper_pdf(paper_id)
                if content:
                    print(f"✓ ({len(content)} bytes)")
                    success_count += 1
                else:
                    print("✗ Failed")
            except Exception as e:
                print(f"✗ Error: {e}")

        print(f"\nSuccessfully downloaded {success_count}/{len(args.paper_ids)} PDFs")
        print(f"Saved to: {service.download_dir}")


def parse_date(date_str: str) -> datetime:
    """Parse date string in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")


def main():
    parser = argparse.ArgumentParser(description="ArXiv CLI for RAG System")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search for papers on arXiv')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--max-results', type=int, default=50, help='Maximum results (default: 50)')
    search_parser.add_argument('--categories', nargs='+', help='Categories to filter by')
    search_parser.add_argument('--date-from', type=parse_date, help='Start date (YYYY-MM-DD)')
    search_parser.add_argument('--date-to', type=parse_date, help='End date (YYYY-MM-DD)')
    search_parser.add_argument('--sort-by', default='submittedDate', help='Sort field')
    search_parser.add_argument('--sort-order', default='descending', help='Sort order')
    search_parser.add_argument('--output', help='Save results to file')

    # Ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest papers into the RAG system')
    group = ingest_parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--input-file', help='File with paper IDs or JSON metadata')
    group.add_argument('--query', help='Search query to find papers')
    ingest_parser.add_argument('--max-results', type=int, default=100, help='Maximum papers to ingest (with --query)')
    ingest_parser.add_argument('--categories', nargs='+', help='Categories to filter (with --query)')
    ingest_parser.add_argument('--download-pdfs', action='store_true', default=True, help='Download PDF files')
    ingest_parser.add_argument('--no-pdf', dest='download_pdfs', action='store_false', help='Skip PDF download')
    ingest_parser.add_argument('--extract-content', action='store_true', default=True, help='Extract full text content')
    ingest_parser.add_argument('--no-extract', dest='extract_content', action='store_false', help='Skip content extraction')
    ingest_parser.add_argument('--batch-size', type=int, default=10, help='Batch size for processing')
    ingest_parser.add_argument('--save-to-db', action='store_true', default=True, help='Save to database')
    ingest_parser.add_argument('--extract-entities', action='store_true', help='Extract entities and add to knowledge graph')

    # Dataset command
    dataset_parser = subparsers.add_parser('dataset', help='Create evaluation dataset')
    dataset_parser.add_argument('--query', default='machine learning', help='Search query')
    dataset_parser.add_argument('--num-papers', type=int, default=50, help='Number of papers')
    dataset_parser.add_argument('--questions-per-paper', type=int, default=5, help='Questions per paper')
    dataset_parser.add_argument('--difficulty-levels', nargs='+', default=['easy', 'medium', 'hard'], help='Difficulty levels')
    dataset_parser.add_argument('--categories', nargs='+', help='Categories to filter')

    # Statistics command
    stats_parser = subparsers.add_parser('stats', help='Show arXiv statistics')
    stats_parser.add_argument('--days', type=int, default=30, help='Number of days to look back')
    stats_parser.add_argument('--query', help='Filter by query')

    # Download command
    download_parser = subparsers.add_parser('download', help='Download PDFs for specific papers')
    download_parser.add_argument('paper_ids', nargs='+', help='ArXiv paper IDs')

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Execute command
    try:
        if args.command == 'search':
            asyncio.run(search_papers(args))
        elif args.command == 'ingest':
            asyncio.run(ingest_papers(args))
        elif args.command == 'dataset':
            asyncio.run(create_dataset(args))
        elif args.command == 'stats':
            asyncio.run(show_statistics(args))
        elif args.command == 'download':
            asyncio.run(download_pdfs(args))
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()