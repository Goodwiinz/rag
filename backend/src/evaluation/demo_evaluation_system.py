"""
RAG Evaluation System Demo

This script demonstrates the complete evaluation framework for the multimodal
Enterprise RAG system, including success criteria, test datasets, and automated
evaluation runner.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

# Import evaluation components
from .success_criteria import success_criteria, QueryType, ModalityType, MetricCategory
from .test_datasets import test_datasets, DatasetCategory
from .deepeval_integration import deepeval_integration, EvaluationFramework, DeepEvalTestCase
from .evaluation_runner import evaluation_runner, EvaluationFrequency

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RAGEvaluationDemo:
    """
    Demonstration of the complete RAG evaluation system
    """

    def __init__(self):
        self.output_dir = Path("evaluation_results")
        self.output_dir.mkdir(exist_ok=True)

    async def run_complete_demo(self):
        """Run the complete evaluation system demo"""
        print("🚀 RAG Evaluation System Demo")
        print("=" * 50)

        # 1. Showcase Success Criteria Framework
        await self.demo_success_criteria()

        # 2. Showcase Test Datasets
        await self.demo_test_datasets()

        # 3. Showcase DeepEval Integration
        await self.demo_deepeval_integration()

        # 4. Showcase Evaluation Runner
        await self.demo_evaluation_runner()

        # 5. Generate comprehensive report
        await self.generate_comprehensive_report()

        print("\n✅ Demo completed successfully!")
        print(f"📁 Results saved to: {self.output_dir}")

    async def demo_success_criteria(self):
        """Demonstrate the success criteria framework"""
        print("\n📋 1. Success Criteria Framework")
        print("-" * 30)

        # Show success thresholds
        print("🎯 Success Thresholds:")
        key_metrics = ["answer_relevancy", "faithfulness", "contextual_relevancy", "hallucination_rate"]
        for metric in key_metrics:
            threshold = success_criteria.thresholds[metric]
            print(f"  • {metric}: {threshold.minimum_threshold:.2f} (min) → {threshold.target_threshold:.2f} (target)")
            print(f"    {threshold.description}")

        # Show query type requirements
        print(f"\n🔍 Supported Query Types: {len(QueryType)}")
        for query_type in QueryType:
            requirements = success_criteria.get_success_criteria_for_query_type(query_type)
            print(f"  • {query_type.value}: {requirements.get('description', 'N/A')}")
            print(f"    Required metrics: {', '.join(requirements.get('success_metrics', []))[:3]}...")
            print(f"    Minimum threshold: {requirements.get('minimum_threshold', 0.0):.2f}")

        # Show modality requirements
        print(f"\n🎨 Supported Modalities: {len(ModalityType)}")
        for modality in ModalityType:
            requirements = success_criteria.modality_requirements[modality]
            print(f"  • {modality.value}: {len(requirements['supported_formats'])} formats, {len(requirements['processing_capabilities'])} capabilities")

        # Export success criteria
        criteria_file = self.output_dir / "success_criteria.json"
        with open(criteria_file, 'w') as f:
            json.dump(success_criteria.export_success_criteria(), f, indent=2)
        print(f"\n💾 Success criteria exported to: {criteria_file}")

    async def demo_test_datasets(self):
        """Demonstrate the test datasets"""
        print("\n📚 2. Test Datasets")
        print("-" * 20)

        # Show dataset overview
        total_datasets = len(test_datasets.datasets)
        total_test_cases = sum(len(ds.test_cases) for ds in test_datasets.datasets.values())
        print(f"📊 Dataset Overview:")
        print(f"  • Total datasets: {total_datasets}")
        print(f"  • Total test cases: {total_test_cases}")

        # Show datasets by category
        print(f"\n📂 Datasets by Category:")
        for category in DatasetCategory:
            datasets = test_datasets.get_datasets_by_category(category)
            total_cases = sum(len(ds.test_cases) for ds in datasets)
            print(f"  • {category.value}: {len(datasets)} datasets, {total_cases} test cases")

        # Show example test cases
        print(f"\n📝 Example Test Cases:")
        example_datasets = ["basic_factual_lookup", "enterprise_business_intelligence", "multimodal_cross_modal"]
        for dataset_name in example_datasets:
            dataset = test_datasets.get_dataset(dataset_name)
            if dataset and dataset.test_cases:
                test_case = dataset.test_cases[0]
                print(f"\n  📋 {dataset.name} ({dataset.query_type.value}):")
                print(f"    Query: {test_case.input}")
                print(f"    Expected: {test_case.expected_output}")
                print(f"    Modalities: {[m.value for m in test_case.modalities]}")

        # Export dataset configurations
        datasets_file = self.output_dir / "test_datasets.json"
        with open(datasets_file, 'w') as f:
            json.dump(test_datasets.export_dataset_configs(), f, indent=2)
        print(f"\n💾 Dataset configurations exported to: {datasets_file}")

    async def demo_deepeval_integration(self):
        """Demonstrate DeepEval integration"""
        print("\n🔬 3. DeepEval Integration")
        print("-" * 25)

        # Show integration status
        print(f"📡 DeepEval Available: {deepeval_integration.is_available}")
        print(f"🤖 Evaluation Models: {len(deepeval_integration.evaluation_models)}")
        print(f"📏 Custom Metrics: {len(deepeval_integration.custom_metrics)}")

        # Run a small evaluation demo
        print(f"\n🧪 Running Sample Evaluation:")

        # Create sample test cases
        sample_test_cases = [
            DeepEvalTestCase(
                input="What is the revenue of Microsoft in 2023?",
                actual_output="Microsoft reported revenue of $211.9 billion in 2023.",
                retrieval_context=[
                    "Microsoft's FY2023 revenue was $211.9 billion, up 7% from previous year.",
                    "The company showed strong growth in cloud services."
                ],
                expected_output="Microsoft's 2023 revenue was $211.9 billion.",
                query_type=QueryType.FACTUAL_LOOKUP,
                modalities=[ModalityType.TEXT],
                test_id="demo_001"
            ),
            DeepEvalTestCase(
                input="How does the performance of Product A compare to Product B?",
                actual_output="Product A outperforms Product B in North American markets with 15% higher revenue, while Product B shows stronger performance in European markets with 20% higher revenue.",
                retrieval_context=[
                    "Product A North America revenue: $45M, Product B: $38M",
                    "Product A Europe revenue: $32M, Product B: $38M",
                    "Market performance varies significantly by region."
                ],
                expected_output="Product A stronger in North America, Product B stronger in Europe.",
                query_type=QueryType.COMPARISON,
                modalities=[ModalityType.TEXT],
                test_id="demo_002"
            )
        ]

        # Run evaluation with different frameworks
        frameworks = [EvaluationFramework.CUSTOM, EvaluationFramework.HYBRID]

        for framework in frameworks:
            print(f"\n  🔄 Running {framework.value} evaluation...")
            start_time = time.time()

            try:
                results = await deepeval_integration.run_comprehensive_evaluation(
                    test_cases=sample_test_cases,
                    query_type=QueryType.FACTUAL_LOOKUP,
                    framework=framework,
                    organization_id="demo",
                    user_id="demo_user"
                )

                execution_time = time.time() - start_time
                print(f"    ✅ Completed in {execution_time:.2f}s")
                print(f"    📊 Overall Score: {results.overall_score:.3f}")
                print(f"    🎯 Success Rate: {results.success_rate:.1f}%")
                print(f"    📋 Test Cases: {results.test_cases_evaluated}")
                print(f"    ⚠️  Violations: {len(results.threshold_violations)}")

                # Save detailed results
                results_file = self.output_dir / f"deepeval_results_{framework.value}.json"
                with open(results_file, 'w') as f:
                    json.dump(results.__dict__, f, default=str, indent=2)
                print(f"    💾 Results saved to: {results_file}")

            except Exception as e:
                print(f"    ❌ Error: {str(e)}")

        # Generate and display report
        print(f"\n📄 Generating Evaluation Report:")
        try:
            results = await deepeval_integration.run_comprehensive_evaluation(
                test_cases=sample_test_cases[:1],  # Use one test case for demo
                framework=EvaluationFramework.CUSTOM,
                organization_id="demo",
                user_id="demo_user"
            )

            report = deepeval_integration.generate_evaluation_report(results, include_recommendations=True)
            report_file = self.output_dir / "evaluation_report.md"
            with open(report_file, 'w') as f:
                f.write(report)
            print(f"    📝 Report saved to: {report_file}")
            print(f"    📊 Report preview (first 500 chars):")
            print(f"    {report[:500]}...")

        except Exception as e:
            print(f"    ❌ Error generating report: {str(e)}")

    async def demo_evaluation_runner(self):
        """Demonstrate the evaluation runner"""
        print("\n🏃 4. Evaluation Runner")
        print("-" * 22)

        # Show available schedules
        print(f"⏰ Available Schedules: {len(evaluation_runner.schedules)}")
        for name, schedule in evaluation_runner.schedules.items():
            status = "✅" if schedule.enabled else "❌"
            print(f"  {status} {name} ({schedule.frequency.value})")
            print(f"      Datasets: {len(schedule.datasets)}")
            print(f"      Recipients: {len(schedule.recipients)}")

        # Run a scheduled evaluation demo
        print(f"\n🚀 Running Scheduled Evaluation Demo:")

        # Use a lightweight schedule for demo
        demo_schedule = "daily_basic_check"
        if demo_schedule in evaluation_runner.schedules:
            print(f"  📅 Running: {demo_schedule}")
            start_time = time.time()

            try:
                report = await evaluation_runner.run_scheduled_evaluation(
                    schedule_name=demo_schedule,
                    organization_id="demo",
                    user_id="demo_user"
                )

                execution_time = time.time() - start_time
                print(f"    ✅ Completed in {execution_time:.2f}s")
                print(f"    📊 Overall Score: {report.overall_score:.3f}")
                print(f"    🎯 Success Rate: {report.success_rate:.1f}%")
                print(f"    📋 Query Types: {len(report.individual_results)}")
                print(f"    🚨 Alerts: {len(report.alerts)}")
                print(f"    💡 Recommendations: {len(report.recommendations)}")

                # Show top recommendations
                if report.recommendations:
                    print(f"    📝 Top Recommendations:")
                    for rec in report.recommendations[:3]:
                        print(f"      • {rec}")

                # Save comprehensive report
                report_json = self.output_dir / "evaluation_report_full.json"
                with open(report_json, 'w') as f:
                    json.dump(report.__dict__, f, default=str, indent=2)
                print(f"    💾 Full report saved to: {report_json}")

                # Save markdown report
                report_md = self.output_dir / "evaluation_report_full.md"
                evaluation_runner.save_report_to_file(report, str(report_md), "markdown")
                print(f"    📝 Markdown report saved to: {report_md}")

            except Exception as e:
                print(f"    ❌ Error: {str(e)}")
        else:
            print(f"    ⚠️ Schedule '{demo_schedule}' not found")

        # Show evaluation summary
        print(f"\n📈 Evaluation Summary:")
        summary = evaluation_runner.get_evaluation_summary(days=7)  # Last 7 days
        if "message" not in summary:
            print(f"  📊 Recent evaluations: {summary['total_evaluations']}")
            print(f"  📈 Average score: {summary['average_score']:.3f}")
            print(f"  🎯 Average success rate: {summary['average_success_rate']:.1f}%")
            print(f"  📊 Trend: {summary['evaluation_trend']}")
        else:
            print(f"  ℹ️ {summary['message']}")

    async def generate_comprehensive_report(self):
        """Generate a comprehensive demo report"""
        print("\n📊 5. Comprehensive Report Generation")
        print("-" * 38)

        # Create summary statistics
        total_thresholds = len(success_criteria.thresholds)
        total_datasets = len(test_datasets.datasets)
        total_test_cases = sum(len(ds.test_cases) for ds in test_datasets.datasets())
        total_schedules = len(evaluation_runner.schedules)

        # Create comprehensive report
        report = f"""# RAG Evaluation System Demo Report

**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC

## System Overview

This demo showcases the complete multimodal Enterprise RAG evaluation system with the following components:

### 🎯 Success Criteria Framework
- **Success Thresholds**: {total_thresholds} metrics defined
- **Query Types**: {len(QueryType)} supported
- **Modalities**: {len(ModalityType)} supported
- **Metric Categories**: {len(MetricCategory)} categories

### 📚 Test Datasets
- **Total Datasets**: {total_datasets}
- **Total Test Cases**: {total_test_cases}
- **Categories**: {len(DatasetCategory)} different categories
- **Difficulty Levels**: Easy, Medium, Hard

### 🔬 Evaluation Frameworks
- **DeepEval Integration**: {'✅ Available' if deepeval_integration.is_available else '❌ Not Available'}
- **Custom Framework**: ✅ Always available
- **Hybrid Approach**: ✅ Combines both frameworks

### 🏃 Automated Evaluation Runner
- **Schedules**: {total_schedules} predefined schedules
- **Alert System**: Multi-level alerting (Info, Warning, Error, Critical)
- **Reporting**: JSON and Markdown formats
- **History Tracking**: Evaluation history and trends

## Key Features Demonstrated

### 1. Evaluation-First Development ✅
- Success criteria defined before implementation
- Clear thresholds and targets for all metrics
- Query-type specific requirements
- Modality-specific validation

### 2. Comprehensive Testing ✅
- Multiple query types (factual, reasoning, comparison, etc.)
- Cross-modal evaluation capabilities
- Edge case and security testing
- Performance stress testing

### 3. Automated Evaluation ✅
- Scheduled evaluations (daily, weekly, monthly)
- Real-time alerting system
- Comprehensive reporting
- Historical trend analysis

### 4. Enterprise-Grade Features ✅
- Multi-tenant support
- Role-based access control
- Comprehensive audit logging
- Performance monitoring

## Next Steps

1. **Integration**: Integrate with your existing RAG system
2. **Customization**: Customize success criteria for your specific use case
3. **Expansion**: Add custom test datasets and evaluation metrics
4. **Deployment**: Deploy the automated scheduler in production
5. **Monitoring**: Set up alert recipients and notification channels

## Files Generated

- `success_criteria.json` - Complete success criteria configuration
- `test_datasets.json` - Test dataset specifications
- `deepeval_results_*.json` - Sample evaluation results
- `evaluation_report*.md` - Sample evaluation reports
- `evaluation_report_full.json` - Comprehensive evaluation report

---

*This demo showcases a production-ready evaluation framework for multimodal RAG systems.*
"""

        # Save comprehensive report
        report_file = self.output_dir / "demo_comprehensive_report.md"
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"📝 Comprehensive report saved to: {report_file}")

        # Create summary JSON
        summary = {
            "demo_timestamp": datetime.now(timezone.utc).isoformat(),
            "system_components": {
                "success_criteria": {
                    "total_thresholds": total_thresholds,
                    "query_types": len(QueryType),
                    "modalities": len(ModalityType),
                    "metric_categories": len(MetricCategory)
                },
                "test_datasets": {
                    "total_datasets": total_datasets,
                    "total_test_cases": total_test_cases,
                    "categories": len(DatasetCategory)
                },
                "evaluation_frameworks": {
                    "deepeval_available": deepeval_integration.is_available,
                    "custom_framework": True,
                    "hybrid_approach": True
                },
                "evaluation_runner": {
                    "total_schedules": total_schedules,
                    "alert_levels": len(evaluation_runner.alert_handlers),
                    "automated_reporting": True
                }
            },
            "features_demonstrated": [
                "evaluation_first_development",
                "comprehensive_testing",
                "automated_evaluation",
                "enterprise_grade_features"
            ]
        }

        summary_file = self.output_dir / "demo_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"📊 Demo summary saved to: {summary_file}")


async def main():
    """Main demo function"""
    demo = RAGEvaluationDemo()
    await demo.run_complete_demo()


if __name__ == "__main__":
    print("🎯 Starting RAG Evaluation System Demo...")
    print("This demo showcases the complete evaluation framework for multimodal Enterprise RAG systems.")
    print()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {str(e)}")
        logging.exception("Demo execution failed")