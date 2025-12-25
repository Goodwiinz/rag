
import os
import asyncio
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load env from backend/.env
load_dotenv("backend/.env")

def list_deployments():
    endpoint = os.getenv("AZURE_OPENAI_CHAT_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_CHAT_API_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
    api_version = os.getenv("AZURE_OPENAI_CHAT_API_VERSION") or "2024-06-01"

    print(f"Endpoint: {endpoint}")
    print(f"API Version: {api_version}")

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version=api_version
    )

    # Try to list deployments directly
    try:
        print("\nAttempting to list deployments via API...")
        # Azure OpenAI API to list deployments: GET /openai/deployments?api-version=...
        import httpx
        
        headers = {"api-key": api_key}
        base_url = endpoint.rstrip('/')
        url = f"{base_url}/openai/deployments?api-version={api_version}"
        
        with httpx.Client() as http_client:
            response = http_client.get(url, headers=headers)
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print("Available deployments:")
                for item in data.get('data', []):
                    model = item.get('model', 'unknown')
                    name = item.get('id', 'unknown')
                    print(f"- Name: {name}, Model: {model}")
                    if "gpt" in name.lower():
                        return name
            else:
                print(f"Failed to list deployments: {response.text}")
    except Exception as e:
        print(f"Error listing deployments: {e}")

    # Fallback to trial
    common_names = ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-35-turbo", "gpt-3.5-turbo", "gpt-4-turbo"]
    
    print("\nTesting common deployment names (fallback):")
    for name in common_names:
        try:
            print(f"Testing '{name}'...", end=" ", flush=True)
            response = client.chat.completions.create(
                model=name,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            print(f"✅ SUCCESS! Found deployment: {name}")
            return name
        except Exception as e:
            if "DeploymentNotFound" in str(e):
                print("❌ Not found")
            else:
                print(f"❌ Error: {e}")



if __name__ == "__main__":
    list_deployments()
