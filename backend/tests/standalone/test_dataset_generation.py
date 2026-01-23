
import asyncio
import logging
from src.services.arxiv import ArxivService as ArXivIngestionService

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_dataset_generation():
    service = ArXivIngestionService()
    
    # Mock specific paper
    papers = [{
        'id': '2512.15687v1',
        'title': 'Can LLMs Guide Their Own Exploration? Gradient-Guided Reinforcement Learning for LLM Reasoning',
        'abstract': 'We propose Gradient-Guided Reinforcement Learning (G2RL), a framework that leverages the gradients of the policy to guide exploration in the action space. By using the gradients, we can identify promising directions for exploration and avoid redundant exploration of the action space. We evaluate our method on several reasoning tasks and show that it outperforms standard RL methods.',
        'authors': ['Zhenwen Liang', 'Sidi Lu', 'Wenhao Yu'],
        'categories': ['cs.LG', 'cs.AI'],
        'primary_category': 'cs.LG'
    }]
    
    print("Generating evaluation dataset using LLM...")
    try:
        dataset = await service.create_evaluation_dataset(papers, num_questions=3)
        
        print("\n--- Generated Questions ---")
        for case in dataset['test_cases']:
            print(f"Paper: {case['paper_title']}")
            for q in case['questions']:
                print(f"\nQuestion ({q.get('source', 'unknown')}): {q['question']}")
                print(f"Type: {q['expected_answer_type']}")
                print(f"Difficulty: {q['difficulty']}")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dataset_generation())
