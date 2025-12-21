
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
import sys

def main():
    # Load Data
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, 'rag_evaluation_data.csv')
    
    if not os.path.exists(data_path):
        print(f"Error: Data file not found at {data_path}")
        print("Please run generate_rag_evaluation_data.py first.")
        sys.exit(1)
        
    try:
        df = pd.read_csv(data_path)
    except pd.errors.EmptyDataError:
        print("Dataset is empty. Skipping EDA.")
        sys.exit(0)
    output_dir = os.path.join(script_dir, 'eda_outputs')
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Retrieval Quality Distribution
    plt.figure(figsize=(10, 6))
    if 'relevance_score' in df.columns:
        sns.histplot(df['relevance_score'], bins=20, kde=True)
        plt.title('Distribution of Relevance Scores')
        plt.xlabel('Relevance Score (LLM Judge)')
        plt.ylabel('Frequency')
        plt.savefig(os.path.join(output_dir, 'relevance_distribution.png'))
        plt.close()
    
    # 2. Feature Correlation Heatmap
    plt.figure(figsize=(10, 8))
    numeric_cols = ['cosine_similarity', 'doc_length', 'query_length', 'rank', 'relevance_score', 'hybrid_score']
    # Filter for columns that actually exist
    existing_numeric = [c for c in numeric_cols if c in df.columns]
    
    if existing_numeric:
        corr_matrix = df[existing_numeric].corr()
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1)
        plt.title('Feature Correlation Matrix')
        plt.savefig(os.path.join(output_dir, 'correlation_heatmap.png'))
        plt.close()
        
    # 3. Relevance by Rank (Boxplot)
    plt.figure(figsize=(10, 6))
    if 'rank' in df.columns and 'relevance_score' in df.columns:
        sns.boxplot(x='rank', y='relevance_score', data=df)
        plt.title('Relevance Score by Rank Position')
        plt.xlabel('Rank')
        plt.ylabel('Relevance Score')
        plt.savefig(os.path.join(output_dir, 'relevance_by_rank.png'))
        plt.close()
    
    # Summary Stats
    print("Summary Statistics:")
    print(df.describe())
    
    # Handle Missing Data Strategy Demonstration
    # (Just printing info, as actual handling depends on model training requirements)
    print("\nMissing Values:")
    print(df.isnull().sum())
    
    print(f"\nEDA Complete. plots saved to {output_dir}")

if __name__ == "__main__":
    main()
