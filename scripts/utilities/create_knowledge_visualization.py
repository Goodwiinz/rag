#!/usr/bin/env python3
import sys
sys.path.append('/Users/goodwiinz/development/RAG_system/backend')

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

# Get Neo4j connection details
URI = os.getenv('NEO4J_URI', 'bolt://127.0.0.1:7687')
USER = os.getenv('NEO4J_USER', 'neo4j')
PASSWORD = os.getenv('NEO4J_PASSWORD', 'neo4j_password')

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

    print("=== Knowledge Graph Visualization ===\n")

    with driver.session() as session:
        # Get all DOCUMENT entities with their relationships
        result = session.run("""
            MATCH (doc:Entity:DOCUMENT)
            OPTIONAL MATCH (doc)-[r:RELATED_TO]->(concept:Entity:CONCEPT)
            WITH doc, collect(DISTINCT concept.name) as Topics
            RETURN doc.name as Paper, doc.id as ID,
                   Topics,
                   size(Topics) as TopicCount,
                   doc.created_at as Created
            ORDER BY Created DESC
        """)

        papers = list(result)
        print(f"📄 Found {len(papers)} documents with topics\n")

        for paper in papers:
            paper_name = paper['Paper']
            topics = paper['Topics']
            topic_count = paper['TopicCount']

            print(f"📄 {paper_name}")
            print(f"   ID: {paper['ID'][:8]}...")
            print(f"   🏷️  Topics ({topic_count}):")

            for topic in topics[:5]:
                print(f"      • {topic}")
            print()

        # Summary statistics
        doc_count = session.run("MATCH (n:Entity:DOCUMENT) RETURN count(n) as count").single()["count"]
        concept_count = session.run("MATCH (n:Entity:CONCEPT) RETURN count(n) as count").single()["count"]
        rel_count = session.run("MATCH ()-[r:RELATED_TO]->() RETURN count(r) as count").single()["count"]

        print("=" * 60)
        print(f"📊 Knowledge Graph Statistics:")
        print(f"   • Documents: {doc_count}")
        print(f"   • Concepts: {concept_count}")
        print(f"   • Relationships: {rel_count}")

        # Show top concepts
        print("\n" + "=" * 60)
        print("🧠 Top Concepts (by connections):")

        top_concepts = session.run("""
            MATCH (c:Entity:CONCEPT)
            OPTIONAL MATCH (c)<-[r:RELATED_TO]-()
            WITH c, count(r) as connections
            RETURN c.name as Concept, connections
            ORDER BY connections DESC
            LIMIT 10
        """)

        for record in top_concepts:
            print(f"   • {record['Concept']}: {record['connections']} connections")

        # Create HTML content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Knowledge Graph Visualization</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .paper {{
            background: rgba(255,255,255,0.1);
            margin-bottom: 20px;
            padding: 20px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
            transition: transform 0.3s;
        }}
        .paper:hover {{ transform: translateY(-5px); }}
        .paper-title {{
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #ffd700;
        }}
        .topics {{
            margin-top: 10px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .topic {{
            background: rgba(76, 175, 80, 0.8);
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            white-space: nowrap;
        }}
        .stats {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }}
        .stats h3 {{ margin: 0 0 10px 0; font-size: 1em; }}
        .stats p {{ margin: 5px 0; font-size: 0.9em; }}
        .paper-id {{
            color: #ccc;
            font-size: 0.9em;
            margin-bottom: 5px;
        }}
        .paper-date {{
            color: #ccc;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🌳 Knowledge Graph Visualization</h1>
        <div class="stats">
            <h3>📊 Statistics</h3>
            <p>📄 Papers: <span id="docCount">{doc_count}</span></p>
            <p>🧠 Concepts: <span id="conceptCount">{concept_count}</span></p>
            <p>🔗 Relations: <span id="relCount">{rel_count}</span></p>
        </div>
"""

        # Add papers to HTML
        for paper in papers:
            paper_name = paper['Paper']
            topics = paper['Topics']
            created = str(paper.get('Created', ''))[:10]

            html_content += f"""
        <div class="paper">
            <div class="paper-title">{paper_name}</div>
            <div class="paper-id">ID: {paper['ID'][:8]}...</div>
            <div class="paper-date">Created: {created}</div>
            <div class="topics">
            """

            if topics and len(topics) > 0:
                for topic in topics[:10]:
                    html_content += f'<span class="topic">{topic}</span>'
            else:
                html_content += '<span class="topic">No topics extracted</span>'

            html_content += "</div></div>"

        html_content += """
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

        # Save HTML file
        with open('/Users/goodwiinz/development/RAG_system/knowledge_tree.html', 'w') as f:
            f.write(html_content)

        print("\n" + "=" * 60)
        print("🌐 HTML Visualization Created!")
        print(f"✅ Saved to: knowledge_tree.html")
        print(f"📂 Open: file:///Users/goodwiinz/development/RAG_system/knowledge_tree.html")
        print("\n💡 Features:")
        print("   - Interactive hover effects")
        print("   - Gradient background")
        print("   - Topic chips")
        print("   - Real-time statistics")

    driver.close()
    print("\n✅ Knowledge tree visualization completed successfully!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()