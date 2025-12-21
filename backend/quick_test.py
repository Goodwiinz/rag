#!/usr/bin/env python3
"""
Quick Test Runner for Multi-Agent Search System
Simple script to quickly run basic tests and verify functionality
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def run_command(cmd, description, critical=True):
    """Run a command and handle the result"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {cmd}")
    print(f"{'='*60}")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ SUCCESS: {description}")
        if result.stdout:
            print("\nOutput:")
            print(result.stdout[:1000] + "..." if len(result.stdout) > 1000 else result.stdout)
    else:
        print(f"❌ FAILED: {description}")
        if result.stderr:
            print("\nError:")
            print(result.stderr[:1000] + "..." if len(result.stderr) > 1000 else result.stderr)

        if critical:
            print("\n❌ Critical test failed. Exiting.")
            sys.exit(1)

    return result.returncode == 0

def main():
    print("🚀 Quick Test Runner for Multi-Agent Search System")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"Working Directory: {Path.cwd()}")

    # Test 1: Import basic modules
    print("\n" + "="*60)
    print("Test 1: Import Verification")
    print("="*60)

    modules_to_test = [
        ("pytest", "Testing framework"),
        ("fastapi", "Web framework"),
        ("sqlalchemy", "ORM"),
        ("pydantic", "Data validation"),
        ("httpx", "HTTP client"),
        ("crewai", "Multi-agent framework"),
    ]

    for module, description in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {module} - {description}")
        except ImportError:
            print(f"❌ {module} - {description} (NOT INSTALLED)")

    # Test 2: Environment check
    print("\n" + "="*60)
    print("Test 2: Environment Variables")
    print("="*60)

    env_vars = [
        "ENVIRONMENT",
        "DATABASE_URL",
        "REDIS_URL",
        "NEO4J_URI",
        "QDRANT_URL",
    ]

    for var in env_vars:
        value = os.getenv(var)
        if value:
            display = value if "KEY" not in var else "***"
            print(f"✅ {var} = {display}")
        else:
            print(f"⚠️  {var} = Not set")

    # Test 3: Fast module tests
    print("\n" + "="*60)
    print("Test 3: Fast Module Tests")
    print("="*60)

    # Create a simple test file
    test_file = Path("quick_test_module.py")
    test_file.write_text("""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from src.core.config import get_settings
    print("✅ Settings import successful")
except ImportError as e:
    print(f"❌ Settings import failed: {e}")

try:
    from src.services.vector_search_service import VectorSearchService
    print("✅ VectorSearchService import successful")
except ImportError as e:
    print(f"❌ VectorSearchService import failed: {e}")

try:
    from src.services.knowledge_graph_service import KnowledgeGraphService
    print("✅ KnowledgeGraphService import successful")
except ImportError as e:
    print(f"❌ KnowledgeGraphService import failed: {e}")

try:
    from src.services.hybrid_search_service import HybridSearchService
    print("✅ HybridSearchService import successful")
except ImportError as e:
    print(f"❌ HybridSearchService import failed: {e}")

# Try to import agents if they exist
try:
    from src.agents.orchestrator import SearchOrchestrator
    print("✅ SearchOrchestrator import successful")
except ImportError:
    print("⚠️  SearchOrchestrator not available (module missing)")

try:
    from crewai import Agent, Task, Crew
    print("✅ CrewAI import successful")
except ImportError as e:
    print(f"❌ CrewAI import failed: {e}")

print("\n📊 Module test completed!")
""")

    # Run the module test
    result = subprocess.run([sys.executable, str(test_file)], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

    # Clean up
    test_file.unlink()

    # Test 4: Database connectivity (quick check)
    print("\n" + "="*60)
    print("Test 4: Quick Database Connectivity")
    print("="*60)

    db_test_file = Path("quick_db_test.py")
    db_test_file.write_text("""
import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_databases():
    # Test Redis
    try:
        import redis
        r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        r.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")

    # Test Qdrant
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"))
        client.get_collections()
        print("✅ Qdrant connection successful")
    except Exception as e:
        print(f"❌ Qdrant connection failed: {e}")

    # Test Neo4j
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=("neo4j", os.getenv("NEO4J_PASSWORD", "password"))
        )
        driver.verify_connectivity()
        driver.close()
        print("✅ Neo4j connection successful")
    except Exception as e:
        print(f"❌ Neo4j connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_databases())
""")

    # Run database tests
    result = subprocess.run([sys.executable, str(db_test_file)], capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("Errors:", result.stderr)

    # Clean up
    db_test_file.unlink()

    # Test 5: Run minimal pytest suite
    print("\n" + "="*60)
    print("Test 5: Minimal Pytest Suite")
    print("="*60)

    # Create a minimal test
    minimal_test_dir = Path("tests_quick")
    minimal_test_dir.mkdir(exist_ok=True)

    (minimal_test_dir / "__init__.py").touch()

    minimal_test_file = minimal_test_dir / "test_basic.py"
    minimal_test_file.write_text('''
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_imports():
    """Test basic imports"""
    from src.core.config import get_settings
    settings = get_settings()
    assert settings is not None

def test_basic_services():
    """Test service instantiation"""
    from src.services.vector_search_service import VectorSearchService

    # This will fail without proper setup, but tests import
    try:
        service = VectorSearchService()
        assert service is not None
    except:
        pytest.skip("Vector service requires Qdrant")

@pytest.mark.asyncio
async def test_async_functionality():
    """Test async functionality"""
    import asyncio
    await asyncio.sleep(0.01)
    assert True
""")

    # Run pytest
    success = run_command(
        f"{sys.executable} -m pytest {minimal_test_dir} -v",
        "Running minimal pytest suite",
        critical=False
    )

    # Clean up
    import shutil
    shutil.rmtree(minimal_test_dir)

    # Summary
    print("\n" + "="*60)
    print("📋 QUICK TEST SUMMARY")
    print("="*60)
    print("\n✅ Tests completed!")
    print("\n📌 Next Steps:")
    print("1. Install missing dependencies if any imports failed")
    print("2. Start Docker services for full integration tests")
    print("3. Run the full test suite: python run_tests.py")
    print("4. Check the TESTING_README.md for detailed instructions")

    print("\n🔗 Useful Commands:")
    print("• Verify environment: python verify_test_environment.py")
    print("• Run unit tests: python run_tests.py unit")
    print("• Run all tests: python run_tests.py all")
    print("• Run with coverage: python run_tests.py all --coverage")

    print("\n✨ Happy Testing! ✨")

if __name__ == "__main__":
    main()