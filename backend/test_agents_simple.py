#!/usr/bin/env python3
"""
Simple test script for the multi-agent search system
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_imports():
    """Test basic imports"""
    print("Testing imports...")

    try:
        from src.core.config import settings
        print("✓ Config imported successfully")
    except Exception as e:
        print(f"✗ Failed to import config: {e}")
        return False

    try:
        from src.services.multi_agent_search_service_v2 import MultiAgentSearchServiceV2
        print("✓ MultiAgentSearchServiceV2 imported successfully")
    except Exception as e:
        print(f"✗ Failed to import MultiAgentSearchServiceV2: {e}")
        return False

    try:
        from src.api.multi_agent_search_v2 import router
        print("✓ Multi-agent search v2 API router imported successfully")
    except Exception as e:
        print(f"✗ Failed to import API router: {e}")
        return False

    return True

def test_service_initialization():
    """Test service initialization"""
    print("\nTesting service initialization...")

    try:
        from src.services.multi_agent_search_service_v2 import (
            MultiAgentSearchServiceV2,
            AgentType,
            WorkflowType
        )

        # Create service instance
        service = MultiAgentSearchServiceV2()
        print("✓ Service instance created successfully")

        # Test agent types
        print(f"✓ Available agent types: {[a.value for a in AgentType]}")

        # Test workflow types
        print(f"✓ Available workflow types: {[w.value for w in WorkflowType]}")

        # Get service status
        status = service.get_agent_status()
        print(f"✓ Service status: {status}")

        return True

    except Exception as e:
        print(f"✗ Service initialization failed: {e}")
        return False

def test_query_analysis():
    """Test query analysis functionality"""
    print("\nTesting query analysis...")

    try:
        from src.services.multi_agent_search_service_v2 import (
            MultiAgentSearchServiceV2,
            WorkflowType
        )

        service = MultiAgentSearchServiceV2()

        # Test simple query
        analysis = service._analyze_query("machine learning", WorkflowType.FACTUAL_LOOKUP)
        print(f"✓ Simple query analysis: complexity={analysis['complexity']}")

        # Test complex query
        analysis = service._analyze_query(
            "Explain why deep learning algorithms are effective for image recognition",
            WorkflowType.REASONING
        )
        print(f"✓ Complex query analysis: complexity={analysis['complexity']}")

        return True

    except Exception as e:
        print(f"✗ Query analysis failed: {e}")
        return False

def test_workflow_recommendations():
    """Test workflow recommendations"""
    print("\nTesting workflow recommendations...")

    try:
        from src.services.multi_agent_search_service_v2 import MultiAgentSearchServiceV2

        service = MultiAgentSearchServiceV2()

        # Test different query types
        queries = [
            "What is machine learning?",
            "Compare Python and JavaScript",
            "Explain how neural networks work",
            "Find information about AI ethics"
        ]

        for query in queries:
            recommendations = service.get_workflow_recommendations(query)
            print(f"✓ Query: '{query[:30]}...' -> Workflow: {recommendations['recommended_workflow'].value}")

        return True

    except Exception as e:
        print(f"✗ Workflow recommendations failed: {e}")
        return False

def test_task_creation():
    """Test task creation"""
    print("\nTesting task creation...")

    try:
        from src.services.multi_agent_search_service_v2 import (
            MultiAgentSearchServiceV2,
            WorkflowType
        )

        service = MultiAgentSearchServiceV2()

        query_analysis = {
            'workflow_type': WorkflowType.REASONING,
            'complexity': 'moderate',
            'intent': 'question',
            'domain': 'technology'
        }

        tasks = service._create_workflow_tasks(
            "How does machine learning work?",
            query_analysis,
            "test_user",
            "test_org"
        )

        print(f"✓ Created {len(tasks)} tasks")
        for task in tasks:
            print(f"  - {task.task_id}: {task.agent_type.value}")

        return True

    except Exception as e:
        print(f"✗ Task creation failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Multi-Agent Search System Tests\n")

    tests = [
        ("Import Tests", test_imports),
        ("Service Initialization", test_service_initialization),
        ("Query Analysis", test_query_analysis),
        ("Workflow Recommendations", test_workflow_recommendations),
        ("Task Creation", test_task_creation)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)

        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name} PASSED")
            else:
                print(f"\n❌ {test_name} FAILED")
        except Exception as e:
            print(f"\n❌ {test_name} ERROR: {e}")

    print(f"\n{'='*50}")
    print(f"Test Results: {passed}/{total} tests passed")
    print('='*50)

    if passed == total:
        print("\n🎉 All tests passed! The multi-agent system is ready.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the issues above.")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)