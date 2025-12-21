#!/usr/bin/env python3
<arg_value>import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from src.services.knowledge_graph_service import KnowledgeGraphService
from src.models.graph import EntityType
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

def create_knowledge_tree():
    """Create a knowledge tree visualization of the extracted papers"""

    print("=== Creating Knowledge Tree ===\n")

    kg = KnowledgeGraphService()
    load_dotenv()

    # Get Neo4j connection details
    URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
    USER = os.getenv('NEO4J_USER', 'neo4j')
    PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_password')

    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

        with driver.session() as session:
            print("🌳 Knowledge Tree - Papers and Topics:")
            print("=" * 60)

            # Get all local arxiv papers with their topics
            query = """
            MATCH (doc:Entity:DOCUMENT)
            WHERE doc.source = 'local_arxiv'
            OPTIONAL MATCH (doc)-[r:RELATED_TO]->(concept:Entity:CONCEPT)
            WITH doc, collect(DISTINCT concept.name) as Topics
            RETURN doc.name as Paper, doc.paper_id as ID, Topics,
                   size(Topics) as TopicCount
            ORDER BY doc.created_at DESC
            """

            result = session.run(query)

            for record in result:
                paper = record['Paper']
                topics = record['Topics']
                topic_count = record['TopicCount']

                # Clean up paper name
                if paper.startswith('ArXiv Paper: '):
                    paper = paper[12:]  # Remove "ArXiv Paper: " prefix

                print(f"\n📄 {paper}")
                print(f"   📋 ID: {record['ID']}")
                print(f"   🏷️  Topics ({topic_count}):")

                for topic in topics[:5]:  # Show up to 5 topics
                    print(f"      • {topic}")

            print("\n" + "=" * 60)

            # Summary statistics
            doc_query = "MATCH (n:Entity:DOCUMENT) WHERE n.source = 'local_arxiv' RETURN count(n) as count"
            doc_count = session.run(doc_query).single()["count"]

            concept_query = "MATCH (n:Entity:CONCEPT) RETURN count(n) as count"
            concept_count = session.run(concept_query).single()["count"]

            rel_query = "MATCH ()-[r:RELATED_TO]->() RETURN count(r) as count"
            rel_count = session.run(rel_query).single()["count"]

            print(f"\n📊 Knowledge Graph Statistics:")
            print(f"   • Local ArXiv Papers: {doc_count}")
            print(f"   • Concepts Extracted: {concept_count}")
            print(f"   • Relationships Created: {rel_count}")

            # Show relationships
            print("\n" + "=" * 60)
            print("🔗 Recent Relationships:")

            rel_query = """
            MATCH (doc:Entity:DOCUMENT)-[r:RELATED_TO]->(concept:Entity:CONCEPT)
            WHERE doc.source = 'local_arxiv'
            RETURN doc.name as Paper, concept.name as Concept, r.created_at as Created
            ORDER BY r.created_at DESC
            LIMIT 15
            """

            rel_result = session.run(rel_query)
            for record in rel_result:
                created = str(record['Created'])[:19] if record['Created'] else "Unknown"
                print(f"   • {record['Paper'][:40]}... → {record['Concept']} ({created})")

        driver.close()

        print("\n✅ Knowledge tree updated successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def save_to_html():
    """Save knowledge tree to HTML for better visualization"""

    print("\n" + "=" * 60)
    print("🌐 Creating HTML Visualization...")

    try:
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

        with driver.session() as session:
            papers = session.run("""
                MATCH (doc:Entity:DOCUMENT)
                WHERE doc.source = 'local_arxiv'
                RETURN doc.name, doc.id, doc.paper_id, doc.created_at
                ORDER BY doc.created_at DESC
                LIMIT 10
            """)

            html = """<!DOCTYPE html>
<html>
<head>
    <title>Knowledge Graph Visualization</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .paper {
            background: rgba(255,255,255,0.1);
            margin-bottom: 20px;
            padding: 20px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            transition: transform 0.3s;
        }
        .paper:hover { transform: translateY(-5px); }
        .paper-title {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #ffd700;
        }
        .topics {
            margin-top: 10px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .topic {
            background: rgba(76, 175, 80, 0.8);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            white-space: nowrap;
        }
        .stats {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }
        .stats h3 { margin: 0 0 10px 0; font-size: 1em; }
        .stats p { margin: 5px 0; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌳 Knowledge Graph Visualization</h1>
        <div class="stats">
            <h3>📊 Statistics</h3>
            <p>📄 Papers: <span id="docCount">0</span></p>
            <p>🧠 Concepts: <span id="conceptCount">0</span></p>
            <p>🔗 Relations: <span id="relCount">0</span></p>
        </div>
"""

            for record in papers:
                paper_name = record['name']
                if paper_name.startswith('ArXiv Paper: '):
                    paper_name = paper_name[12:]

                # Get topics for this paper
                topics_result = session.run("""
                    MATCH (d:Entity {id: $doc_id})-[r:RELATED_TO]->(c:Entity:CONCEPT)
                    RETURN c.name as topic
                    LIMIT 8
                """, doc_id=record['id'])

                html += f"""
                <div class="paper">
                    <div class="paper-title">{paper_name}</div>
                    <div class="paper-id">ID: {record.get('paper_id', 'N/A')}</div>
                    <div class="paper-date">Created: {record.get('created_at', 'N/A')}</div>
                    <div class="topics">
                """

                for topic in topics_result:
                    html += f'<span class="topic">{topic["topic"]}</span>'

                html += "</div></div>"

            # Get counts
            doc_count = session.run("MATCH (n:Entity:DOCUMENT) WHERE n.source = 'local_arxiv' RETURN count(n)").single()["count"]
            concept_count = session.run("MATCH (n:Entity:CONCEPT) RETURN count(n)").single()["count"]
            rel_count = session.run("MATCH ()-[r]->() RETURN count(r)").single()["count"]

            html = html.replace('<span id="docCount">0</span>', str(doc_count))
            html = html.replace('<span id="conceptCount">0</span>', str(concept_count))
            html = html.replace('<span id="relCount">0</span>', str(rel_count))
            html += """
        </div>
        <script>
            // Add animations
            setTimeout(() => {
                document.querySelectorAll('.paper').forEach((paper, i) => {
                    paper.style.opacity = '0';
                    paper.style.transform = 'translateY(20px)';
                    setTimeout(() => {
                        paper.style.transition = 'all 0.5s ease';
                        paper.style.opacity = '1';
                        paper.style.transform = 'translateY(0)';
                    }, i * 100);
                });
            }, 100);
        </script>
    </body>
    </html>
            """

            with open('/Users/goodwiinz/development/RAG_system/knowledge_tree.html', 'w') as f:
                f.write(html)

            print(f"\n✅ HTML visualization saved to: knowledge_tree.html")
            print(f"📂 Open: file:///Users/goodwiinz/development/RAG_system/knowledge_tree.html")
            print("\n💡 Features:")
            print("   - Interactive hover effects")
            print("   - Gradient background")
            print("   - Topic chips")
            print("   - Real-time statistics")

        driver.close()

    except Exception as e:
        print(f"❌ Error creating HTML: {e}")

def main():
    """Main function"""

    # Create text-based tree
    create_knowledge_tree()

    # Create HTML visualization
    save_to_html()

if __name__ == "__main__":
    main()