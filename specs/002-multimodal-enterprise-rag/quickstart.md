# Quickstart Guide: Multimodal Enterprise RAG UI

**Feature**: Multimodal Enterprise RAG UI
**Date**: 2025-10-14
**Purpose**: Developer onboarding and setup guide
**Status**: ✅ COMPLETED

## Overview

This guide helps developers quickly set up and start working on the Multimodal Enterprise RAG UI. The frontend is a React 18 + TypeScript application that integrates with an existing FastAPI backend.

**Prerequisites**: Node.js 18+, Docker, Git
**Estimated Setup Time**: 15-30 minutes

---

## 1. System Requirements

### Development Environment
```bash
# Node.js version check
node --version  # Should be 18.0.0 or higher

# npm version check
npm --version   # Should be 8.0.0 or higher

# Docker version check
docker --version
docker-compose --version

# Git version check
git --version
```

### Required Ports
Ensure these ports are available:
- **3000**: Frontend development server
- **8000**: Backend API server
- **5432**: PostgreSQL database
- **7474/7687**: Neo4j database
- **6333/6334**: Qdrant vector database
- **6379**: Redis cache

---

## 2. Project Setup

### Clone and Install
```bash
# Clone the repository
git clone <repository-url>
cd rag

# Start backend services (if not already running)
docker-compose up -d

# Wait for services to be ready (20-30 seconds)
docker-compose ps

# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Copy environment configuration
cp .env.example .env.local
```

### Environment Configuration
Create `.env.local` in the frontend directory:

```bash
# API Configuration
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000/ws

# Application Settings
REACT_APP_APP_NAME="Multimodal RAG System"
REACT_APP_VERSION=1.0.0
REACT_APP_ENVIRONMENT=development

# Feature Flags
REACT_APP_ENABLE_ANALYTICS=true
REACT_APP_ENABLE_GRAPH_VISUALIZATION=true
REACT_APP_ENABLE_EVALUATION_METRICS=true

# Upload Limits
REACT_APP_MAX_FILE_SIZE_MB=50
REACT_APP_MAX_FILES_PER_UPLOAD=10

# Performance Settings
REACT_APP_DEBOUNCE_DELAY_MS=300
REACT_APP_WEBSOCKET_RETRY_ATTEMPTS=5
REACT_APP_CACHE_DURATION_MS=300000

# Development Settings
REACT_APP_DEBUG_MODE=true
REACT_APP_LOG_LEVEL=debug
```

---

## 3. Backend Services Setup

### Start Docker Services
```bash
# From the project root directory
docker-compose up -d

# Check service status
docker-compose ps

# View logs if needed
docker-compose logs -f
```

### Verify Services
```bash
# Test backend health
curl http://localhost:8000/health

# Test API documentation
curl http://localhost:8000/docs

# Test database connections
curl http://localhost:8000/debug/info  # Development only
```

### Initialize Database (First Time Only)
```bash
# Run database migrations
docker-compose exec backend python -m alembic upgrade head

# Create test user (optional)
docker-compose exec backend python -m scripts.create_test_user
```

### Verify ML Models
```bash
# Check if models are downloaded
docker-compose exec backend python -c "
from src.services.ml_models import ModelManager
models = ModelManager()
print('Models status:', models.check_models_loaded())
"
```

**Expected Output**: All models (sentence-transformers, Whisper, spaCy) should be loaded.

---

## 4. Frontend Development Setup

### Start Development Server
```bash
# From the frontend directory
npm start

# The application should open at http://localhost:3000
```

### Verify Frontend Setup
Open http://localhost:3000 in your browser and verify:

1. ✅ Application loads without errors
2. ✅ Login page is displayed
3. ✅ Can connect to backend API
4. ✅ WebSocket connection establishes
5. ✅ No TypeScript errors in console

### Test API Integration
```bash
# In browser console, test API connectivity
fetch('http://localhost:8000/health')
  .then(r => r.json())
  .then(console.log);

# Test WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws');
ws.onopen = () => console.log('WebSocket connected');
ws.onerror = (e) => console.error('WebSocket error:', e);
```

---

## 5. Development Workflow

### Project Structure
```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── common/         # Generic components
│   │   ├── upload/         # File upload components
│   │   ├── search/         # Search and query components
│   │   ├── graph/          # Knowledge graph components
│   │   └── evaluation/     # Metrics and analytics components
│   ├── pages/              # Main application pages
│   │   ├── Dashboard.tsx   # Main dashboard
│   │   ├── Login.tsx       # Authentication
│   │   └── Settings.tsx    # User settings
│   ├── services/           # API service layers
│   │   ├── api.ts          # API client
│   │   ├── websocket.ts    # WebSocket manager
│   │   └── auth.ts         # Authentication service
│   ├── hooks/              # Custom React hooks
│   │   ├── useAuth.ts      # Authentication state
│   │   ├── useWebSocket.ts # WebSocket connection
│   │   └── useDocuments.ts # Document management
│   ├── types/              # TypeScript type definitions
│   │   ├── api.ts          # API response types
│   │   ├── document.ts     # Document types
│   │   └── search.ts       # Search result types
│   ├── utils/              # Utility functions
│   │   ├── validation.ts   # Form validation
│   │   ├── formatting.ts   # Data formatting
│   │   └── constants.ts    # Application constants
│   └── styles/             # CSS and styling
│       ├── globals.css     # Global styles
│       └── components/     # Component-specific styles
├── public/                 # Static assets
├── tests/                  # Test files
└── package.json
```

### Common Development Tasks

#### Creating a New Component
```bash
# Create component directory
mkdir src/components/NewFeature

# Create component files
touch src/components/NewFeature/NewFeature.tsx
touch src/components/NewFeature/NewFeature.test.tsx
touch src/components/NewFeature/NewFeature.module.css
```

**Component Template**:
```typescript
// src/components/NewFeature/NewFeature.tsx
import React from 'react';
import styles from './NewFeature.module.css';

interface NewFeatureProps {
  // Define component props
}

export const NewFeature: React.FC<NewFeatureProps> = (props) => {
  return (
    <div className={styles.container}>
      {/* Component JSX */}
    </div>
  );
};

export default NewFeature;
```

#### Adding API Integration
```typescript
// src/services/api.ts
export class APIClient {
  // Add new method
  async newFeature(params: NewFeatureParams): Promise<NewFeatureResponse> {
    return this.request<NewFeatureResponse>('/new-feature', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }
}

// src/types/api.ts
export interface NewFeatureParams {
  // Request parameters
}

export interface NewFeatureResponse {
  // Response structure
}
```

#### Testing API Integration
```typescript
// src/components/NewFeature/NewFeature.test.tsx
import { render, screen } from '@testing-library/react';
import { NewFeature } from './NewFeature';

describe('NewFeature', () => {
  test('renders component', () => {
    render(<NewFeature />);
    expect(screen.getByTestId('new-feature')).toBeInTheDocument();
  });
});
```

### Code Quality Tools

#### Linting and Formatting
```bash
# Run ESLint
npm run lint

# Fix linting issues
npm run lint:fix

# Run Prettier
npm run format

# Run type checking
npm run type-check
```

#### Testing
```bash
# Run all tests
npm test

# Run tests with coverage
npm run test:coverage

# Run tests in watch mode
npm run test:watch
```

#### Building
```bash
# Build for development
npm run build:dev

# Build for production
npm run build

# Preview production build
npm run preview
```

---

## 6. Authentication Flow

### Development User Setup
For development, create a test user:

```bash
# Using the backend API directly
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dev@example.com",
    "password": "devpassword123",
    "name": "Development User",
    "organization_name": "Dev Org"
  }'

# Or use the provided script
docker-compose exec backend python scripts/create_test_user.py
```

### Testing Authentication
```typescript
// In browser console or test file
const testAuth = async () => {
  try {
    const response = await fetch('http://localhost:8000/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: 'dev@example.com',
        password: 'devpassword123'
      })
    });

    const data = await response.json();
    console.log('Auth successful:', data);
    localStorage.setItem('access_token', data.access_token);
  } catch (error) {
    console.error('Auth failed:', error);
  }
};
```

---

## 7. File Upload Testing

### Prepare Test Files
Create sample files for testing:

```bash
# Create test directory
mkdir test-files

# Create sample text file
echo "This is a test document for the RAG system." > test-files/sample.txt

# Create sample PDF (if you have pandoc)
echo "Sample PDF content" | pandoc -o test-files/sample.pdf

# Download sample images (optional)
curl -o test-files/sample.jpg "https://via.placeholder.com/300x200"
curl -o test-files/sample.png "https://via.placeholder.com/300x200.png"
```

### Test Upload via API
```javascript
// Test file upload
const testFile = new File(['test content'], 'test.txt', { type: 'text/plain' });
const formData = new FormData();
formData.append('file', testFile);

fetch('http://localhost:8000/api/v1/files/upload', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
    'X-Organization-ID': 'test-org-id'
  },
  body: formData
})
.then(r => r.json())
.then(console.log)
.catch(console.error);
```

---

## 8. Common Issues and Solutions

### Backend Services Not Starting
```bash
# Check Docker status
docker-compose ps

# View specific service logs
docker-compose logs backend
docker-compose logs postgres
docker-compose logs neo4j

# Restart specific service
docker-compose restart backend

# Rebuild if needed
docker-compose up -d --build
```

### Port Conflicts
```bash
# Check what's using ports
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
lsof -i :5432  # PostgreSQL

# Kill processes if needed
kill -9 <PID>

# Or change ports in docker-compose.yml
```

### Permission Issues
```bash
# Fix Docker permissions
sudo chown -R $USER:$USER .

# Fix Node modules permissions
rm -rf node_modules package-lock.json
npm install
```

### API Connection Issues
```bash
# Test backend connectivity
curl -v http://localhost:8000/health

# Check CORS settings
# In development, CORS should allow http://localhost:3000

# Verify API base URL in .env.local
echo $REACT_APP_API_BASE_URL
```

### WebSocket Connection Issues
```bash
# Test WebSocket connection
wscat -c ws://localhost:8000/ws

# Check firewall settings
# Ensure WebSocket connections are allowed
```

### Memory Issues
```bash
# Increase Node.js memory limit
export NODE_OPTIONS="--max-old-space-size=4096"

# Clear Docker cache
docker system prune -a

# Monitor resource usage
docker stats
```

---

## 9. Performance Monitoring

### Frontend Performance
```javascript
// Add performance monitoring
const measurePerformance = (name: string, fn: () => void) => {
  const start = performance.now();
  fn();
  const end = performance.now();
  console.log(`${name} took ${end - start} milliseconds`);
};

// Monitor API calls
const wrappedFetch = async (url: string, options?: RequestInit) => {
  const start = performance.now();
  const response = await fetch(url, options);
  const end = performance.now();
  console.log(`API call to ${url} took ${end - start}ms`);
  return response;
};
```

### Backend Performance
```bash
# Monitor backend performance
curl http://localhost:8000/api/v1/analytics/performance/dashboard

# Check query performance
docker-compose logs backend | grep "slow query"
```

---

## 10. Development Tips

### Hot Reloading
- React components hot reload automatically
- CSS changes apply immediately
- API changes may require browser refresh

### Debugging
```typescript
// Add debug logging
const DEBUG = process.env.REACT_APP_DEBUG_MODE === 'true';
const debug = DEBUG ? console.log : () => {};

// React DevTools
// Install React DevTools browser extension for component inspection

// Redux DevTools (if using Redux)
// Install Redux DevTools browser extension
```

### Environment Variables
```typescript
// Access environment variables
const apiUrl = process.env.REACT_APP_API_BASE_URL;
const isDev = process.env.REACT_APP_ENVIRONMENT === 'development';

// Type-safe environment variables
const env = {
  apiUrl: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000',
  wsUrl: process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws',
  maxFileSize: parseInt(process.env.REACT_APP_MAX_FILE_SIZE_MB || '50'),
} as const;
```

### Component Development
```typescript
// Use React.memo for performance optimization
const ExpensiveComponent = React.memo(({ data }) => {
  return <div>{/* Expensive rendering */}</div>;
});

// Use useMemo for expensive calculations
const expensiveValue = useMemo(() => {
  return data.reduce(/* expensive computation */);
}, [data]);

// Use useCallback for stable function references
const handleClick = useCallback((id: string) => {
  onItemClick(id);
}, [onItemClick]);
```

---

## 11. Next Steps

### Feature Development
1. **File Upload Component**: Start with drag-and-drop functionality
2. **Search Interface**: Build query input and results display
3. **Document Management**: Create document list and status indicators
4. **Knowledge Graph**: Implement interactive graph visualization
5. **Evaluation Dashboard**: Build metrics display and analytics

### Testing Strategy
1. **Unit Tests**: Test individual components and utilities
2. **Integration Tests**: Test API integration and data flow
3. **E2E Tests**: Test complete user workflows
4. **Performance Tests**: Test with large datasets and concurrent users

### Deployment Preparation
1. **Build Optimization**: Configure production build settings
2. **Environment Configuration**: Set up production environment variables
3. **Security**: Implement proper authentication and data validation
4. **Monitoring**: Set up error tracking and performance monitoring

---

## 12. Support and Resources

### Documentation
- [React Documentation](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)

### Tools and Extensions
- **VS Code Extensions**:
  - ES7+ React/Redux/React-Native snippets
  - TypeScript Importer
  - Prettier - Code formatter
  - ESLint
  - Thunder Client (for API testing)

- **Browser Extensions**:
  - React Developer Tools
  - Redux DevTools (if applicable)
  - JSON Viewer

### Getting Help
- Check the console for error messages
- Review the browser network tab for API issues
- Consult the API documentation at http://localhost:8000/docs
- Check backend logs: `docker-compose logs backend`
- Verify environment variables and configuration

---

**Happy coding!** 🚀

If you encounter any issues not covered in this guide, please check the project documentation or reach out to the development team.