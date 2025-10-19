/*
Multimodal Enterprise RAG System - K6 Spike Testing
Spike testing to evaluate system behavior under sudden load surges
*/

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.1.0/index.js';

// Custom metrics
export let errorRate = new Rate('errors');
export let spikeResponseTime = new Trend('spike_response_time');
export let requestRate = new Trend('request_rate');

// Spike test configuration - simulate sudden traffic spikes
export let options = {
  stages: [
    { duration: '2m', target: 5 },    // Baseline
    { duration: '10s', target: 100 }, // Spike 1
    { duration: '1m', target: 5 },    // Recovery
    { duration: '10s', target: 150 }, // Spike 2 (larger)
    { duration: '1m', target: 5 },    // Recovery
    { duration: '10s', target: 200 }, // Spike 3 (largest)
    { duration: '2m', target: 5 },    // Extended recovery
  ],
  thresholds: {
    http_req_duration: ['p(95)<10000'], // More lenient during spikes
    http_req_failed: ['rate<0.5'],     // Allow higher errors during spikes
    errors: ['rate<0.5'],
    spikeResponseTime: ['p(95)<10000'],
  },
  discardResponseBodies: true, // Maximize performance during spikes
  noConnectionReuse: false,
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

// Critical operations for spike testing
const CRITICAL_SEARCHES = [
  'urgent query',
  'emergency search',
  'critical information',
  'immediate results needed',
  'high priority request'
];

const SPIKE_USERS = [
  { email: 'spike1@test.com', password: 'Password123!', token: null },
  { email: 'spike2@test.com', password: 'Password123!', token: null },
  { email: 'spike3@test.com', password: 'Password123!', token: null },
  { email: 'spike4@test.com', password: 'Password123!', token: null },
  { email: 'spike5@test.com', password: 'Password123!', token: null },
];

export function setup() {
  console.log('Setting up spike test environment...');

  // Setup spike test users
  SPIKE_USERS.forEach(user => {
    try {
      const registerResponse = http.post(`${BASE_URL}${API_PREFIX}/auth/register`, JSON.stringify({
        email: user.email,
        password: user.password,
        first_name: 'Spike',
        last_name: 'Test',
        organization_name: 'Spike Test Organization'
      }), {
        headers: { 'Content-Type': 'application/json' },
      });

      if (registerResponse.status === 201) {
        const data = JSON.parse(registerResponse.body);
        user.token = data.access_token;
      } else if (registerResponse.status === 409) {
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

  const validUsers = SPIKE_USERS.filter(u => u.token !== null);
  console.log(`Setup complete. ${validUsers.length} users ready for spike test.`);
}

export default function(data) {
  const validUsers = SPIKE_USERS.filter(u => u.token !== null);
  if (validUsers.length === 0) {
    console.error('No valid users available for spike test');
    sleep(0.1);
    return;
  }

  const user = randomItem(validUsers);
  const headers = {
    'Authorization': `Bearer ${user.token}`,
    'Content-Type': 'application/json',
  };

  const startTime = Date.now();

  // During spikes, focus on most critical operations
  const operation = Math.random();

  if (operation < 0.8) {
    // 80% - Critical search operations
    performCriticalSearch(headers);
  } else if (operation < 0.95) {
    // 15% - Document access
    performDocumentAccess(headers);
  } else {
    // 5% - User profile
    performUserProfile(headers);
  }

  const responseTimeMs = Date.now() - startTime;
  spikeResponseTime.add(responseTimeMs);
  requestRate.add(1);

  // Minimal to no think time during spikes
  sleep(0.1);
}

function performCriticalSearch(headers) {
  const query = randomItem(CRITICAL_SEARCHES);
  const timestamp = Date.now();

  const payload = {
    query: `${query} ${timestamp}`, // Make queries unique
    search_type: 'hybrid',
    max_results: 10, // Limit results for speed
  };

  const response = http.post(`${BASE_URL}${API_PREFIX}/search/`, JSON.stringify(payload), {
    headers: headers,
    timeout: '15s', // Shorter timeout during spikes
  });

  const success = check(response, {
    'search status is 200': (r) => r.status === 200,
    'search response time < 15s': (r) => r.timings.duration < 15000,
  });

  errorRate.add(!success);

  // During spikes, we don't wait for detailed results
}

function performDocumentAccess(headers) {
  // Try to access a known document or list
  const response = http.get(`${BASE_URL}${API_PREFIX}/documents?page_size=10`, {
    headers: headers,
    timeout: '10s',
  });

  const success = check(response, {
    'document access status is 200': (r) => r.status === 200,
    'document access response time < 10s': (r) => r.timings.duration < 10000,
  });

  errorRate.add(!success);
}

function performUserProfile(headers) {
  const response = http.get(`${BASE_URL}${API_PREFIX}/users/profile`, {
    headers: headers,
    timeout: '5s',
  });

  const success = check(response, {
    'profile status is 200': (r) => r.status === 200,
    'profile response time < 5s': (r) => r.timings.duration < 5000,
  });

  errorRate.add(!success);
}

export function teardown(data) {
  console.log('Spike test completed.');
  console.log(`Average response time during spikes: ${spikeResponseTime.mean || 0}ms`);
  console.log(`95th percentile response time: ${spikeResponseTime.p(95) || 0}ms`);
  console.log(`Error rate during spikes: ${(errorRate.rate * 100).toFixed(2)}%`);
  console.log(`Total requests during spikes: ${requestRate.count || 0}`);
}