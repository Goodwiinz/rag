# Component Tree Diagram: Multimodal Enterprise RAG UI

**Version**: 1.0.0
**Date**: 2025-10-19
**Author**: Claude Code Assistant

## Visual Component Hierarchy

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                       App                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │                                 AuthProvider                                 │   │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │   │
│  │  │                               Router                                 │   │   │
│  │  │  ┌─────────────────────────────────────────────────────────────┐   │   │   │
│  │  │  │                         ErrorBoundary                         │   │   │   │
│  │  │  │  ┌─────────────────────────────────────────────────────┐   │   │   │   │
│  │  │  │  │                    ProtectedRoute                    │   │   │   │   │
│  │  │  │  │  ┌─────────────────────────────────────────────────┐ │   │   │   │   │
│  │  │  │  │  │                   AppLayout                     │ │   │   │   │   │
│  │  │  │  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │ │   │   │   │   │
│  │  │  │  │  │  │    Header   │ │   Sidebar   │ │ MainContent │ │ │   │   │   │   │
│  │  │  │  │  │  └─────────────┘ └─────────────┘ └─────────────┘ │ │   │   │   │   │
│  │  │  │  │  │       │               │               │           │ │   │   │   │   │
│  │  │  │  │  │       │               │               │           │ │   │   │   │   │
│  │  │  │  │  │       │               │               ▼           │ │   │   │   │   │
│  │  │  │  │  │       │               │         ┌─────────────┐ │ │   │   │   │   │
│  │  │  │  │  │       │               │         │ Dashboard   │ │ │   │   │   │   │
│  │  │  │  │  │       │               │         └─────────────┘ │ │   │   │   │   │
│  │  │  │  │  │       │               │               │           │ │   │   │   │   │
│  │  │  │  │  │       │               │               ▼           │ │   │   │   │   │
│  │  │  │  │  │       │               │         ┌─────────────┐ │ │   │   │   │   │
│  │  │  │  │  │       │               │         │TwoPanelLayout│ │ │   │   │   │   │
│  │  │  │  │  │       │               │         └─────────────┘ │ │   │   │   │   │
│  │  │  │  │  │       │               │               │           │ │   │   │   │   │
│  │  │  │  │  │       │               │      ┌────────────────┐│ │   │   │   │   │
│  │  │  │  │  │       │               │      │                ││ │   │   │   │   │
│  │  │  │  │  │       │               │      ▼                ││ │   │   │   │   │
│  │  │  │  │  │       │               │  ┌───────────────┐   ││ │   │   │   │   │
│  │  │  │  │  │       │               │  │   LeftPanel   │   ││ │   │   │   │   │
│  │  │  │  │  │       │               │  └───────────────┘   ││ │   │   │   │   │
│  │  │  │  │  │       │               │          │            ││ │   │   │   │   │
│  │  │  │  │  │       │               │    ┌─────────────────┘│ │   │   │   │   │
│  │  │  │  │  │       │               │    │                │ │   │   │   │   │
│  │  │  │  │  │       │               │    ▼                │ │   │   │   │   │
│  │  │  │  │  │       │               │  ┌───────────────┐ │ │   │   │   │   │
│  │  │  │  │  │       │               │  │DocumentUpload │ │ │   │   │   │   │
│  │  │  │  │  │       │               │  │    Zone       │ │ │   │   │   │   │
│  │  │  │  │  │       │               │  └───────────────┘ │ │   │   │   │   │
│  │  │  │  │  │       │               │          │            │ │   │   │   │   │
│  │  │  │  │  │       │               │  ┌─────────────────┘ │ │   │   │   │   │
│  │  │  │  │  │       │               │  │                   │ │   │   │   │   │
│  │  │  │  │  │       │               │  ▼                   │ │   │   │   │   │
│  │  │  │  │  │       │               │┌─────────────────────┐│ │   │   │   │   │
│  │  │  │  │  │       │               ││   DocumentLibrary  ││ │   │   │   │   │
│  │  │  │  │  │       │               │└─────────────────────┘│ │   │   │   │   │
│  │  │  │  │  │       │               │          │            │ │   │   │   │   │
│  │  │  │  │  │       │               │    ┌─────────────────┘│ │   │   │   │   │
│  │  │  │  │  │       │               │    │                │ │   │   │   │   │
│  │  │  │  │  │       │               │    ▼                │ │   │   │   │   │
│  │  │  │  │  │       │               │  ┌───────────────┐ │ │   │   │   │   │
│  │  │  │  │  │       │               │  │ DocumentGrid │ │ │   │   │   │   │
│  │  │  │  │  │       │               │  └───────────────┘ │ │   │   │   │   │
│  │  │  │  │  │       │               │          │            │ │   │   │   │   │
│  │  │  │  │  │       │               │    ┌─────────────────┘│ │   │   │   │   │
│  │  │  │  │  │       │               │    │                │ │   │   │   │   │
│  │  │  │  │  │       │               │    ▼                │ │   │   │   │   │
│  │  │  │  │  │       │               │  ┌───────────────┐ │ │   │   │   │   │
│  │  │  │  │  │       │               │  │ DocumentCard │ │ │   │   │   │   │
│  │  │  │  │  │       │               │  └───────────────┘ │ │   │   │   │   │
│  │  │  │  │  │       │               │                      │ │   │   │   │   │
│  │  │  │  │  │       │               │                      │ │   │   │   │   │
│  │  │  │  │  │       │               └──────────────────────┘ │   │   │   │   │
│  │  │  │  │  │       │                           │            │   │   │   │   │
│  │  │  │  │  │       │                           ▼            │   │   │   │   │
│  │  │  │  │  │       │                     ┌─────────────┐   │   │   │   │   │
│  │  │  │  │  │       │                     │  RightPanel │   │   │   │   │   │
│  │  │  │  │  │       │                     └─────────────┘   │   │   │   │   │
│  │  │  │  │  │       │                           │            │   │   │   │   │
│  │  │  │  │  │       │                     ┌─────────────────┐ │   │   │   │   │
│  │  │  │  │  │       │                     │                 │ │   │   │   │   │
│  │  │  │  │  │       │                     ▼                 │ │   │   │   │   │
│  │  │  │  │  │       │               ┌───────────────┐     │ │   │   │   │   │
│  │  │  │  │  │       │               │ QueryInterface│     │ │   │   │   │   │
│  │  │  │  │  │       │               └───────────────┘     │ │   │   │   │   │
│  │  │  │  │  │       │                       │               │ │   │   │   │   │
│  │  │  │  │  │       │                 ┌─────────────────┐   │ │   │   │   │   │
│  │  │  │  │  │       │                 │                 │   │ │   │   │   │   │
│  │  │  │  │  │       │                 ▼                 │ │ │   │   │   │   │
│  │  │  │  │  │       │           ┌───────────────┐     │ │ │   │   │   │   │
│  │  │  │  │  │       │           │ SearchInput   │     │ │ │   │   │   │   │
│  │  │  │  │  │       │           └───────────────┘     │ │ │   │   │   │   │
│  │  │  │  │  │       │                   │               │ │ │   │   │   │   │
│  │  │  │  │  │       │             ┌─────────────────┐   │ │ │   │   │   │   │
│  │  │  │  │  │       │             │                 │   │ │ │   │   │   │   │
│  │  │  │  │  │       │             ▼                 │ │ │ │   │   │   │   │
│  │  │  │  │  │       │         ┌───────────────┐     │ │ │ │   │   │   │   │
│  │  │  │  │  │       │         │SearchFilters  │     │ │ │ │   │   │   │   │
│  │  │  │  │  │       │         └───────────────┘     │ │ │ │   │   │   │   │
│  │  │  │  │  │       │                 │               │ │ │ │   │   │   │   │
│  │  │  │  │  │       │               ┌─────────────────┘ │ │ │   │   │   │   │
│  │  │  │  │  │       │               │                   │ │ │   │   │   │   │
│  │  │  │  │  │       │               ▼                   │ │ │   │   │   │   │
│  │  │  │  │  │       │         ┌───────────────┐     │ │ │ │   │   │   │   │
│  │  │  │  │  │       │         │ResultsDisplay │     │ │ │ │   │   │   │   │
│  │  │  │  │  │       │         └───────────────┘     │ │ │ │   │   │   │   │
│  │  │  │  │  │       │                 │               │ │ │ │   │   │   │   │
│  │  │  │  │  │       │           ┌─────────────────┐   │ │ │ │   │   │   │   │
│  │  │  │  │  │       │           │                 │   │ │ │ │   │   │   │   │
│  │  │  │  │  │       │           ▼                 │ │ │ │ │   │   │   │   │
│  │  │  │  │  │       │     ┌─────────────────┐     │ │ │ │   │   │   │   │   │
│  │  │  │  │  │       │     │ TabNavigation   │     │ │ │ │   │   │   │   │   │
│  │  │  │  │  │       │     └─────────────────┘     │ │ │ │   │   │   │   │   │
│  │  │  │  │  │       │             │                   │ │ │ │   │   │   │   │   │
│  │  │  │  │  │       │     ┌─────────────────────────┘ │ │ │   │   │   │   │
│  │  │  │  │  │       │     │                           │ │ │   │   │   │   │
│  │  │  │  │  │       │     ▼                           │ │ │   │   │   │   │   │
│  │  │  │  │  │       │   ┌─────────────────────────────┐│ │ │   │   │   │   │   │
│  │  │  │  │  │       │   │         AnswersTab          ││ │ │   │   │   │   │   │
│  │  │  │  │  │       │   └─────────────────────────────┘│ │ │   │   │   │   │   │
│  │  │  │  │  │       │   ┌─────────────────────────────┐│ │ │   │   │   │   │   │
│  │  │  │  │  │       │   │         SourcesTab          ││ │ │   │   │   │   │   │
│  │  │  │  │  │       │   └─────────────────────────────┘│ │ │   │   │   │   │   │
│  │  │  │  │  │       │   ┌─────────────────────────────┐│ │ │   │   │   │   │   │
│  │  │  │  │  │       │   │          GraphTab           ││ │ │   │   │   │   │   │
│  │  │  │  │  │       │   └─────────────────────────────┘│ │ │   │   │   │   │   │
│  │  │  │  │  │       │   ┌─────────────────────────────┐│ │ │   │   │   │   │   │
│  │  │  │  │  │       │   │           EvalTab           ││ │ │   │   │   │   │   │
│  │  │  │  │  │       │   └─────────────────────────────┘│ │ │   │   │   │   │   │
│  │  │  │  │  │       │                                   │ │ │   │   │   │   │   │
│  │  │  │  │  │       │                                   │ │ │   │   │   │   │   │
│  │  │  │  │  │       └───────────────────────────────────┘ │   │   │   │   │   │
│  │  │  │  │                                                   │   │   │   │   │
│  │  │  │  │                                                   │   │   │   │   │
│  │  │  │  └─────────────────────────────────────────────────┘   │   │   │   │
│  │  │  │                                                         │   │   │   │
│  │  │  └─────────────────────────────────────────────────────────┘   │   │   │
│  │  │                                                               │   │   │
│  │  └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │   │
│                                                                       │   │
└───────────────────────────────────────────────────────────────────────┘   │
                                                                           │
                                                                           │
                                                                           ▼
```

## Component Flow Diagrams

### 1. Document Upload Flow

```
User Drag & Drop Files
          │
          ▼
┌─────────────────┐
│ DocumentUpload  │
│      Zone       │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ validateFiles   │  ←─── File validation
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ uploadFiles()   │  ←─── API call to /api/v1/documents
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ updateUIState   │  ←─── Optimistic UI update
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ WebSocket       │  ←─── Real-time processing updates
│ Connection      │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ProcessingStatus │
│   Component     │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│DocumentLibrary  │
│   Update        │
└─────────────────┘
```

### 2. Search Execution Flow

```
User Enters Query
          │
          ▼
┌─────────────────┐
│  SearchInput    │
│   Component     │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│  performSearch  │  ←─── API call to /api/v1/search
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ SearchProgress  │  ←─── WebSocket progress updates
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ ResultsDisplay  │
│   Component     │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ TabNavigation   │
└─────────────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌─────────┐ ┌─────────┐
│Answers  │ │ Sources │
│   Tab   │ │   Tab   │
└─────────┘ └─────────┘
    │           │
    ▼           ▼
┌─────────┐ ┌─────────┐
│GraphTab │ │ EvalTab │
└─────────┘ └─────────┘
```

### 3. Knowledge Graph Visualization Flow

```
User Clicks Graph Tab
          │
          ▼
┌─────────────────┐
│   GraphTab      │
│   Component     │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ fetchGraphData  │  ←─── API call to /api/v1/knowledge-graph/graph
└─────────────────┘
          │
          ▼
┌─────────────────┐
│KnowledgeGraph   │
│    Viewer       │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ Cytoscape.js    │  ←─── Graph rendering library
│  Rendering      │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ GraphControls   │
│   Component     │
└─────────────────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌─────────┐ ┌─────────┐
│Entity   │ │Graph    │
│Details  │ │Analytics│
│Panel    │ │         │
└─────────┘ └─────────┘
```

### 4. Evaluation Metrics Flow

```
Search Completed
          │
          ▼
┌─────────────────┐
│   EvalTab       │
│   Component     │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ calculateMetrics│  ←─── API call to /api/v1/evaluation/metrics
└─────────────────┘
          │
          ▼
┌─────────────────┐
│ RAGTriadMetrics │
│   Component     │
└─────────────────┘
          │
          ▼
┌─────────────────┐
│PerformanceCharts│  ←─── Recharts visualization
└─────────────────┘
          │
          ▼
┌─────────────────┐
│QualityIndicators│
│   Component     │
└─────────────────┘
```

## Props Flow Patterns

### 1. Top-Down Data Flow

```
AuthProvider
    │ (user, isAuthenticated)
    ▼
AppLayout
    │ (navigation state)
    ▼
Dashboard
    │ (documents, search results)
    ▼
TwoPanelLayout
    │             │
    ▼             ▼
LeftPanel    RightPanel
    │             │ (query, results)
    ▼             ▼
DocumentList  QueryInterface
    │             │
    ▼             ▼
DocumentCard   ResultsDisplay
```

### 2. Event Bubbling Pattern

```
DocumentCard.onClick
    │
    ▼
DocumentList.onDocumentSelect
    │
    ▼
LeftPanel.onDocumentSelect
    │
    ▼
Dashboard.onDocumentSelect
    │
    ▼
Update Global State
    │
    ▼
RightPanel Re-renders
```

### 3. Context Provider Pattern

```
SearchContext.Provider
    │
    ├─ QueryInterface (consumes search state)
    ├─ ResultsDisplay (consumes search results)
    ├─ AnswersTab (consumes search results)
    ├─ SourcesTab (consumes search results)
    ├─ GraphTab (consumes entities from results)
    └─ EvalTab (consumes query for evaluation)
```

## State Management Flow

### 1. Document Upload State Flow

```
Component Action → Dispatch Action → Reducer → State Update → Component Re-render

Dropzone.onDrop → dispatch('UPLOAD_START', files) →
documentReducer → { uploading: true, files: [...files] } →
UploadProgress renders
```

### 2. WebSocket Integration Flow

```
WebSocket Message → Context Handler → State Update → UI Update

'processing_update' → DocumentContext.handleWebSocket →
dispatch('UPDATE_PROCESSING_STATUS', data) →
ProcessingStatus component updates
```

### 3. Search State Flow

```
User Input → Search Action → API Call → Success/Error → State Update

SearchInput.onSubmit → dispatch('SEARCH_START', query) →
searchService.performSearch → dispatch('SEARCH_SUCCESS', results) →
ResultsDisplay renders with new data
```

## Component Dependencies

### 1. External Dependencies

```
┌─────────────────┐    ┌─────────────────┐
│   React Core    │    │ React Router    │
│                 │    │                 │
│ • useState      │    │ • BrowserRouter │
│ • useEffect     │    │ • Routes        │
│ • useContext    │    │ • Route         │
│ • useMemo       │    │ • Navigate      │
│ • useCallback   │    │ • useParams     │
└─────────────────┘    └─────────────────┘

┌─────────────────┐    ┌─────────────────┐
│ TanStack Query  │    │   Tailwind      │
│                 │    │     CSS         │
│ • useQuery      │    │                 │
│ • useMutation   │    │ • Responsive    │
│ • QueryClient   │    │ • Components    │
│ • Cache         │    │ • Utilities     │
└─────────────────┘    └─────────────────┘

┌─────────────────┐    ┌─────────────────┐
│  shadcn/ui      │    │  Libraries      │
│                 │    │                 │
│ • Button        │    │ • Cytoscape.js  │
│ • Card          │    │ • Recharts      │
│ • Input         │    │ • react-dropzone│
│ • Tabs          │    │ • React Hook    │
│ • Dialog        │    │   Form          │
│ • Select        │    │ • date-fns      │
└─────────────────┘    └─────────────────┘
```

### 2. Internal Dependencies

```
Core Components:
├── AppLayout
├── TwoPanelLayout
├── ErrorBoundary
└── ProtectedRoute

Feature Components:
├── DocumentUploadZone
│   ├── DropzoneArea
│   ├── FileList
│   ├── UploadProgress
│   └── ProcessingStatus
├── QueryInterface
│   ├── SearchInput
│   ├── SearchFilters
│   └── SearchHistory
├── ResultsDisplay
│   ├── AnswersTab
│   ├── SourcesTab
│   ├── GraphTab
│   └── EvalTab
└── KnowledgeGraphViewer
    ├── GraphControls
    ├── EntityDetailsPanel
    └── GraphAnalytics

Utility Components:
├── Button
├── Card
├── Modal
├── Tabs
├── Table
├── Progress
├── Alert
└── LoadingSpinner
```

## Component Communication Patterns

### 1. Parent-Child Communication

```typescript
// Parent passes props to child
<DocumentCard
  document={document}
  onSelect={handleDocumentSelect}
  isSelected={selectedDocumentId === document.id}
/>

// Child calls parent callback
const handleClick = () => {
  onSelect(document.id);
};
```

### 2. Context-Based Communication

```typescript
// Provider provides state
const SearchContext = createContext<SearchContextType>();

// Consumer uses state
const { searchResults, isSearching, performSearch } = useContext(SearchContext);
```

### 3. Event Bus Pattern

```typescript
// Custom event emitter for component communication
const eventBus = new EventTarget();

// Component A dispatches event
eventBus.dispatchEvent(new CustomEvent('documentSelected', {
  detail: { documentId }
}));

// Component B listens for event
eventBus.addEventListener('documentSelected', (event) => {
  const { documentId } = event.detail;
  // Handle document selection
});
```

This component tree diagram provides a visual understanding of the frontend architecture, showing the hierarchical structure, data flow patterns, and component relationships that support the core user stories of the Multimodal Enterprise RAG system.