
import requests
import json

def check_paper():
    # Note: Authentication is required for this endpoint.
    # Please add 'Authorization': 'Bearer <token>' header if running against a secured backend.
    url = "http://localhost:8000/api/v1/search/hybrid"
    payload = {
        "query": "2512.16875v1 Learning Confidence Ellipsoids",
        "top_n": 5
    }
    
    print(f"Searching for paper 2512.16875v1...")
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            return

        data = response.json()
        results = data.get("results", [])
        
        found = False
        for res in results:
            doc_id = res.get("document_id")
            title = res.get("title", "")
            if "2512.16875v1" in doc_id or "Confidence Ellipsoids" in title:
                print(f"✅ Found paper: {doc_id} - {title}")
                found = True
                break
        
        if not found:
            print("❌ Paper NOT found in top 5 results.")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_paper()
