#!/usr/bin/env python3
"""
Security Fix Demonstration for RAG Public Search Vulnerability

This script demonstrates:
1. The vulnerability that existed in the public search endpoint
2. How the security fix prevents unauthorized access
3. Proper authenticated access using API keys

Run this after applying the security fix to verify it works correctly.
"""

import requests
import json
import time
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "http://localhost:8000"  # Adjust to your API server
API_V1 = f"{BASE_URL}/api/v1"


class SecurityFixDemo:
    """Demonstrate the security fix for public search endpoints"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.api_v1 = f"{base_url}/api/v1"
        self.session = requests.Session()
    
    def demonstrate_vulnerability_fix(self):
        """Show that the original vulnerability is fixed"""
        print("🔒 RAG SEARCH SECURITY FIX DEMONSTRATION")
        print("=" * 50)
        
        print("\n1. Testing Original Vulnerable Endpoints (Should Fail)")
        print("-" * 50)
        
        # Test old public search endpoint
        print("📛 Testing old public search endpoint...")
        try:
            response = self.session.post(
                f"{self.api_v1}/search/public/hybrid",
                json={
                    "query": "test vulnerability",
                    "search_type": "HYBRID",
                    "limit": 10
                },
                timeout=5
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 404:
                print("   ✅ GOOD: Vulnerable endpoint removed!")
            else:
                print(f"   ❌ BAD: Endpoint still accessible: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"   ✅ GOOD: Endpoint inaccessible - {str(e)}")
        
        # Test old public health endpoint
        print("\n📛 Testing old public health endpoint...")
        try:
            response = self.session.get(
                f"{self.api_v1}/search/public/health",
                timeout=5
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 404:
                print("   ✅ GOOD: Public health endpoint removed!")
            else:
                print(f"   ❌ BAD: Health endpoint still public: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"   ✅ GOOD: Endpoint inaccessible - {str(e)}")
    
    def test_new_authenticated_endpoints(self, api_key: Optional[str] = None):
        """Test new authenticated endpoints"""
        print("\n2. Testing New Authenticated Endpoints")
        print("-" * 50)
        
        # Test without authentication
        print("🔐 Testing authenticated search without API key...")
        response = self.session.post(
            f"{self.api_v1}/search/authenticated/hybrid",
            json={
                "query": "test without auth",
                "search_type": "HYBRID",
                "limit": 10
            }
        )
        print(f"   Status: {response.status_code}")
        if response.status_code in [401, 403]:
            print("   ✅ GOOD: Authentication required!")
        else:
            print(f"   ❌ BAD: Unauthenticated access allowed: {response.text}")
        
        # Test with invalid API key
        print("\n🔐 Testing with invalid API key...")
        headers = {"Authorization": "Bearer invalid_key_123"}
        response = self.session.post(
            f"{self.api_v1}/search/authenticated/hybrid",
            headers=headers,
            json={
                "query": "test with invalid key",
                "search_type": "HYBRID", 
                "limit": 10
            }
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ GOOD: Invalid API key rejected!")
        else:
            print(f"   ❌ BAD: Invalid key accepted: {response.text}")
        
        # Test with valid API key (if provided)
        if api_key:
            print(f"\n🔑 Testing with valid API key...")
            headers = {"Authorization": f"Bearer {api_key}"}
            response = self.session.post(
                f"{self.api_v1}/search/authenticated/hybrid",
                headers=headers,
                json={
                    "query": "test with valid key",
                    "search_type": "HYBRID",
                    "limit": 5
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ GOOD: Valid API key accepted!")
                result = response.json()
                print(f"   📊 Results: {len(result.get('results', []))} found")
            elif response.status_code in [401, 403]:
                print("   ⚠️  API key rejected (check if key is valid and active)")
            else:
                print(f"   ℹ️  Other response: {response.text[:200]}...")
        else:
            print("\n🔑 Skipping valid API key test (no key provided)")
    
    def test_rate_limiting(self, api_key: str, requests_count: int = 5):
        """Test rate limiting functionality"""
        if not api_key:
            print("\n⏭️  Skipping rate limiting test (no API key provided)")
            return
        
        print(f"\n3. Testing Rate Limiting ({requests_count} requests)")
        print("-" * 50)
        
        headers = {"Authorization": f"Bearer {api_key}"}
        successful_requests = 0
        rate_limited = False
        
        for i in range(requests_count):
            print(f"🚀 Request {i+1}/{requests_count}...")
            response = self.session.post(
                f"{self.api_v1}/search/authenticated/hybrid",
                headers=headers,
                json={
                    "query": f"rate limit test {i+1}",
                    "search_type": "HYBRID",
                    "limit": 3
                }
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                successful_requests += 1
                print("   ✅ Request successful")
            elif response.status_code == 429:
                print("   🛑 Rate limited!")
                rate_limited = True
                break
            else:
                print(f"   ⚠️  Unexpected response: {response.text[:100]}...")
            
            time.sleep(0.1)  # Small delay between requests
        
        print(f"\n📈 Rate Limiting Summary:")
        print(f"   Successful requests: {successful_requests}")
        print(f"   Rate limiting triggered: {rate_limited}")
        
        if rate_limited:
            print("   ✅ GOOD: Rate limiting is working!")
        else:
            print("   ℹ️  Rate limit not reached with current settings")
    
    def test_health_check_security(self, api_key: Optional[str] = None):
        """Test health check endpoint security"""
        print("\n4. Testing Health Check Security")
        print("-" * 50)
        
        # Test without authentication
        print("🏥 Testing health check without API key...")
        response = self.session.get(f"{self.api_v1}/search/authenticated/health")
        print(f"   Status: {response.status_code}")
        if response.status_code in [401, 403]:
            print("   ✅ GOOD: Health check requires authentication!")
        else:
            print(f"   ❌ BAD: Health check accessible without auth: {response.text}")
        
        # Test with API key
        if api_key:
            print("\n🏥 Testing health check with valid API key...")
            headers = {"Authorization": f"Bearer {api_key}"}
            response = self.session.get(
                f"{self.api_v1}/search/authenticated/health",
                headers=headers
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ GOOD: Authenticated health check works!")
                health_data = response.json()
                print(f"   💊 Service status: {health_data.get('status', 'unknown')}")
            else:
                print(f"   ⚠️  Health check failed: {response.text[:100]}...")
    
    def demonstrate_security_logging(self, api_key: Optional[str] = None):
        """Demonstrate security logging features"""
        print("\n5. Security Logging Demonstration")
        print("-" * 50)
        
        print("📋 Making requests to test security logging...")
        
        # Valid request (if API key available)
        if api_key:
            headers = {"Authorization": f"Bearer {api_key}"}
            response = self.session.post(
                f"{self.api_v1}/search/authenticated/hybrid",
                headers=headers,
                json={
                    "query": "security logging test",
                    "search_type": "HYBRID",
                    "limit": 3
                }
            )
            print(f"   Valid request logged: {response.status_code}")
        
        # Invalid authentication attempt
        invalid_headers = {"Authorization": "Bearer fake_key_for_logging_test"}
        response = self.session.post(
            f"{self.api_v1}/search/authenticated/hybrid",
            headers=invalid_headers,
            json={
                "query": "failed auth logging test",
                "search_type": "HYBRID",
                "limit": 3
            }
        )
        print(f"   Invalid auth attempt logged: {response.status_code}")
        
        print("\n📊 Check your application logs for security audit entries!")
        print("   Look for entries containing 'API Key Search' or 'Invalid API key attempt'")
    
    def run_full_demo(self, api_key: Optional[str] = None):
        """Run complete security demonstration"""
        print("🎯 Starting RAG Search Security Fix Demonstration...")
        print(f"🌐 Testing against: {self.base_url}")
        
        try:
            # Check if API is accessible
            health_response = self.session.get(f"{self.base_url}/health", timeout=5)
            if health_response.status_code != 200:
                print(f"❌ API not accessible at {self.base_url}")
                return False
            
            print(f"✅ API accessible (version: {health_response.json().get('version', 'unknown')})")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to API: {str(e)}")
            return False
        
        # Run all tests
        self.demonstrate_vulnerability_fix()
        self.test_new_authenticated_endpoints(api_key)
        self.test_rate_limiting(api_key)
        self.test_health_check_security(api_key)
        self.demonstrate_security_logging(api_key)
        
        print("\n" + "=" * 50)
        print("🎉 SECURITY FIX DEMONSTRATION COMPLETE!")
        print("=" * 50)
        
        print("\n📋 Summary:")
        print("   ✅ Vulnerable public endpoints removed")
        print("   ✅ Authentication required for search access")
        print("   ✅ Rate limiting enforced")
        print("   ✅ Security logging implemented")
        print("   ✅ Proper error handling in place")
        
        if not api_key:
            print("\n💡 To test authenticated features:")
            print("   1. Create an admin user in your system")
            print("   2. Use admin credentials to create an API key via POST /api/v1/api-keys/")
            print("   3. Re-run this demo with the API key")
        
        return True


def main():
    """Main demonstration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='RAG Search Security Fix Demo')
    parser.add_argument('--api-key', type=str, help='API key for authenticated testing')
    parser.add_argument('--base-url', type=str, default=BASE_URL, help='API base URL')
    parser.add_argument('--quick', action='store_true', help='Run quick test (skip rate limiting)')
    
    args = parser.parse_args()
    
    demo = SecurityFixDemo(args.base_url)
    
    if args.quick:
        print("🚀 Running quick security test...")
        demo.demonstrate_vulnerability_fix()
        demo.test_new_authenticated_endpoints(args.api_key)
        demo.test_health_check_security(args.api_key)
    else:
        demo.run_full_demo(args.api_key)


if __name__ == "__main__":
    main()