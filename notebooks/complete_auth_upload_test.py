# Complete Authentication + Upload Test
# Paste this into a NEW cell in your notebook

import time
import requests

BASE_URL = "http://localhost:8000"
session = requests.Session()

print("=" * 60)
print("🔐 STEP 1: Authentication")
print("=" * 60)

# Generate unique credentials
test_timestamp = int(time.time())
test_email = f"test_{test_timestamp}@example.com"
test_password = "SecurePass123!"
test_org = f"Test Org {test_timestamp}"

print(f"📧 Email: {test_email}")
print(f"🏢 Organization: {test_org}\n")

# Register
reg_data = {
    "email": test_email,
    "password": test_password,
    "first_name": "Test",
    "last_name": "User",
    "organization_name": test_org
}

try:
    reg_response = session.post(f"{BASE_URL}/api/v1/auth/register", json=reg_data, timeout=10)
    if reg_response.status_code in [200, 201]:
        print("✅ Registration successful")
    else:
        print(f"❌ Registration failed: {reg_response.status_code}")
        print(f"Response: {reg_response.text[:300]}")
        raise Exception("Registration failed")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    raise

# Login
login_data = {"email": test_email, "password": test_password}

try:
    login_response = session.post(f"{BASE_URL}/api/v1/auth/login", json=login_data, timeout=10)
    if login_response.status_code == 200:
        login_result = login_response.json()
        auth_token = login_result.get("access_token")

        # IMPORTANT: Set the authorization header
        session.headers.update({"Authorization": f"Bearer {auth_token}"})

        print("✅ Login successful")
        print(f"🔑 Token: {auth_token[:50]}...")
        print(f"🔑 Authorization header set\n")
        auth_success = True
    else:
        print(f"❌ Login failed: {login_response.status_code}")
        print(f"Response: {login_response.text[:300]}")
        raise Exception("Login failed")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    raise

print("=" * 60)
print("📄 STEP 2: Document Upload")
print("=" * 60)

# Create sample document
sample_content = """# Artificial Intelligence Overview

## Introduction
Artificial Intelligence (AI) is transforming how we interact with technology.

### Machine Learning
- Supervised learning algorithms
- Unsupervised clustering
- Reinforcement learning
- Deep neural networks

### Applications
- Natural language processing
- Computer vision
- Robotics and automation
- Healthcare diagnostics
"""

# Save sample file
with open("test_ai_doc.txt", "w") as f:
    f.write(sample_content)

print("📝 Created test document: test_ai_doc.txt")

# Debug: Check headers
print(f"🔍 Session headers: {dict(session.headers)}\n")

# Upload document
try:
    with open("test_ai_doc.txt", "rb") as f:
        files = {"file": ("test_ai_doc.txt", f, "text/plain")}
        data = {"title": "AI Overview Test", "description": "Test document for RAG system"}

        upload_response = session.post(
            f"{BASE_URL}/api/v1/files/upload",
            files=files,
            data=data,
            timeout=30
        )

        print(f"Upload response status: {upload_response.status_code}")

        if upload_response.status_code in [200, 201]:
            upload_result = upload_response.json()
            document_id = upload_result.get("id")
            print(f"✅ Document uploaded successfully")
            print(f"📄 Document ID: {document_id}")
            print(f"📊 Status: {upload_result.get('status', 'processing')}")
            upload_success = True
        else:
            print(f"❌ Upload failed: {upload_response.status_code}")
            print(f"Response: {upload_response.text[:500]}")
            upload_success = False
except Exception as e:
    print(f"❌ Upload error: {str(e)}")
    import traceback
    traceback.print_exc()
    upload_success = False

print("\n" + "=" * 60)
if auth_success and upload_success:
    print("🎉 SUCCESS! Both authentication and upload completed!")
else:
    print("❌ Something failed - check errors above")
print("=" * 60)
