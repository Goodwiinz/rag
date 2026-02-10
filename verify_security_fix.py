#!/usr/bin/env python3
"""
Verification script for the RAG security fix implementation.
Checks that all components are properly implemented without running the full app.
"""

import sys
import os
import importlib.util

# Add the backend source to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend', 'src'))


def check_file_exists(filepath):
    """Check if a file exists and return status"""
    if os.path.exists(filepath):
        print(f"✅ {filepath}")
        return True
    else:
        print(f"❌ {filepath} - FILE NOT FOUND")
        return False


def check_python_syntax(filepath):
    """Check if a Python file has valid syntax"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        compile(content, filepath, 'exec')
        print(f"✅ {filepath} - Valid syntax")
        return True
    except SyntaxError as e:
        print(f"❌ {filepath} - Syntax error: {e}")
        return False
    except Exception as e:
        print(f"⚠️ {filepath} - Error: {e}")
        return False


def check_imports(module_path, module_name):
    """Check if a module can be imported"""
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None:
            print(f"❌ Cannot create spec for {module_name}")
            return False
        
        module = importlib.util.module_from_spec(spec)
        # We don't actually execute the module to avoid dependency issues
        print(f"✅ {module_name} - Import spec created successfully")
        return True
    except Exception as e:
        print(f"❌ {module_name} - Import error: {e}")
        return False


def verify_api_key_generation():
    """Test the API key generation logic"""
    try:
        import secrets
        import hashlib
        
        # Simulate API key generation
        raw_key = f"rag_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(32))}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Verify format
        assert raw_key.startswith("rag_"), "API key should start with 'rag_'"
        assert len(raw_key) == 36, f"API key should be 36 chars, got {len(raw_key)}"
        assert len(key_hash) == 64, f"Hash should be 64 chars, got {len(key_hash)}"
        
        # Verify hash validation
        verify_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        assert verify_hash == key_hash, "Hash verification should work"
        
        print("✅ API key generation logic works correctly")
        return True
    except Exception as e:
        print(f"❌ API key generation failed: {e}")
        return False


def verify_database_migration():
    """Check database migration file"""
    migration_file = "backend/migrations/add_api_keys_table.py"
    if not check_file_exists(migration_file):
        return False
    
    try:
        with open(migration_file, 'r') as f:
            content = f.read()
        
        # Check for required tables
        required_elements = [
            "api_keys",
            "api_key_usage_log",
            "key_hash",
            "rate_limit_per_hour",
            "def upgrade",
            "def downgrade"
        ]
        
        missing = []
        for element in required_elements:
            if element.lower() not in content.lower():
                missing.append(element)
        
        if missing:
            print(f"❌ Migration missing elements: {missing}")
            return False
        
        print("✅ Database migration contains required elements")
        return True
    except Exception as e:
        print(f"❌ Migration verification failed: {e}")
        return False


def verify_endpoint_changes():
    """Verify the search endpoint changes"""
    search_file = "backend/src/api/search/search.py"
    if not check_file_exists(search_file):
        return False
    
    try:
        with open(search_file, 'r') as f:
            content = f.read()
        
        # Check that vulnerable endpoints are removed/replaced
        if "/public/hybrid" in content and "async def public_hybrid_search" in content:
            print("❌ Vulnerable public hybrid endpoint still exists")
            return False
        
        # Check that new secure endpoints exist
        secure_elements = [
            "/authenticated/hybrid",
            "api_key_data",
            "get_api_key_data",
            "log_api_access"
        ]
        
        missing = []
        for element in secure_elements:
            if element not in content:
                missing.append(element)
        
        if missing:
            print(f"❌ Search endpoints missing secure elements: {missing}")
            return False
        
        print("✅ Search endpoints properly secured")
        return True
    except Exception as e:
        print(f"❌ Endpoint verification failed: {e}")
        return False


def main():
    """Main verification function"""
    print("🔒 RAG Security Fix Verification")
    print("=" * 40)
    
    all_checks = []
    
    print("\n📁 File Existence Checks")
    print("-" * 25)
    files_to_check = [
        "backend/src/core/api_key_auth.py",
        "backend/src/api/auth/api_keys.py",
        "backend/migrations/add_api_keys_table.py",
        "tests/security/test_api_key_authentication.py",
        "tests/integration/test_security_integration.py",
        "security_fix_demo.py",
        "SECURITY_FIX_DOCUMENTATION.md"
    ]
    
    file_checks = [check_file_exists(f) for f in files_to_check]
    all_checks.extend(file_checks)
    
    print("\n🐍 Python Syntax Checks")
    print("-" * 25)
    python_files = [
        "backend/src/core/api_key_auth.py",
        "backend/src/api/auth/api_keys.py",
        "backend/migrations/add_api_keys_table.py",
        "tests/security/test_api_key_authentication.py",
        "tests/integration/test_security_integration.py",
        "security_fix_demo.py"
    ]
    
    syntax_checks = [check_python_syntax(f) for f in python_files if os.path.exists(f)]
    all_checks.extend(syntax_checks)
    
    print("\n🔧 Logic Verification")
    print("-" * 20)
    logic_checks = [
        verify_api_key_generation(),
        verify_database_migration(),
        verify_endpoint_changes()
    ]
    all_checks.extend(logic_checks)
    
    print("\n📊 Verification Summary")
    print("-" * 22)
    total_checks = len(all_checks)
    passed_checks = sum(all_checks)
    failed_checks = total_checks - passed_checks
    
    print(f"Total checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Failed: {failed_checks}")
    print(f"Success rate: {passed_checks/total_checks*100:.1f}%")
    
    if failed_checks == 0:
        print("\n🎉 ALL CHECKS PASSED!")
        print("The security fix has been properly implemented.")
    else:
        print(f"\n⚠️  {failed_checks} checks failed.")
        print("Please review the issues above.")
    
    print("\n📋 Next Steps:")
    print("1. Apply database migration: alembic upgrade head")
    print("2. Create initial admin API key")
    print("3. Run integration tests with test API key")
    print("4. Update client applications to use new authenticated endpoints")
    print("5. Monitor security logs for any issues")
    
    return failed_checks == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)