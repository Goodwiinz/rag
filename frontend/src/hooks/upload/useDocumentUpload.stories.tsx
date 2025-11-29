import type { Meta, StoryObj } from '@storybook/react';
import { useEffect, useState } from 'react';
import { useDocumentUpload } from './useDocumentUpload';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CloudArrowUpIcon, TrashIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

// Mock component to demonstrate the hook
const UploadDemo = ({ options }: { options?: any }) => {
  const {
    queueItems,
    stats,
    addToQueue,
    removeFromQueue,
    retryUpload,
    cancelAllUploads,
    cleanupCompleted,
    isUploading,
    hasActiveUploads,
    allCompleted,
    hasErrors,
    overallProgress,
    uploadSpeed,
    estimatedTimeRemaining,
    validateFiles,
    formatFileSize,
    formatTime,
    getStatusText,
    getFileIcon,
  } = useDocumentUpload(options);

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    setSelectedFiles(files);
  };

  const handleAddToQueue = () => {
    if (selectedFiles.length > 0) {
      const result = addToQueue(selectedFiles);
      if (result.errors.length > 0) {
        console.error('Validation errors:', result.errors);
      }
      setSelectedFiles([]);
    }
  };

  const createMockFiles = () => {
    const mockFiles = [
      new File(['PDF content'], 'mock-document.pdf', { type: 'application/pdf' }),
      new File(['Image content'], 'mock-image.jpg', { type: 'image/jpeg' }),
      new File(['Text content'], 'mock-notes.txt', { type: 'text/plain' }),
    ];
    setSelectedFiles(mockFiles);
  };

  return (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="max-w-6xl mx-auto space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">useDocumentUpload Hook Demo</h2>
          <p className="text-gray-600">
            This demonstrates the useDocumentUpload hook functionality with mock data.
          </p>
        </div>

        {/* File Selection */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-4">File Selection</h3>
          <div className="space-y-4">
            <div className="flex items-center space-x-4">
              <input
                type="file"
                multiple
                onChange={handleFileSelect}
                className="block w-full text-sm text-gray-500
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-full file:border-0
                  file:text-sm file:font-semibold
                  file:bg-blue-50 file:text-blue-700
                  hover:file:bg-blue-100"
              />
              <Button
                variant="outline"
                onClick={createMockFiles}
              >
                Add Mock Files
              </Button>
              <Button
                onClick={handleAddToQueue}
                disabled={selectedFiles.length === 0}
              >
                <CloudArrowUpIcon className="h-4 w-4 mr-2" />
                Add to Queue ({selectedFiles.length})
              </Button>
            </div>

            {selectedFiles.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-700">Selected Files:</p>
                {selectedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                    <div className="flex items-center space-x-2">
                      <span>{getFileIcon(file)}</span>
                      <span className="text-sm">{file.name}</span>
                      <Badge variant="secondary">{formatFileSize(file.size)}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Statistics */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-4">Upload Statistics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.totalFiles}</div>
              <div className="text-sm text-gray-600">Total Files</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.completedFiles}</div>
              <div className="text-sm text-gray-600">Completed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-600">{stats.processingFiles}</div>
              <div className="text-sm text-gray-600">Processing</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{stats.failedFiles}</div>
              <div className="text-sm text-gray-600">Failed</div>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <div className="text-sm font-medium text-gray-700">Overall Progress</div>
              <div className="mt-1">
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${overallProgress}%` }}
                  />
                </div>
                <div className="text-sm text-gray-600 mt-1">{overallProgress}%</div>
              </div>
            </div>
            <div>
              <div className="text-sm font-medium text-gray-700">Upload Speed</div>
              <div className="text-lg font-semibold text-gray-900">{uploadSpeed}</div>
            </div>
            <div>
              <div className="text-sm font-medium text-gray-700">Time Remaining</div>
              <div className="text-lg font-semibold text-gray-900">{estimatedTimeRemaining}</div>
            </div>
          </div>
        </div>

        {/* Queue Management */}
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Queue Management</h3>
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => cleanupCompleted()}
              >
                <TrashIcon className="h-4 w-4 mr-2" />
                Cleanup Completed
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => cancelAllUploads()}
                disabled={!hasActiveUploads}
              >
                Cancel All
              </Button>
            </div>
          </div>

          <div className="flex items-center space-x-4 mb-4">
            <Badge variant={isUploading ? "default" : "secondary"}>
              {isUploading ? 'Uploading' : 'Idle'}
            </Badge>
            <Badge variant={hasActiveUploads ? "default" : "secondary"}>
              {hasActiveUploads ? 'Active' : 'No Active Uploads'}
            </Badge>
            <Badge variant={allCompleted ? "default" : "secondary"}>
              {allCompleted ? 'All Completed' : 'In Progress'}
            </Badge>
            <Badge variant={hasErrors ? "destructive" : "secondary"}>
              {hasErrors ? 'Has Errors' : 'No Errors'}
            </Badge>
          </div>
        </div>

        {/* Queue Items */}
        {queueItems.length > 0 && (
          <div className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold mb-4">Queue Items ({queueItems.length})</h3>
            <div className="space-y-3">
              {queueItems.map((item) => (
                <div key={item.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center space-x-3 flex-1 min-w-0">
                    <div className="text-lg">{getFileIcon(item.file)}</div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{item.file.name}</p>
                      <div className="flex items-center space-x-2 mt-1">
                        <Badge variant="outline">{getStatusText(item.status)}</Badge>
                        <span className="text-xs text-gray-500">{formatFileSize(item.file.size)}</span>
                        {item.progress > 0 && (
                          <span className="text-xs text-gray-500">{item.progress}%</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    {item.status === 'error' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => retryUpload(item.id)}
                      >
                        <ArrowPathIcon className="h-4 w-4" />
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => removeFromQueue(item.id)}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </Button>
                  </div>

                  {item.error && (
                    <div className="col-span-full mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                      {item.error}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {queueItems.length === 0 && (
          <div className="bg-white p-12 rounded-lg shadow text-center">
            <CloudArrowUpIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No files in queue</h3>
            <p className="text-gray-600">Select files above to add them to the upload queue.</p>
          </div>
        )}
      </div>
    </div>
  );
};

const meta: Meta<typeof UploadDemo> = {
  title: 'Hooks/useDocumentUpload',
  component: UploadDemo,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
A comprehensive hook for managing document uploads with queue management, progress tracking, validation, and real-time status updates.

Features:
- Queue management with concurrent upload limits
- File validation with detailed error messages
- Real-time progress tracking and statistics
- WebSocket integration for live updates
- Retry functionality for failed uploads
- Comprehensive upload statistics and metrics
- TypeScript support with full type safety
- Memory efficient with automatic cleanup
- Configurable upload limits and options

**Hook API:**
- \`queueItems\`: Array of items in the upload queue
- \`stats\`: Upload statistics and metrics
- \`addToQueue(files)\`: Add files to the upload queue
- \`removeFromQueue(fileId)\`: Remove item from queue
- \`retryUpload(fileId)\`: Retry a failed upload
- \`cancelAllUploads()\`: Cancel all active uploads
- \`cleanupCompleted()\`: Remove completed items from queue
- Various status flags and formatting utilities
        `,
      },
    },
  },
  argTypes: {
    options: {
      control: 'object',
      description: 'Configuration options for the hook',
    },
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    options: {
      maxConcurrentUploads: 3,
      maxFiles: 10,
      maxFileSize: 50 * 1024 * 1024, // 50MB
      currentQuotaUsed: 0,
      maxQuota: 5 * 1024 * 1024 * 1024, // 5GB
      autoCleanup: false,
    },
  },
};

export const WithStrictLimits: Story = {
  args: {
    options: {
      maxConcurrentUploads: 1,
      maxFiles: 3,
      maxFileSize: 10 * 1024 * 1024, // 10MB
      currentQuotaUsed: 4 * 1024 * 1024 * 1024, // 4GB
      maxQuota: 5 * 1024 * 1024 * 1024, // 5GB
      autoCleanup: true,
      cleanupInterval: 5, // 5 minutes
    },
  },
};

export const HighConcurrency: Story = {
  args: {
    options: {
      maxConcurrentUploads: 5,
      maxFiles: 50,
      maxFileSize: 100 * 1024 * 1024, // 100MB
      currentQuotaUsed: 0,
      maxQuota: 10 * 1024 * 1024 * 1024, // 10GB
      autoCleanup: false,
    },
  },
};

export const WithAutoCleanup: Story = {
  args: {
    options: {
      maxConcurrentUploads: 2,
      maxFiles: 10,
      maxFileSize: 25 * 1024 * 1024, // 25MB
      currentQuotaUsed: 0,
      maxQuota: 2 * 1024 * 1024 * 1024, // 2GB
      autoCleanup: true,
      cleanupInterval: 1, // 1 minute (for demo purposes)
    },
  },
  parameters: {
    docs: {
      description: {
        story: 'Demonstrates auto-cleanup functionality. Completed items will be automatically removed from the queue after the specified interval.',
      },
    },
  },
};

export const Playground: Story = {
  args: {
    options: {
      maxConcurrentUploads: 3,
      maxFiles: 10,
      maxFileSize: 50 * 1024 * 1024,
      currentQuotaUsed: 1 * 1024 * 1024 * 1024, // 1GB
      maxQuota: 5 * 1024 * 1024 * 1024, // 5GB
      autoCleanup: false,
    },
  },
  parameters: {
    docs: {
      description: {
        story: 'Interactive playground for testing the useDocumentUpload hook. Use the file input to select files or add mock files to test the upload queue functionality. The hook provides a complete upload management system with real-time progress tracking, error handling, and queue management.',
      },
    },
  },
};