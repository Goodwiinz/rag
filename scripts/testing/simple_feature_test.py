#!/usr/bin/env python3
"""
Simple Feature Test - No external dependencies

This script tests the platform by importing modules directly and checking
if the key features are implemented.
"""

import os
import sys
import importlib
import inspect
from pathlib import Path

def check_file_exists(file_path: str) -> bool:
    """Check if file exists"""
    return os.path.exists(file_path)

def check_module_import(module_path: str) -> bool:
    """Check if module can be imported"""
    try:
        importlib.import_module(module_path)
        return True
    except ImportError as e:
        print(f"  ❌ Import failed: {str(e)}")
        return False

def check_class_methods(module_path: str, class_name: str, expected_methods: list) -> bool:
    """Check if class has expected methods"""
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)

        existing_methods = [method for method in dir(cls) if not method.startswith('_')]
        missing_methods = [method for method in expected_methods if method not in existing_methods]

        if missing_methods:
            print(f"  ⚠️  Missing methods: {missing_methods}")
            return False
        else:
            print(f"  ✅ All expected methods present: {expected_methods}")
            return True
    except Exception as e:
        print(f"  ❌ Class check failed: {str(e)}")
        return False

def test_t3_analytics():
    """Test T3 Analytics implementation"""
    print("\n🔍 Testing T3 Analytics Features")
    print("-" * 40)

    t3_files = [
        "backend/src/services/quality_metrics_service.py",
        "backend/src/services/performance_dashboard_service.py",
        "backend/src/services/user_behavior_service.py",
        "backend/src/services/quality_recommendations_service.py",
        "backend/src/cache/analytics_cache.py",
        "backend/src/tasks/analytics_processor.py",
        "backend/src/tasks/data_aggregator.py",
        "backend/src/tasks/recommendation_generator.py",
        "backend/src/api/quality_metrics.py",
        "backend/src/api/performance_dashboard.py",
        "backend/src/api/user_behavior.py",
        "backend/src/api/quality_recommendations.py",
        "backend/src/schemas/analytics_query.py",
        "backend/src/schemas/analytics_response.py"
    ]

    t3_modules = [
        "src.services.quality_metrics_service",
        "src.services.performance_dashboard_service",
        "src.services.user_behavior_service",
        "src.services.quality_recommendations_service",
        "src.cache.analytics_cache"
    ]

    # Check file existence
    existing_files = 0
    for file_path in t3_files:
        if check_file_exists(file_path):
            print(f"  ✅ {file_path}")
            existing_files += 1
        else:
            print(f"  ❌ {file_path}")

    # Check module imports
    importable_modules = 0
    for module_path in t3_modules:
        if check_module_import(module_path):
            print(f"  ✅ {module_path}")
            importable_modules += 1
        else:
            print(f"  ❌ {module_path}")

    # Check specific class methods
    quality_metrics_ok = check_class_methods(
        "src.services.quality_metrics_service",
        "QualityMetricsService",
        ["calculate_answer_relevancy", "calculate_factual_accuracy", "calculate_contextual_precision"]
    )

    print(f"\n📊 T3 Analytics Summary:")
    print(f"  Files: {existing_files}/{len(t3_files)} exist")
    print(f"  Modules: {importable_modules}/{len(t3_modules)} importable")
    print(f"  Core classes: {'✅' if quality_metrics_ok else '❌'}")

    return existing_files >= len(t3_files) * 0.8 and importable_modules >= len(t3_modules) * 0.8

def test_t4_security():
    """Test T4 Security implementation"""
    print("\n🔒 Testing T4 Security Features")
    print("-" * 40)

    t4_files = [
        "backend/src/core/encryption.py",
        "backend/src/models/encrypted_fields.py",
        "backend/src/models/encrypted_user.py",
        "backend/src/services/encryption_service.py",
        "backend/src/middleware/encryption_middleware.py",
        "backend/src/api/encryption.py",
        "backend/src/config/encryption_config.py",
        "backend/src/migrations/add_encryption_tables.py",
        "backend/src/middleware/multi_tenancy.py",
        "backend/src/middleware/rbac.py",
        "backend/src/services/audit_service.py",
        "backend/src/api/compliance.py",
        "backend/src/middleware/rate_limiting.py",
        "backend/src/services/rbac_service.py",
        "backend/src/api/rbac_management.py",
        "backend/src/services/tenant_service.py",
        "backend/src/api/tenant_management.py"
    ]

    t4_modules = [
        "src.core.encryption",
        "src.services.encryption_service",
        "src.services.audit_service",
        "src.services.rbac_service",
        "src.services.tenant_service"
    ]

    # Check file existence
    existing_files = 0
    for file_path in t4_files:
        if check_file_exists(file_path):
            print(f"  ✅ {file_path}")
            existing_files += 1
        else:
            print(f"  ❌ {file_path}")

    # Check module imports
    importable_modules = 0
    for module_path in t4_modules:
        if check_module_import(module_path):
            print(f"  ✅ {module_path}")
            importable_modules += 1
        else:
            print(f"  ❌ {module_path}")

    # Check specific class methods
    encryption_ok = check_class_methods(
        "src.core.encryption",
        "KeyManager",
        ["generate_key", "get_key", "rotate_key"]
    )

    audit_ok = check_class_methods(
        "src.services.audit_service",
        "AuditService",
        ["log_event", "get_compliance_report", "log_security_incident"]
    )

    print(f"\n🛡️ T4 Security Summary:")
    print(f"  Files: {existing_files}/{len(t4_files)} exist")
    print(f"  Modules: {importable_modules}/{len(t4_modules)} importable")
    print(f"  Encryption classes: {'✅' if encryption_ok else '❌'}")
    print(f"  Audit classes: {'✅' if audit_ok else '❌'}")

    return existing_files >= len(t4_files) * 0.8 and importable_modules >= len(t4_modules) * 0.8

def test_core_infrastructure():
    """Test core infrastructure"""
    print("\n🏗️ Testing Core Infrastructure")
    print("-" * 40)

    core_files = [
        "backend/src/core/database.py",
        "backend/src/core/config.py",
        "backend/src/core/security.py",
        "backend/src/core/dependencies.py",
        "backend/src/models/base.py",
        "backend/src/models/user.py",
        "backend/src/models/organization.py",
        "backend/src/models/document.py",
        "backend/src/models/search.py",
        "backend/src/services/processing_service.py",
        "backend/src/services/search_service.py",
        "backend/src/api/auth.py",
        "backend/src/api/documents.py",
        "backend/src/api/search.py",
        "backend/src/main.py"
    ]

    # Check file existence
    existing_files = 0
    for file_path in core_files:
        if check_file_exists(file_path):
            print(f"  ✅ {file_path}")
            existing_files += 1
        else:
            print(f"  ❌ {file_path}")

    print(f"\n⚙️ Core Infrastructure Summary:")
    print(f"  Files: {existing_files}/{len(core_files)} exist")

    return existing_files >= len(core_files) * 0.8

def test_documentation():
    """Test documentation files"""
    print("\n📚 Testing Documentation")
    print("-" * 40)

    doc_files = [
        "TESTING_GUIDE.md",
        "README.md",
        "t3ToDoList.md",
        "specs/001-multimodal-enterprise-rag/plan.md",
        "specs/001-multimodal-enterprise-rag/data-model.md",
        "specs/001-multimodal-enterprise-rag/quickstart.md",
        "quick_test.py"
    ]

    existing_files = 0
    for file_path in doc_files:
        if check_file_exists(file_path):
            print(f"  ✅ {file_path}")
            existing_files += 1
        else:
            print(f"  ❌ {file_path}")

    print(f"\n📖 Documentation Summary:")
    print(f"  Files: {existing_files}/{len(doc_files)} exist")

    return existing_files >= len(doc_files) * 0.7

def test_docker_configuration():
    """Test Docker configuration"""
    print("\n🐳 Testing Docker Configuration")
    print("-" * 40)

    docker_files = [
        "docker-compose.yml",
        "backend/Dockerfile.simple",
        "backend/Dockerfile.worker.simple",
        "frontend/Dockerfile"
    ]

    existing_files = 0
    for file_path in docker_files:
        if check_file_exists(file_path):
            print(f"  ✅ {file_path}")
            existing_files += 1
        else:
            print(f"  ❌ {file_path}")

    # Check docker-compose.yml content
    if check_file_exists("docker-compose.yml"):
        with open("docker-compose.yml", "r") as f:
            content = f.read()
            services = ["backend", "frontend", "postgres", "redis", "neo4j", "qdrant"]
            found_services = [service for service in services if service in content]
            print(f"  🐋 Docker services found: {len(found_services)}/{len(services)}")

    print(f"\n🐳 Docker Configuration Summary:")
    print(f"  Files: {existing_files}/{len(docker_files)} exist")

    return existing_files >= len(docker_files) * 0.7

def main():
    """Main test function"""
    print("🔍 RAG Platform Simple Feature Test")
    print("=" * 50)
    print("This script tests the current implementation without external dependencies.")
    print()

    results = {}

    # Run tests
    results["Core Infrastructure"] = test_core_infrastructure()
    results["T3 Analytics"] = test_t3_analytics()
    results["T4 Security"] = test_t4_security()
    results["Docker Configuration"] = test_docker_configuration()
    results["Documentation"] = test_documentation()

    # Summary
    print("\n" + "=" * 50)
    print("📊 FINAL TEST SUMMARY")
    print("=" * 50)

    passed = sum(results.values())
    total = len(results)

    for category, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {category}")

    print("\n" + "-" * 50)
    print(f"🎯 Overall Progress: {passed}/{total} categories implemented ({(passed/total)*100:.1f}%)")

    if passed == total:
        print("🎉 Excellent! All major feature categories are implemented!")
    elif passed >= total * 0.8:
        print("👍 Great progress! Most features are implemented.")
    elif passed >= total * 0.6:
        print("👍 Good progress! Several features are implemented.")
    else:
        print("🔧 Some features need implementation.")

    print("\n🚀 Next Steps:")
    print("1. Start the platform: docker-compose up -d")
    print("2. Run comprehensive tests: python3 quick_test.py")
    print("3. Test the web interface: http://localhost:3000")
    print("4. Test the API: http://localhost:8000/docs")

if __name__ == "__main__":
    main()