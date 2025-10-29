# Quick Start Guide: Multimodal Enterprise RAG UI

**Generated**: 2025-10-27
**Target**: Frontend Development Team
**Purpose**: Rapid setup and development environment configuration

## Overview

This guide provides step-by-step instructions for setting up the development environment for the Multimodal Enterprise RAG System UI. The frontend is a React 18 + TypeScript application that consumes the existing FastAPI backend microservices.

## Prerequisites

### System Requirements

- **Node.js**: 18.x or higher (LTS recommended)
- **npm**: 9.x or higher or **yarn**: 1.22.x or higher
- **Git**: Latest version
- **Docker**: Latest version (for backend services)
- **IDE**: VS Code with recommended extensions

### Backend Services

Ensure the following backend services are running:
- **FastAPI Backend**: `http://localhost:8000`
- **PostgreSQL**: `localhost:5432`
- **Neo4j**: `localhost:7474` (HTTP), `localhost:7687` (Bolt)
- **Qdrant**: `http://localhost:6333`
- **Redis**: `localhost:6379`

## Quick Setup (5 Minutes)

### 1. Project Setup

```bash
# Clone the repository
git clone <repository-url>
cd rag/frontend

# Install dependencies
npm install

# Copy environment template
cp .env.example .env.local

# Start development server
npm run dev
```

### 2. Environment Configuration

Edit `.env.local` with your configuration:

```env
# API Configuration
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_API_VERSION=v1
REACT_APP_WS_URL=ws://localhost:8000

# Feature Flags
REACT_APP_ENABLE_ANALYTICS=true
REACT_APP_ENABLE_GRAPH_EXPLORER=true
REACT_APP_ENABLE_EVALUATION_METRICS=true

# Development Settings
REACT_APP_DEV_MODE=true
REACT_APP_LOG_LEVEL=debug
```

### 3. Verify Setup

Open `http://localhost:3000` in your browser:

1. **Login Screen**: Should show authentication interface
2. **Dashboard**: Main two-panel layout should be visible
3. **API Connection**: Should successfully connect to backend
4. **WebSocket**: Real-time updates should be working

## Development Workflow

### Project Structure

```
frontend/
├── public/                 # Static assets
├── src/
│   ├── components/         # Reusable UI components
│   │   ├── common/         # Generic components
│   │   ├── upload/         # File upload components
│   │   ├── search/         # Search interface
│   │   ├── graph/          # Knowledge graph
│   │   └── evaluation/     # Metrics dashboard
│   ├── pages/              # Main application pages
│   ├── services/           # API client services
│   ├── hooks/              # Custom React hooks
│   ├── types/              # TypeScript definitions
│   ├── utils/              # Utility functions
│   └── styles/             # CSS/styling
├── tests/                  # Test files
└── docs/                   # Component documentation
```

### Component Development

#### Creating a New Component

```typescript
// src/components/search/SearchInput.tsx
import React, { useState, useCallback } from 'react';
import { SearchRequest, SearchResponse } from '../../types/search';
import { useSearch } from '../../hooks/useSearch';

interface SearchInputProps {
  onSearchComplete: (results: SearchResponse) => void;
  placeholder?: string;
  disabled?: boolean;
}

export const SearchInput: React.FC<SearchInputProps> = ({
  onSearchComplete,
  placeholder = "Ask a question...",
  disabled = false
}) => {
  const [query, setQuery] = useState('');
  const { search, isLoading, error } = useSearch();

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    try {
      const results = await search({ query });
      onSearchComplete(results);
    } catch (err) {
      console.error('Search failed:', err);
    }
  }, [query, search, onSearchComplete]);

  return (
    <form onSubmit={handleSubmit} className="search-input">
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={placeholder}
        disabled={disabled || isLoading}
        className="search-field"
      />
      <button
        type="submit"
        disabled={disabled || isLoading || !query.trim()}
        className="search-button"
      >
        {isLoading ? 'Searching...' : 'Search'}
      </button>
      {error && <div className="error-message">{error.message}</div>}
    </form>
  );
};
```

#### Custom Hook Example

```typescript
// src/hooks/useSearch.ts
import { useState, useCallback } from 'react';
import { searchService } from '../services/searchService';
import { SearchRequest, SearchResponse } from '../types/search';

export const useSearch = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const search = useCallback(async (request: SearchRequest): Promise<SearchResponse> => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await searchService.executeSearch(request);
      return response;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Search failed');
      setError(error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    search,
    isLoading,
    error
  };
};
```

### API Integration

#### Service Layer

```typescript
// src/services/searchService.ts
import { APIClient } from './apiClient';
import { SearchRequest, SearchResponse } from '../types/search';

class SearchService {
  constructor(private apiClient: APIClient) {}

  async executeSearch(request: SearchRequest): Promise<SearchResponse> {
    return this.apiClient.post<SearchResponse>('/search', request);
  }

  async getSearchHistory(params?: {
    page?: number;
    limit?: number;
  }): Promise<{ queries: SearchResponse[]; pagination: any }> {
    const queryParams = new URLSearchParams(params as any).toString();
    return this.apiClient.get(`/search/history?${queryParams}`);
  }

  async submitFeedback(queryId: string, feedback: {
    helpfulness: number;
    accuracy: number;
    completeness: number;
    comment?: string;
  }): Promise<void> {
    return this.apiClient.post(`/analytics/quality/feedback`, {
      query_id: queryId,
      ...feedback
    });
  }
}

export const searchService = new SearchService(new APIClient());
```

#### API Client Base

```typescript
// src/services/apiClient.ts
export class APIClient {
  private baseURL: string;
  private token: string | null = null;
  private organizationId: string | null = null;

  constructor() {
    this.baseURL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
  }

  setAuth(token: string, organizationId: string) {
    this.token = token;
    this.organizationId = organizationId;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };

    if (this.token && this.organizationId) {
      headers['Authorization'] = `Bearer ${this.token}`;
      headers['X-Organization-ID'] = this.organizationId;
    }

    return headers;
  }

  async post<T>(endpoint: string, data?: any): Promise<T> {
    const response = await fetch(`${this.baseURL}/api/v1${endpoint}`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: data ? JSON.stringify(data) : undefined,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error?.message || 'API request failed');
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseURL}/api/v1${endpoint}`, {
      method: 'GET',
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error?.message || 'API request failed');
    }

    return response.json();
  }
}
```

### State Management

#### Context Provider

```typescript
// src/contexts/AppContext.tsx
import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import { User, Document, SearchResponse } from '../types';

interface AppState {
  user: User | null;
  documents: Document[];
  currentSearch: SearchResponse | null;
  isLoading: boolean;
  error: string | null;
}

type AppAction =
  | { type: 'SET_USER'; payload: User | null }
  | { type: 'SET_DOCUMENTS'; payload: Document[] }
  | { type: 'SET_SEARCH_RESULT'; payload: SearchResponse }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };

const AppContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
} | null>(null);

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, initialState);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return context;
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_USER':
      return { ...state, user: action.payload };
    case 'SET_DOCUMENTS':
      return { ...state, documents: action.payload };
    case 'SET_SEARCH_RESULT':
      return { ...state, currentSearch: action.payload };
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    default:
      return state;
  }
}

const initialState: AppState = {
  user: null,
  documents: [],
  currentSearch: null,
  isLoading: false,
  error: null,
};
```

## Testing

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run E2E tests
npm run test:e2e
```

### Test Example

```typescript
// src/components/search/__tests__/SearchInput.test.tsx
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SearchInput } from '../SearchInput';
import { searchService } from '../../../services/searchService';

// Mock the search service
jest.mock('../../../services/searchService');
const mockSearchService = searchService as jest.Mocked<typeof searchService>;

describe('SearchInput', () => {
  const mockOnSearchComplete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders search input and button', () => {
    render(<SearchInput onSearchComplete={mockOnSearchComplete} />);

    expect(screen.getByPlaceholderText('Ask a question...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Search' })).toBeInTheDocument();
  });

  test('submits search on form submission', async () => {
    const mockResponse = {
      query_id: 'test-id',
      answer: { text: 'Test answer', confidence: 0.9 }
    };
    mockSearchService.executeSearch.mockResolvedValue(mockResponse);

    render(<SearchInput onSearchComplete={mockOnSearchComplete} />);

    const input = screen.getByPlaceholderText('Ask a question...');
    const button = screen.getByRole('button', { name: 'Search' });

    fireEvent.change(input, { target: { value: 'test query' } });
    fireEvent.click(button);

    await waitFor(() => {
      expect(mockSearchService.executeSearch).toHaveBeenCalledWith({
        query: 'test query'
      });
      expect(mockOnSearchComplete).toHaveBeenCalledWith(mockResponse);
    });
  });

  test('disables button while loading', async () => {
    mockSearchService.executeSearch.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 1000)));

    render(<SearchInput onSearchComplete={mockOnSearchComplete} />);

    const input = screen.getByPlaceholderText('Ask a question...');
    const button = screen.getByRole('button', { name: 'Search' });

    fireEvent.change(input, { target: { value: 'test query' } });
    fireEvent.click(button);

    expect(screen.getByText('Searching...')).toBeInTheDocument();
    expect(button).toBeDisabled();
  });
});
```

## Styling

### Tailwind CSS Configuration

The project uses Tailwind CSS for styling. Key configuration in `tailwind.config.js`:

```javascript
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        gray: {
          50: '#f9fafb',
          900: '#111827',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
```

### Component Styling Example

```typescript
// src/components/common/Button.tsx
import React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background',
  {
    variants: {
      variant: {
        default: 'bg-primary-600 text-white hover:bg-primary-700',
        destructive: 'bg-red-500 text-white hover:bg-red-600',
        outline: 'border border-gray-300 bg-white hover:bg-gray-50',
        secondary: 'bg-gray-100 text-gray-900 hover:bg-gray-200',
        ghost: 'hover:bg-gray-100',
        link: 'underline-offset-4 hover:underline text-primary-600',
      },
      size: {
        default: 'h-10 py-2 px-4',
        sm: 'h-9 px-3 rounded-md',
        lg: 'h-11 px-8 rounded-md',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    return (
      <button
        className={buttonVariants({ variant, size, className })}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';
```

## Real-time Features

### WebSocket Integration

```typescript
// src/services/websocketService.ts
export class WebSocketService {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Function[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  connect(token: string, organizationId: string) {
    const wsUrl = `${process.env.REACT_APP_WS_URL}/ws?token=${token}&organization_id=${organizationId}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      this.emit(message.type, message.payload);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.attemptReconnect(token, organizationId);
    };
  }

  on(event: string, callback: Function) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(callback);
  }

  private emit(event: string, data: any) {
    const callbacks = this.listeners.get(event) || [];
    callbacks.forEach(callback => callback(data));
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
```

### Using WebSocket in Components

```typescript
// src/components/upload/UploadProgress.tsx
import React, { useEffect, useState } from 'react';
import { websocketService } from '../../services/websocketService';

interface UploadProgressProps {
  documentId: string;
}

export const UploadProgress: React.FC<UploadProgressProps> = ({ documentId }) => {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('processing');

  useEffect(() => {
    const handleProcessingUpdate = (data: any) => {
      if (data.document_id === documentId) {
        setProgress(data.progress);
        setStatus(data.status);
      }
    };

    websocketService.on('document_processing_update', handleProcessingUpdate);

    return () => {
      // Cleanup listener
    };
  }, [documentId]);

  return (
    <div className="upload-progress">
      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="status">{status}</div>
    </div>
  );
};
```

## Performance Optimization

### Code Splitting

```typescript
// src/pages/LazyPages.tsx
import { lazy } from 'react';

export const Dashboard = lazy(() => import('./Dashboard'));
export const KnowledgeGraph = lazy(() => import('./KnowledgeGraph'));
export const Evaluation = lazy(() => import('./Evaluation'));

// Usage in routing
<Suspense fallback={<div>Loading...</div>}>
  <Route path="/graph" element={<KnowledgeGraph />} />
</Suspense>
```

### Virtualization for Large Lists

```typescript
// src/components/common/VirtualizedList.tsx
import { FixedSizeList as List } from 'react-window';

interface VirtualizedListProps {
  items: any[];
  itemHeight: number;
  height: number;
  renderItem: ({ index, style }: any) => React.ReactNode;
}

export const VirtualizedList: React.FC<VirtualizedListProps> = ({
  items,
  itemHeight,
  height,
  renderItem
}) => {
  const Row = ({ index, style }) => (
    <div style={style}>
      {renderItem({ index, style, item: items[index] })}
    </div>
  );

  return (
    <List
      height={height}
      itemCount={items.length}
      itemSize={itemHeight}
      width="100%"
    >
      {Row}
    </List>
  );
};
```

## Troubleshooting

### Common Issues

#### Backend Connection Failed
```bash
# Check if backend is running
curl http://localhost:8000/health

# Check environment variables
echo $REACT_APP_API_BASE_URL
```

#### WebSocket Connection Issues
```javascript
// Add debug logging to WebSocket
console.log('WebSocket URL:', wsUrl);
console.log('Token available:', !!token);

// Check browser developer tools Network tab for WebSocket connection
```

#### Build Errors
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install

# Check TypeScript errors
npm run type-check
```

### Performance Issues

1. **Large Bundle Size**: Use `npm run analyze` to check bundle size
2. **Slow Initial Load**: Implement code splitting for heavy components
3. **Memory Leaks**: Check for unmounted components with lingering subscriptions
4. **Slow Renders**: Use React.memo and useMemo for expensive computations

## Deployment

### Build for Production

```bash
# Create production build
npm run build

# Test build locally
npm run serve

# Build with analysis
npm run build -- --analyze
```

### Environment Variables for Production

```env
# Production settings
REACT_APP_API_BASE_URL=https://api.ragsystem.com
REACT_APP_WS_URL=wss://api.ragsystem.com
REACT_APP_ENABLE_ANALYTICS=true
REACT_APP_DEV_MODE=false
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM node:18-alpine as builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## Resources

### Documentation
- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [API Contracts](./contracts/api-contracts.md)

### Tools & Extensions
- **VS Code Extensions**:
  - ES7+ React/Redux/React-Native snippets
  - TypeScript Importer
  - Tailwind CSS IntelliSense
  - Prettier - Code formatter

### Development Commands

```bash
# Development
npm run dev              # Start development server
npm run build            # Build for production
npm run test             # Run tests
npm run lint             # Run ESLint
npm run type-check       # Run TypeScript check

# Analysis
npm run analyze          # Analyze bundle size
npm run serve            # Serve production build
```

This quick start guide provides everything needed to get up and running quickly with the Multimodal Enterprise RAG System UI development. For more detailed information, refer to the component documentation and API contracts.