
import os
import json
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler, normalize
from scipy.cluster.hierarchy import dendrogram, linkage
from qdrant_client import QdrantClient
from dotenv import load_dotenv

# Setup
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 12
sns.set_style('whitegrid')
sns.set_palette('husl')

# Load environment
load_dotenv('backend/.env')

print("🚀 Starting Clustering Analysis...")

# 1. Load Data
print("\n📂 Loading Data...")
try:
    with open('backend/data/arxiv/evaluation_dataset_improved.json', 'r') as f:
        dataset = json.load(f)
    print(f"   Loaded dataset with {len(dataset.get('test_cases', []))} papers")
    
    with open('evaluation_results.json', 'r') as f:
        results = json.load(f)
    print(f"   Loaded results with {len(results.get('test_cases', []))} test cases")
except Exception as e:
    print(f"❌ Error loading data: {e}")
    exit(1)

# Prepare DataFrames
papers_data = []
for tc in dataset.get('test_cases', []):
    papers_data.append({
        'paper_id': tc.get('paper_id', ''),
        'title': tc.get('paper_title', ''),
        'primary_category': tc.get('primary_category', 'Unknown'),
        'categories': ', '.join(tc.get('categories', [])),
    })
papers_df = pd.DataFrame(papers_data)

query_data = []
for tc in results.get('test_cases', []):
    for q in tc.get('question_results', []):
        am = q.get('answer_metrics', {})
        rm = q.get('retrieval_metrics', {})
        passed = (am.get('answer_relevancy', 0) >= 0.75 and am.get('faithfulness', 0) >= 0.85)
        query_data.append({
            'question_type': q.get('expected_answer_type', ''),
            'difficulty': q.get('difficulty', ''),
            'precision_at_1': rm.get('precision_at_1', 0),
            'answer_relevancy': am.get('answer_relevancy', 0),
            'faithfulness': am.get('faithfulness', 0),
            'passed': passed
        })
query_df = pd.DataFrame(query_data)


# 2. Connect to Qdrant & Fetch Embeddings
print("\n🔍 Connecting to Qdrant...")
qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
qdrant_key = os.getenv("QDRANT_API_KEY", None)

try:
    client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
    collection_name = "document_chunks"
    
    points = []
    next_offset = None
    while True:
        batch, next_offset = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=True,
            offset=next_offset
        )
        points.extend(batch)
        if not next_offset:
            break
            
    print(f"   Retrieved {len(points)} vector chunks")

    # Aggregate vectors
    doc_vectors = {}
    for point in points:
        payload = point.payload or {}
        doc_id = payload.get('document_id') or payload.get('paper_id') # Handle both naming conventions if needed
        # Fallback: try to extract from 'source' or similar if document_id is missing? 
        # For now assume document_id exists as per previous analysis
        
        vector = point.vector
        if doc_id and vector:
            if doc_id not in doc_vectors:
                doc_vectors[doc_id] = []
            if isinstance(vector, list):
                doc_vectors[doc_id].append(vector)

    # Match to papers
    real_embeddings = []
    valid_indices = []
    
    for idx, row in papers_df.iterrows():
        paper_id = row['paper_id']
        if paper_id in doc_vectors:
            # Mean pooling
            avg_vector = np.mean(doc_vectors[paper_id], axis=0)
            real_embeddings.append(avg_vector)
            valid_indices.append(idx)
            
    if not real_embeddings:
        print("⚠️  No embeddings matched. Creating random embeddings for demonstration.")
        real_embeddings = np.random.rand(len(papers_df), 1536)
        valid_indices = range(len(papers_df))
    else:
        papers_df = papers_df.iloc[valid_indices].reset_index(drop=True)

    doc_embeddings = np.array(real_embeddings)
    # Normalize for cosine similarity behavior in K-Means
    doc_embeddings_norm = normalize(doc_embeddings)
    print(f"✅ Prepared {len(doc_embeddings)} document embeddings")

except Exception as e:
    print(f"❌ Qdrant error: {e}")
    print("⚠️  Falling back to random embeddings for pipeline verification.")
    doc_embeddings = np.random.rand(len(papers_df), 1536)
    doc_embeddings_norm = normalize(doc_embeddings)


# 3. Elbow Method & Optimal K
print("\n📈 Running Elbow Method...")
inertias = []
silhouette_scores = []
K_range = range(2, min(12, len(doc_embeddings)))

for k in K_range:
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    kmeans.fit(doc_embeddings_norm)
    inertias.append(kmeans.inertia_)
    silhouette_scores.append(silhouette_score(doc_embeddings_norm, kmeans.labels_))

OPTIMAL_K = K_range[np.argmax(silhouette_scores)]
print(f"   Optimal K found: {OPTIMAL_K} (Silhouette: {max(silhouette_scores):.3f})")

# Save Elbow Plot
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
ax1.plot(K_range, inertias, 'bo-')
ax1.set_title('Elbow Method')
ax2.plot(K_range, silhouette_scores, 'go-')
ax2.set_title('Silhouette Score')
plt.savefig('clustering_elbow_analysis.png')
plt.close()


# 4. Metrics Comparison
print("\n📊 Comparing Clustering Methods...")
def compute_metrics(X, labels, name, time_taken):
    return {
        'Method': name,
        'Silhouette': silhouette_score(X, labels),
        'Calinski-Harabasz': calinski_harabasz_score(X, labels),
        'Davies-Bouldin': davies_bouldin_score(X, labels),
        'Time': time_taken
    }

metrics = []

# K-Means
start = time.time()
kmeans = KMeans(n_clusters=OPTIMAL_K, random_state=42, n_init=10).fit(doc_embeddings_norm)
metrics.append(compute_metrics(doc_embeddings_norm, kmeans.labels_, 'K-Means', time.time()-start))

# Hierarchical (Ward)
start = time.time()
ward = AgglomerativeClustering(n_clusters=OPTIMAL_K, linkage='ward').fit(doc_embeddings_norm)
metrics.append(compute_metrics(doc_embeddings_norm, ward.labels_, 'Hierarchical (Ward)', time.time()-start))

metrics_df = pd.DataFrame(metrics)
print(metrics_df.to_string())
metrics_df.to_csv('clustering_metrics_comparison.csv', index=False)

# Save Comparison Plot
plt.figure(figsize=(10, 6))
sns.barplot(data=metrics_df, x='Method', y='Silhouette')
plt.title('Clustering Quality Comparison')
plt.savefig('clustering_methods_comparison.png')
plt.close()


# 5. Dendrogram
print("\n🌳 Generating Dendrogram...")
linkage_matrix = linkage(doc_embeddings_norm, method='ward')
plt.figure(figsize=(12, 8))
dendrogram(linkage_matrix, truncate_mode='lastp', p=30)
plt.title('Hierarchical Clustering Dendrogram')
plt.savefig('hierarchical_dendrogram.png')
plt.close()


# 6. t-SNE Visualization
print("\n🌐 Generating t-SNE...")
tsne = TSNE(n_components=2, metric='cosine', random_state=42, perplexity=min(30, len(doc_embeddings)-1))
embeddings_2d = tsne.fit_transform(doc_embeddings)

plt.figure(figsize=(12, 8))
plt.scatter(embeddings_2d[:, 0], embeddings_2d[:, 1], c=kmeans.labels_, cmap='tab10', s=100)
plt.title(f'Document Clustering (k={OPTIMAL_K})')
plt.savefig('document_clustering_tsne.png')
plt.close()


# 7. Insights
print("\n💡 Generating Insights...")
papers_df['cluster'] = kmeans.labels_

# Extract main category from primary_category (e.g., "cs.LG" -> "cs")
papers_df['main_category'] = papers_df['primary_category'].apply(
    lambda x: x.split('.')[0] if '.' in str(x) else str(x)
)

# Calculate cluster-category alignment
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
from sklearn.preprocessing import LabelEncoder

le = LabelEncoder()
category_labels = le.fit_transform(papers_df['main_category'])
ari = adjusted_rand_score(category_labels, kmeans.labels_)
nmi = normalized_mutual_info_score(category_labels, kmeans.labels_)

print(f"\n📊 Cluster-Category Alignment:")
print(f"   Adjusted Rand Index: {ari:.3f}")
print(f"   Normalized Mutual Info: {nmi:.3f}")

# Analyze cluster composition
print(f"\n🔍 Cluster Composition Analysis:")
for cluster_id in range(OPTIMAL_K):
    cluster_papers = papers_df[papers_df['cluster'] == cluster_id]
    category_dist = cluster_papers['main_category'].value_counts()
    dominant_cat = category_dist.index[0] if len(category_dist) > 0 else 'Unknown'
    purity = category_dist.iloc[0] / len(cluster_papers) if len(cluster_papers) > 0 else 0
    
    print(f"\n   Cluster {cluster_id} ({len(cluster_papers)} papers):")
    print(f"   • Dominant category: {dominant_cat} ({purity:.1%} purity)")
    for cat, count in category_dist.head(3).items():
        print(f"     - {cat}: {count} papers ({count/len(cluster_papers):.1%})")

# Key insights summary
print("\n" + "=" * 60)
print("📈 KEY INSIGHTS")
print("=" * 60)

category_counts = papers_df['main_category'].value_counts()
print(f"\n1. DATASET COMPOSITION:")
for cat, count in category_counts.items():
    print(f"   • {cat}: {count} papers ({count/len(papers_df):.1%})")

print(f"\n2. CLUSTERING QUALITY:")
print(f"   • Optimal K: {OPTIMAL_K} clusters")
print(f"   • Silhouette Score: {max(silhouette_scores):.3f}")
print(f"   • K-Means outperforms Ward clustering" if metrics_df.iloc[0]['Silhouette'] > metrics_df.iloc[1]['Silhouette'] else "   • Ward clustering outperforms K-Means")

print(f"\n3. CATEGORY ALIGNMENT:")
if ari > 0.3:
    print(f"   ✅ Strong alignment between clusters and categories (ARI={ari:.3f})")
elif ari > 0.1:
    print(f"   ⚠️ Moderate alignment between clusters and categories (ARI={ari:.3f})")
else:
    print(f"   ❌ Weak alignment - clusters don't strongly correspond to categories (ARI={ari:.3f})")
    print(f"   → This suggests embeddings capture semantic similarity beyond category labels")

print(f"\n4. EMBEDDING INSIGHTS:")
print(f"   • Embeddings dimension: {doc_embeddings.shape[1]}")
print(f"   • Papers with embeddings: {len(papers_df)}")
print(f"   • Mean chunks per paper: {len(points) / len(papers_df):.1f}")

print("\n" + "=" * 60)
print("✅ Analysis Complete!")
print("=" * 60)
print("\nOutput files generated:")
print("  • clustering_elbow_analysis.png")
print("  • clustering_methods_comparison.png")
print("  • clustering_metrics_comparison.csv")
print("  • hierarchical_dendrogram.png")
print("  • document_clustering_tsne.png")
