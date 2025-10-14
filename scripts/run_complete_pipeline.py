#!/usr/bin/env python3
"""
Complete Dataset Pipeline Runner
Orchestrates the full dataset integration: download -> process -> upload -> evaluate
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime
import subprocess
import json
from typing import Dict, Any

# Import our modules
from dataset_integration import DatasetIntegrator
from dataset_upload_api import DatasetUploader, UploadConfig
from evaluation_framework import EvaluationRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class CompletePipeline:
    """Orchestrates the complete dataset pipeline"""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.results = {
            "integration": {},
            "upload": {},
            "evaluation": {},
            "summary": {}
        }

    async def check_system_health(self) -> bool:
        """Check if the RAG system is running"""
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_base_url}/health", timeout=10) as response:
                    if response.status == 200:
                        logger.info("✅ RAG system is healthy")
                        return True
                    else:
                        logger.error(f"❌ RAG system returned status {response.status}")
                        return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to RAG system: {str(e)}")
            return False

    def run_dataset_integration(self) -> Dict[str, bool]:
        """Run dataset integration (download and processing)"""
        logger.info("🚀 Starting Dataset Integration Phase")
        logger.info("=" * 60)

        try:
            integrator = DatasetIntegrator(self.api_base_url)
            results = integrator.integrate_all_datasets()

            # Generate integration report
            report = integrator.create_integration_report(results)
            report_path = Path("pipeline/integration_report.txt")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, 'w') as f:
                f.write(report)

            logger.info("✅ Dataset integration completed")
            logger.info(f"📄 Report saved to: {report_path}")

            self.results["integration"] = results
            return results

        except Exception as e:
            logger.error(f"❌ Dataset integration failed: {str(e)}")
            self.results["integration"] = {"error": str(e)}
            return {"error": str(e)}

    async def run_dataset_upload(self) -> Dict[str, Any]:
        """Run dataset upload to RAG system"""
        logger.info("📤 Starting Dataset Upload Phase")
        logger.info("=" * 60)

        try:
            config = UploadConfig(
                batch_size=10,
                max_retries=3,
                max_concurrent_uploads=5
            )

            async with DatasetUploader(self.api_base_url, config) as uploader:
                # Authenticate
                logger.info("🔐 Authenticating with RAG system...")
                if not await uploader.authenticate():
                    raise Exception("Authentication failed")

                logger.info("✅ Authentication successful")

                # Upload datasets
                results = await uploader.upload_all_datasets()

                # Generate upload report
                report = uploader.generate_upload_report(results)
                report_path = Path("pipeline/upload_report.txt")
                report_path.parent.mkdir(parents=True, exist_ok=True)
                with open(report_path, 'w') as f:
                    f.write(report)

                logger.info("✅ Dataset upload completed")
                logger.info(f"📄 Report saved to: {report_path}")

                self.results["upload"] = results
                return results

        except Exception as e:
            logger.error(f"❌ Dataset upload failed: {str(e)}")
            self.results["upload"] = {"error": str(e)}
            return {"error": str(e)}

    async def run_evaluation(self) -> Dict[str, Any]:
        """Run evaluation on uploaded datasets"""
        logger.info("🔍 Starting Evaluation Phase")
        logger.info("=" * 60)

        try:
            runner = EvaluationRunner(self.api_base_url)

            # Authenticate
            logger.info("🔐 Authenticating for evaluation...")
            if not runner.evaluator.authenticate():
                raise Exception("Authentication failed")

            logger.info("✅ Authentication successful")

            # Run evaluations
            results = runner.run_all_evaluations()

            # Generate summary report
            summary = runner.generate_summary_report(results)
            summary_path = Path("pipeline/evaluation_summary.txt")
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            with open(summary_path, 'w') as f:
                f.write(summary)

            logger.info("✅ Evaluation completed")
            logger.info(f"📄 Summary saved to: {summary_path}")

            self.results["evaluation"] = results
            return results

        except Exception as e:
            logger.error(f"❌ Evaluation failed: {str(e)}")
            self.results["evaluation"] = {"error": str(e)}
            return {"error": str(e)}

    def generate_final_report(self) -> str:
        """Generate a comprehensive final report"""
        report = []
        report.append("Complete Dataset Pipeline Report")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append(f"API Base URL: {self.api_base_url}")
        report.append("")

        # Integration Phase
        report.append("1. DATASET INTEGRATION PHASE")
        report.append("-" * 40)
        integration_results = self.results.get("integration", {})

        if "error" in integration_results:
            report.append(f"Status: ❌ FAILED")
            report.append(f"Error: {integration_results['error']}")
        else:
            successful = sum(1 for success in integration_results.values() if success)
            total = len(integration_results)
            report.append(f"Status: ✅ SUCCESS")
            report.append(f"Datasets Integrated: {successful}/{total}")

            for dataset, success in integration_results.items():
                status = "✅" if success else "❌"
                report.append(f"  {dataset}: {status}")
        report.append("")

        # Upload Phase
        report.append("2. DATASET UPLOAD PHASE")
        report.append("-" * 40)
        upload_results = self.results.get("upload", {})

        if "error" in upload_results:
            report.append(f"Status: ❌ FAILED")
            report.append(f"Error: {upload_results['error']}")
        else:
            total_docs = sum(r.get("total_documents", 0) for r in upload_results.values() if isinstance(r, dict))
            total_successful = sum(r.get("successful_uploads", 0) for r in upload_results.values() if isinstance(r, dict))

            report.append(f"Status: ✅ SUCCESS")
            report.append(f"Total Documents Uploaded: {total_successful}/{total_docs}")
            report.append(f"Success Rate: {(total_successful / total_docs * 100) if total_docs > 0 else 0:.1f}%")

            for dataset, result in upload_results.items():
                if isinstance(result, dict) and "total_documents" in result:
                    status = "✅" if result.get("failed_uploads", 0) == 0 else "⚠️"
                    report.append(f"  {dataset}: {status} {result.get('successful_uploads', 0)}/{result.get('total_documents', 0)}")
                elif isinstance(result, dict) and "error" in result:
                    report.append(f"  {dataset}: ❌ {result['error']}")
        report.append("")

        # Evaluation Phase
        report.append("3. EVALUATION PHASE")
        report.append("-" * 40)
        evaluation_results = self.results.get("evaluation", {})

        if "error" in evaluation_results:
            report.append(f"Status: ❌ FAILED")
            report.append(f"Error: {evaluation_results['error']}")
        else:
            report.append(f"Status: ✅ SUCCESS")
            report.append(f"Datasets Evaluated: {len(evaluation_results)}")

            # Calculate overall metrics
            all_evaluations = list(evaluation_results.values())
            if all_evaluations:
                total_queries = sum(eval.total_queries for eval in all_evaluations)
                successful_queries = sum(eval.successful_queries for eval in all_evaluations)
                overall_success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0

                report.append(f"Total Queries Evaluated: {total_queries}")
                report.append(f"Overall Success Rate: {overall_success_rate:.1f}%")

                # Performance metrics summary
                if hasattr(all_evaluations[0], 'metrics'):
                    avg_answer_relevancy = sum(eval.metrics.get('answer_relevancy', 0) for eval in all_evaluations) / len(all_evaluations)
                    avg_faithfulness = sum(eval.metrics.get('faithfulness', 0) for eval in all_evaluations) / len(all_evaluations)
                    avg_response_time = sum(eval.average_response_time for eval in all_evaluations) / len(all_evaluations)

                    report.append(f"Average Answer Relevancy: {avg_answer_relevancy:.3f}")
                    report.append(f"Average Faithfulness: {avg_faithfulness:.3f}")
                    report.append(f"Average Response Time: {avg_response_time:.2f}ms")

            for dataset, evaluation in evaluation_results.items():
                if hasattr(evaluation, 'successful_queries'):
                    report.append(f"  {dataset}: {evaluation.successful_queries}/{evaluation.total_queries} queries")
        report.append("")

        # Summary
        report.append("4. PIPELINE SUMMARY")
        report.append("-" * 40)

        integration_success = "error" not in self.results.get("integration", {})
        upload_success = "error" not in self.results.get("upload", {})
        evaluation_success = "error" not in self.results.get("evaluation", {})

        overall_success = integration_success and upload_success and evaluation_success

        if overall_success:
            report.append("Overall Status: ✅ SUCCESS")
            report.append("All pipeline phases completed successfully!")
        else:
            report.append("Overall Status: ⚠️  PARTIAL SUCCESS")
            failed_phases = []
            if not integration_success:
                failed_phases.append("Integration")
            if not upload_success:
                failed_phases.append("Upload")
            if not evaluation_success:
                failed_phases.append("Evaluation")
            report.append(f"Failed Phases: {', '.join(failed_phases)}")

        report.append("")
        report.append("Generated Files:")
        report.append("  - pipeline/integration_report.txt")
        report.append("  - pipeline/upload_report.txt")
        report.append("  - pipeline/evaluation_summary.txt")
        report.append("  - evaluation/reports/ (individual dataset reports)")
        report.append("  - evaluation/plots/ (performance visualizations)")
        report.append("  - pipeline.log (detailed execution log)")

        return "\n".join(report)

    async def run_complete_pipeline(self) -> Dict[str, Any]:
        """Run the complete pipeline"""
        logger.info("🚀 Starting Complete Dataset Pipeline")
        logger.info("=" * 80)

        start_time = datetime.now()

        try:
            # Phase 1: Check system health
            logger.info("🔍 Phase 0: Checking System Health")
            if not await self.check_system_health():
                raise Exception("RAG system is not available")

            # Phase 2: Dataset Integration
            logger.info("\n📥 Phase 1: Dataset Integration")
            integration_results = self.run_dataset_integration()

            # Phase 3: Dataset Upload
            logger.info("\n📤 Phase 2: Dataset Upload")
            upload_results = await self.run_dataset_upload()

            # Phase 4: Evaluation
            logger.info("\n🔍 Phase 3: Evaluation")
            evaluation_results = await self.run_evaluation()

            # Generate final report
            logger.info("\n📊 Generating Final Report")
            final_report = self.generate_final_report()

            # Save final report
            final_report_path = Path("pipeline/final_report.txt")
            final_report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(final_report_path, 'w') as f:
                f.write(final_report)

            # Save results as JSON for programmatic access
            json_results_path = Path("pipeline/results.json")
            with open(json_results_path, 'w') as f:
                # Convert datetime objects to strings for JSON serialization
                serializable_results = self._make_serializable(self.results)
                json.dump(serializable_results, f, indent=2)

            end_time = datetime.now()
            duration = end_time - start_time

            logger.info("\n" + "=" * 80)
            logger.info("🎉 COMPLETE PIPELINE FINISHED")
            logger.info(f"Total Duration: {duration}")
            logger.info(f"Final Report: {final_report_path}")
            logger.info(f"JSON Results: {json_results_path}")
            logger.info("=" * 80)

            print("\n" + final_report)

            return {
                "success": True,
                "duration": str(duration),
                "results": self.results,
                "final_report_path": str(final_report_path),
                "json_results_path": str(json_results_path)
            }

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "results": self.results
            }

    def _make_serializable(self, obj):
        """Convert objects to JSON-serializable format"""
        if hasattr(obj, '__dict__'):
            return self._make_serializable(obj.__dict__)
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj

async def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(description="Run complete dataset pipeline")
    parser.add_argument("--api-url", default="http://localhost:8000",
                       help="RAG system API base URL")
    parser.add_argument("--phase", choices=["integration", "upload", "evaluation", "all"],
                       default="all", help="Run specific phase or all phases")

    args = parser.parse_args()

    pipeline = CompletePipeline(args.api_url)

    if args.phase == "all":
        result = await pipeline.run_complete_pipeline()
    elif args.phase == "integration":
        result = pipeline.run_dataset_integration()
    elif args.phase == "upload":
        result = await pipeline.run_dataset_upload()
    elif args.phase == "evaluation":
        result = await pipeline.run_evaluation()

    if isinstance(result, dict) and result.get("success") is False:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())