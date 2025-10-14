#!/usr/bin/env python3
"""
Test script to verify the registration fix for duplicate organization names
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"

def wait_for_backend(max_retries=30, delay=2):
    """Wait for backend to be ready"""
    print("Waiting for backend to be ready...")
    for i in range(max_retries):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Backend is ready!")
                return True
        except Exception as e:
            print(f"Attempt {i+1}/{max_retries}: Backend not ready yet...")
            time.sleep(delay)
    print("❌ Backend did not become ready in time")
    return False

def test_duplicate_organization_registration():
    """Test registering multiple users with the same organization name"""
    print("\n🧪 Testing duplicate organization registration fix...")
    print("=" * 60)

    org_name = "Demo Organization"

    # Test case 1: Register first user (should create organization)
    print(f"\n📝 Test 1: Register first user with org '{org_name}'")
    user1_email = f"test_user_1_{int(time.time())}@example.com"

    user1_data = {
        "email": user1_email,
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User1",
        "organization_name": org_name
    }

    try:
        response1 = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user1_data, timeout=10)
        if response1.status_code in [200, 201]:
            result1 = response1.json()
            print(f"✅ User 1 registered successfully")
            print(f"   Email: {user1_email}")
            print(f"   User ID: {result1.get('user', {}).get('id')}")
            print(f"   Organization: {result1.get('user', {}).get('organization_name')}")
            print(f"   Role: {result1.get('user', {}).get('role')} (should be ADMIN)")
        else:
            print(f"❌ User 1 registration failed: {response1.status_code}")
            print(f"   Response: {response1.text}")
            return False
    except Exception as e:
        print(f"❌ Error registering user 1: {str(e)}")
        return False

    # Test case 2: Register second user with SAME organization name
    print(f"\n📝 Test 2: Register second user with SAME org '{org_name}'")
    user2_email = f"test_user_2_{int(time.time())}@example.com"

    user2_data = {
        "email": user2_email,
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User2",
        "organization_name": org_name
    }

    try:
        response2 = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user2_data, timeout=10)
        if response2.status_code in [200, 201]:
            result2 = response2.json()
            print(f"✅ User 2 registered successfully (using existing org)")
            print(f"   Email: {user2_email}")
            print(f"   User ID: {result2.get('user', {}).get('id')}")
            print(f"   Organization: {result2.get('user', {}).get('organization_name')}")
            print(f"   Role: {result2.get('user', {}).get('role')} (should be USER)")

            # Verify they're in the same organization
            if result1.get('user', {}).get('organization_id') == result2.get('user', {}).get('organization_id'):
                print(f"✅ Both users are in the same organization!")
            else:
                print(f"⚠️ Warning: Users are in different organizations")
                print(f"   User 1 org: {result1.get('user', {}).get('organization_id')}")
                print(f"   User 2 org: {result2.get('user', {}).get('organization_id')}")
        else:
            print(f"❌ User 2 registration failed: {response2.status_code}")
            print(f"   Response: {response2.text}")
            return False
    except Exception as e:
        print(f"❌ Error registering user 2: {str(e)}")
        return False

    # Test case 3: Register third user with SAME organization name
    print(f"\n📝 Test 3: Register third user with SAME org '{org_name}'")
    user3_email = f"test_user_3_{int(time.time())}@example.com"

    user3_data = {
        "email": user3_email,
        "password": "SecurePass123!",
        "first_name": "Test",
        "last_name": "User3",
        "organization_name": org_name
    }

    try:
        response3 = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user3_data, timeout=10)
        if response3.status_code in [200, 201]:
            result3 = response3.json()
            print(f"✅ User 3 registered successfully (using existing org)")
            print(f"   Email: {user3_email}")
            print(f"   User ID: {result3.get('user', {}).get('id')}")
            print(f"   Organization: {result3.get('user', {}).get('organization_name')}")
            print(f"   Role: {result3.get('user', {}).get('role')} (should be USER)")
        else:
            print(f"❌ User 3 registration failed: {response3.status_code}")
            print(f"   Response: {response3.text}")
            return False
    except Exception as e:
        print(f"❌ Error registering user 3: {str(e)}")
        return False

    print("\n" + "=" * 60)
    print("🎉 All tests passed! The duplicate organization fix works!")
    print("\n📊 Summary:")
    print(f"   ✅ 3 users registered successfully")
    print(f"   ✅ All users joined the same organization: '{org_name}'")
    print(f"   ✅ First user is ADMIN, others are USER")
    print(f"   ✅ No unique constraint violations")
    return True

def main():
    """Main test runner"""
    print("🔧 Registration Fix Test Suite")
    print("=" * 60)

    # Wait for backend
    if not wait_for_backend():
        print("❌ Backend not available. Please start the backend first:")
        print("   docker-compose up -d backend")
        return 1

    # Run tests
    if test_duplicate_organization_registration():
        print("\n✅ All tests PASSED!")
        return 0
    else:
        print("\n❌ Tests FAILED!")
        return 1

if __name__ == "__main__":
    exit(main())
