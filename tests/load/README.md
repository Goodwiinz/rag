# Load Testing Suite for Multimodal Enterprise RAG System

This directory contains comprehensive load testing scripts using K6 to evaluate the performance, scalability, and reliability of the RAG system under various load conditions.

## Test Types

### 1. Load Testing (`k6-load-testing.js`)
- **Purpose**: Evaluate system performance under expected normal and peak load conditions
- **Virtual Users**: Gradually ramp up from 10 to 50 concurrent users
- **Duration**: ~26 minutes total
- **Focus**: Realistic user behavior simulation with mixed operations

### 2. Stress Testing (`k6-stress-testing.js`)
- **Purpose**: Find system breaking points and performance limits
- **Virtual Users**: Ramp up to 400 concurrent users
- **Duration**: ~34 minutes total
- **Focus**: Maximum throughput and system resilience

### 3. Spike Testing (`k6-spike-testing.js`)
- **Purpose**: Evaluate system behavior under sudden traffic surges
- **Virtual Users**: Sudden spikes from 5 to 200 users
- **Duration**: ~6 minutes total
- **Focus**: System recovery and stability during traffic spikes

## Prerequisites

1. **Install K6**:
   ```bash
   # macOS
   brew install k6

   # Linux
   sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
   echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
   sudo apt-get update
   sudo apt-get install k6

   # Windows
   # Download from https://k6.io/docs/get-started/installation/
   ```

2. **Target System**:
   - Ensure the RAG system is running and accessible
   - Set up test environment variables if needed

3. **Environment Setup**:
   ```bash
   export BASE_URL=http://localhost:8000  # Default target URL
   ```

## Running Tests

### Basic Load Testing
```bash
# Run standard load test
k6 run k6-load-testing.js

# Run with custom target
k6 run --env BASE_URL=http://your-server:8000 k6-load-testing.js

# Run with specific output
k6 run --out json=results.json k6-load-testing.js
```

### Stress Testing
```bash
# Run stress test to find breaking points
k6 run k6-stress-testing.js

# Monitor system resources during stress test
# Use htop, top, or system monitoring tools
```

### Spike Testing
```bash
# Run spike test for traffic surge simulation
k6 run k6-spike-testing.js
```

### Advanced Options

#### Custom Thresholds
```bash
# Create custom thresholds file
cat > thresholds.js << 'EOF'
export let options = {
  thresholds: {
    http_req_duration: ['p(95)<2000'], // Stricter thresholds
    http_req_failed: ['rate<0.05'],    // Lower error tolerance
  },
};
EOF

# Run with custom thresholds
k6 run --config thresholds.js k6-load-testing.js
```

#### Cloud Execution (K6 Cloud)
```bash
# Login to K6 Cloud
k6 login cloud --token YOUR_K6_CLOUD_TOKEN

# Run test in cloud
k6 cloud k6-load-testing.js

# Run with cloud options
k6 cloud --project-id YOUR_PROJECT_ID k6-load-testing.js
```

#### Distributed Testing
```bash
# Run distributed load test across multiple instances
k6 run --vus 50 --iterations 1000 --execution-segment 1/2 k6-load-testing.js
```

## Test Scenarios

### Load Testing Scenarios

1. **Search Operations (40%)**:
   - Hybrid, vector, full-text, and graph searches
   - Various query complexity levels
   - Occasional detailed result fetching

2. **Document Management (35%)**:
   - Document listing with pagination
   - Document detail views
   - Processing status checks

3. **User Operations (15%)**:
   - Profile management
   - Authentication token refresh

4. **Advanced Features (10%)**:
   - Advanced search with facets
   - Aggregations and filtering
   - Document uploads

### Stress Testing Scenarios

- **High-frequency searches** with minimal think time
- **Concurrent document operations**
- **Maximum user session simulation**
- **Resource exhaustion testing**

### Spike Testing Scenarios

- **Critical search operations** during traffic spikes
- **Emergency access patterns**
- **System recovery evaluation**
- **Graceful degradation testing**

## Performance Benchmarks

### Success Criteria

| Metric | Target | Load Test | Stress Test | Spike Test |
|--------|--------|-----------|-------------|------------|
| Response Time (p95) | < 3s | ✓ | < 5s | < 10s |
| Error Rate | < 10% | ✓ | < 30% | < 50% |
| Concurrent Users | 50 | ✓ | 400 | 200 |
| Document Upload | < 5s | ✓ | < 10s | N/A |
| Search Queries | < 3s | ✓ | < 5s | < 15s |

### Performance Metrics

- **Response Time**: API response time percentiles
- **Throughput**: Requests per second
- **Error Rate**: Failed request percentage
- **Concurrent Users**: Active virtual users
- **Resource Usage**: Memory, CPU, database connections

## Monitoring and Analysis

### Real-time Monitoring
```bash
# Monitor system resources during tests
htop                                    # CPU and memory
iostat -x 1                            # Disk I/O
netstat -an | grep :8000               # Network connections
tail -f /var/log/rag-system/*.log      # Application logs
```

### Database Monitoring
```bash
# PostgreSQL monitoring
SELECT * FROM pg_stat_activity WHERE state = 'active';

# Redis monitoring
redis-cli info stats
redis-cli monitor

# Neo4j monitoring
# Check Neo4j browser or use Cypher queries
```

### Result Analysis

#### K6 HTML Report
```bash
# Generate HTML report
k6 run --out html=report.html k6-load-testing.js
```

#### Custom Metrics Analysis
The test scripts collect custom metrics:
- `api_response_time`: Overall API response times
- `document_upload_time`: Document upload performance
- `search_response_time`: Search query performance
- `auth_response_time`: Authentication operation performance

## Test Data Management

### Test Users
- Pre-configured test users are automatically created during setup
- Credentials: `stressuserX@test.com` / `Password123!`
- Users are cleaned up after test completion

### Test Documents
- Sample documents are generated during test execution
- Document cleanup is performed in teardown phase
- Content varies to simulate real-world usage

### Search Queries
- Predefined set of realistic search queries
- Randomized to avoid query caching effects
- Covers different domains: AI/ML, research, technology

## Troubleshooting

### Common Issues

1. **Connection Refused**:
   - Ensure target system is running
   - Check firewall settings
   - Verify BASE_URL environment variable

2. **High Error Rates**:
   - Check system logs for errors
   - Verify database connections
   - Monitor resource utilization

3. **Test Not Starting**:
   - Verify K6 installation
   - Check JavaScript syntax
   - Ensure proper file permissions

4. **Performance Degradation**:
   - Monitor system resources
   - Check database performance
   - Review application logs

### Debug Mode
```bash
# Run with debug output
k6 run --vus 1 --iterations 1 --http-debug k6-load-testing.js

# Run with verbose logging
k6 run --verbose k6-load-testing.js
```

## Best Practices

1. **Before Running Tests**:
   - Ensure test environment is isolated
   - Verify system health checks pass
   - Clear caches and temporary data

2. **During Tests**:
   - Monitor system resources continuously
   - Watch for error patterns
   - Log any unusual behavior

3. **After Tests**:
   - Review performance metrics
   - Analyze error patterns
   - Clean up test data and resources

4. **Continuous Integration**:
   - Integrate load tests into CI/CD pipeline
   - Set performance regression alerts
   - Track performance trends over time

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: Load Tests
on: [push, pull_request]

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup K6
        run: |
          sudo gpg -k
          sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6

      - name: Run Load Tests
        run: k6 run --env BASE_URL=http://target-system:8000 tests/load/k6-load-testing.js
```

## Security Considerations

- Test environment should be isolated from production
- Use separate test databases and services
- Clean up all test data after execution
- Monitor for unintended side effects
- Validate that tests don't expose sensitive information

## Reporting

Test results should include:
- Executive summary with key metrics
- Detailed performance analysis
- Error analysis and recommendations
- Resource utilization graphs
- Comparison with baseline performance
- Action items for performance improvements

## Next Steps

1. Establish baseline performance metrics
2. Set up automated performance monitoring
3. Create performance regression tests
4. Integrate with deployment pipeline
5. Establish performance SLAs and alerting