/*
Multimodal Enterprise RAG System - K6 Stress Testing
Stress testing to find system limits and breaking points
*/

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { randomIntBetween, randomItem } from 'https://jslib.k6.io/k6-utils/1.1.0/index.js';

// Custom metrics for stress testing
export let errorRate = new Rate('errors');
export let responseTime = new Trend('response_time');
export let throughput = new Trend('throughput');
export let concurrentUsers = new Trend('concurrent_users');

// Stress test configuration - gradual ramp up to find breaking point
export let options = {
  stages: [
    { duration: '2m', target: 20 },   // Warm up
    { duration: '5m', target: 50 },   // Moderate load
    { duration: '5m', target: 100 },  // High load
    { duration: '10m', target: 200 }, // Stress level
    { duration: '5m', target: 300 },  // Extreme load
    { duration: '5m', target: 400 },  // Breaking point attempt
    { duration: '2m', target: 0 },    // Cool down
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'], // More lenient for stress test
    http_req_failed: ['rate<0.3'],     // Allow higher error rate
    errors: ['rate<0.3'],
    response_time: ['p(95)<5000'],
  },
  discardResponseBodies: true, // Improve performance under load
  noConnectionReuse: false,    // Enable connection reuse
  insecureSkipTLSVerify: true,  // Skip TLS verification if needed
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

// Simplified test data for stress testing
const SEARCH_QUERIES = [
  'machine learning',
  'artificial intelligence',
  'data science',
  'neural networks',
  'deep learning',
  'natural language processing',
  'computer vision',
  'algorithms',
  'models',
  'AI research'
];

const USERS = Array.from({ length: 50 }, (_, i) => ({
  email: `stressuser${i + 1}@test.com`,
  password: 'Password123!',
  token: null
}));

// Track active virtual users
let activeUsers = 0;

export function setup() {
  console.log('Setting up stress test environment...');

  // Setup users (simplified for stress testing)
  USERS.forEach((user, index) => {
    try {
      const registerResponse = http.post(`${BASE_URL}${API_PREFIX}/auth/register`, JSON.stringify({
        email: user.email,
        password: user.password,
        first_name: `Stress${index}`,
        last_name: `User${index}`,
        organization_name: `Stress Test Organization ${index}`
      }), {
        headers: { 'Content-Type': 'application/json' },
      });

      if (registerResponse.status === 201) {
        const data = JSON.parse(registerResponse.body);
        user.token = data.access_token;
      } else if (registerResponse.status === 409) {
        // User exists, try to login
        const loginResponse = http.post(`${BASE_URL}${API_PREFIX}/auth/login`, JSON.stringify({
          email: user.email,
          password: user.password
        }), {
          headers: { 'Content-Type': 'application/json' },
        });

        if (loginResponse.status === 200) {
          const data = JSON.parse(loginResponse.body);
          user.token = data.access_token;
        }
      }
    } catch (error) {
      console.error(`Failed to setup user ${user.email}:`, error);
    }
  });

  const validUsers = USERS.filter(u => u.token !== null);
  console.log(`Setup complete. ${validUsers.length} users ready for stress test.`);

  return { userCount: validUsers.length };
}

export default function(data) {
  activeUsers++;
  concurrentUsers.add(activeUsers);

  // Select a random user with valid token
  const validUsers = USERS.filter(u => u.token !== null);
  if (validUsers.length === 0) {
    console.error('No valid users available');
    sleep(1);
    return;
  }

  const user = randomItem(validUsers);
  const headers = {
    'Authorization': `Bearer ${user.token}`,
    'Content-Type': 'application/json',
  };

  const startTime = Date.now();

  // Stress test focuses on high-frequency operations
  const operation = Math.random();

  try {
    if (operation < 0.6) {
      // 60% - Search operations (highest frequency)
      performStressSearch(headers);
    } else if (operation < 0.8) {
      // 20% - Document listing
      performStressDocumentList(headers);
    } else if (operation < 0.95) {
      // 15% - User operations
      performStressUserOperations(headers);
    } else {
      // 5% - Document upload (minimal for stress test)
      performStressDocumentUpload(headers);
    }
  } catch (error) {
    console.error('Operation failed:', error);
    errorRate.add(1);
  }

  const responseTimeMs = Date.now() - startTime;
  responseTime.add(responseTimeMs);

  // Minimal think time for stress test
  sleep(randomIntBetween(0.1, 0.5));

  activeUsers--;
}

function performStressSearch(headers) {
  const query = randomItem(SEARCH_QUERIES);
  const searchTypes = ['hybrid', 'vector', 'fulltext'];
  const searchType = randomItem(searchTypes);

  const payload = {
    query: query,
    search_type: searchType,
    max_results: randomIntBetween(5, 15),
  };

  const response = http.post(`${BASE_URL}${API_PREFIX}/search/`, JSON.stringify(payload), {
    headers: headers,
    timeout: '10s',
  });

  throughput.add(1);

  const success = check(response, {
    'search status is 200': (r) => r.status === 200,
    'search response time < 10s': (r) => r.timings.duration < 10000,
  });

  errorRate.add(!success);
}

function performStressDocumentList(headers) {
  const page = randomIntBetween(1, 5);
  const pageSize = randomIntBetween(10, 25);

  const response = http.get(`${BASE_URL}${API_PREFIX}/documents?page=${page}&page_size=${pageSize}`, {
    headers: headers,
    timeout: '5s',
  });

  throughput.add(1);

  const success = check(response, {
    'document list status is 200': (r) => r.status === 200,
    'document list response time < 5s': (r) => r.timings.duration < 5000,
  });

  errorRate.add(!success);
}

function performStressUserOperations(headers) {
  const response = http.get(`${BASE_URL}${API_PREFIX}/users/profile`, {
    headers: headers,
    timeout: '3s',
  });

  throughput.add(1);

  const success = check(response, {
    'profile status is 200': (r) => r.status === 200,
    'profile response time < 3s': (r) => r.timings.duration < 3000,
  });

  errorRate.add(!success);
}

function performStressDocumentUpload(headers) {
  // Simplified document upload for stress test
  const content = `Stress test document content - ${Date.now()}`.repeat(10);
  const boundary = '----WebKitFormBoundary' + Math.random().toString(36).substring(2);

  let body = `--${boundary}\r\n`;
  body += 'Content-Disposition: form-data; name="file"; filename="stress_test.txt"\r\n';
  body += 'Content-Type: text/plain\r\n\r\n';
  body += content + '\r\n';
  body += `--${boundary}\r\n`;
  body += 'Content-Disposition: form-data; name="title"\r\n\r\n';
  body += `Stress Test Document ${Date.now()}\r\n`;
  body += `--${boundary}\r\n`;
  body += 'Content-Disposition: form-data; name="tags"\r\n\r\n';
  body += JSON.stringify(['stress-test']) + '\r\n';
  body += `--${boundary}--\r\n`;

  const uploadHeaders = {
    'Authorization': headers.Authorization,
    'Content-Type': `multipart/form-data; boundary=${boundary}`,
  };

  const response = http.post(`${BASE_URL}${API_PREFIX}/documents/upload`, body, {
    headers: uploadHeaders,
    timeout: '30s',
  });

  throughput.add(1);

  const success = check(response, {
    'upload status is 201 or 400': (r) => r.status === 201 || r.status === 400,
    'upload response time < 30s': (r) => r.timings.duration < 30000,
  });

  errorRate.add(!success);
}

export function teardown(data) {
  console.log('Stress test completed.');
  console.log(`Peak concurrent users: ${concurrentUsers.max || 0}`);
  console.log(`Average response time: ${responseTime.mean || 0}ms`);
  console.log(`95th percentile response time: ${responseTime.p(95) || 0}ms`);
  console.log(`Error rate: ${(errorRate.rate * 100).toFixed(2)}%`);
  console.log(`Total requests processed: ${throughput.count || 0}`);
}