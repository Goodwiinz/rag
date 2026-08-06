# Multimodal Enterprise RAG Evaluation Framework

This directory contains a comprehensive evaluation framework for the multimodal Enterprise RAG system, following evaluation-first development principles.

## 🏗️ Architecture Overview

The evaluation framework is designed around the principle that **success criteria must be defined before implementation**. It provides comprehensive testing, metrics, and automated evaluation capabilities for enterprise-grade RAG systems.

### Core Components

```
src/evaluation/
├── success_criteria.py          # Success thresholds and requirements
├── deepeval_integration.py      # DeepEval integration and custom metrics
├── test_datasets.py            # Comprehensive test datasets
├── evaluation_runner.py        # Automated evaluation scheduler
├── demo_evaluation_system.py   # Complete demo and showcase
├── rag_evaluation_service.py   # Core RAG evaluation service
└── README.md                   # This documentation
```

## 🎯 Success Criteria Framework

### Query Types Supported

1. **Factual Lookup** - Direct fact retrieval
2. **Reasoning** - Complex inference and reasoning
3. **Summarization** - Document summarization
4. **Comparison** - Comparative analysis
5. **Semantic Linkage** - Relationship discovery
6. **Multimodal Query** - Cross-modal information synthesis
7. **Temporal Query** - Time-based analysis
8. **Causal Query** - Cause-and-effect relationships

### Modalities Supported

- **Text**: PDF, TXT, DOCX, MD, RTF
- **Image**: JPG, PNG, GIF, BMP, TIFF
- **Audio**: MP3, WAV, M4A, FLAC, AAC
- **Video**: MP4, AVI, MOV, MKV, WMV

### Success Thresholds

| Metric | Minimum | Target | Weight |
|--------|---------|--------|--------|
| Answer Relevancy | 0.70 | 0.85 | 25% |
| Faithfulness | 0.90 | 0.95 | 30% |
| Contextual Relevancy | 0.70 | 0.85 | 25% |
| Hallucination Rate | <0.15 | <0.05 | 20% |
| Latency P95 | <3000ms | <2000ms | 10% |

## 📚 Test Datasets

### Categories

1. **Basic Functionality** - Core RAG capabilities
2. **Enterprise Scenarios** - Business intelligence use cases
3. **Multimodal Tests** - Cross-modal evaluation
4. **Edge Cases** - Ambiguous queries, no results
5. **Performance Stress** - High-volume testing
6. **Security Tests** - Injection attacks, unauthorized access

### Sample Test Cases

```python
# Factual Lookup Example
DeepEvalTestCase(
    input="What is the annual revenue of Microsoft for fiscal year 2023?",
    actual_output="Microsoft reported annual revenue of $211.9 billion for fiscal year 2023.",
    retrieval_context=["Microsoft's FY2023 revenue reached $211.9 billion..."],
    expected_output="Microsoft's annual revenue for fiscal year 2023 was $211.9 billion.",
    query_type=QueryType.FACTUAL_LOOKUP,
    modalities=[ModalityType.TEXT]
)

# Multimodal Example
DeepEvalTestCase(
    input="What information do the charts in the Q3 financial report convey?",
    actual_output="Charts show 15% YoY revenue growth with cloud services at 40% of revenue...",
    retrieval_context=["Q3 Financial Presentation contains charts showing..."],
    expected_output="Revenue grew 15% YoY, cloud services are 40% of revenue...",
    query_type=QueryType.MULTIMODAL_QUERY,
    modalities=[ModalityType.TEXT, ModalityType.IMAGE]
)
```

## 🔬 Evaluation Frameworks

### 1. DeepEval Integration

- **Answer Relevancy Metric**: Measures answer relevance to query
- **Faithfulness Metric**: Measures answer support in context
- **Contextual Relevancy Metric**: Measures context relevance to query
- **Hallucination Metric**: Detects fabricated information
- **Custom Metrics**: Cross-modal coherence, entity consistency, temporal consistency

### 2. Custom Framework

- RAG Triad metrics using LLM judgment
- Configurable thresholds per organization
- Fallback scoring when LLM unavailable
- Database integration for persistence

### 3. Hybrid Approach

- Combines DeepEval and custom frameworks
- Weighted scoring (70% DeepEval, 30% custom)
- Comprehensive coverage of evaluation scenarios

## 🏃 Automated Evaluation Runner

### Schedule Types

1. **Daily Basic Check** - Core functionality validation
2. **Weekly Multimodal** - Cross-modal capabilities
3. **Weekly Enterprise** - Business scenario validation
4. **Monthly Full Suite** - Comprehensive evaluation
5. **Daily Security** - Security validation

### Alert System

- **Info**: General information and status updates
- **Warning**: Performance degradation warnings
- **Error**: Critical performance issues
- **Critical**: Security breaches or system failures

### Reporting

- **JSON Format**: Machine-readable detailed results
- **Markdown Format**: Human-readable reports
- **Historical Tracking**: Trend analysis and performance monitoring
- **Recommendations**: Automated improvement suggestions

## 🚀 Quick Start

### 1. Installation

```bash
# Install DeepEval (optional but recommended)
pip install deepeval

# Install evaluation dependencies
pip install schedule  # For automated evaluation runner
```

### 2. Basic Usage

```python
from src.evaluation import success_criteria, test_datasets, deepeval_integration

# Check success criteria
thresholds = success_criteria.thresholds
print(f"Answer Relevancy Threshold: {thresholds['answer_relevancy'].minimum_threshold}")

# Load test datasets
factual_tests = test_datasets.get_dataset("basic_factual_lookup")
print(f"Found {len(factual_tests.test_cases)} factual test cases")

# Run evaluation
results = await deepeval_integration.run_comprehensive_evaluation(
    test_cases=factual_tests.test_cases[:5],
    query_type=QueryType.FACTUAL_LOOKUP,
    framework=EvaluationFramework.HYBRID
)
print(f"Overall Score: {results.overall_score:.3f}")
```

### 3. Automated Evaluation

```python
from src.evaluation import evaluation_runner

# Run scheduled evaluation
report = await evaluation_runner.run_scheduled_evaluation(
    schedule_name="daily_basic_check",
    organization_id="your_org",
    user_id="your_user"
)

# Check results
print(f"Score: {report.overall_score:.3f}")
print(f"Success Rate: {report.success_rate:.1f}%")
print(f"Alerts: {len(report.alerts)}")
```

### 4. Complete Demo

```bash
# Run the complete evaluation system demo
python src/evaluation/demo_evaluation_system.py
```

## 📊 Integration Guide

### 1. Custom Success Criteria

```python
# Define custom thresholds
custom_thresholds = {
    "my_custom_metric": SuccessThreshold(
        metric_name="my_custom_metric",
        minimum_threshold=0.8,
        target_threshold=0.9,
        description="My custom evaluation metric",
        category=MetricCategory.ANSWER_QUALITY,
        weight=0.15
    )
}

# Add to success criteria
success_criteria.thresholds.update(custom_thresholds)
```

### 2. Custom Test Datasets

```python
# Create custom test dataset
custom_test_cases = [
    DeepEvalTestCase(
        input="Your custom query",
        actual_output="Expected answer",
        retrieval_context=["Relevant context"],
        expected_output="Reference answer",
        query_type=QueryType.FACTUAL_LOOKUP,
        modalities=[ModalityType.TEXT]
    )
]

# Create dataset
custom_dataset = TestDataset(
    name="Custom Business Logic",
    description="Tests for specific business logic",
    category=DatasetCategory.ENTERPRISE_SCENARIOS,
    query_type=QueryType.FACTUAL_LOOKUP,
    test_cases=custom_test_cases,
    modalities=[ModalityType.TEXT],
    difficulty_level="medium",
    expected_success_rate=0.85
)

# Add to test datasets
test_datasets.datasets["custom_business_logic"] = custom_dataset
```

### 3. Custom Metrics

```python
# Create custom evaluation metric
class CustomBusinessMetric:
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        # Your custom evaluation logic here
        return 0.85  # Return score between 0-1

# Add to DeepEval integration
deepeval_integration.custom_metrics["custom_business"] = CustomBusinessMetric()
```

## 🔧 Configuration

### Environment Variables

```bash
# OpenAI API (for evaluation)
OPENAI_API_KEY=your_openai_key

# Anthropic API (for evaluation)
ANTHROPIC_API_KEY=your_anthropic_key

# Database configuration
DATABASE_URL=postgresql://user:pass@localhost/rag_db

# Redis (for caching)
REDIS_URL=redis://localhost:6379
```

### Custom Thresholds

```python
# Organization-specific thresholds
org_thresholds = {
    "answer_relevancy": 0.75,  # Higher than default
    "faithfulness": 0.95,      # Stricter requirement
    "latency_p95": 1500        # Faster requirement
}
```

## 📈 Monitoring and Alerting

### Performance Monitoring

- **Real-time Metrics**: Track evaluation scores in real-time
- **Historical Trends**: Monitor performance over time
- **Threshold Violations**: Automatic alerting on threshold breaches
- **Comparative Analysis**: Compare performance across query types

### Alert Recipients

```python
# Configure alert recipients
evaluation_runner.schedules["daily_basic_check"].recipients = [
    "dev-team@company.com",
    "qa-team@company.com",
    "alerts@company.com"
]
```

### Custom Alert Handlers

```python
# Custom alert handler (e.g., Slack integration)
async def send_slack_alert(alert, recipients):
    # Your Slack integration code here
    pass

# Register custom handler
evaluation_runner.alert_handlers[AlertLevel.ERROR] = send_slack_alert
```

## 🎯 Best Practices

### 1. Evaluation-First Development

- Define success criteria before implementing features
- Create test cases for each new capability
- Validate against thresholds continuously

### 2. Comprehensive Testing

- Test all query types and modalities
- Include edge cases and security tests
- Validate performance under load

### 3. Continuous Monitoring

- Schedule regular automated evaluations
- Monitor trends and performance degradation
- Set up appropriate alerting

### 4. Iterative Improvement

- Use evaluation results to guide improvements
- Update success criteria as requirements evolve
- Expand test coverage based on usage patterns

## 📋 Troubleshooting

### Common Issues

1. **DeepEval Not Available**
   ```bash
   pip install deepeval
   ```

2. **Missing API Keys**
   - Set OPENAI_API_KEY and/or ANTHROPIC_API_KEY
   - Check environment variable configuration

3. **Database Connection Issues**
   - Verify DATABASE_URL is correct
   - Check database is running and accessible

4. **Low Evaluation Scores**
   - Review test case quality and relevance
   - Check retrieval context quality
   - Verify answer generation logic

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Run evaluation with debug logging
results = await deepeval_integration.run_comprehensive_evaluation(...)
```

## 📚 Additional Resources

- [DeepEval Documentation](https://docs.confident-ai.com/)
- [RAG Evaluation Best Practices](https://docs.confident-ai.com/docs/rag-evaluation)
- [Enterprise RAG Architecture](../../architecture/README.md)
- [Testing Guidelines](../../testing/README.md)

---

## 🤝 Contributing

To contribute to the evaluation framework:

1. Add new success criteria in `success_criteria.py`
2. Create test datasets in `test_datasets.py`
3. Implement custom metrics in `deepeval_integration.py`
4. Add evaluation schedules in `evaluation_runner.py`
5. Update documentation and examples

---

*This evaluation framework ensures enterprise-grade quality and reliability for multimodal RAG systems through comprehensive, automated testing and monitoring.*