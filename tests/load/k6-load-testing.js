/*
Multimodal Enterprise RAG System - K6 Load Testing Scripts
Comprehensive performance testing for API endpoints and user workflows
*/

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { randomIntBetween, randomItem } from 'https://jslib.k6.io/k6-utils/1.1.0/index.js';

// Custom metrics
export let errorRate = new Rate('errors');
export let apiResponseTime = new Trend('api_response_time');
export let documentUploadTime = new Trend('document_upload_time');
export let searchResponseTime = new Trend('search_response_time');
export let authResponseTime = new Trend('auth_response_time');

// Test configuration
export let options = {
  stages: [
    { duration: '2m', target: 10 }, // Ramp up to 10 users
    { duration: '5m', target: 10 }, // Stay at 10 users
    { duration: '2m', target: 25 }, // Ramp up to 25 users
    { duration: '5m', target: 25 }, // Stay at 25 users
    { duration: '2m', target: 50 }, // Ramp up to 50 users
    { duration: '10m', target: 50 }, // Stay at 50 users (load test)
    { duration: '2m', target: 0 }, // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000'], // 95% of requests under 3s
    http_req_failed: ['rate<0.1'], // Error rate under 10%
    errors: ['rate<0.1'],
    api_response_time: ['p(95)<3000'],
    document_upload_time: ['p(95)<5000'], // Document uploads under 5s
    search_response_time: ['p(95)<3000'], // Search queries under 3s
    auth_response_time: ['p(95)<2000'], // Auth operations under 2s
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

// Test data
const TEST_USERS = [
  { email: 'user1@test.com', password: 'Password123!', firstName: 'User', 'lastName': 'One' },
  { email: 'user2@test.com', password: 'Password123!', firstName: 'User', 'lastName': 'Two' },
  { email: 'user3@test.com', password: 'Password123!', firstName: 'User', 'lastName': 'Three' },
  { email: 'user4@test.com', password: 'Password123!', firstName: 'User', 'lastName': 'Four' },
  { email: 'user5@test.com', password: 'Password123!', firstName: 'User', 'lastName': 'Five' },
];

const SEARCH_QUERIES = [
  'machine learning algorithms',
  'natural language processing',
  'computer vision applications',
  'deep neural networks',
  'artificial intelligence ethics',
  'data preprocessing techniques',
  'model evaluation metrics',
  'feature engineering methods',
  'neural network architectures',
  'reinforcement learning',
  'supervised learning',
  'unsupervised learning',
  'transfer learning',
  'generative AI models',
  'large language models'
];

const DOCUMENT_TITLES = [
  'Machine Learning Fundamentals',
  'Advanced Neural Networks',
  'Natural Language Processing Guide',
  'Computer Vision Applications',
  'AI Ethics and Governance',
  'Data Science Best Practices',
  'Deep Learning Research',
  'Algorithm Optimization',
  'Statistical Learning Theory',
  'Artificial Intelligence Overview'
];

// Global state
let userTokens = new Map();
let uploadedDocuments = [];

export function setup() {
  console.log('Setting up load test environment...');

  // Register test users and get tokens
  TEST_USERS.forEach((user, index) => {
    try {
      const registerResponse = http.post(`${BASE_URL}${API_PREFIX}/auth/register`, JSON.stringify({
        email: user.email,
        password: user.password,
        first_name: user.firstName,
        last_name: user.lastName,
        organization_name: `Load Test Organization ${index + 1}`
      }), {
        headers: { 'Content-Type': 'application/json' },
      });

      if (registerResponse.status === 201) {
        const registerData = JSON.parse(registerResponse.body);
        userTokens.set(user.email, registerData.access_token);
        console.log(`Registered user: ${user.email}`);
      } else {
        // Try to login if registration fails
        const loginResponse = http.post(`${BASE_URL}${API_PREFIX}/auth/login`, JSON.stringify({
          email: user.email,
          password: user.password
        }), {
          headers: { 'Content-Type': 'application/json' },
        });

        if (loginResponse.status === 200) {
          const loginData = JSON.parse(loginResponse.body);
          userTokens.set(user.email, loginData.access_token);
          console.log(`Logged in user: ${user.email}`);
        }
      }
    } catch (error) {
      console.error(`Failed to setup user ${user.email}:`, error);
    }
  });

  console.log(`Setup complete. ${userTokens.size} users ready.`);
  return { userCount: userTokens.size };
}

export default function(data) {
  const user = randomItem(TEST_USERS);
  const token = userTokens.get(user.email);

  if (!token) {
    console.error(`No token found for user ${user.email}`);
    return;
  }

  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  // Simulate realistic user behavior with weighted operations
  const operation = Math.random();

  if (operation < 0.4) {
    // 40% - Search operations (most common)
    performSearch(headers);
  } else if (operation < 0.6) {
    // 20% - Document listing
    listDocuments(headers);
  } else if (operation < 0.75) {
    // 15% - Get document details
    getDocumentDetails(headers);
  } else if (operation < 0.85) {
    // 10% - User profile operations
    userProfileOperations(headers);
  } else if (operation < 0.95) {
    // 10% - Advanced search
    performAdvancedSearch(headers);
  } else {
    // 5% - Document upload (less frequent)
    uploadDocument(headers);
  }

  // Simulate user think time
  sleep(randomIntBetween(1, 3));
}

function performSearch(headers) {
  const startTime = Date.now();

  const searchQuery = randomItem(SEARCH_QUERIES);
  const searchTypes = ['hybrid', 'vector', 'fulltext', 'graph'];
  const searchType = randomItem(searchTypes);

  const searchPayload = {
    query: searchQuery,
    search_type: searchType,
    max_results: randomIntBetween(5, 20),
    include_metadata: Math.random() > 0.5,
  };

  // Add filters occasionally
  if (Math.random() > 0.7) {
    searchPayload.filters = {
      document_types: [randomItem(['pdf', 'text', 'image'])],
      tags: [randomItem(['AI', 'machine learning', 'research'])]
    };
  }

  const response = http.post(`${BASE_URL}${API_PREFIX}/search/`, JSON.stringify(searchPayload), {
    headers: headers,
  });

  const responseTime = Date.now() - startTime;
  searchResponseTime.add(responseTime);
  apiResponseTime.add(responseTime);

  const success = check(response, {
    'search status is 200': (r) => r.status === 200,
    'search response time < 3s': (r) => r.timings.duration < 3000,
    'search response has results': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.results && Array.isArray(body.results);
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!success);

  if (response.status === 200 && Math.random() > 0.8) {
    // Occasionally get detailed results
    const searchResult = JSON.parse(response.body);
    if (searchResult.query_id) {
      http.get(`${BASE_URL}${API_PREFIX}/search/${searchResult.query_id}`, {
        headers: headers,
      });
    }
  }
}

function performAdvancedSearch(headers) {
  const startTime = Date.now();

  const searchPayload = {
    query: randomItem(SEARCH_QUERIES),
    search_type: 'hybrid',
    max_results: randomIntBetween(10, 30),
    enable_facets: true,
    facet_fields: ['document_type', 'tags'],
    enable_aggregations: true,
    aggregations: {
      document_type: { type: 'terms', size: 10 },
      file_size: { type: 'histogram', interval: 5 }
    },
    rerank: Math.random() > 0.5,
    filters: {
      document_types: randomItem([['pdf'], ['text'], ['pdf', 'text']]),
      date_range: {
        start_date: '2023-01-01',
        end_date: '2024-12-31'
      }
    }
  };

  const response = http.post(`${BASE_URL}${API_PREFIX}/search/advanced`, JSON.stringify(searchPayload), {
    headers: headers,
  });

  const responseTime = Date.now() - startTime;
  searchResponseTime.add(responseTime);
  apiResponseTime.add(responseTime);

  const success = check(response, {
    'advanced search status is 200': (r) => r.status === 200,
    'advanced search response time < 5s': (r) => r.timings.duration < 5000,
    'advanced search has facets': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.facets && body.aggregations;
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!success);
}

function listDocuments(headers) {
  const startTime = Date.now();

  const page = randomIntBetween(1, 3);
  const pageSize = randomIntBetween(5, 20);

  let url = `${BASE_URL}${API_PREFIX}/documents?page=${page}&page_size=${pageSize}`;

  // Add filters occasionally
  if (Math.random() > 0.6) {
    const docTypes = ['pdf', 'text', 'image', 'video'];
    url += `&document_type=${randomItem(docTypes)}`;
  }

  const response = http.get(url, {
    headers: headers,
  });

  const responseTime = Date.now() - startTime;
  apiResponseTime.add(responseTime);

  const success = check(response, {
    'document list status is 200': (r) => r.status === 200,
    'document list response time < 2s': (r) => r.timings.duration < 2000,
    'document list has documents': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.documents && Array.isArray(body.documents);
      } catch {
        return false;
      }
    },
  });

  errorRate.add(!success);

  // Store document IDs for detail view testing
  if (response.status === 200) {
    try {
      const body = JSON.parse(response.body);
      if (body.documents && body.documents.length > 0) {
        uploadedDocuments.push(...body.documents.map(d => d.id));
      }
    } catch (e) {
      // Ignore parsing errors
    }
  }
}

function getDocumentDetails(headers) {
  if (uploadedDocuments.length === 0) {
    return;
  }

  const startTime = Date.now();
  const documentId = randomItem(uploadedDocuments);

  const response = http.get(`${BASE_URL}${API_PREFIX}/documents/${documentId}`, {
    headers: headers,
  });

  const responseTime = Date.now() - startTime;
  apiResponseTime.add(responseTime);

  const success = check(response, {
    'document details status is 200 or 404': (r) => r.status === 200 || r.status === 404,
    'document details response time < 2s': (r) => r.timings.duration < 2000,
  });

  errorRate.add(!success);

  // Occasionally check processing status
  if (response.status === 200 && Math.random() > 0.7) {
    http.get(`${BASE_URL}${API_PREFIX}/documents/${documentId}/status`, {
      headers: headers,
    });
  }
}

function uploadDocument(headers) {
  const startTime = Date.now();

  const title = randomItem(DOCUMENT_TITLES);
  const content = `This is a test document titled "${title}". It contains sample text for load testing purposes. The content discusses various aspects of ${title.toLowerCase()} and related topics in the field of artificial intelligence and machine learning.`;

  // Create form data for file upload
  const boundary = '----WebKitFormBoundary' + Math.random().toString(36).substring(2);
  let body = `--${boundary}\r\n`;
  body += 'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n';
  body += 'Content-Type: text/plain\r\n\r\n';
  body += content + '\r\n';
  body += `--${boundary}\r\n`;
  body += 'Content-Disposition: form-data; name="title"\r\n\r\n';
  body += title + '\r\n';
  body += `--${boundary}\r\n`;
  body += 'Content-Disposition: form-data; name="tags"\r\n\r\n';
  body += JSON.stringify(['test', 'load-testing', 'performance']) + '\r\n';
  body += `--${boundary}--\r\n`;

  const uploadHeaders = {
    'Authorization': headers.Authorization,
    'Content-Type': `multipart/form-data; boundary=${boundary}`,
  };

  const response = http.post(`${BASE_URL}${API_PREFIX}/documents/upload`, body, {
    headers: uploadHeaders,
  });

  const responseTime = Date.now() - startTime;
  documentUploadTime.add(responseTime);
  apiResponseTime.add(responseTime);

  const success = check(response, {
    'document upload status is 201 or 400': (r) => r.status === 201 || r.status === 400,
    'document upload response time < 10s': (r) => r.timings.duration < 10000,
  });

  errorRate.add(!success);

  // Store uploaded document ID
  if (response.status === 201) {
    try {
      const body = JSON.parse(response.body);
      uploadedDocuments.push(body.id);
    } catch (e) {
      // Ignore parsing errors
    }
  }
}

function userProfileOperations(headers) {
  const startTime = Date.now();

  // Get user profile
  const profileResponse = http.get(`${BASE_URL}${API_PREFIX}/users/profile`, {
    headers: headers,
  });

  const responseTime = Date.now() - startTime;
  authResponseTime.add(responseTime);
  apiResponseTime.add(responseTime);

  const success = check(profileResponse, {
    'profile status is 200': (r) => r.status === 200,
    'profile response time < 2s': (r) => r.timings.duration < 2000,
  });

  errorRate.add(!success);

  // Occasionally update profile
  if (profileResponse.status === 200 && Math.random() > 0.8) {
    const updatePayload = {
      first_name: `Updated${Date.now()}`,
      profile_data: {
        bio: `Updated bio at ${new Date().toISOString()}`,
        last_login: new Date().toISOString()
      }
    };

    http.put(`${BASE_URL}${API_PREFIX}/users/profile`, JSON.stringify(updatePayload), {
      headers: headers,
    });
  }
}

export function teardown(data) {
  console.log('Load test completed.');
  console.log(`Total documents uploaded: ${uploadedDocuments.length}`);
  console.log(`Error rate: ${errorRate.rate * 100}%`);

  // Cleanup some uploaded documents
  if (uploadedDocuments.length > 0) {
    console.log(`Cleaning up ${Math.min(10, uploadedDocuments.length)} documents...`);

    for (let i = 0; i < Math.min(10, uploadedDocuments.length); i++) {
      const docId = uploadedDocuments[i];
      const user = randomItem(TEST_USERS);
      const token = userTokens.get(user.email);

      if (token) {
        http.del(`${BASE_URL}${API_PREFIX}/documents/${docId}`, null, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
      }
    }
  }
}