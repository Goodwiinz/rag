# Real-Time Document Processing Status Display Architecture

## Component Tree Structure

```
RealtimeProcessingDashboard/
├── RealtimeProcessingProvider
│   ├── WebSocketManager
│   └── NotificationSystem
├── Header/
│   ├── ConnectionStatus
│   ├── SystemMetrics
│   └── GlobalControls
├── Sidebar/
│   ├── FiltersPanel
│   ├── BulkActions
│   └── QueueStats
├── MainContent/
│   ├── ProcessingQueue/
│   │   ├── QueueHeader
│   │   ├── DocumentList
│   │   │   └── DocumentCard/
│   │   │       ├── DocumentInfo
│   │   │       ├── ProgressBar
│   │   │       ├── StageIndicator
│   │   │       ├── ActionButtons
│   │   │       └── ErrorDisplay
│   │   └── PaginationControls
│   ├── DetailedView/
│   │   ├── DocumentDetails
│   │   ├── StageBreakdown
│   │   ├── TimelineView
│   │   └── PerformanceMetrics
│   └── EmptyState
└── Modals/
    ├── DocumentDetailsModal
    ├── SettingsModal
    └── ConfirmActionModal
```

## State Management Strategy (Zustand)

### Primary Store: `realtimeProcessingStore`
- **Connection State**: WebSocket status, reconnection logic
- **Queue Management**: Document processing states, filters, pagination
- **UI State**: Selected documents, sidebar state, preferences
- **Notifications**: Toast notifications, alerts
- **System Metrics**: Performance data, throughput stats

### Store Advantages:
- **Performance**: Selective subscriptions prevent unnecessary re-renders
- **Type Safety**: Full TypeScript integration with inferred types
- **Persistence**: Optional middleware for local storage
- **DevTools**: Built-in debugging capabilities
- **Optimistic Updates**: Immediate UI feedback

## WebSocket Client Integration

### WebSocket Manager Component
```typescript
interface WebSocketManagerProps {
  url: string;
  token: string;
  organizationId: string;
  children: React.ReactNode;
}

interface WebSocketMessage {
  type: 'document_update' | 'queue_update' | 'system_metrics' | 'notification';
  payload: any;
  timestamp: string;
  documentId?: string;
  jobId?: string;
}
```

### Connection Management
- **Auto-reconnection**: Exponential backoff with max attempts
- **Heartbeat**: Keep-alive pings for connection health
- **Message Queue**: Buffer messages during disconnection
- **Error Handling**: Graceful degradation and retry logic
- **Latency Monitoring**: Track connection performance

## Component Interfaces and Props

### Core Interfaces

```typescript
interface DocumentProcessingState {
  id: string;
  filename: string;
  fileType: 'pdf' | 'txt' | 'jpg' | 'png' | 'mp3' | 'mp4';
  overallProgress: number; // 0-100
  currentStage: ProcessingStage;
  stages: ProcessingStage[];
  status: 'queued' | 'uploading' | 'processing' | 'completed' | 'failed' | 'paused' | 'cancelled';
  uploadProgress: number; // 0-100
  metadata: {
    fileSize: number;
    pageCount?: number;
    duration?: number;
    uploadStartedAt: string;
    processingStartedAt?: string;
    completedAt?: string;
    estimatedTimeRemaining?: number;
  };
  error?: string;
  retryCount: number;
  canRetry: boolean;
  actions: {
    pause: boolean;
    resume: boolean;
    cancel: boolean;
    retry: boolean;
    download: boolean;
  };
}

interface ProcessingStage {
  id: string;
  name: string;
  description: string;
  progress: number; // 0-100
  status: 'pending' | 'in_progress' | 'completed' | 'failed' | 'skipped';
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  error?: string;
}

interface RealtimeDashboardProps {
  className?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
  showControls?: boolean;
  maxHeight?: string;
  enableSounds?: boolean;
  theme?: 'light' | 'dark' | 'auto';
  compactView?: boolean;
}
```

### Component Props

```typescript
// Document Card Props
interface DocumentCardProps {
  document: DocumentProcessingState;
  isSelected: boolean;
  onSelect: (documentId: string) => void;
  onPause: (documentId: string) => void;
  onResume: (documentId: string) => void;
  onCancel: (documentId: string) => void;
  onRetry: (documentId: string) => void;
  onShowDetails: (documentId: string) => void;
  compact?: boolean;
}

// Progress Bar Props
interface ProgressBarProps {
  progress: number;
  stage: ProcessingStage;
  showPercentage?: boolean;
  showStageName?: boolean;
  animated?: boolean;
  color?: string;
  size?: 'sm' | 'md' | 'lg';
}

// Stage Indicator Props
interface StageIndicatorProps {
  stages: ProcessingStage[];
  currentStage: ProcessingStage;
  showIcons?: boolean;
  showProgress?: boolean;
  layout?: 'horizontal' | 'vertical';
}

// Connection Status Props
interface ConnectionStatusProps {
  status: WebSocketConnectionState['status'];
  latency: number;
  reconnectionAttempts: number;
  onReconnect: () => void;
  onDisconnect: () => void;
  showDetails?: boolean;
}
```

## Performance Optimizations

### 1. React Performance
- **Memoization**: React.memo for pure components
- **Callback Memoization**: useCallback for event handlers
- **Virtual Scrolling**: react-window for large document lists
- **Debounced Updates**:lodash.debounce for search/filter inputs
- **Lazy Loading**: React.lazy for modals and detailed views

### 2. State Management Optimization
- **Selector-based Subscriptions**: Only subscribe to needed state slices
- **Batch Updates**: Combine multiple state updates
- **Computed Values**: Derived state in selectors
- **State Normalization**: Flat state structure for efficient lookups

### 3. WebSocket Optimization
- **Message Throttling**: Limit update frequency (100-500ms)
- **Batch Updates**: Combine multiple document updates
- **Connection Pooling**: Reuse connections across components
- **Message Prioritization**: Critical updates first

### 4. Rendering Optimization
```typescript
// Virtual scrolling for large document lists
import { FixedSizeList as List } from 'react-window';

const DocumentList: React.FC<DocumentListProps> = ({ documents }) => {
  const Row = useCallback(({ index, style }: { index: number; style: React.CSSProperties }) => (
    <div style={style}>
      <DocumentCard document={documents[index]} />
    </div>
  ), [documents]);

  return (
    <List
      height={600}
      itemCount={documents.length}
      itemSize={80}
      itemData={documents}
    >
      {Row}
    </List>
  );
};
```

## Error Handling Patterns

### 1. Error Boundary
```typescript
class ProcessingErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Processing Dashboard Error:', error, errorInfo);
    // Send to error reporting service
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} onRetry={this.handleRetry} />;
    }

    return this.props.children;
  }
}
```

### 2. WebSocket Error Handling
```typescript
const useWebSocketErrorHandler = () => {
  const addNotification = useRealtimeProcessingStore(state => state.addNotification);

  const handleError = useCallback((error: Error) => {
    addNotification({
      type: 'error',
      title: 'Connection Error',
      message: 'Lost connection to processing server. Attempting to reconnect...',
      autoHide: false,
      actions: [
        {
          label: 'Reconnect',
          action: () => window.location.reload()
        }
      ]
    });
  }, [addNotification]);

  return { handleError };
};
```

### 3. Document Processing Errors
```typescript
const useDocumentErrorHandler = () => {
  const addNotification = useRealtimeProcessingStore(state => state.addNotification);

  const handleDocumentError = useCallback((documentId: string, error: string) => {
    addNotification({
      type: 'error',
      title: 'Processing Failed',
      message: `Document processing failed: ${error}`,
      documentId,
      autoHide: false,
      actions: [
        {
          label: 'Retry',
          action: () => retryDocument(documentId)
        },
        {
          label: 'Details',
          action: () => showDocumentDetails(documentId)
        }
      ]
    });
  }, [addNotification]);

  return { handleDocumentError };
};
```

## Accessibility Features (WCAG 2.1 AA)

### 1. Keyboard Navigation
- **Tab Order**: Logical navigation flow
- **Focus Management**: Visible focus indicators
- **Skip Links**: Jump to main content
- **Keyboard Shortcuts**: Common actions (Ctrl+P for pause)

### 2. Screen Reader Support
- **ARIA Labels**: Descriptive labels for all interactive elements
- **Live Regions**: Announce status changes
- **Semantic HTML**: Proper heading hierarchy
- **Alt Text**: Meaningful descriptions for icons

### 3. Visual Accessibility
- **Color Contrast**: 4.5:1 minimum ratio
- **Text Scaling**: Support 200% zoom
- **High Contrast Mode**: Respect OS preferences
- **Reduced Motion**: Respect prefers-reduced-motion

### 4. Accessibility Implementation
```typescript
const DocumentCard: React.FC<DocumentCardProps> = ({ document, ...props }) => {
  const statusAriaLabel = `Document ${document.filename}, ${document.status}, ${document.overallProgress}% complete`;

  return (
    <div
      role="article"
      aria-label={statusAriaLabel}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      className="document-card"
    >
      <button
        aria-label={`Pause processing for ${document.filename}`}
        aria-describedby={`progress-${document.id}`}
        onClick={() => props.onPause(document.id)}
        disabled={!document.actions.pause}
      >
        <PauseIcon aria-hidden="true" />
      </button>

      <div
        id={`progress-${document.id}`}
        role="progressbar"
        aria-valuenow={document.overallProgress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Processing progress: ${document.overallProgress}%`}
        className="progress-bar"
      >
        {document.overallProgress}%
      </div>

      <div aria-live="polite" aria-atomic="true" className="sr-only">
        Status: {document.status}, Current stage: {document.currentStage.name}
      </div>
    </div>
  );
};
```

## Storybook Documentation Plan

### 1. Component Stories
```typescript
// stories/RealtimeProcessingDashboard.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { RealtimeProcessingDashboard } from './RealtimeProcessingDashboard';

const meta: Meta<typeof RealtimeProcessingDashboard> = {
  title: 'Components/RealtimeProcessingDashboard',
  component: RealtimeProcessingDashboard,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Real-time document processing status dashboard with WebSocket integration and accessibility support.'
      }
    }
  }
};

export default meta;
type Story = StoryObj<typeof meta>;

// Base story with sample data
export const Default: Story = {
  args: {
    autoRefresh: true,
    refreshInterval: 500,
    showControls: true,
    enableSounds: true
  }
};

// Different states
export const Empty: Story = {
  args: {
    ...Default.args
  }
};

export const Processing: Story = {
  args: {
    ...Default.args
  }
};

export const WithErrors: Story = {
  args: {
    ...Default.args
  }
};

// Accessibility testing
export const Accessibility: Story = {
  args: {
    ...Default.args
  },
  parameters: {
    a11y: {
      disable: false
    }
  }
};
```

### 2. Documentation Structure
- **Component API**: Props, events, and methods
- **Usage Examples**: Common implementation patterns
- **Design Guidelines**: When and how to use components
- **Accessibility Guide**: ARIA patterns and keyboard navigation
- **Performance Tips**: Optimization best practices
- **Migration Guide**: Upgrading from older versions

### 3. Interactive Examples
- **WebSocket Mock**: Simulate real-time updates
- **State Management**: Store integration examples
- **Custom Themes**: Theme customization guide
- **Keyboard Shortcuts**: Accessibility demo

## Implementation Checklist

### Phase 1: Core Architecture
- [ ] Set up Zustand store with TypeScript
- [ ] Create WebSocket client with reconnection logic
- [ ] Build basic component structure
- [ ] Implement error boundaries
- [ ] Add accessibility basics

### Phase 2: UI Components
- [ ] Document card with progress indicators
- [ ] Stage visualization components
- [ ] Connection status indicators
- [ ] Filter and search functionality
- [ ] Bulk action controls

### Phase 3: Real-time Features
- [ ] WebSocket message handling
- [ ] Real-time progress updates
- [ ] Notification system
- [ ] System metrics display
- [ ] Performance monitoring

### Phase 4: Advanced Features
- [ ] Virtual scrolling for large lists
- [ ] Detailed document views
- [ ] Historical data visualization
- [ ] Export/import functionality
- [ ] Advanced filtering

### Phase 5: Polish & Documentation
- [ ] Comprehensive Storybook stories
- [ ] Accessibility testing
- [ ] Performance optimization
- [ ] Error handling validation
- [ ] User acceptance testing

This architecture provides a comprehensive foundation for building a real-time document processing status display that is performant, accessible, and maintainable while leveraging the existing React/TypeScript/Zustand stack.