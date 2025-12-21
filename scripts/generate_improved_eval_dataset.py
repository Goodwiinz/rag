#!/usr/bin/env python3
"""
Improved Evaluation Dataset Generator

Fetches papers from ArXiv API across diverse AI/ML categories and generates
comprehensive evaluation test cases with proper metadata.
"""

import asyncio
import json
import logging
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import xml.etree.ElementTree as ET

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_CONFIG = {
    "target_papers": 100,
    "questions_per_paper": 5,
    "categories": [
        "cs.AI",      # Artificial Intelligence
        "cs.CL",      # Computation and Language (NLP)
        "cs.LG",      # Machine Learning
        "cs.CV",      # Computer Vision
        "cs.IR",      # Information Retrieval
        "cs.NE",      # Neural and Evolutionary Computing
        "stat.ML",    # Machine Learning (Statistics)
    ],
    "output_path": "data/arxiv/evaluation_dataset_improved.json",
}

# Question templates for different question types  
QUESTION_TEMPLATES = {
    "contribution": [
        "What is the main contribution of '{title}'?",
        "What are the key innovations introduced in this paper?",
        "How does '{title}' advance the field of {category}?",
    ],
    "methodology": [
        "What methods or techniques are used in '{title}'?",
        "Describe the approach taken in this paper.",
        "What is the core algorithm or model proposed?",
    ],
    "comparison": [
        "How does this paper compare to previous work in {category}?",
        "What baselines were compared against in this research?",
        "What improvements does this approach achieve over existing methods?",
    ],
    "problem": [
        "What problem does '{title}' address?",
        "What research gap does this paper fill?",
        "What are the limitations of existing approaches that this paper addresses?",
    ],
    "results": [
        "What are the main experimental results of this paper?",
        "What datasets were used to evaluate this approach?",
        "What metrics were used to measure performance?",
    ],
    "application": [
        "What are the practical applications of this research?",
        "How can the findings of '{title}' be applied in real-world scenarios?",
        "What domains could benefit from this work?",
    ],
    "author": [
        "Who are the authors of '{title}' and what institutions are they affiliated with?",
        "What is the research background of the authors?",
    ],
    "future_work": [
        "What future work is suggested in this paper?",
        "What are the limitations mentioned by the authors?",
    ],
}

DIFFICULTY_WEIGHTS = {
    "easy": 0.3,
    "medium": 0.5,
    "hard": 0.2
}


class ImprovedEvalDatasetGenerator:
    """Generates comprehensive evaluation datasets from ArXiv papers."""
    
    ARXIV_API_BASE = "https://export.arxiv.org/api/query"
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self
    
    async def __aexit__(self, *args):
        if self.client:
            await self.client.aclose()
    
    async def fetch_papers_by_category(
        self,
        category: str,
        max_results: int = 50,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """Fetch papers from a specific ArXiv category."""
        
        query = f"cat:{category}"
        params = {
            'search_query': query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        
        try:
            logger.info(f"Fetching papers from category {category}...")
            response = await self.client.get(self.ARXIV_API_BASE, params=params)
            response.raise_for_status()
            
            papers = self._parse_arxiv_response(response.text, category)
            logger.info(f"  → Found {len(papers)} papers in {category}")
            return papers
            
        except Exception as e:
            logger.error(f"Error fetching papers from {category}: {e}")
            return []
    
    def _parse_arxiv_response(self, xml_text: str, primary_category: str) -> List[Dict[str, Any]]:
        """Parse ArXiv API XML response."""
        
        papers = []
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }
        
        try:
            root = ET.fromstring(xml_text)
            
            for entry in root.findall('atom:entry', namespaces):
                paper = self._parse_entry(entry, namespaces, primary_category)
                if paper and paper.get('title') and paper.get('abstract'):
                    papers.append(paper)
                    
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            
        return papers
    
    def _parse_entry(self, entry: ET.Element, ns: Dict, primary_cat: str) -> Optional[Dict[str, Any]]:
        """Parse a single ArXiv entry."""
        
        try:
            # Get paper ID
            id_elem = entry.find('atom:id', ns)
            paper_id = id_elem.text.split('/')[-1] if id_elem is not None else None
            
            # Get title (clean whitespace)
            title_elem = entry.find('atom:title', ns)
            title = ' '.join(title_elem.text.split()) if title_elem is not None else None
            
            # Get abstract  
            abstract_elem = entry.find('atom:summary', ns)
            abstract = ' '.join(abstract_elem.text.split()) if abstract_elem is not None else None
            
            # Get authors
            authors = []
            for author in entry.findall('atom:author', ns):
                name_elem = author.find('atom:name', ns)
                if name_elem is not None:
                    authors.append(name_elem.text)
            
            # Get categories
            categories = [primary_cat]
            for cat in entry.findall('atom:category', ns):
                term = cat.get('term')
                if term and term not in categories:
                    categories.append(term)
            
            # Get dates
            published = entry.find('atom:published', ns)
            updated = entry.find('atom:updated', ns)
            
            # Get PDF link
            pdf_link = None
            for link in entry.findall('atom:link', ns):
                if link.get('title') == 'pdf':
                    pdf_link = link.get('href')
            
            return {
                'id': paper_id,
                'title': title,
                'abstract': abstract,
                'authors': authors,
                'categories': categories,
                'primary_category': primary_cat,
                'published': published.text if published is not None else None,
                'updated': updated.text if updated is not None else None,
                'pdf_link': pdf_link,
            }
            
        except Exception as e:
            logger.warning(f"Error parsing entry: {e}")
            return None
    
    def generate_questions(self, paper: Dict[str, Any], num_questions: int = 5) -> List[Dict[str, Any]]:
        """Generate diverse evaluation questions for a paper."""
        
        questions = []
        question_types = list(QUESTION_TEMPLATES.keys())
        
        # Sample question types
        selected_types = random.sample(
            question_types, 
            min(num_questions, len(question_types))
        )
        
        for i, qtype in enumerate(selected_types):
            templates = QUESTION_TEMPLATES[qtype]
            template = random.choice(templates)
            
            # Fill in template
            question_text = template.format(
                title=paper['title'],
                category=paper['primary_category']
            )
            
            # Assign difficulty
            difficulty = random.choices(
                list(DIFFICULTY_WEIGHTS.keys()),
                weights=list(DIFFICULTY_WEIGHTS.values())
            )[0]
            
            # Create expected answer from abstract for ground truth
            expected_answer = self._generate_expected_answer(paper, qtype)
            
            questions.append({
                'id': f"{paper['id']}_q_{i+1}",
                'question': question_text,
                'question_type': qtype,
                'difficulty': difficulty,
                'expected_answer_type': qtype,
                'expected_answer_hint': expected_answer,
                'requires_context': ['title', 'abstract', 'categories'],
                'evaluation_criteria': {
                    'answer_relevancy': 0.75 if difficulty == 'easy' else 0.70 if difficulty == 'medium' else 0.65,
                    'faithfulness': 0.85,
                    'contextual_precision': 0.70,
                }
            })
        
        return questions
    
    def _generate_expected_answer(self, paper: Dict[str, Any], qtype: str) -> str:
        """Generate a hint for expected answer based on paper abstract."""
        
        abstract = paper.get('abstract', '')
        
        # Just return relevant portion of abstract as context
        if qtype in ['contribution', 'methodology']:
            # First few sentences often describe contribution
            sentences = abstract.split('. ')
            return '. '.join(sentences[:2]) + '.' if sentences else abstract[:300]
        elif qtype == 'results':
            # Look for result-related sentences
            result_keywords = ['result', 'achieve', 'outperform', 'accuracy', 'performance']
            for sent in abstract.split('. '):
                if any(kw in sent.lower() for kw in result_keywords):
                    return sent
            return abstract[-300:] if len(abstract) > 300 else abstract
        else:
            return abstract[:200]
    
    async def generate_dataset(self) -> Dict[str, Any]:
        """Generate the complete evaluation dataset."""
        
        all_papers = []
        papers_per_category = max(20, self.config['target_papers'] // len(self.config['categories']))
        
        logger.info(f"Fetching ~{papers_per_category} papers from each of {len(self.config['categories'])} categories...")
        
        # Fetch papers from each category
        for category in self.config['categories']:
            papers = await self.fetch_papers_by_category(category, papers_per_category)
            all_papers.extend(papers)
            await asyncio.sleep(0.5)  # Rate limiting
        
        # Deduplicate by paper ID
        seen_ids = set()
        unique_papers = []
        for paper in all_papers:
            if paper['id'] not in seen_ids:
                seen_ids.add(paper['id'])
                unique_papers.append(paper)
        
        logger.info(f"Total unique papers fetched: {len(unique_papers)}")
        
        # Sample if we have more than target
        if len(unique_papers) > self.config['target_papers']:
            unique_papers = random.sample(unique_papers, self.config['target_papers'])
        
        # Generate test cases
        test_cases = []
        for paper in unique_papers:
            questions = self.generate_questions(paper, self.config['questions_per_paper'])
            
            test_cases.append({
                'paper_id': paper['id'],
                'paper_title': paper['title'],
                'paper_abstract': paper['abstract'],
                'authors': paper['authors'],
                'categories': paper['categories'],
                'primary_category': paper['primary_category'],
                'published': paper['published'],
                'pdf_link': paper['pdf_link'],
                'questions': questions,
                'ground_truth_context': {
                    'title': paper['title'],
                    'abstract': paper['abstract'],
                    'authors': paper['authors'],
                    'categories': paper['categories'],
                }
            })
        
        # Create dataset
        dataset = {
            'dataset_info': {
                'name': 'ArXiv RAG Evaluation Dataset (Improved)',
                'version': '2.0',
                'created_at': datetime.now().isoformat(),
                'num_papers': len(test_cases),
                'total_questions': sum(len(tc['questions']) for tc in test_cases),
                'questions_per_paper': self.config['questions_per_paper'],
                'categories': self.config['categories'],
                'question_types': list(QUESTION_TEMPLATES.keys()),
            },
            'test_cases': test_cases
        }
        
        return dataset
    
    async def save_dataset(self, dataset: Dict[str, Any], output_path: Optional[str] = None):
        """Save dataset to JSON file."""
        
        path = Path(output_path or self.config['output_path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(dataset, f, indent=2)
        
        logger.info(f"Dataset saved to {path}")
        return path


async def main():
    """Main execution function."""
    
    import argparse
    parser = argparse.ArgumentParser(description='Generate improved ArXiv evaluation dataset')
    parser.add_argument('--papers', type=int, default=100, help='Target number of papers')
    parser.add_argument('--questions', type=int, default=5, help='Questions per paper')
    parser.add_argument('--output', type=str, default=None, help='Output file path')
    args = parser.parse_args()
    
    config = {
        'target_papers': args.papers,
        'questions_per_paper': args.questions,
    }
    if args.output:
        config['output_path'] = args.output
    
    logger.info("="*60)
    logger.info("ArXiv RAG Evaluation Dataset Generator v2.0")
    logger.info("="*60)
    
    async with ImprovedEvalDatasetGenerator(config) as generator:
        # Generate dataset
        dataset = await generator.generate_dataset()
        
        # Print summary
        info = dataset['dataset_info']
        logger.info("")
        logger.info("="*60)
        logger.info("Dataset Generation Complete!")
        logger.info("="*60)
        logger.info(f"  Papers:         {info['num_papers']}")
        logger.info(f"  Total Questions:{info['total_questions']}")
        logger.info(f"  Categories:     {', '.join(info['categories'])}")
        logger.info(f"  Question Types: {', '.join(info['question_types'])}")
        
        # Save dataset
        output_path = await generator.save_dataset(dataset, args.output)
        
        # Also save to the standard locations
        backend_path = Path(__file__).parent.parent / 'backend' / 'data' / 'arxiv' / 'evaluation_dataset_improved.json'
        if backend_path.parent.exists():
            await generator.save_dataset(dataset, str(backend_path))
            logger.info(f"Also saved to {backend_path}")
        
        logger.info("")
        logger.info("✅ Done! Ready for evaluation runs.")


if __name__ == "__main__":
    asyncio.run(main())
