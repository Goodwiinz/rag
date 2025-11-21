import type { Meta, StoryObj } from '@storybook/react';
import { fn } from '@storybook/test';
import { RealtimeProcessingDashboard } from './RealtimeProcessingDashboard';
import { DocumentProcessingState, ProcessingStage } from '@/types/realtime-processing';
import { within, expect, fireEvent, waitFor } from '@storybook/test';
import { axe, toHaveNoViolations } from 'jest-axe';

// Extend Jest matchers
expect.extend(toHaveNoViolations);

const meta: Meta<typeof RealtimeProcessingDashboard> = {
  title: 'Components/RealtimeProcessing/RealtimeProcessingDashboard',
  component: RealtimeProcessingDashboard,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
        A comprehensive real-time dashboard for monitoring document processing status with WebSocket integration.

        Features:
        - Real-time document status updates
        - Multi-stage processing visualization
        - Bulk operations on selected documents
        - Connection status monitoring
        - Performance metrics display
        - Accessibility support (WCAG 2.1 AA)
        - Responsive design
        - Error handling and retry mechanisms
        `
      }
    },
    a11y: {
      // Disable automatic axe testing for some stories that need special setup
      disable: false
    }
  },
  tags: ['autodocs'],
  argTypes: {
    autoRefresh: {
      control: 'boolean',
      description: 'Enable automatic refresh of processing status'
    },
    refreshInterval: {
      control: { type: 'range', min: 1, max: 60, step: 1 },
      description: 'Refresh interval in seconds'
    },
    showControls: {
      control: 'boolean',
      description: 'Show bulk action controls'
    },
    maxHeight: {
      control: 'text',
      description: 'Maximum height of the document list'
    },
    enableSounds: {
      control: 'boolean',
      description: 'Enable sound notifications'
    },
    theme: {
      control: 'select',
      options: ['light', 'dark', 'auto'],
      description: 'Theme preference'
    },
    compactView: {
      control: 'boolean',
      description: 'Use compact view layout'
    }
  }
};

export default meta;
type Story = StoryObj<typeof meta>;

// Sample data generators
const createProcessingStage = (
  name: string,
  status: ProcessingStage['status'],
  progress: number = 0
): ProcessingStage => ({
  id: `stage-${name.toLowerCase().replace(/\s+/g, '-')}`,
  name,
  description: `${name} processing stage`,
  progress,
  status,
  startedAt: status !== 'pending' ? new Date(Date.now() - 60000).toISOString() : undefined,
  completedAt: status === 'completed' ? new Date().toISOString() : undefined,
  duration: status === 'completed' ? 45000 : undefined
});

const createDocumentProcessingState = (
  filename: string,
  fileType: DocumentProcessingState['fileType'],
  status: DocumentProcessingState['status'],
  overallProgress: number = 0
): DocumentProcessingState => {
  const stages: ProcessingStage[] = [
    createProcessingStage('Upload', status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'completed', 100),
    createProcessingStage('OCR Processing', status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : status === 'processing' ? 'in_progress' : status === 'queued' ? 'pending' : 'completed', status === 'processing' ? overallProgress : status === 'completed' ? 100 : status === 'failed' ? 0 : 0),
    createProcessingStage('Entity Extraction', status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'pending', 0),
    createProcessingStage('Vector Embedding', status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'pending', 0),
    createProcessingStage('Indexing', status === 'completed' ? 'completed' : status === 'failed' ? 'failed' : 'pending', 0)
  ];

  const currentStage = stages.find(s => s.status === 'in_progress') || stages.find(s => s.status === 'failed') || stages[stages.length - 1];

  return {
    id: `doc-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    filename,
    fileType,
    overallProgress,
    currentStage: currentStage || stages[0],
    stages,
    status,
    uploadProgress: status === 'uploading' ? overallProgress : 100,
    metadata: {
      fileSize: Math.floor(Math.random() * 10 * 1024 * 1024), // 0-10MB
      pageCount: fileType === 'pdf' ? Math.floor(Math.random() * 50) + 1 : undefined,
      duration: (fileType === 'mp3' || fileType === 'mp4') ? Math.floor(Math.random() * 300) + 60 : undefined,
      uploadStartedAt: new Date(Date.now() - 120000).toISOString(),
      processingStartedAt: status !== 'queued' && status !== 'uploading' ? new Date(Date.now() - 60000).toISOString() : undefined,
      completedAt: status === 'completed' ? new Date().toISOString() : undefined,
      estimatedTimeRemaining: status === 'processing' ? Math.floor(Math.random() * 300) + 30 : undefined
    },
    error: status === 'failed' ? 'Processing failed due to corrupted file data' : undefined,
    retryCount: status === 'failed' ? Math.floor(Math.random() * 3) : 0,
    canRetry: status === 'failed',
    actions: {
      pause: status === 'processing',
      resume: status === 'paused',
      cancel: status === 'processing' || status === 'uploading' || status === 'queued',
      retry: status === 'failed',
      download: status === 'completed'
    }
  };
};

// Mock store for stories
const mockDocuments: DocumentProcessingState[] = [
  createDocumentProcessingState('report-2024.pdf', 'pdf', 'completed', 100),
  createDocumentProcessingState('meeting-notes.txt', 'txt', 'processing', 65),
  createDocumentProcessingState('presentation-slides.pdf', 'pdf', 'processing', 35),
  createDocumentProcessingState('product-image.jpg', 'jpg', 'queued', 0),
  createDocumentProcessingState('interview-recording.mp3', 'mp3', 'failed', 25),
  createDocumentProcessingState('training-video.mp4', 'mp4', 'uploading', 45),
  createDocumentProcessingState('user-manual.pdf', 'pdf', 'paused', 80),
  createDocumentProcessingState('logo-design.png', 'png', 'completed', 100),
  createDocumentProcessingState('technical-doc.pdf', 'pdf', 'processing', 15),
  createDocumentProcessingState('audio-book.mp3', 'mp3', 'queued', 0)
];

// Base story with all documents
export const Default: Story = {
  args: {
    autoRefresh: true,
    refreshInterval: 5,
    showControls: true,
    maxHeight: '600px',
    enableSounds: true,
    theme: 'auto',
    compactView: false
  },
  decorators: [
    (Story) => (
      <div className="p-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <Story />
        </div>
      </div>
    )
  ]
};

// Empty state
export const Empty: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => {
      // Mock empty store
      const mockUseRealtimeProcessingStore = () => ({
        queue: { documents: [], summary: { total: 0, queued: 0, processing: 0, completed: 0, failed: 0, paused: 0 }, metrics: { averageProcessingTime: 0, throughput: 0, successRate: 0, errorRate: 0 }, filters: {}, pagination: {} },
        connection: { status: 'connected', reconnectionAttempts: 0, latency: 50 },
        systemMetrics: { concurrentConnections: 5, memoryUsage: 60, cpuUsage: 30, activeJobs: 0 },
        notifications: [],
        ui: { selectedDocuments: [], compactView: false, theme: 'auto' }
      });

      return (
        <div className="p-6 bg-gray-50">
          <div className="max-w-7xl mx-auto">
            <Story />
          </div>
        </div>
      );
    }
  ]
};

// Single processing document
export const Processing: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => {
      const singleDocument = [createDocumentProcessingState('large-report.pdf', 'pdf', 'processing', 45)];

      return (
        <div className="p-6 bg-gray-50">
          <div className="max-w-7xl mx-auto">
            <Story />
          </div>
        </div>
      );
    }
  ]
};

// Documents with errors
export const WithErrors: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => {
      const documentsWithErrors = [
        createDocumentProcessingState('corrupted-file.pdf', 'pdf', 'failed', 0),
        createDocumentProcessingState('invalid-image.jpg', 'jpg', 'failed', 0),
        createDocumentProcessingState('damaged-audio.mp3', 'mp3', 'processing', 25)
      ];

      return (
        <div className="p-6 bg-gray-50">
          <div className="max-w-7xl mx-auto">
            <Story />
          </div>
        </div>
      );
    }
  ]
};

// Compact view
export const CompactView: Story = {
  args: {
    ...Default.args,
    compactView: true
  }
};

// Dark theme
export const DarkTheme: Story = {
  args: {
    ...Default.args,
    theme: 'dark'
  },
  decorators: [
    (Story) => (
      <div className="p-6 bg-gray-900 text-white min-h-screen">
        <div className="max-w-7xl mx-auto">
          <Story />
        </div>
      </div>
    )
  ]
};

// Disconnected state
export const Disconnected: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => (
      <div className="p-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <Story />
        </div>
      </div>
    )
  ]
};

// Large dataset (performance test)
export const LargeDataset: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => {
      // Generate 100 documents for performance testing
      const largeDataset = Array.from({ length: 100 }, (_, i) =>
        createDocumentProcessingState(
          `document-${i + 1}.${['pdf', 'txt', 'jpg', 'mp3', 'mp4'][i % 5]}`,
          ['pdf', 'txt', 'jpg', 'mp3', 'mp4'][i % 5] as DocumentProcessingState['fileType'],
          ['queued', 'processing', 'completed', 'failed'][i % 4] as DocumentProcessingState['status'],
          Math.floor(Math.random() * 100)
        )
      );

      return (
        <div className="p-6 bg-gray-50">
          <div className="max-w-7xl mx-auto">
            <Story />
          </div>
        </div>
      );
    }
  ]
};

// Accessibility tests
export const Accessibility: Story = {
  args: {
    ...Default.args,
    enableSounds: false // Disable sounds for accessibility testing
  },
  decorators: [
    (Story) => (
      <div className="p-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <Story />
        </div>
      </div>
    )
  ],
  play: async ({ canvasElement }) => {
    // Run axe accessibility tests
    const results = await axe(canvasElement);
    expect(results).toHaveNoViolations();

    // Test keyboard navigation
    const canvas = within(canvasElement);

    // Test tab navigation
    await fireEvent.keyDown(canvasElement, { key: 'Tab' });
    await fireEvent.keyDown(canvasElement, { key: 'Tab' });

    // Test Enter key on interactive elements
    const firstDocument = canvas.getByRole('article');
    expect(firstDocument).toHaveAttribute('tabIndex', '0');

    // Test ARIA labels
    expect(firstDocument).toHaveAttribute('aria-label');

    // Test progress bar accessibility
    const progressBars = canvas.getAllByRole('progressbar');
    progressBars.forEach(progressBar => {
      expect(progressBar).toHaveAttribute('aria-valuenow');
      expect(progressBar).toHaveAttribute('aria-valuemin');
      expect(progressBar).toHaveAttribute('aria-valuemax');
    });
  }
};

// Interactive tests
export const Interactive: Story = {
  args: {
    ...Default.args
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    // Test document selection
    const checkboxes = canvas.getAllByRole('checkbox');
    if (checkboxes.length > 0) {
      await fireEvent.click(checkboxes[0]);
      expect(checkboxes[0]).toBeChecked();
    }

    // Test details modal
    const viewDetailsButtons = canvas.getAllByLabelText(/View details/);
    if (viewDetailsButtons.length > 0) {
      await fireEvent.click(viewDetailsButtons[0]);

      // Wait for modal to appear
      await waitFor(() => {
        expect(canvas.getByText('Processing Details')).toBeInTheDocument();
      });
    }

    // Test settings modal
    const settingsButton = canvas.getByRole('button', { name: /settings/i });
    await fireEvent.click(settingsButton);

    await waitFor(() => {
      expect(canvas.getByText('Dashboard Settings')).toBeInTheDocument();
    });

    // Test notification panel
    const notificationButton = canvas.getByRole('button', { name: /notifications/i });
    await fireEvent.click(notificationButton);

    await waitFor(() => {
      expect(canvas.getByText('Notifications')).toBeInTheDocument();
    });
  }
};

// Performance monitoring story
export const PerformanceMonitor: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => {
      // Add performance monitoring
      const startTime = performance.now();

      return (
        <>
          <div className="fixed top-4 right-4 bg-black text-white p-2 rounded text-xs z-50">
            <div>Render Time: {performance.now() - startTime}ms</div>
          </div>
          <div className="p-6 bg-gray-50">
            <div className="max-w-7xl mx-auto">
              <Story />
            </div>
          </div>
        </>
      );
    }
  ]
};

// Real-time simulation story
export const RealTimeSimulation: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => {
      // Simulate real-time updates
      React.useEffect(() => {
        const interval = setInterval(() => {
          // Update progress of processing documents
          const progressElements = document.querySelectorAll('[role="progressbar"]');
          progressElements.forEach(element => {
            const currentProgress = parseInt(element.getAttribute('aria-valuenow') || '0');
            if (currentProgress < 100 && Math.random() > 0.7) {
              const newProgress = Math.min(currentProgress + Math.floor(Math.random() * 10), 100);
              element.setAttribute('aria-valuenow', newProgress.toString());

              // Update visual progress bar
              const progressBar = element.querySelector('div[style*="width"]');
              if (progressBar) {
                progressBar.style.width = `${newProgress}%`;
              }
            }
          });
        }, 1000);

        return () => clearInterval(interval);
      }, []);

      return (
        <div className="p-6 bg-gray-50">
          <div className="max-w-7xl mx-auto">
            <Story />
          </div>
        </div>
      );
    }
  ]
};

// Mobile responsive story
export const MobileResponsive: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => (
      <div className="p-2 bg-gray-50">
        <div className="max-w-md mx-auto">
          <Story />
        </div>
      </div>
    )
  ],
  parameters: {
    viewport: {
      defaultViewport: 'mobile1'
    }
  }
};

// Tablet responsive story
export const TabletResponsive: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => (
      <div className="p-4 bg-gray-50">
        <div className="max-w-2xl mx-auto">
          <Story />
        </div>
      </div>
    )
  ],
  parameters: {
    viewport: {
      defaultViewport: 'tablet'
    }
  }
};

// Story with various file types
export const MultipleFileTypes: Story = {
  args: {
    ...Default.args
  },
  decorators: [
    (Story) => {
      const variousFileTypes = [
        createDocumentProcessingState('annual-report.pdf', 'pdf', 'completed', 100),
        createDocumentProcessingState('meeting-notes.txt', 'txt', 'processing', 55),
        createDocumentProcessingState('company-logo.png', 'png', 'queued', 0),
        createDocumentProcessingState('product-shot.jpg', 'jpg', 'processing', 75),
        createDocumentProcessingState('podcast-episode.mp3', 'mp3', 'uploading', 30),
        createDocumentProcessingState('tutorial-video.mp4', 'mp4', 'processing', 40)
      ];

      return (
        <div className="p-6 bg-gray-50">
          <div className="max-w-7xl mx-auto">
            <Story />
          </div>
        </div>
      );
    }
  ]
};