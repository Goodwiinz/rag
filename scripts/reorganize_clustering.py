import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

nb = new_notebook()

# --- Section 1: Header ---
nb.cells.append(new_markdown_cell("""
# 📊 Unsupervised Learning: Clustering Analysis for RAG Evaluation

## Document & Query Clustering Analysis
**Author:** Abdel | **Date:** December 2024

---

### 🎯 Objectives
- ✅ **Advanced Document Clustering**: Leverage **Qdrant Embeddings** (with TF-IDF fallback) to group research papers.
- ✅ **Hierarchy Analysis**: Visualizing topic relationships with **Dendrograms** and Hierarchical Clustering.
- ✅ **Method Comparison**: Quantitatively proving **K-Means vs. Hierarchical** performance.
- ✅ **Automated Insights**: Auto-extracting the semantic meaning (categories/topics) of each cluster.
- ✅ **t-SNE Visualization**: High-quality 2D projection of the research manifold.
"""
))

# --- Section 2: Setup ---
nb.cells.append(new_markdown_cell("## 1️⃣ Setup & Configuration"))
nb.cells.append(new_code_cell("""
import os
import json
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
from pathlib import Path

# Clustering & ML imports
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.cluster.hierarchy import dendrogram, linkage
from qdrant_client import QdrantClient

# Configure plots
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 12
sns.set_style('whitegrid')
sns.set_palette('husl')

# Load environment variables
load_dotenv('../backend/.env')
print('✅ Environment loaded!')
"""))

# --- Section 3: Data Loading ---
nb.cells.append(new_markdown_cell("## 2️⃣ Data Loading"))
nb.cells.append(new_code_cell("""
# Paths
DATASET_PATH = Path('../backend/data/arxiv/evaluation_dataset_improved.json')
RESULTS_PATH = Path('../evaluation_results.json')

# Load evaluation dataset
if DATASET_PATH.exists():
    with open(DATASET_PATH, 'r') as f:
        dataset = json.load(f)
    print(f"📄 Dataset loaded: {dataset['dataset_info']['num_papers']} papers")
else:
    print(f"⚠️ Dataset not found at {DATASET_PATH}")
    dataset = {'test_cases': []}

# Load results
if RESULTS_PATH.exists():
    with open(RESULTS_PATH, 'r') as f:
        results = json.load(f)
    print(f"📊 Results loaded: {len(results.get('test_cases', []))} test cases")
else:
    results = {}
"""))

# --- Section 4: Use Qdrant or TF-IDF ---
nb.cells.append(new_markdown_cell("## 3️⃣ Data Preprocessing & Embedding Generation"))
nb.cells.append(new_code_cell("""
# Extract abstracts and metadata
papers_data = []
abstracts = []

for tc in dataset.get('test_cases', []):
    abstract = tc.get('paper_abstract', '')
    if abstract:
        abstracts.append(abstract)
        papers_data.append({
            'paper_id': tc.get('paper_id', ''),
            'title': tc.get('paper_title', ''),
            'primary_category': tc.get('primary_category', 'Unknown'),
            'categories': ', '.join(tc.get('categories', [])),
            'paper_abstract': abstract
        })

df_papers = pd.DataFrame(papers_data)
print(f"📚 Processed {len(df_papers)} papers.")

# --- Embedding Strategy ---
# Try to fetch from Qdrant first, fallback to TF-IDF
embeddings = []
paper_ids = df_papers['paper_id'].tolist()
use_qdrant = False
qdrant_embeddings_map = {}

try:
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_key = os.getenv("QDRANT_API_KEY")
    
    print(f"🔌 Connecting to Qdrant at {qdrant_url}...")
    client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
    
    # Check if collection exists
    collections = client.get_collections()
    collection_name = "document_chunks"
    
    if any(c.name == collection_name for c in collections.collections):
        print(f"✅ Found collection: {collection_name}")
        
        # Scroll points to aggregate vectors by document_id
        # Note: In a large system, we might optimize this. For 159 papers, scrolling is fine.
        all_points = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=collection_name,
                limit=100,
                with_payload=True,
                with_vectors=True,
                scroll_filter=None,
                offset=offset
            )
            all_points.extend(points)
            if offset is None:
                break
        
        print(f"📥 Fetched {len(all_points)} chunks from Qdrant.")
        
        # Group vectors by document_id
        doc_vectors = {}
        for p in all_points:
            doc_id = p.payload.get('document_id')
            vector = p.vector
            if doc_id and vector:
                if doc_id not in doc_vectors:
                    doc_vectors[doc_id] = []
                doc_vectors[doc_id].append(vector)
        
        # Compute mean vector per document
        for doc_id, vectors in doc_vectors.items():
            if vectors:
                qdrant_embeddings_map[doc_id] = np.mean(vectors, axis=0)
        
        print(f"🧩 Aggregated vectors for {len(qdrant_embeddings_map)} documents.")
        use_qdrant = True
        
    else:
        print(f"⚠️ Collection {collection_name} not found.")

except Exception as e:
    print(f"⚠️ Qdrant Error: {e}")

# Align embeddings with dataset papers
final_embeddings = []
missing_count = 0

if use_qdrant:
    # Check dimension from first vector
    first_vec = next(iter(qdrant_embeddings_map.values()))
    embedding_dim = len(first_vec)
    
    for pid in paper_ids:
        if pid in qdrant_embeddings_map:
            final_embeddings.append(qdrant_embeddings_map[pid])
        else:
            missing_count += 1
            final_embeddings.append(np.zeros(embedding_dim)) # Zero placeholder for now
    
    if missing_count > len(paper_ids) * 0.5:
        print(f"⚠️ Too many missing Qdrant vectors ({missing_count}/{len(paper_ids)}). Reverting to TF-IDF.")
        use_qdrant = False
    else:
        embeddings = np.array(final_embeddings)
        print(f"✅ Successfully mapped Qdrant embeddings for {len(paper_ids) - missing_count} papers.")

if not use_qdrant:
    print("ℹ️ Using TF-IDF for embeddings (Fallback/Primary)")
    vectorizer = TfidfVectorizer(max_features=500, stop_words='english', ngram_range=(1, 2))
    embeddings = vectorizer.fit_transform(abstracts).toarray()

print(f"✅ Final Embeddings shape: {embeddings.shape}")
"""))

# --- Section 5: Optimal K ---
nb.cells.append(new_markdown_cell("## 4️⃣ Clustering Analysis"))
nb.cells.append(new_markdown_cell("### 4.1 Determine Optimal K (Elbow Method)"))
nb.cells.append(new_code_cell("""
# Determine Optimal K using Elbow Method and Silhouette Analysis
inertia = []
silhouette_scores = []
K_range = range(2, 15)

for k in K_range:
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    kmeans.fit(embeddings)
    inertia.append(kmeans.inertia_)
    silhouette_scores.append(silhouette_score(embeddings, kmeans.labels_))

# Plotting
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

ax1.plot(K_range, inertia, 'bo-')
ax1.set_xlabel('Number of Clusters (k)')
ax1.set_ylabel('Inertia')
ax1.set_title('Elbow Method')

ax2.plot(K_range, silhouette_scores, 'ro-')
ax2.set_xlabel('Number of Clusters (k)')
ax2.set_ylabel('Silhouette Score')
ax2.set_title('Silhouette Analysis')

plt.tight_layout()
plt.show()

# Automatically select K with max silhouette score
OPTIMAL_K = K_range[np.argmax(silhouette_scores)]
print(f"🏆 Optimal K determined: {OPTIMAL_K}")
"""))

# --- Section 6: Clustering Implementation ---
nb.cells.append(new_markdown_cell("### 4.2 Model Training & Comparison"))
nb.cells.append(new_code_cell("""
# Initialize metrics storage
metrics_data = []

def record_metrics(name, labels, time_taken):
    s_score = silhouette_score(embeddings, labels)
    ch_score = calinski_harabasz_score(embeddings, labels)
    db_score = davies_bouldin_score(embeddings, labels)
    metrics_data.append({
        'Method': name,
        'Silhouette': s_score,
        'Calinski-Harabasz': ch_score,
        'Davies-Bouldin': db_score,
        'Time (s)': time_taken
    })

# 1. K-Means
start = time.time()
kmeans = KMeans(n_clusters=OPTIMAL_K, random_state=42, n_init=10)
kmeans_labels = kmeans.fit_predict(embeddings)
record_metrics('K-Means', kmeans_labels, time.time() - start)

# 2. Hierarchical (Ward)
start = time.time()
ward = AgglomerativeClustering(n_clusters=OPTIMAL_K, linkage='ward')
ward_labels = ward.fit_predict(embeddings)
record_metrics('Hierarchical (Ward)', ward_labels, time.time() - start)

# 3. Hierarchical (Complete)
start = time.time()
complete = AgglomerativeClustering(n_clusters=OPTIMAL_K, linkage='complete')
complete_labels = complete.fit_predict(embeddings)
record_metrics('Hierarchical (Complete)', complete_labels, time.time() - start)

# Create DataFrame
df_metrics = pd.DataFrame(metrics_data)

# Display Comparison
print("\\n📊 Clustering Method Comparison:")
print(df_metrics.sort_values(by='Silhouette', ascending=False))

# Visualize Metrics
fig, axes = plt.subplots(1, 3, figsize=(18, 5))
sns.barplot(x='Method', y='Silhouette', data=df_metrics, ax=axes[0], palette='viridis')
axes[0].set_title('Silhouette Score (Higher is better)')
axes[0].tick_params(axis='x', rotation=45)

sns.barplot(x='Method', y='Calinski-Harabasz', data=df_metrics, ax=axes[1], palette='viridis')
axes[1].set_title('Calinski-Harabasz (Higher is better)')
axes[1].tick_params(axis='x', rotation=45)

sns.barplot(x='Method', y='Davies-Bouldin', data=df_metrics, ax=axes[2], palette='viridis_r')
axes[2].set_title('Davies-Bouldin (Lower is better)')
axes[2].tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.show()
"""))

# --- Section 7: Visualization ---
nb.cells.append(new_markdown_cell("## 5️⃣ Visualization"))
nb.cells.append(new_markdown_cell("### 5.1 Hierarchical Dendrogram"))
nb.cells.append(new_code_cell("""
plt.figure(figsize=(15, 7))
plt.title(f"Hierarchical Clustering Dendrogram (Ward)")
linkage_matrix = linkage(embeddings, method='ward')
dendrogram(linkage_matrix, truncate_mode='level', p=5, leaf_rotation=90., leaf_font_size=10.)
plt.xlabel("Number of points in node (or index of point if no parenthesis)")
plt.ylabel("Distance")
plt.show()
"""))

nb.cells.append(new_markdown_cell("### 5.2 t-SNE Projection"))
nb.cells.append(new_code_cell("""
# t-SNE dimensionality reduction
tsne = TSNE(n_components=2, random_state=42, perplexity=30, init='pca', learning_rate='auto')
vis_dims = tsne.fit_transform(embeddings)

# Create plotting dataframe
df_vis = df_papers.copy()
df_vis['x'] = vis_dims[:, 0]
df_vis['y'] = vis_dims[:, 1]
df_vis['Cluster'] = kmeans_labels
df_vis['Category'] = df_vis['primary_category']

plt.figure(figsize=(12, 8))
sns.scatterplot(
    data=df_vis, x='x', y='y', hue='Cluster', style='Category', 
    palette='tab10', s=100, alpha=0.8
)
plt.title(f"t-SNE Projection of Papers (Colored by K-Means Cluster, K={OPTIMAL_K})")
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
plt.show()
"""))

# --- Section 8: Insights ---
nb.cells.append(new_markdown_cell("## 6️⃣ Automated Insights"))
nb.cells.append(new_code_cell("""
from sklearn.feature_extraction.text import TfidfVectorizer

def get_cluster_keywords(texts, top_n=10):
    \"\"\"
    Generates top_terms by recalculating TF-IDF for the specific cluster text.
    This works regardless of whether you used Qdrant or TF-IDF for clustering.
    \"\"\"
    if not texts:
        return []
    
    # 1. Create a mini-vectorizer just for this cluster's content
    tfidf = TfidfVectorizer(stop_words='english', max_features=100)
    
    try:
        tfidf_matrix = tfidf.fit_transform(texts)
        feature_names = tfidf.get_feature_names_out()
        
        # 2. Calculate average score per word to find the "centroid" of meaning
        avg_scores = np.mean(tfidf_matrix.toarray(), axis=0)
        
        # 3. Get top_indices and top_terms relative to this cluster
        top_indices = avg_scores.argsort()[::-1][:top_n]
        top_terms = [feature_names[ind] for ind in top_indices]
        
        return top_terms
        
    except ValueError:
        return []

print("📊 CLUSTER COMPOSITION ANALYSIS")
print("=" * 60)

# Add cluster labels to dataframe for easier analysis
df_papers['cluster'] = kmeans_labels

for i in range(OPTIMAL_K):
    cluster_papers = df_papers[df_papers['cluster'] == i]
    papers_count = len(cluster_papers)
    
    if papers_count > 0:
        # Get abstracts for keywords
        cluster_abstracts = cluster_papers['paper_abstract'].dropna().tolist()
        keywords = get_cluster_keywords(cluster_abstracts)
        
        # Get category distribution
        cat_dist = cluster_papers['primary_category'].value_counts().head(3).to_dict()
        
        print(f"\\n🔹 Cluster {i}: {papers_count} papers")
        print(f"   Top Categories: {cat_dist}")
        print(f"   Keywords: {', '.join(keywords)}")
        
        print(f"   Sample Papers:")
        for title in cluster_papers['title'].head(3):
            print(f"      • {title[:80]}...")
    else:
        print(f"\\n🔹 Cluster {i} (Empty)")
"""))

# Write the notebook
output_path = 'notebooks/clustering_analysis_v2.ipynb'
with open(output_path, 'w') as f:
    nbf.write(nb, f)

print(f"✅ Reorganized notebook written to {output_path}")
