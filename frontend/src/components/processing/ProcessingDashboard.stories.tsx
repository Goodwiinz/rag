import type { Meta, StoryObj } from '@storybook/react';
import { ProcessingDashboard } from './ProcessingDashboard';
import { UploadQueueItem } from '@/services/uploadService';

// Mock data for stories
const createMockQueueItem = (
  overrides: Partial<UploadQueueItem> = {}
): UploadQueueItem => ({
  id: `job-${Math.random().toString(36).substr(2, 9)}`,
  file: new File(['test content'], `test-file-${Math.random().toString(36).substr(2, 5)}.pdf`, {
    type: 'application/pdf',
  }),
  status: 'processing',
  progress: Math.floor(Math.random() * 100),
  uploadStartTime: Date.now() - Math.random() * 300000, // Random time in last 5 minutes
  ...overrides,
});

const mockQueueItems: UploadQueueItem[] = [
  createMockQueueItem({
    file: new File(['PDF content'], 'document.pdf', { type: 'application/pdf' }),
    status: 'completed',
    progress: 100,
    completedAt: Date.now() - 60000,
    documentId: 'doc-123',
  }),
  createMockQueueItem({
    file: new File(['Image content'], 'image.jpg', { type: 'image/jpeg' }),
    status: 'processing',
    progress: 65,
    jobId: 'job-456',
  }),
  createMockQueueItem({
    file: new File(['Audio content'], 'audio.mp3', { type: 'audio/mpeg' }),
    status: 'processing',
    progress: 30,
    jobId: 'job-789',
  }),
  createMockQueueItem({
    file: new File(['Video content'], 'video.mp4', { type: 'video/mp4' }),
    status: 'error',
    progress: 45,
    error: 'Processing failed: Unable to extract audio from video',
    jobId: 'job-101',
  }),
  createMockQueueItem({
    file: new File(['Text content'], 'notes.txt', { type: 'text/plain' }),
    status: 'pending',
    progress: 0,
  }),
];

const meta: Meta<typeof ProcessingDashboard> = {
  title: 'Components/Processing/ProcessingDashboard',
  component: ProcessingDashboard,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
A real-time processing dashboard that monitors document upload and processing status with live updates, statistics, and management controls.

Features:
- Real-time WebSocket updates for processing status
- Comprehensive statistics and metrics
- Individual file progress tracking
- Filtering and search capabilities
- Retry failed uploads
- Performance monitoring
- Time-series activity charts
- Queue management controls
        `,
      },
    },
  },
  argTypes: {
    className: {
      control: 'text',
      description: 'Additional CSS classes',
    },
    autoRefresh: {
      control: 'boolean',
      description: 'Enable auto-refresh of data',
    },
    refreshInterval: {
      control: 'number',
      description: 'Refresh interval in seconds',
    },
    showControls: {
      control: 'boolean',
      description: 'Show control buttons',
    },
    maxHeight: {
      control: 'text',
      description: 'Maximum height for the queue list',
    },
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 5,
    showControls: true,
    maxHeight: '600px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <ProcessingDashboard {...args} />
    </div>
  ),
};

export const ActiveProcessing: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 2,
    showControls: true,
    maxHeight: '500px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <ProcessingDashboard {...args} />
    </div>
  ),
};

export const CompletedOnly: Story = {
  args: {
    className: '',
    autoRefresh: false,
    refreshInterval: 5,
    showControls: true,
    maxHeight: '400px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <ProcessingDashboard {...args} />
    </div>
  ),
};

export const WithErrors: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 5,
    showControls: true,
    maxHeight: '600px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <ProcessingDashboard {...args} />
    </div>
  ),
};

export const Compact: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 10,
    showControls: false,
    maxHeight: '300px',
  },
  render: (args) => (
    <div className="p-4 bg-white">
      <ProcessingDashboard {...args} />
    </div>
  ),
};

export const DarkMode: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 5,
    showControls: true,
    maxHeight: '600px',
  },
  parameters: {
    backgrounds: {
      default: 'dark',
      values: [
        {
          name: 'dark',
          value: '#1a1a1a',
        },
      ],
    },
  },
  render: (args) => (
    <div className="p-6 bg-gray-900 min-h-screen">
      <ProcessingDashboard {...args} />
    </div>
  ),
};

// Mock data for different scenarios
const largeQueueItems = Array.from({ length: 20 }, (_, i) =>
  createMockQueueItem({
    file: new File([`Content ${i}`], `file-${i}.pdf`, { type: 'application/pdf' }),
    status: i < 3 ? 'completed' : i < 8 ? 'processing' : i < 15 ? 'pending' : 'error',
    progress: i < 3 ? 100 : i < 8 ? Math.floor(Math.random() * 100) : 0,
    completedAt: i < 3 ? Date.now() - (i * 10000) : undefined,
    error: i >= 15 ? `Error processing file ${i}` : undefined,
  })
);

export const LargeQueue: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 3,
    showControls: true,
    maxHeight: '500px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <ProcessingDashboard {...args} />
    </div>
  ),
};

export const Playground: Story = {
  args: {
    className: '',
    autoRefresh: true,
    refreshInterval: 5,
    showControls: true,
    maxHeight: '600px',
  },
  parameters: {
    docs: {
      description: {
        story: 'Interactive playground for testing the processing dashboard. The dashboard will show mock data and update in real-time to demonstrate the features.',
      },
    },
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Processing Dashboard Demo</h2>
        <p className="text-gray-600">
          This dashboard shows real-time processing status with mock data. Try the controls to filter, pause, or interact with the queue.
        </p>
      </div>
      <ProcessingDashboard {...args} />
    </div>
  ),
};