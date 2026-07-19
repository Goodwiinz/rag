#!/usr/bin/env python3
"""
Embedding Visualization with PCA and t-SNE
Compares document clusters with ArXiv categories

Generates:
- PCA scatter plot colored by ArXiv category
- t-SNE scatter plot colored by K-Means cluster
- Category vs Cluster comparison heatmap
- Silhouette analysis
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, adjusted_rand_score, normalized_mutual_info_score
from sklearn.preprocessing import normalize, LabelEncoder
from pathlib import Path

# Load environment from backend
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / 'backend' / '.env')

# Setup visualization style
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 11
sns.set_style('whitegrid')
sns.set_palette('husl')

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent / 'visualizations'
OUTPUT_DIR.mkdir(exist_ok=True)

print("=" * 60)
print("📊 EMBEDDING VISUALIZATION: PCA & t-SNE")
print("=" * 60)

# ============================================================
# 1. LOAD DATA
# ============================================================
print("\n📂 Loading Data...")

# Load evaluation dataset
dataset_path = Path(__file__).parent.parent / 'backend' / 'data' / 'arxiv' / 'evaluation_dataset_improved.json'
if not dataset_path.exists():
    dataset_path = Path(__file__).parent.parent / 'data' / 'arxiv' / 'evaluation_dataset_improved.json'

with open(dataset_path, 'r') as f:
    dataset = json.load(f)

print(f"   Loaded {len(dataset.get('test_cases', []))} papers")

# Prepare paper DataFrame with categories
papers_data = []
for tc in dataset.get('test_cases', []):
    categories = tc.get('categories', [])
    primary_cat = tc.get('primary_category', categories[0] if categories else 'Unknown')
    # Extract main category (e.g., "cs.LG" -> "cs")
    main_category = primary_cat.split('.')[0] if '.' in primary_cat else primary_cat
    
    papers_data.append({
        'paper_id': tc.get('paper_id', ''),
        'title': tc.get('paper_title', ''),
        'primary_category': primary_cat,
        'main_category': main_category,
        'all_categories': ', '.join(categories),
        'num_categories': len(categories)
    })

papers_df = pd.DataFrame(papers_data)
print(f"   Unique main categories: {papers_df['main_category'].nunique()}")
print(f"   Categories: {papers_df['main_category'].value_counts().head(10).to_dict()}")

# ============================================================
# 2. FETCH EMBEDDINGS FROM QDRANT
# ============================================================
print("\n🔍 Fetching Embeddings from Qdrant...")

from qdrant_client import QdrantClient

qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
qdrant_key = os.getenv("QDRANT_API_KEY", None)

try:
    client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
    collection_name = "document_chunks"
    
    # Scroll through all points
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
    
    # Aggregate vectors by document (mean pooling of chunks)
    doc_vectors = {}
    for point in points:
        payload = point.payload or {}
        doc_id = payload.get('document_id') or payload.get('arxiv_id') or payload.get('paper_id')
        vector = point.vector
        
        if doc_id and vector:
            if doc_id not in doc_vectors:
                doc_vectors[doc_id] = []
            if isinstance(vector, list):
                doc_vectors[doc_id].append(vector)
    
    # Match embeddings to papers
    embeddings = []
    valid_indices = []
    
    for idx, row in papers_df.iterrows():
        paper_id = row['paper_id']
        if paper_id in doc_vectors:
            # Mean pooling of all chunks
            avg_vector = np.mean(doc_vectors[paper_id], axis=0)
            embeddings.append(avg_vector)
            valid_indices.append(idx)
    
    if not embeddings:
        raise ValueError("No embeddings matched to papers")
    
    # Filter DataFrame to only matched papers
    papers_df = papers_df.iloc[valid_indices].reset_index(drop=True)
    embeddings = np.array(embeddings)
    embeddings_norm = normalize(embeddings)
    
    print(f"✅ Matched {len(embeddings)} papers with embeddings")
    print(f"   Embedding dimension: {embeddings.shape[1]}")

except Exception as e:
    print(f"❌ Qdrant error: {e}")
    print("⚠️  Using random embeddings for demonstration")
    embeddings = np.random.rand(len(papers_df), 1536)
    embeddings_norm = normalize(embeddings)

# ============================================================
# 3. DIMENSIONALITY REDUCTION
# ============================================================
print("\n📉 Applying Dimensionality Reduction...")

# PCA
print("   Running PCA...")
pca = PCA(n_components=50, random_state=42)
embeddings_pca_50 = pca.fit_transform(embeddings_norm)
print(f"   PCA variance explained (50 components): {pca.explained_variance_ratio_.sum():.2%}")

pca_2d = PCA(n_components=2, random_state=42)
embeddings_pca_2d = pca_2d.fit_transform(embeddings_norm)
print(f"   PCA variance explained (2 components): {pca_2d.explained_variance_ratio_.sum():.2%}")

# t-SNE (on PCA-reduced data for speed)
print("   Running t-SNE...")
perplexity = min(30, len(embeddings) - 1)
tsne = TSNE(n_components=2, perplexity=perplexity, random_state=42, max_iter=1000)
embeddings_tsne_2d = tsne.fit_transform(embeddings_pca_50)
print(f"   t-SNE perplexity: {perplexity}")

# ============================================================
# 4. CLUSTERING
# ============================================================
print("\n🔬 Clustering Analysis...")

# Find optimal K using silhouette score
K_range = range(2, min(15, len(embeddings)))
silhouette_scores = []

for k in K_range:
    kmeans_temp = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels_temp = kmeans_temp.fit_predict(embeddings_norm)
    score = silhouette_score(embeddings_norm, labels_temp)
    silhouette_scores.append(score)

OPTIMAL_K = K_range[np.argmax(silhouette_scores)]
print(f"   Optimal K: {OPTIMAL_K} (Silhouette: {max(silhouette_scores):.3f})")

# Final K-Means clustering
kmeans = KMeans(n_clusters=OPTIMAL_K, random_state=42, n_init=10)
cluster_labels = kmeans.fit_predict(embeddings_norm)
papers_df['cluster'] = cluster_labels

# ============================================================
# 5. COMPARE CLUSTERS WITH CATEGORIES
# ============================================================
print("\n📊 Comparing Clusters with ArXiv Categories...")

# Encode categories for metric calculation
le = LabelEncoder()
category_labels = le.fit_transform(papers_df['main_category'])

# Clustering quality vs ground truth
ari = adjusted_rand_score(category_labels, cluster_labels)
nmi = normalized_mutual_info_score(category_labels, cluster_labels)
sil = silhouette_score(embeddings_norm, cluster_labels)

print(f"   Adjusted Rand Index (vs categories): {ari:.3f}")
print(f"   Normalized Mutual Information: {nmi:.3f}")
print(f"   Silhouette Score: {sil:.3f}")

# ============================================================
# 6. VISUALIZATIONS
# ============================================================
print("\n🎨 Generating Visualizations...")

# Get unique categories and assign colors
unique_categories = papers_df['main_category'].unique()
n_categories = len(unique_categories)
category_colors = plt.cm.tab20(np.linspace(0, 1, max(n_categories, 20)))[:n_categories]
category_color_map = dict(zip(unique_categories, category_colors))

# --- Figure 1: PCA by Category ---
fig, ax = plt.subplots(figsize=(14, 10))
for cat in unique_categories:
    mask = papers_df['main_category'] == cat
    ax.scatter(
        embeddings_pca_2d[mask, 0], 
        embeddings_pca_2d[mask, 1],
        c=[category_color_map[cat]],
        label=cat,
        s=100,
        alpha=0.7,
        edgecolors='white',
        linewidth=0.5
    )
ax.set_xlabel(f'PC1 ({pca_2d.explained_variance_ratio_[0]:.1%} variance)')
ax.set_ylabel(f'PC2 ({pca_2d.explained_variance_ratio_[1]:.1%} variance)')
ax.set_title('PCA Projection of Document Embeddings\nColored by ArXiv Category', fontsize=14)
ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', title='ArXiv Category')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'pca_by_category.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"   Saved: {OUTPUT_DIR / 'pca_by_category.png'}")

# --- Figure 2: t-SNE by Cluster ---
fig, ax = plt.subplots(figsize=(14, 10))
scatter = ax.scatter(
    embeddings_tsne_2d[:, 0], 
    embeddings_tsne_2d[:, 1],
    c=cluster_labels,
    cmap='tab10',
    s=100,
    alpha=0.7,
    edgecolors='white',
    linewidth=0.5
)
# Add cluster labels at centroid positions
for i in range(OPTIMAL_K):
    mask = cluster_labels == i
    if mask.sum() > 0:
        center_x = embeddings_tsne_2d[mask, 0].mean()
        center_y = embeddings_tsne_2d[mask, 1].mean()
        ax.annotate(f'C{i}', (center_x, center_y), fontsize=12, fontweight='bold', 
                    ha='center', va='center',
                    bbox=dict(boxstyle='circle', facecolor='white', edgecolor='gray', alpha=0.8))

ax.set_xlabel('t-SNE Dimension 1')
ax.set_ylabel('t-SNE Dimension 2')
ax.set_title(f't-SNE Projection of Document Embeddings\nColored by K-Means Cluster (K={OPTIMAL_K})', fontsize=14)
plt.colorbar(scatter, ax=ax, label='Cluster')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'tsne_by_cluster.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"   Saved: {OUTPUT_DIR / 'tsne_by_cluster.png'}")

# --- Figure 3: t-SNE by Category ---
fig, ax = plt.subplots(figsize=(14, 10))
for cat in unique_categories:
    mask = papers_df['main_category'] == cat
    ax.scatter(
        embeddings_tsne_2d[mask, 0], 
        embeddings_tsne_2d[mask, 1],
        c=[category_color_map[cat]],
        label=cat,
        s=100,
        alpha=0.7,
        edgecolors='white',
        linewidth=0.5
    )
ax.set_xlabel('t-SNE Dimension 1')
ax.set_ylabel('t-SNE Dimension 2')
ax.set_title('t-SNE Projection of Document Embeddings\nColored by ArXiv Category', fontsize=14)
ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', title='ArXiv Category')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'tsne_by_category.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"   Saved: {OUTPUT_DIR / 'tsne_by_category.png'}")

# --- Figure 4: Cluster vs Category Heatmap ---
confusion = pd.crosstab(papers_df['cluster'], papers_df['main_category'], normalize='index')
fig, ax = plt.subplots(figsize=(12, 8))
sns.heatmap(confusion, annot=True, fmt='.2f', cmap='Blues', ax=ax, cbar_kws={'label': 'Proportion'})
ax.set_xlabel('ArXiv Category')
ax.set_ylabel('K-Means Cluster')
ax.set_title(f'Cluster vs Category Distribution\n(ARI={ari:.3f}, NMI={nmi:.3f})', fontsize=14)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'cluster_category_heatmap.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"   Saved: {OUTPUT_DIR / 'cluster_category_heatmap.png'}")

# --- Figure 5: Silhouette Analysis ---
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Elbow/Silhouette plot
axes[0].plot(list(K_range), silhouette_scores, 'b-o', linewidth=2, markersize=8)
axes[0].axvline(x=OPTIMAL_K, color='red', linestyle='--', label=f'Optimal K={OPTIMAL_K}')
axes[0].set_xlabel('Number of Clusters (K)')
axes[0].set_ylabel('Silhouette Score')
axes[0].set_title('Silhouette Score vs Number of Clusters')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# Category distribution
category_counts = papers_df['main_category'].value_counts()
axes[1].barh(category_counts.index, category_counts.values, color=[category_color_map[c] for c in category_counts.index])
axes[1].set_xlabel('Number of Papers')
axes[1].set_ylabel('ArXiv Category')
axes[1].set_title('Papers per ArXiv Category')
axes[1].invert_yaxis()

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'clustering_analysis.png', dpi=150, bbox_inches='tight')
plt.close()
print(f"   Saved: {OUTPUT_DIR / 'clustering_analysis.png'}")

# ============================================================
# 7. SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("📈 VISUALIZATION SUMMARY")
print("=" * 60)
print(f"Total papers analyzed: {len(papers_df)}")
print(f"Embedding dimension: {embeddings.shape[1]}")
print(f"Optimal clusters (K): {OPTIMAL_K}")
print(f"\nClustering Quality:")
print(f"  • Silhouette Score: {sil:.3f}")
print(f"  • Adjusted Rand Index: {ari:.3f}")
print(f"  • Normalized MI: {nmi:.3f}")
print(f"\nCategory Distribution:")
for cat, count in papers_df['main_category'].value_counts().items():
    print(f"  • {cat}: {count} papers")
print(f"\nVisualizations saved to: {OUTPUT_DIR}")
print("=" * 60)

# Save metrics to JSON
metrics = {
    'total_papers': len(papers_df),
    'embedding_dimension': int(embeddings.shape[1]),
    'optimal_k': int(OPTIMAL_K),
    'silhouette_score': float(sil),
    'adjusted_rand_index': float(ari),
    'normalized_mutual_info': float(nmi),
    'category_counts': papers_df['main_category'].value_counts().to_dict(),
    'output_files': [
        str(OUTPUT_DIR / 'pca_by_category.png'),
        str(OUTPUT_DIR / 'tsne_by_cluster.png'),
        str(OUTPUT_DIR / 'tsne_by_category.png'),
        str(OUTPUT_DIR / 'cluster_category_heatmap.png'),
        str(OUTPUT_DIR / 'clustering_analysis.png')
    ]
}

with open(OUTPUT_DIR / 'clustering_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
print(f"\n✅ Metrics saved to: {OUTPUT_DIR / 'clustering_metrics.json'}")
