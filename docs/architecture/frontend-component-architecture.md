# Frontend Component Architecture: Multimodal Enterprise RAG UI

**Version**: 1.0.0
**Date**: 2025-10-19
**Author**: Claude Code Assistant

## Executive Summary

This document defines the comprehensive frontend component architecture for the Multimodal Enterprise RAG UI system. The architecture follows React 18 + TypeScript best practices with API-first design, consuming the 9 microservices backend through proper REST APIs and WebSocket connections. The design emphasizes separation of concerns, reusability, performance, and accessibility while addressing the 4 core user stories: Document Ingestion, Natural Language Query, Knowledge Graph Exploration, and Query Performance Evaluation.

## Architecture Overview

### Design Principles

1. **API-First Frontend**: All data consumed through backend APIs, no frontend processing
2. **Component-Driven Architecture**: Reusable, testable components with clear boundaries
3. **Progressive Enhancement**: Core functionality works without JavaScript, enhanced with it
4. **Mobile-First Responsive Design**: Works seamlessly on desktop, tablet, and mobile
5. **Accessibility First**: WCAG 2.1 AA compliance with semantic HTML and ARIA support
6. **Performance Optimized**: Lazy loading, code splitting, and efficient rendering
7. **Error Resilient**: Graceful degradation with comprehensive error boundaries

### Technology Stack

- **Framework**: React 18.2+ with TypeScript 5.0+
- **State Management**: React Context API + useReducer for complex state
- **UI Library**: Tailwind CSS + shadcn/ui components
- **Data Fetching**: React Query (TanStack Query) with caching
- **Routing**: React Router v6 with lazy loading
- **Forms**: React Hook Form with Zod validation
- **Graph Visualization**: Cytoscape.js for knowledge graph
- **Charts**: Recharts for evaluation metrics
- **File Upload**: react-dropzone
- **Real-time**: WebSocket connections
- **Testing**: Jest + React Testing Library + Cypress
- **Build Tool**: Vite for fast development and optimized builds

### Core Architecture Corrections

**Critical Fix**: The original implementation incorrectly placed graph algorithms in the frontend. This architecture corrects that by:

- **Frontend Responsibility**: UI visualization, user interaction, data presentation
- **Backend Responsibility**: All graph processing, entity extraction, Neo4j operations
- **API Consumption**: Frontend consumes processed graph data via REST APIs
- **Real-time Updates**: WebSocket provides live processing status and results

## Component Architecture

### Component Hierarchy

```
App
├── AuthProvider
├── Router
├── ErrorBoundary
└── Routes
    ├── Public Routes
    │   └── LoginPage
    └── Protected Routes
        └── AppLayout
            ├── Header
            │   ├── UserMenu
            │   ├── NotificationCenter
            │   └── HelpButton
            ├── Sidebar
            │   ├── NavigationMenu
            │   ├── QuickActions
            │   └── StorageIndicator
            └── MainContent
                ├── Dashboard (Core User Stories)
                │   ├── TwoPanelLayout
                │   │   ├── LeftPanel
                │   │   │   ├── DocumentUploadZone
                │   │   │   │   ├── DropzoneArea
                │   │   │   │   ├── FileList
                │   │   │   │   ├── UploadProgress
                │   │   │   │   └── ProcessingStatus
                │   │   │   └── DocumentLibrary
                │   │   │       ├── DocumentGrid
                │   │   │       ├── DocumentCard
                │   │   │       └── DocumentPreview
                │   │   └── RightPanel
                │   │       ├── QueryInterface
                │   │       │   ├── SearchInput
                │   │       │   ├── AdvancedSearchBuilder
                │   │       │   ├── SearchFilters
                │   │       │   └── SearchHistory
                │   │       └── ResultsDisplay
                │   │           ├── TabNavigation
                │   │           ├── AnswersTab
                │   │           │   ├── GeneratedAnswer
                │   │           │   ├── SourceCitations
                │   │           │   └── ConfidenceScores
                │   │           ├── SourcesTab
                │   │           │   ├── SourceList
                │   │           │   ├── MultimodalViewer
                │   │           │   └── RankingScores
                │   │           ├── GraphTab
                │   │           │   ├── KnowledgeGraphViewer
                │   │           │   ├── GraphControls
                │   │           │   ├── EntityDetailsPanel
                │   │           │   └── GraphAnalytics
                │   │           └── EvalTab
                │   │               ├── RAGTriadMetrics
                │   │               ├── PerformanceCharts
                │   │               ├── QualityIndicators
                │   │                                       └── QueryAnalysis
                ├── Analytics Pages
                │   ├── AnalyticsDashboard
                │   ├── PerformanceAnalytics
                │   └── UsageAnalytics
                ├── Evaluation Pages
                │   ├── EvaluationManagement
                │   ├── EvaluationDetails
                │   └── BenchmarkComparison
                ├── Settings Pages
                │   ├── UserSettings
                │   ├── OrganizationSettings
                │   └── APIKeyManagement
                └── ErrorPages
                    ├── NotFoundPage
                    └── ServerErrorPage
```

### Component Categories

#### 1. Layout Components

**Purpose**: Provide application structure and navigation

```typescript
// components/layout/
├── AppLayout.tsx              // Main application layout
├── Header.tsx                 // Top navigation header
├── Sidebar.tsx                // Side navigation panel
├── MainContent.tsx            // Main content area
├── TwoPanelLayout.tsx         // Dashboard two-panel layout
├── PageSkeleton.tsx           // Loading skeleton
├── ErrorBoundary.tsx          // Error boundary wrapper
└── ProtectedRoute.tsx         // Authentication wrapper
```

#### 2. Document Management Components

**Purpose**: Handle file upload, processing, and library management

```typescript
// components/documents/
├── DocumentUploadZone.tsx     // Drag-and-drop upload area
├── DropzoneArea.tsx           // Dropzone implementation
├── FileList.tsx               // Uploaded files list
├── FileListItem.tsx           // Individual file item
├── UploadProgress.tsx         // Upload progress indicator
├── ProcessingStatus.tsx       // Processing status display
├── DocumentLibrary.tsx        // Document library view
├── DocumentGrid.tsx           // Grid layout for documents
├── DocumentCard.tsx           // Document card component
├── DocumentPreview.tsx        // Document preview modal
├── DocumentMetadata.tsx       // Document metadata display
├── BatchUploadManager.tsx     // Batch upload operations
└── DocumentFilters.tsx        // Document filtering options
```

#### 3. Search Interface Components

**Purpose**: Handle query input, search execution, and results display

```typescript
// components/search/
├── QueryInterface.tsx         // Main search interface
├── SearchInput.tsx            // Search input field
├── AdvancedSearchBuilder.tsx  // Advanced query builder
├── SearchFilters.tsx          // Search filter controls
├── SearchHistory.tsx          // Search history display
├── ResultsDisplay.tsx         // Results container
├── TabNavigation.tsx          // Results tab navigation
├── AnswerDisplay.tsx          // Generated answer display
├── SourceCitations.tsx        // Source citation display
├── MultimodalViewer.tsx       // Multi-modal content viewer
├── SearchProgressBar.tsx      // Search progress indicator
└── QuerySuggestions.tsx       // Query autocomplete
```

#### 4. Knowledge Graph Components

**Purpose**: Visualize and interact with knowledge graph data from backend

```typescript
// components/graph/
├── KnowledgeGraphViewer.tsx   // Main graph visualization
├── GraphControls.tsx          // Graph control panel
├── GraphLayout.tsx            // Graph layout manager
├── EntityDetailsPanel.tsx     // Entity information panel
├── GraphAnalytics.tsx         // Graph analytics display
├── GraphFilters.tsx           // Graph filtering controls
├── NodeRenderer.tsx           // Custom node rendering
├── EdgeRenderer.tsx           // Custom edge rendering
├── GraphLegend.tsx            // Graph legend
└── GraphExporter.tsx          // Graph export functionality
```

#### 5. Evaluation Components

**Purpose**: Display RAG triad metrics and performance analytics

```typescript
// components/evaluation/
├── EvaluationDashboard.tsx    // Main evaluation dashboard
├── RAGTriadMetrics.tsx        // RAG triad metrics display
├── PerformanceCharts.tsx      // Performance visualization
├── QualityIndicators.tsx      // Quality score indicators
├── QueryAnalysis.tsx          // Query analysis display
├── MetricDetails.tsx          // Detailed metric view
├── TrendAnalysis.tsx          // Performance trends
├── BenchmarkComparison.tsx    // Benchmark comparison view
└── EvaluationReports.tsx      // Evaluation reports
```

#### 6. Common UI Components

**Purpose**: Reusable UI components across the application

```typescript
// components/common/
├── Button.tsx                 // Enhanced button component
├── Input.tsx                  // Input field component
├── Modal.tsx                  // Modal dialog component
├── Card.tsx                   // Card container component
├── Badge.tsx                  // Badge/status component
├── Tabs.tsx                   // Tab navigation component
├── Table.tsx                  // Data table component
├── Select.tsx                 // Select dropdown component
├── Progress.tsx               // Progress indicator component
├── Alert.tsx                  // Alert/notification component
├── Spinner.tsx                // Loading spinner component
├── Tooltip.tsx                // Tooltip component
├── Collapse.tsx               // Collapsible content component
└── Pagination.tsx             // Pagination component
```

## State Management Architecture

### Global State Structure

```typescript
interface AppState {
  auth: AuthState;
  documents: DocumentState;
  search: SearchState;
  graph: GraphState;
  evaluation: EvaluationState;
  ui: UIState;
  notifications: NotificationState;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  token: string | null;
  permissions: Permission[];
  organization: Organization | null;
}

interface DocumentState {
  documents: Document[];
  selectedDocument: Document | null;
  uploadProgress: Record<string, UploadProgress>;
  processingStatus: Record<string, ProcessingStatus>;
  filters: DocumentFilters;
  pagination: PaginationState;
  isLoading: boolean;
  error: string | null;
}

interface SearchState {
  currentQuery: string;
  searchHistory: SearchHistoryItem[];
  searchResults: SearchResponse | null;
  isSearching: boolean;
  searchProgress: SearchProgress;
  filters: SearchFilters;
  selectedResult: SearchResult | null;
  activeTab: 'answers' | 'sources' | 'graph' | 'eval';
}

interface GraphState {
  graphData: GraphData | null;
  selectedEntity: Entity | null;
  highlightedConnections: Entity[];
  layout: GraphLayout;
  filters: GraphFilters;
  isLoading: boolean;
  error: string | null;
}

interface EvaluationState {
  currentMetrics: EvaluationMetrics | null;
  historicalData: EvaluationMetrics[];
  benchmarks: Benchmark[];
  trends: PerformanceTrend[];
  isLoading: boolean;
  error: string | null;
}

interface UIState {
  theme: 'light' | 'dark';
  sidebarCollapsed: boolean;
  activeView: 'dashboard' | 'analytics' | 'evaluation' | 'settings';
  modals: Record<string, boolean>;
  notifications: Notification[];
}
```

### Context Providers Structure

```typescript
// contexts/
├── AuthContext.tsx            // Authentication state
├── DocumentContext.tsx        // Document management state
├── SearchContext.tsx          // Search and results state
├── GraphContext.tsx           // Knowledge graph state
├── EvaluationContext.tsx      // Evaluation metrics state
├── UIContext.tsx              // UI state management
├── NotificationContext.tsx    // Notification system
└── WebSocketContext.tsx       // WebSocket connection
```

### State Flow Patterns

#### 1. Document Upload Flow

```typescript
// User uploads document → Update document state → Backend processing → WebSocket updates
const handleDocumentUpload = async (files: File[]) => {
  // 1. Optimistic update
  dispatch({ type: 'UPLOAD_STARTED', payload: files });

  // 2. API call
  try {
    const response = await documentService.uploadFiles(files);
    dispatch({ type: 'UPLOAD_SUCCESS', payload: response.data });
  } catch (error) {
    dispatch({ type: 'UPLOAD_ERROR', payload: error });
  }

  // 3. WebSocket handles processing updates
  // 4. State updated with processing progress
};
```

#### 2. Search Execution Flow

```typescript
// User submits query → Search API → Results display → Optional graph visualization
const handleSearch = async (query: string, filters?: SearchFilters) => {
  // 1. Update search state
  dispatch({ type: 'SEARCH_STARTED', payload: { query, filters } });

  // 2. Execute search
  try {
    const response = await searchService.performSearch({ query, filters });
    dispatch({ type: 'SEARCH_SUCCESS', payload: response.data });

    // 3. Trigger graph data fetch if needed
    if (response.data.entities.length > 0) {
      await fetchGraphData(response.data.entities);
    }
  } catch (error) {
    dispatch({ type: 'SEARCH_ERROR', payload: error });
  }
};
```

#### 3. Real-time Updates Flow

```typescript
// WebSocket receives updates → State updates → UI re-renders
useWebSocket((message) => {
  switch (message.type) {
    case 'PROCESSING_STATUS_UPDATE':
      dispatch({
        type: 'UPDATE_PROCESSING_STATUS',
        payload: message.data
      });
      break;
    case 'SEARCH_PROGRESS':
      dispatch({
        type: 'UPDATE_SEARCH_PROGRESS',
        payload: message.data
      });
      break;
    case 'GRAPH_DATA_UPDATE':
      dispatch({
        type: 'UPDATE_GRAPH_DATA',
        payload: message.data
      });
      break;
  }
});
```

## API Integration Architecture

### API Client Structure

```typescript
// services/
├── apiClient.ts               // Base API client configuration
├── authService.ts             // Authentication API calls
├── documentService.ts         // Document management API calls
├── searchService.ts           // Search API calls
├── graphService.ts            // Knowledge graph API calls
├── evaluationService.ts       // Evaluation API calls
├── analyticsService.ts        // Analytics API calls
├── websocketService.ts        // WebSocket connection management
└── uploadService.ts           // File upload handling
```

### API Client Configuration

```typescript
// services/apiClient.ts
class ApiClient {
  private baseURL: string;
  private defaultHeaders: Record<string, string>;

  constructor() {
    this.baseURL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8080';
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    };
  }

  // Authenticated request wrapper
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const token = getAuthToken();
    const url = `${this.baseURL}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        ...this.defaultHeaders,
        ...(token && { Authorization: `Bearer ${token}` }),
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new ApiError(response.status, await response.text());
    }

    return response.json();
  }

  // HTTP methods with type safety
  async get<T>(endpoint: string, params?: Record<string, any>): Promise<ApiResponse<T>> {
    const url = params ? `${endpoint}?${new URLSearchParams(params)}` : endpoint;
    return this.request<T>(url);
  }

  async post<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put<T>(endpoint: string, data?: any): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      method: 'DELETE',
    });
  }
}
```

### Service Implementations

#### Document Service

```typescript
// services/documentService.ts
class DocumentService {
  private apiClient: ApiClient;

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient;
  }

  async uploadFiles(files: File[]): Promise<ApiResponse<Document[]>> {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    return this.apiClient.post('/api/v1/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  }

  async getDocuments(params: DocumentListParams): Promise<ApiResponse<PaginatedResponse<Document>>> {
    return this.apiClient.get('/api/v1/documents', params);
  }

  async getDocument(id: string): Promise<ApiResponse<DocumentDetail>> {
    return this.apiClient.get(`/api/v1/documents/${id}`);
  }

  async deleteDocument(id: string): Promise<ApiResponse<void>> {
    return this.apiClient.delete(`/api/v1/documents/${id}`);
  }

  async getProcessingStatus(id: string): Promise<ApiResponse<ProcessingStatus>> {
    return this.apiClient.get(`/api/v1/documents/${id}/processing-status`);
  }
}
```

#### Search Service

```typescript
// services/searchService.ts
class SearchService {
  private apiClient: ApiClient;

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient;
  }

  async performSearch(query: SearchQuery): Promise<ApiResponse<SearchResponse>> {
    return this.apiClient.post('/api/v1/search', query);
  }

  async getSearchSuggestions(query: string, limit = 5): Promise<ApiResponse<SearchSuggestion[]>> {
    return this.apiClient.get('/api/v1/search/suggestions', { q: query, limit });
  }

  async getSearchHistory(): Promise<ApiResponse<SearchHistoryItem[]>> {
    return this.apiClient.get('/api/v1/search/history');
  }

  async deleteSearchItem(id: string): Promise<ApiResponse<void>> {
    return this.apiClient.delete(`/api/v1/search/history/${id}`);
  }
}
```

#### Knowledge Graph Service

```typescript
// services/graphService.ts
class GraphService {
  private apiClient: ApiClient;

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient;
  }

  async getGraphData(params: GraphRequest): Promise<ApiResponse<GraphData>> {
    return this.apiClient.get('/api/v1/knowledge-graph/graph', params);
  }

  async getEntities(params: EntityFilters): Promise<ApiResponse<Entity[]>> {
    return this.apiClient.get('/api/v1/knowledge-graph/entities', params);
  }

  async getEntityDetails(id: string): Promise<ApiResponse<EntityDetail>> {
    return this.apiClient.get(`/api/v1/knowledge-graph/entities/${id}`);
  }

  async getGraphAnalytics(params: AnalyticsRequest): Promise<ApiResponse<GraphAnalytics>> {
    return this.apiClient.get('/api/v1/knowledge-graph/analytics', params);
  }
}
```

### Caching Strategy

```typescript
// hooks/useQueryWithCache.ts
import { useQuery, useQueryClient } from '@tanstack/react-query';

export const useDocuments = (params: DocumentListParams) => {
  return useQuery({
    queryKey: ['documents', params],
    queryFn: () => documentService.getDocuments(params),
    staleTime: 5 * 60 * 1000, // 5 minutes
    cacheTime: 10 * 60 * 1000, // 10 minutes
    refetchOnWindowFocus: false,
  });
};

export const useSearchResults = (query: string, filters?: SearchFilters) => {
  return useQuery({
    queryKey: ['search', query, filters],
    queryFn: () => searchService.performSearch({ query, ...filters }),
    enabled: !!query,
    staleTime: 2 * 60 * 1000, // 2 minutes
    cacheTime: 5 * 60 * 1000, // 5 minutes
  });
};

export const useGraphData = (params: GraphRequest) => {
  return useQuery({
    queryKey: ['graph', params],
    queryFn: () => graphService.getGraphData(params),
    enabled: !!params.center_entity_id || !!params.entity_types?.length,
    staleTime: 10 * 60 * 1000, // 10 minutes
    cacheTime: 30 * 60 * 1000, // 30 minutes
  });
};
```

## Routing and Navigation Structure

### Route Definitions

```typescript
// router/routes.ts
export const routes = {
  // Public routes
  login: '/login',

  // Main application routes
  dashboard: '/',

  // Document management
  documents: '/documents',
  documentDetail: '/documents/:id',

  // Search interface (main feature)
  search: '/search',
  searchWithQuery: '/search?q=:query',

  // Analytics
  analytics: '/analytics',
  analyticsOverview: '/analytics/overview',
  analyticsPerformance: '/analytics/performance',
  analyticsUsage: '/analytics/usage',

  // Evaluation
  evaluation: '/evaluation',
  evaluationDetails: '/evaluation/:id',
  evaluationCompare: '/evaluation/compare',

  // Settings
  settings: '/settings',
  settingsProfile: '/settings/profile',
  settingsOrganization: '/settings/organization',
  settingsAPI: '/settings/api-keys',

  // Error pages
  notFound: '/404',
  serverError: '/500',
};
```

### Navigation Components

```typescript
// components/navigation/
├── MainNavigation.tsx         // Primary navigation
├── UserMenu.tsx               // User account menu
├── Breadcrumbs.tsx            // Breadcrumb navigation
├── QuickActions.tsx           // Quick action buttons
└── HelpMenu.tsx               // Help and support menu
```

### Route Guards

```typescript
// components/auth/
├── ProtectedRoute.tsx         // Authentication wrapper
├── RoleBasedRoute.tsx         // Role-based access control
└── PermissionGuard.tsx        // Permission-based access control
```

## Performance Optimization Strategy

### Code Splitting

```typescript
// Lazy loading with React.lazy
const DashboardPage = React.lazy(() => import('@/pages/DashboardPage'));
const SearchPage = React.lazy(() => import('@/pages/SearchPage'));
const AnalyticsPage = React.lazy(() => import('@/pages/analytics/AnalyticsPage'));
const EvaluationPage = React.lazy(() => import('@/pages/evaluation/EvaluationPage'));

// Route-based code splitting
const router = createBrowserRouter([
  {
    path: '/',
    element: <ProtectedRoute><AppLayout /></ProtectedRoute>,
    children: [
      {
        index: true,
        element: (
          <Suspense fallback={<PageSkeleton />}>
            <DashboardPage />
          </Suspense>
        ),
      },
      {
        path: 'search',
        element: (
          <Suspense fallback={<PageSkeleton />}>
            <SearchPage />
          </Suspense>
        ),
      },
      // ... other routes
    ],
  },
]);
```

### Component Optimization

```typescript
// React.memo for component memoization
const DocumentCard = React.memo(({ document, onSelect }: DocumentCardProps) => {
  return (
    <Card onClick={() => onSelect(document.id)}>
      {/* Card content */}
    </Card>
  );
}, (prevProps, nextProps) => {
  // Custom comparison function
  return prevProps.document.id === nextProps.document.id &&
         prevProps.document.processing_status === nextProps.document.processing_status;
});

// useMemo for expensive calculations
const filteredDocuments = useMemo(() => {
  return documents.filter(doc =>
    doc.title.toLowerCase().includes(searchTerm.toLowerCase()) &&
    matchesFilters(doc, activeFilters)
  );
}, [documents, searchTerm, activeFilters]);

// useCallback for event handlers
const handleDocumentSelect = useCallback((documentId: string) => {
  onSelectDocument(documentId);
}, [onSelectDocument]);
```

### Virtual Scrolling

```typescript
// components/common/VirtualizedList.tsx
import { FixedSizeList as List } from 'react-window';

interface VirtualizedListProps<T> {
  items: T[];
  itemHeight: number;
  height: number;
  renderItem: (props: { index: number; style: React.CSSProperties }) => React.ReactNode;
}

export const VirtualizedList = <T,>({
  items,
  itemHeight,
  height,
  renderItem
}: VirtualizedListProps<T>) => {
  return (
    <List
      height={height}
      itemCount={items.length}
      itemSize={itemHeight}
      itemData={items}
    >
      {renderItem}
    </List>
  );
};
```

### Image and Media Optimization

```typescript
// components/common/OptimizedImage.tsx
interface OptimizedImageProps {
  src: string;
  alt: string;
  width?: number;
  height?: number;
  lazy?: boolean;
}

export const OptimizedImage: React.FC<OptimizedImageProps> = ({
  src,
  alt,
  width,
  height,
  lazy = true,
}) => {
  const [isLoaded, setIsLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="relative">
      {!isLoaded && (
        <div className="absolute inset-0 bg-gray-200 animate-pulse" />
      )}
      <img
        src={src}
        alt={alt}
        width={width}
        height={height}
        loading={lazy ? 'lazy' : 'eager'}
        onLoad={() => setIsLoaded(true)}
        onError={() => setError('Failed to load image')}
        className={`transition-opacity duration-300 ${
          isLoaded ? 'opacity-100' : 'opacity-0'
        }`}
      />
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <span className="text-gray-500 text-sm">{error}</span>
        </div>
      )}
    </div>
  );
};
```

## Accessibility Implementation Plan

### WCAG 2.1 AA Compliance Checklist

#### 1. Semantic HTML Structure

```typescript
// Semantic markup for screen readers
export const SearchInterface: React.FC = () => {
  return (
    <main role="main" aria-label="Search interface">
      <section aria-labelledby="search-heading">
        <h1 id="search-heading">Document Search</h1>
        <form role="search" aria-label="Search documents">
          <label htmlFor="search-input" className="sr-only">
            Search documents
          </label>
          <input
            id="search-input"
            type="search"
            aria-describedby="search-help"
            aria-expanded={showSuggestions}
            aria-autocomplete="list"
          />
          <div id="search-help" className="sr-only">
            Enter keywords to search through your documents
          </div>
        </form>
      </section>

      <section aria-labelledby="results-heading">
        <h2 id="results-heading">Search Results</h2>
        <div role="region" aria-live="polite" aria-label="Search results">
          {/* Results content */}
        </div>
      </section>
    </main>
  );
};
```

#### 2. Keyboard Navigation

```typescript
// Keyboard navigation implementation
export const DocumentCard: React.FC<DocumentCardProps> = ({ document, onSelect }) => {
  const handleKeyDown = (event: React.KeyboardEvent) => {
    switch (event.key) {
      case 'Enter':
      case ' ':
        event.preventDefault();
        onSelect(document.id);
        break;
      case 'Tab':
        // Allow default tab behavior
        break;
      default:
        break;
    }
  };

  return (
    <div
      tabIndex={0}
      role="button"
      aria-label={`Select document ${document.title}`}
      onKeyDown={handleKeyDown}
      onClick={() => onSelect(document.id)}
      className="focus:ring-2 focus:ring-blue-500 focus:outline-none"
    >
      {/* Card content */}
    </div>
  );
};
```

#### 3. ARIA Attributes and Live Regions

```typescript
// ARIA live regions for dynamic content
export const SearchProgress: React.FC<{ progress: SearchProgress }> = ({ progress }) => {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      aria-label={`Search progress: ${progress.percentage}% complete`}
    >
      <div className="sr-only">
        Search is {progress.percentage}% complete. Current stage: {progress.stage}
      </div>
      <ProgressBar value={progress.percentage} />
      <span aria-hidden="true">{progress.stage}</span>
    </div>
  );
};

// ARIA for graph visualization
export const KnowledgeGraphViewer: React.FC = () => {
  return (
    <div
      role="application"
      aria-label="Knowledge graph visualization"
      aria-describedby="graph-help"
    >
      <div id="graph-help" className="sr-only">
        Interactive knowledge graph showing entity relationships. Use arrow keys to navigate, Space to select nodes, and Enter to view details.
      </div>
      {/* Graph content */}
    </div>
  );
};
```

#### 4. Focus Management

```typescript
// Focus management for modals and dynamic content
export const Modal: React.FC<ModalProps> = ({ isOpen, onClose, children }) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      // Store current focus
      previousFocusRef.current = document.activeElement as HTMLElement;

      // Focus modal
      modalRef.current?.focus();

      // Trap focus within modal
      const handleTabKey = (e: KeyboardEvent) => {
        if (e.key !== 'Tab') return;

        const focusableElements = modalRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );

        if (!focusableElements?.length) return;

        const firstElement = focusableElements[0] as HTMLElement;
        const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            lastElement.focus();
            e.preventDefault();
          }
        } else {
          if (document.activeElement === lastElement) {
            firstElement.focus();
            e.preventDefault();
          }
        }
      };

      document.addEventListener('keydown', handleTabKey);

      return () => {
        document.removeEventListener('keydown', handleTabKey);
        // Restore focus
        previousFocusRef.current?.focus();
      };
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div
        ref={modalRef}
        className="relative bg-white rounded-lg p-6 max-w-2xl mx-auto mt-20"
        tabIndex={-1}
      >
        {children}
      </div>
    </div>
  );
};
```

### Screen Reader Support

```typescript
// Screen reader announcements
export const useScreenReader = () => {
  const announce = (message: string, priority: 'polite' | 'assertive' = 'polite') => {
    const announcement = document.createElement('div');
    announcement.setAttribute('aria-live', priority);
    announcement.setAttribute('aria-atomic', 'true');
    announcement.className = 'sr-only';
    announcement.textContent = message;

    document.body.appendChild(announcement);

    setTimeout(() => {
      document.body.removeChild(announcement);
    }, 1000);
  };

  return { announce };
};

// Usage in components
export const DocumentUploadZone: React.FC = () => {
  const { announce } = useScreenReader();

  const handleDrop = (files: File[]) => {
    // Process files
    announce(`${files.length} files uploaded successfully. Processing has begun.`);
  };

  return (
    <div>
      {/* Dropzone content */}
    </div>
  );
};
```

## Testing Strategy

### Unit Testing with React Testing Library

```typescript
// __tests__/components/DocumentCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { DocumentCard } from '../DocumentCard';

describe('DocumentCard', () => {
  const mockDocument = {
    id: '1',
    title: 'Test Document',
    processing_status: 'indexed',
    file_type: 'pdf',
  };

  it('renders document information correctly', () => {
    render(<DocumentCard document={mockDocument} onSelect={jest.fn()} />);

    expect(screen.getByText('Test Document')).toBeInTheDocument();
    expect(screen.getByLabelText('Select document Test Document')).toBeInTheDocument();
  });

  it('calls onSelect when clicked', () => {
    const mockOnSelect = jest.fn();
    render(<DocumentCard document={mockDocument} onSelect={mockOnSelect} />);

    fireEvent.click(screen.getByRole('button'));
    expect(mockOnSelect).toHaveBeenCalledWith('1');
  });

  it('supports keyboard navigation', () => {
    const mockOnSelect = jest.fn();
    render(<DocumentCard document={mockDocument} onSelect={mockOnSelect} />);

    fireEvent.keyDown(screen.getByRole('button'), { key: 'Enter' });
    expect(mockOnSelect).toHaveBeenCalledWith('1');
  });
});
```

### Integration Testing

```typescript
// __tests__/integration/SearchFlow.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SearchPage } from '../pages/SearchPage';
import { mockSearchService } from '../__mocks__/searchService';

describe('Search Flow Integration', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
  });

  it('performs search and displays results', async () => {
    mockSearchService.performSearch.mockResolvedValue({
      data: {
        results: [
          { id: '1', title: 'Result 1', content_snippet: 'Snippet 1' },
          { id: '2', title: 'Result 2', content_snippet: 'Snippet 2' },
        ],
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <SearchPage />
      </QueryClientProvider>
    );

    const searchInput = screen.getByLabelText('Search documents');
    const searchButton = screen.getByRole('button', { name: 'Search' });

    fireEvent.change(searchInput, { target: { value: 'test query' } });
    fireEvent.click(searchButton);

    await waitFor(() => {
      expect(screen.getByText('Result 1')).toBeInTheDocument();
      expect(screen.getByText('Result 2')).toBeInTheDocument();
    });
  });
});
```

### E2E Testing with Cypress

```typescript
// cypress/e2e/user-workflows.cy.ts
describe('Document Upload and Search Workflow', () => {
  beforeEach(() => {
    cy.login('test@example.com', 'password');
    cy.visit('/');
  });

  it('should upload documents and perform search', () => {
    // Upload documents
    cy.get('[data-testid="upload-zone"]').attachFile('test-document.pdf', {
      subjectType: 'drag-n-drop',
    });

    cy.get('[data-testid="upload-progress"]', { timeout: 10000 })
      .should('contain', 'Processing');

    cy.get('[data-testid="processing-status"]', { timeout: 30000 })
      .should('contain', 'Indexed');

    // Perform search
    cy.get('[data-testid="search-input"]').type('test query');
    cy.get('[data-testid="search-button"]').click();

    // Verify results
    cy.get('[data-testid="search-results"]', { timeout: 10000 })
      .should('be.visible');

    cy.get('[data-testid="result-item"]')
      .should('have.length.greaterThan', 0);

    // Test graph tab
    cy.get('[data-testid="graph-tab"]').click();
    cy.get('[data-testid="knowledge-graph"]')
      .should('be.visible');

    // Test evaluation tab
    cy.get('[data-testid="eval-tab"]').click();
    cy.get('[data-testid="rag-metrics"]')
      .should('be.visible');
  });
});
```

## Component Library Integration

### shadcn/ui Component Customization

```typescript
// components/ui/customized/
├── Button.tsx                 // Enhanced shadcn button
├── Card.tsx                   // Enhanced shadcn card
├── Input.tsx                  // Enhanced shadcn input
├── Tabs.tsx                   // Enhanced shadcn tabs
└── Modal.tsx                  // Enhanced shadcn dialog

// Example: Enhanced Button component
import { Button as ShadcnButton } from '@/components/ui/button';
import { cva, type VariantProps } from 'class-variance-authority';

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "underline-offset-4 hover:underline text-primary",
        // Custom variants for RAG system
        search: "bg-blue-600 text-white hover:bg-blue-700",
        upload: "bg-green-600 text-white hover:bg-green-700",
        graph: "bg-purple-600 text-white hover:bg-purple-700",
      },
      size: {
        default: "h-10 py-2 px-4",
        sm: "h-9 px-3 rounded-md",
        lg: "h-11 px-8 rounded-md",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading, icon, children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled || loading}
        {...props}
      >
        {loading && <LoadingSpinner className="mr-2 h-4 w-4" />}
        {icon && !loading && <span className="mr-2">{icon}</span>}
        {children}
      </Comp>
    );
  }
);
```

### Design System Tokens

```typescript
// styles/tokens.ts
export const designTokens = {
  colors: {
    primary: {
      50: '#eff6ff',
      500: '#3b82f6',
      600: '#2563eb',
      700: '#1d4ed8',
    },
    semantic: {
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#06b6d4',
    },
    graph: {
      entity: {
        person: '#3b82f6',
        organization: '#10b981',
        location: '#f59e0b',
        concept: '#8b5cf6',
      },
      relationship: {
        strong: '#1f2937',
        medium: '#6b7280',
        weak: '#d1d5db',
      },
    },
  },
  spacing: {
    xs: '0.25rem',
    sm: '0.5rem',
    md: '1rem',
    lg: '1.5rem',
    xl: '2rem',
  },
  typography: {
    fontFamily: {
      sans: ['Inter', 'system-ui', 'sans-serif'],
      mono: ['JetBrains Mono', 'monospace'],
    },
    fontSize: {
      xs: ['0.75rem', { lineHeight: '1rem' }],
      sm: ['0.875rem', { lineHeight: '1.25rem' }],
      base: ['1rem', { lineHeight: '1.5rem' }],
      lg: ['1.125rem', { lineHeight: '1.75rem' }],
    },
  },
  animation: {
    duration: {
      fast: '150ms',
      normal: '300ms',
      slow: '500ms',
    },
    easing: {
      ease: 'cubic-bezier(0.4, 0, 0.2, 1)',
      easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
      easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
    },
  },
};
```

## Implementation Roadmap

### Phase 1: Core Foundation (2 weeks)

#### Week 1: Setup and Basic Structure
- [ ] Project setup with Vite and TypeScript configuration
- [ ] Tailwind CSS and shadcn/ui integration
- [ ] Basic routing structure with React Router
- [ ] Authentication context and API client setup
- [ ] Error boundaries and loading states

#### Week 2: Document Management
- [ ] Document upload zone with drag-and-drop
- [ ] File validation and progress tracking
- [ ] Document library with grid/list views
- [ ] Processing status display with WebSocket updates
- [ ] Basic document preview functionality

### Phase 2: Search Interface (2 weeks)

#### Week 3: Search Implementation
- [ ] Search input with autocomplete suggestions
- [ ] Advanced search builder with filters
- [ ] Search results display with tabbed interface
- [ ] Answer display with source citations
- [ ] Multimodal content viewer

#### Week 4: Results Enhancement
- [ ] Search progress indicators
- [ ] Real-time search updates via WebSocket
- [ ] Search history and saved searches
- [ ] Results ranking and relevance scores
- [ ] Export and sharing functionality

### Phase 3: Knowledge Graph (2 weeks)

#### Week 5: Graph Visualization
- [ ] Cytoscape.js integration for graph rendering
- [ ] Basic graph layout algorithms
- [ ] Node and edge rendering with styling
- [ ] Graph controls (zoom, pan, filters)
- [ ] Entity selection and details panel

#### Week 6: Graph Features
- [ ] Graph analytics and insights
- [ ] Interactive graph exploration
- [ ] Graph export functionality
- [ ] Performance optimization for large graphs
- [ ] Graph search and filtering

### Phase 4: Evaluation and Analytics (2 weeks)

#### Week 7: RAG Evaluation
- [ ] RAG Triad metrics display
- [ ] Performance charts and visualizations
- [ ] Quality indicators and scoring
- [ ] Query analysis and classification
- [ ] Benchmark comparison tools

#### Week 8: Analytics Dashboard
- [ ] Usage analytics and statistics
- [ ] Performance monitoring
- [ ] User behavior tracking
- [ ] Custom report generation
- [ ] Data export functionality

### Phase 5: Polish and Optimization (1 week)

#### Week 9: Final Polish
- [ ] Comprehensive accessibility audit
- [ ] Performance optimization and code splitting
- [ ] Error handling and edge cases
- [ ] Documentation and testing
- [ ] Deployment preparation

## Success Metrics

### Technical Metrics
- **Page Load Time**: <2 seconds for initial load
- **Time to Interactive**: <3 seconds
- **Bundle Size**: <500KB (gzipped) for initial load
- **Lighthouse Performance Score**: >90
- **Accessibility Score**: 100 (WCAG 2.1 AA compliance)

### User Experience Metrics
- **Task Completion Rate**: >95% for core user stories
- **User Satisfaction Score**: >4.5/5
- **Error Rate**: <1% of user interactions
- **Support Tickets**: <5% reduction in documentation-related tickets

### Business Metrics
- **Feature Adoption Rate**: >80% within 3 months
- **User Retention**: >90% monthly retention
- **Query Success Rate**: >85%
- **Document Processing Success Rate**: >95%

This comprehensive frontend architecture provides a solid foundation for the Multimodal Enterprise RAG UI system, addressing all user requirements while maintaining high standards for performance, accessibility, and maintainability. The API-first design ensures proper separation of concerns and leverages the robust backend microservices architecture.