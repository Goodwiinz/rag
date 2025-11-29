import type { Meta, StoryObj } from '@storybook/react';
import { DocumentUploadWizard } from './DocumentUploadWizard';

const meta: Meta<typeof DocumentUploadWizard> = {
  title: 'Components/Upload/DocumentUploadWizard',
  component: DocumentUploadWizard,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: `
A comprehensive document upload wizard with drag-and-drop functionality, file validation, progress tracking, and real-time status updates.

Features:
- Drag-and-drop file upload
- Multi-file support with batch processing
- File type and size validation
- Real-time upload progress tracking
- Step-by-step wizard interface
- Error handling and retry functionality
- Image preview support
- Responsive design
        `,
      },
    },
  },
  argTypes: {
    isOpen: {
      control: 'boolean',
      description: 'Whether the wizard is open',
    },
    maxFiles: {
      control: 'number',
      description: 'Maximum number of files allowed',
    },
    maxFileSize: {
      control: 'number',
      description: 'Maximum file size in bytes',
    },
    currentQuotaUsed: {
      control: 'number',
      description: 'Current storage quota used in bytes',
    },
    maxQuota: {
      control: 'number',
      description: 'Maximum storage quota in bytes',
    },
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    isOpen: true,
    maxFiles: 10,
    maxFileSize: 50 * 1024 * 1024, // 50MB
    currentQuotaUsed: 1024 * 1024 * 1024, // 1GB
    maxQuota: 5 * 1024 * 1024 * 1024, // 5GB
  },
};

export const WithQuotaWarning: Story = {
  args: {
    isOpen: true,
    maxFiles: 10,
    maxFileSize: 50 * 1024 * 1024,
    currentQuotaUsed: 4.5 * 1024 * 1024 * 1024, // 4.5GB (close to limit)
    maxQuota: 5 * 1024 * 1024 * 1024, // 5GB
  },
};

export const WithStrictLimits: Story = {
  args: {
    isOpen: true,
    maxFiles: 3,
    maxFileSize: 10 * 1024 * 1024, // 10MB
    currentQuotaUsed: 0,
    maxQuota: 100 * 1024 * 1024, // 100MB
  },
};

export const Closed: Story = {
  args: {
    isOpen: false,
  },
};

// Mock interactions for different states
export const MockProcessingState: Story = {
  args: {
    isOpen: true,
    maxFiles: 10,
    maxFileSize: 50 * 1024 * 1024,
    currentQuotaUsed: 0,
    maxQuota: 5 * 1024 * 1024 * 1024,
  },
  render: (args) => {
    // Mock files that would be selected
    const mockFiles = [
      new File(['test content'], 'test.pdf', { type: 'application/pdf' }),
      new File(['image content'], 'test.jpg', { type: 'image/jpeg' }),
    ];

    return (
      <DocumentUploadWizard
        {...args}
        onComplete={(documentIds) => {
          console.log('Upload completed:', documentIds);
        }}
      />
    );
  },
};

// Playground story for interactive testing
export const Playground: Story = {
  args: {
    isOpen: true,
    maxFiles: 5,
    maxFileSize: 25 * 1024 * 1024, // 25MB
    currentQuotaUsed: 500 * 1024 * 1024, // 500MB
    maxQuota: 2 * 1024 * 1024 * 1024, // 2GB
  },
  parameters: {
    docs: {
      description: {
        story: 'Interactive playground for testing different configurations. Try dragging and dropping files, adjusting the limits, and testing the complete flow.',
      },
    },
  },
};