
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score
import seaborn as sns

# Try to import sentence_transformers, but if not available we can skip or use dummy embeddings?
# Actually, the plan was to use AzureOpenAI for embeddings in this script too, or re-use existing ones.
# The user prompt example used SentenceTransformer. I will stick to AzureOpenAI to be consistent with the app's services, 
# BUT reusing the backend service here might be complex due to async.
# Alternatively, I can use the 'cosine_similarity' logic which implies we already have embeddings, 
# but the CSV doesn't store the full embedding vectors (usually).
# Better to generate embeddings on the fly for the unique queries using the same service as data gen.

# To simplify, I'll assume we can import the service again or use a local lightweight model like 'all-MiniLM-L6-v2' 
# as requested in the user prompt example, which is easier for a standalone script if installed.
# I'll check if sentence_transformers is installed or just use the backend service.
# Using backend service is safer for consistency.

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from backend.src.services.azure_openai_service import azure_openai_service
    # We need to run async calls synchronously here
    import asyncio
except ImportError:
    print("Could not import AzureOpenAIService. Ensure you are in the project root.")
    sys.exit(1)

async def get_embeddings(texts):
    return azure_openai_service.get_embeddings(texts)

def main():
    # Load Data
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, 'rag_evaluation_data.csv')
    
    if not os.path.exists(data_path):
        print(f"Error: Data file not found at {data_path}")
        sys.exit(1)
        
    try:
        df = pd.read_csv(data_path)
    except pd.errors.EmptyDataError:
        print("Dataset is empty. Skipping Clustering.")
        sys.exit(0)
    output_dir = os.path.join(script_dir, 'clustering_outputs')
    os.makedirs(output_dir, exist_ok=True)
    
    unique_queries = df['query'].unique().tolist()
    print(f"Found {len(unique_queries)} unique queries.")
    
    if len(unique_queries) < 5:
        print("Not enough unique queries for meaningful clustering (need at least 5).")
        # Proceed if meaningful, else exit or mock
        if len(unique_queries) == 0:
            sys.exit(0)
            
    # Generate Embeddings
    print("Generating query embeddings...")
    # Run async loop to get embeddings
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    query_embeddings = loop.run_until_complete(get_embeddings(unique_queries))
    query_embeddings = np.array(query_embeddings)
    
    # Clustering
    print("Running Clustering Algorithms...")
    
    results = {}
    
    # K-Means
    n_clusters = min(5, len(unique_queries))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    clusters_km = kmeans.fit_predict(query_embeddings)
    sil_km = silhouette_score(query_embeddings, clusters_km) if len(unique_queries) > n_clusters else 0
    results['KMeans'] = sil_km
    print(f"K-Means Silhouette: {sil_km:.3f}")
    
    # DBSCAN
    dbscan = DBSCAN(eps=0.5, min_samples=2)
    clusters_db = dbscan.fit_predict(query_embeddings)
    # Handle case where all noise or single cluster
    if len(set(clusters_db)) > 1:
        sil_db = silhouette_score(query_embeddings, clusters_db)
    else:
        sil_db = 0
    results['DBSCAN'] = sil_db
    print(f"DBSCAN Silhouette: {sil_db:.3f}")
    
    # GMM
    gmm = GaussianMixture(n_components=n_clusters, random_state=42)
    clusters_gmm = gmm.fit_predict(query_embeddings)
    
    # Agglomerative
    agg = AgglomerativeClustering(n_clusters=n_clusters)
    clusters_agg = agg.fit_predict(query_embeddings)
    
    # t-SNE Visualization
    print("Generating t-SNE visualization...")
    if len(unique_queries) > 5:  # t-SNE needs some samples
        tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(unique_queries)-1))
        query_2d = tsne.fit_transform(query_embeddings)
        
        plt.figure(figsize=(12, 8))
        scatter = plt.scatter(query_2d[:, 0], query_2d[:, 1], 
                            c=clusters_km, cmap='viridis', alpha=0.6)
        plt.colorbar(scatter, label='Cluster ID')
        plt.title(f't-SNE Projection of Query Clusters (K-Means, n={n_clusters})')
        plt.xlabel('t-SNE Component 1')
        plt.ylabel('t-SNE Component 2')
        
        # Annotate points with short query text
        for i, txt in enumerate(unique_queries):
            plt.annotate(txt[:20]+"...", (query_2d[i, 0], query_2d[i, 1]), fontsize=8, alpha=0.7)
            
        plt.savefig(os.path.join(output_dir, 'tsne_clusters.png'))
        plt.close()
    
    print(f"Clustering Complete. Results saved to {output_dir}")

if __name__ == "__main__":
    main()
