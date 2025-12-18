#!/usr/bin/env python3
"""
Simple test script to check arXiv API connectivity
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime

def test_arxiv_api():
    """Test arXiv API with requests"""

    base_url = "http://export.arxiv.org/api/query"

    # Test parameters
    params = {
        'search_query': 'machine learning',
        'start': 0,
        'max_results': 5,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }

    print(f"Testing arXiv API...")
    print(f"URL: {base_url}")
    print(f"Params: {params}")
    print()

    try:
        # Make request
        response = requests.get(base_url, params=params)
        print(f"Response status: {response.status_code}")

        if response.status_code == 200:
            print(f"Response text length: {len(response.text)}")
            print(f"Response preview:\n{response.text[:500]}...")

            # Parse XML
            root = ET.fromstring(response.text)

            # Namespace handling
            namespaces = {
                'atom': 'http://www.w3.org/2005/Atom',
                'arxiv': 'http://arxiv.org/schemas/atom'
            }

            # Extract entries
            entries = root.findall('atom:entry', namespaces)
            print(f"\nFound {len(entries)} papers:")

            for i, entry in enumerate(entries, 1):
                title = entry.find('atom:title', namespaces).text.strip()
                paper_id = entry.find('atom:id', namespaces).text.split('/')[-1]
                authors = []
                for author in entry.findall('atom:author', namespaces):
                    name = author.find('atom:name', namespaces).text
                    authors.append(name)

                print(f"\n{i}. {title}")
                print(f"   ID: {paper_id}")
                print(f"   Authors: {', '.join(authors[:3])}{'...' if len(authors) > 3 else ''}")

        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text}")

    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_arxiv_api()