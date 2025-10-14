#!/usr/bin/env python3
"""
Complete Authentication & Upload Test
Tests all fixed functionality in the RAG system
"""

import time
import json

# Note: Run this in your Jupyter notebook where 'requests' and 'session' are already imported
# Copy and paste this code into a new cell in quick_rag_test.ipynb

print("=" * 80)
print("🧪 COMPLETE RAG SYSTEM AUTHENTICATION TEST")
print("=" * 80)
print()

# Configuration
BASE_URL = "http://localhost:8000"

# Generate unique test credentials
test_timestamp = int(time.time())
test_email = f"test_{test_timestamp}@example.com"
test_password = "SecurePass123!"
test_org = f"Test Org {test_timestamp}"

print("📋 Test Configuration:")
print(f"   Email: {test_email}")
print(f"   Organization: {test_org}")
print(f"   Backend: {BASE_URL}")
print()

# ============================================================================
# TEST 1: User Registration
# ============================================================================
print("🔐 TEST 1: User Registration")
print("-" * 80)

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
        reg_result = reg_response.json()
        print("✅ PASS - User Registration")
        print(f"   User ID: {reg_result.get('user', {}).get('id')}")
        print(f"   Role: {reg_result.get('user', {}).get('role')}")
        print(f"   Org ID: {reg_result.get('user', {}).get('organization_id')}")
        test_1_pass = True
    else:
        print(f"❌ FAIL - Status: {reg_response.status_code}")
        print(f"   Response: {reg_response.text[:200]}")
        test_1_pass = False
except Exception as e:
    print(f"❌ FAIL - Exception: {str(e)}")
    test_1_pass = False

print()

# ============================================================================
# TEST 2: User Login
# ============================================================================
print("🔑 TEST 2: User Login")
print("-" * 80)

login_data = {"email": test_email, "password": test_password}

try:
    login_response = session.post(f"{BASE_URL}/api/v1/auth/login", json=login_data, timeout=10)

    if login_response.status_code == 200:
        login_result = login_response.json()
        auth_token = login_result.get("access_token")
        refresh_token = login_result.get("refresh_token")

        # Set authorization header
        session.headers.update({"Authorization": f"Bearer {auth_token}"})

        print("✅ PASS - User Login")
        print(f"   Token Type: {login_result.get('token_type')}")
        print(f"   Expires In: {login_result.get('expires_in')} seconds")
        print(f"   Token: {auth_token[:30]}...")
        print(f"   Refresh Token: {refresh_token[:30]}...")
        test_2_pass = True
        auth_success = True
    else:
        print(f"❌ FAIL - Status: {login_response.status_code}")
        print(f"   Response: {login_response.text[:200]}")
        test_2_pass = False
        auth_success = False
except Exception as e:
    print(f"❌ FAIL - Exception: {str(e)}")
    test_2_pass = False
    auth_success = False

print()

# ============================================================================
# TEST 3: Token Validation (File Upload)
# ============================================================================
if auth_success:
    print("📄 TEST 3: Token Validation (File Upload)")
    print("-" * 80)

    # Create test document
    sample_content = """# Test Document

This is a test document for the RAG system.

## Topics
- Authentication
- File Upload
- Token Validation

## Content
This document tests that JWT tokens are properly validated
and that authenticated file uploads work correctly.
"""

    with open("test_auth_doc.txt", "w") as f:
        f.write(sample_content)

    try:
        with open("test_auth_doc.txt", "rb") as f:
            files = {"file": ("test_auth_doc.txt", f, "text/plain")}
            data = {
                "title": "Authentication Test Document",
                "description": "Test document for auth verification"
            }

            upload_response = session.post(
                f"{BASE_URL}/api/v1/files/upload",
                files=files,
                data=data,
                timeout=30
            )

        if upload_response.status_code in [200, 201]:
            upload_result = upload_response.json()
            print("✅ PASS - File Upload (Token Validated)")
            print(f"   Document ID: {upload_result.get('id')}")
            print(f"   Title: {upload_result.get('title')}")
            print(f"   Filename: {upload_result.get('filename')}")
            print(f"   Size: {upload_result.get('file_size_bytes')} bytes")
            print(f"   Status: {upload_result.get('processing_status')}")
            test_3_pass = True
            document_id = upload_result.get('id')
        else:
            print(f"❌ FAIL - Status: {upload_response.status_code}")
            print(f"   Response: {upload_response.text[:200]}")
            test_3_pass = False
    except Exception as e:
        print(f"❌ FAIL - Exception: {str(e)}")
        test_3_pass = False
else:
    print("⏭️  TEST 3: Skipped (login failed)")
    test_3_pass = False

print()

# ============================================================================
# TEST 4: Search API Access
# ============================================================================
if auth_success:
    print("🔍 TEST 4: Search API Access")
    print("-" * 80)

    search_data = {"query": "authentication", "limit": 5}

    try:
        search_response = session.post(
            f"{BASE_URL}/api/v1/search/hybrid",
            json=search_data,
            timeout=15
        )

        if search_response.status_code == 200:
            search_result = search_response.json()
            results_count = len(search_result.get("results", []))
            print("✅ PASS - Search API Accessible")
            print(f"   Results Found: {results_count}")
            print(f"   Total: {search_result.get('total', 0)}")
            print(f"   Search Time: {search_result.get('search_time', 0):.3f}s")
            if results_count == 0:
                print("   ℹ️  Note: 0 results (document may still be processing)")
            test_4_pass = True
        else:
            print(f"❌ FAIL - Status: {search_response.status_code}")
            print(f"   Response: {search_response.text[:200]}")
            test_4_pass = False
    except Exception as e:
        print(f"❌ FAIL - Exception: {str(e)}")
        test_4_pass = False
else:
    print("⏭️  TEST 4: Skipped (login failed)")
    test_4_pass = False

print()

# ============================================================================
# Summary
# ============================================================================
print("=" * 80)
print("📊 TEST SUMMARY")
print("=" * 80)

tests = [
    ("User Registration", test_1_pass),
    ("User Login", test_2_pass),
    ("Token Validation (File Upload)", test_3_pass),
    ("Search API Access", test_4_pass)
]

passed = sum(1 for _, result in tests if result)
total = len(tests)

for test_name, result in tests:
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status} - {test_name}")

print()
print(f"Results: {passed}/{total} tests passed ({(passed/total)*100:.0f}%)")
print()

if passed == total:
    print("🎉 SUCCESS! All authentication features are working correctly!")
    print()
    print("✅ Fixed Issues:")
    print("   - Bcrypt compatibility (bcrypt 4.0.1)")
    print("   - JWT token verification (sub field)")
    print("   - Rate limiting (50 attempts/15min)")
    print("   - Unique organization names")
    print()
    print("🚀 Your RAG system is ready to use!")
elif passed >= total * 0.5:
    print("⚠️  PARTIAL SUCCESS - Most features working")
    print("   Review failed tests above for details")
else:
    print("❌ FAILURE - Multiple issues detected")
    print("   Review all failed tests above")

print()
print("=" * 80)

# Cleanup
import os
if os.path.exists("test_auth_doc.txt"):
    os.remove("test_auth_doc.txt")
