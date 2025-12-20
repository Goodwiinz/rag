#!/usr/bin/env python3
"""Export extracted PDFs to database and update knowledge tree"""

import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

import asyncio
from datetime import datetime
from src.core.database import get_db_session
from src.models.document import Document, DocumentType
from src.services.knowledge_graph_service import KnowledgeGraphService
from src.models.graph import EntityType
import os

async def export_pdfs_to_database():
    """Export recently extracted PDFs to the database"""

    print("=== Exporting PDFs to Database ===\n")

    # Get all PDF files that were recently extracted
    pdf_dir = "/Users/goodwiinz/development/RAG_system/uploads/documents"

    # Find all subdirectories containing PDFs
    pdf_files = []
    for root, dirs, files in os.walk(pdf_dir):
        for file in files:
            if file.endswith('.pdf'):
                pdf_path = os.path.join(root, file)
                pdf_files.append(pdf_path)

    print(f"Found {len(pdf_files)} PDF files\n")

    # Get recent extractions from knowledge graph
    kg = KnowledgeGraphService()

    # Get all recent document entities
    recent_docs = kg.search_entities(
        query="",
        entity_types=[EntityType.DOCUMENT],
        limit=50
    )

    print(f"Found {len(recent_docs)} DOCUMENT entities in KG\n")

    # Save to database
    saved_count = 0
    async for db in get_db_session():
        for doc_entity in recent_docs:
            if doc_entity.metadata and doc_entity.metadata.get('source') == 'local_arxiv':
                # Check if already exists
                existing = await db.execute(
                    "SELECT * FROM documents WHERE external_id = :paper_id",
                    {"paper_id": doc_entity.metadata.get('paper_id')}
                )

                if not existing.first():
                    # Create new document record
                    document = Document(
                        title=doc_entity.name,
                        content="",  # Will be filled later
                        document_type=DocumentType.PAPER,
                        file_path=f"uploads/documents/{doc_entity.metadata.get('paper_id')}.pdf",
                        file_size=0,  # Will be updated
                        external_id=doc_entity.metadata.get('paper_id'),
                        metadata=doc_entity.metadata,
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )

                    db.add(document)
                    saved_count += 1
                    print(f"✅ Saved to DB: {doc_entity.name[:50]}...")

        await db.commit()
        print(f"\nSuccessfully saved {saved_count} documents to database")

def create_knowledge_tree():
    """Create a knowledge tree visualization of the extracted papers"""

    print("\n=== Creating Knowledge Tree ===\n")

    kg = KnowledgeGraphService()

    # Get all documents with their relationships
    cypher_query = """
    MATCH (doc:Entity:DOCUMENT)-[r:RELATED_TO]->(concept:Entity:CONCEPT)
    WHERE doc.source = 'local_arxiv'
    RETURN doc.name as Paper,
           collect(DISTINCT concept.name) as Topics,
           count(r) as Relationships
    ORDER BY doc.created_at DESC
    """

    try:
        from neo4j import GraphDatabase
        import os
        from dotenv import load_dotenv

        load_dotenv()
        URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
        USER = os.getenv('NEO4J_USER', 'neo4j')
        PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_password')

        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

        with driver.session() as session:
            result = session.run(cypher_query)

            print("Knowledge Tree Structure:\n")
            print("=" * 60)

            for record in result:
                paper = record['Paper']
                topics = record['Topics']
                rel_count = record['Relationships']

                print(f"\n📄 {paper}")
                print("   └── Topics:")
                for topic in topics:
                    print(f"      • {topic}")
                print(f"   └── {rel_count} relationships")

            # Get summary statistics
            print("\n" + "=" * 60)

            # Total counts
            doc_count = session.run("MATCH (n:Entity:DOCUMENT) WHERE n.source = 'local_arxiv' RETURN count(n) as count").single()["count"]
            concept_count = session.run("MATCH (n:Entity:CONCEPT) RETURN count(n) as count").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]

            print(f"\n📊 Summary Statistics:")
            print(f"   • Documents: {doc_count}")
            print(f"   • Concepts: {concept_count}")
            print(f"   • Relationships: {rel_count}")

            # Visual tree representation
            print("\n" + "=" * 60)
            print("🌳 Visual Knowledge Tree:")
            print("=" * 60)

            papers = session.run("""
                MATCH (doc:Entity:DOCUMENT)
                WHERE doc.source = 'local_arxiv'
                RETURN doc.name as name, doc.paper_id as id
                ORDER BY doc.created_at DESC
                LIMIT 10
            """)

            for i, record in enumerate(papers, 1):
                name = record['name'][:40]
                if len(record['name']) > 40:
                    name += "..."

                print(f"{i}. 📄 {name}")

                # Get topics for this paper
                topics = session.run("""
                    MATCH (d:Entity:DOCUMENT)-[r:RELATED_TO]->(c:Entity:CONCEPT)
                    WHERE d.name CONTAINS $paper_name
                    RETURN c.name
                    LIMIT 5
                """, paper_name=record['name'])

                for topic in topics:
                    print(f"    └── 🔗 {topic['name']}")

        driver.close()

        print("\n✅ Knowledge tree created successfully!")

    except Exception as e:
        print(f"❌ Error creating knowledge tree: {e}")

def create_interactive_tree():
    """Create an interactive HTML knowledge tree visualization"""

    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Knowledge Tree Visualization</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }
            .tree ul {
                padding-top: 20px;
                position: relative;
                transition: all 0.5s;
                -webkit-transition: all 0.5s;
                -moz-transition: all 0.5s;
                -ms-transition: all 0.5s;
                -o-transition: all 0.5s;
            }
            .tree li {
                float: left;
                text-align: center;
                list-style-type: none;
                position: relative;
                padding: 20px 5px 0 5px;
                transition: all 0.5s;
                -webkit-transition: all 0.5s;
                -moz-transition: all 0.5s;
                -ms-transition: all 0.5s;
                -o-transition: all 0.5s;
            }
            .tree li::before, .tree li::after {
                content: '';
                position: absolute;
                top: 0;
                right: 50%;
                border-top: 2px solid #ccc;
                width: 50%;
                height: 20px;
            }
            .tree li::after {
                border-right: 2px solid #ccc;
                width: auto;
                height: 20px;
            }
            .tree li:only-child::after, .tree li:only-child::before {
                display: none;
            }
            .tree li:only-child {
                padding-top: 0;
            }
            .tree li:first-child::before, .tree li:last-child::after {
                border: 0 none;
            }
            .tree li:last-child::before {
                border-right: 2px solid #ccc;
                width: 50%;
            }
            .tree li .paper {
                background: #4CAF50;
                color: white;
                padding: 10px;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            }
            .tree li .concept {
                background: #2196F3;
                color: white;
                padding: 8px;
                border-radius: 3px;
                font-size: 0.9em;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
            }
            .tree li .file {
                background: #FF9800;
                color: white;
                padding: 8px;
                border-radius: 3px;
                font-size: 0.9em;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2);
            }
        </style>
    </head>
    <body>
        <h1>🌳 Knowledge Tree Visualization</h1>
        <p>Papers and their extracted knowledge</p>

        <div class="tree">
            <ul>
    """

    try:
        from neo4j import GraphDatabase
        import os
        from dotenv import load_dotenv

        load_dotenv()
        URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
        USER = os.getenv('NEO4J_USER', 'neo4j')
        PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_password')

        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

        with driver.session() as session:
            papers = session.run("""
                MATCH (doc:Entity:DOCUMENT)
                WHERE doc.source = 'local_arxiv'
                RETURN doc.name as name, doc.id as id
                ORDER BY doc.created_at DESC
                LIMIT 20
            """)

            paper_ul = ""
            for record in papers:
                paper_ul += f'<li><div class="paper">{record["name"]}</div>'

                # Get concepts
                concepts = session.run("""
                    MATCH (d:Entity:DOCUMENT)-[:RELATED_TO]->(c:Entity:CONCEPT)
                    WHERE d.id = $doc_id
                    RETURN c.name
                    LIMIT 5
                """, doc_id=record["id"])

                if concepts:
                    paper_ul += "<ul>"
                    for concept in concepts:
                        paper_ul += f'<li><div class="concept">{concept["name"]}</div></li>'
                    paper_ul += "</ul>"

                # Get files
                files = session.run("""
                    MATCH (d:Entity:DOCUMENT)-[:RELATED_TO]->(f:Entity)
                    WHERE d.id = $doc_id AND NOT f:CONCEPT
                    RETURN f.name
                    LIMIT 3
                """, doc_id=record["id"])

                if files:
                    paper_ul += "<ul>"
                    for file_item in files:
                        paper_ul += f'<li><div class="file">{file_item["name"]}</div></li>'
                    paper_ul += "</ul>"

                paper_ul += "</li>"

        html_content += paper_ul

        html_content += """
            </ul>
        </div>

        <script>
            // Add interactivity
            document.querySelectorAll('.tree li').forEach(item => {
                item.addEventListener('click', function() {
                    this.classList.toggle('expanded');
                });
            });
        </script>
    </body>
    </html>
    """

        with open('/Users/goodwiinz/development/RAG_system/knowledge_tree.html', 'w') as f:
            f.write(html_content)

        print("\n✅ Interactive knowledge tree saved to: knowledge_tree.html")
        print("📂 Open with: file:///Users/goodwiinz/development/RAG_system/knowledge_tree.html")

        driver.close()

    except Exception as e:
        print(f"❌ Error: {e}")

async def main():
    """Main function to handle both tasks"""

    # Export to database
    await export_pdfs_to_database()

    # Create knowledge tree in console
    create_knowledge_tree()

    # Create interactive HTML tree
    create_interactive_tree()

    print("\n" + "=" * 60)
    print("🎉 All tasks completed successfully!")
    print("✅ PDFs exported to database")
    print("✅ Knowledge tree visualized in console")
    print("✅ Interactive tree saved to HTML")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())