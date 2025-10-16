import type { Meta, StoryObj } from '@storybook/react';
import { MultimodalViewer } from './MultimodalViewer';

// Mock document data
const createMockDocument = (type: 'pdf' | 'txt' | 'jpg' | 'png' | 'mp3' | 'mp4', overrides = {}) => ({
  id: `doc-${Math.random().toString(36).substr(2, 9)}`,
  title: `Sample ${type.toUpperCase()} Document`,
  filename: `sample.${type}`,
  file_type: type as const,
  file_size: Math.floor(Math.random() * 10000000), // Random file size
  thumbnail_url: type === 'jpg' || type === 'png'
    ? `https://picsum.photos/800/600?random=${Math.random()}`
    : undefined,
  extracted_text_preview: type === 'txt'
    ? `This is a sample text document content.\n\nLorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.\n\nDuis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur.`
    : type === 'pdf'
    ? `Sample PDF document content with extracted text. This would typically include the OCR'd text from the PDF document pages.\n\nPage 1: Introduction\nThis document contains important information about the multimodal RAG system.`
    : type === 'mp3' || type === 'mp4'
    ? `This is a transcript of the audio/video content. The automatic speech recognition has processed the media file and extracted this text content for search and analysis purposes.\n\n[00:00:00] Welcome to this presentation about document processing.\n[00:00:15] Today we'll discuss the various file formats supported.`
    : 'Extracted content would appear here for this document type.',
  metadata: {
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    tags: ['sample', 'demo', type],
    custom_fields: {
      category: 'demo',
      priority: 'normal',
    },
  },
  processing_status: 'completed',
  processing_completed_at: new Date().toISOString(),
  ...overrides,
});

const meta: Meta<typeof MultimodalViewer> = {
  title: 'Components/Preview/MultimodalViewer',
  component: MultimodalViewer,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
A versatile document viewer that supports multiple file formats including PDF, text, images, audio, and video files with appropriate controls and features for each type.

Features:
- Support for PDF documents with page navigation
- Text document display with formatted content
- Image viewer with zoom and pan controls
- Audio player with waveform visualization and transcripts
- Video player with playback controls and transcripts
- Download and sharing capabilities
- Fullscreen mode
- Responsive design
- File metadata display
        `,
      },
    },
  },
  argTypes: {
    document: {
      control: 'object',
      description: 'Document object with metadata and content',
    },
    className: {
      control: 'text',
      description: 'Additional CSS classes',
    },
    showControls: {
      control: 'boolean',
      description: 'Show control buttons',
    },
    allowDownload: {
      control: 'boolean',
      description: 'Allow downloading the document',
    },
    allowFullscreen: {
      control: 'boolean',
      description: 'Allow fullscreen viewing',
    },
    maxHeight: {
      control: 'text',
      description: 'Maximum height for the viewer',
    },
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

export const PDFDocument: Story = {
  args: {
    document: createMockDocument('pdf'),
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: true,
    maxHeight: '600px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const TextDocument: Story = {
  args: {
    document: createMockDocument('txt'),
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: true,
    maxHeight: '600px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const ImageDocument: Story = {
  args: {
    document: createMockDocument('jpg'),
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: true,
    maxHeight: '600px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const PNGImage: Story = {
  args: {
    document: createMockDocument('png'),
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: true,
    maxHeight: '600px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const AudioDocument: Story = {
  args: {
    document: createMockDocument('mp3'),
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: true,
    maxHeight: '600px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const VideoDocument: Story = {
  args: {
    document: createMockDocument('mp4'),
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: true,
    maxHeight: '600px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const MinimalControls: Story = {
  args: {
    document: createMockDocument('pdf'),
    className: '',
    showControls: false,
    allowDownload: false,
    allowFullscreen: false,
    maxHeight: '500px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const Compact: Story = {
  args: {
    document: createMockDocument('jpg'),
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: false,
    maxHeight: '400px',
  },
  render: (args) => (
    <div className="p-4 bg-white">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const LargeDocument: Story = {
  args: {
    document: {
      ...createMockDocument('pdf', {
        title: 'Large Technical Documentation',
        file_size: 25000000, // 25MB
        metadata: {
          ...createMockDocument('pdf').metadata,
          page_count: 156,
          author: 'Technical Writer',
          department: 'Engineering',
        },
      }),
      extracted_text_preview: `This is a large technical document with multiple chapters.\n\nChapter 1: Introduction\nWelcome to the comprehensive technical documentation for our multimodal RAG system. This document covers all aspects of the system architecture, implementation details, and usage guidelines.\n\nChapter 2: Architecture Overview\nThe system consists of several key components working together to provide a seamless experience for processing and querying various types of documents.\n\n[Content continues for many pages...]`,
    },
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: true,
    maxHeight: '700px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const ErrorState: Story = {
  args: {
    document: {
      ...createMockDocument('pdf'),
      processing_status: 'failed',
      extracted_text_preview: undefined,
    },
    className: '',
    showControls: true,
    allowDownload: false,
    allowFullscreen: false,
    maxHeight: '600px',
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const DarkMode: Story = {
  args: {
    document: createMockDocument('pdf'),
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: true,
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
      <MultimodalViewer {...args} />
    </div>
  ),
};

export const Gallery: Story = {
  render: () => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Document Type Gallery</h2>
        <p className="text-gray-600">Examples of different document types supported by the MultimodalViewer</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MultimodalViewer
          document={createMockDocument('pdf', {
            title: 'Technical Specification',
            filename: 'spec-v2.1.pdf',
          })}
          maxHeight="500px"
        />

        <MultimodalViewer
          document={createMockDocument('jpg', {
            title: 'Architecture Diagram',
            filename: 'architecture-diagram.jpg',
          })}
          maxHeight="500px"
        />

        <MultimodalViewer
          document={createMockDocument('mp3', {
            title: 'Meeting Recording',
            filename: 'team-meeting-2024-01-15.mp3',
          })}
          maxHeight="500px"
        />

        <MultimodalViewer
          document={createMockDocument('txt', {
            title: 'Project Notes',
            filename: 'project-notes.txt',
          })}
          maxHeight="500px"
        />
      </div>
    </div>
  ),
};

export const Playground: Story = {
  args: {
    document: createMockDocument('pdf'),
    className: '',
    showControls: true,
    allowDownload: true,
    allowFullscreen: true,
    maxHeight: '600px',
  },
  parameters: {
    docs: {
      description: {
        story: 'Interactive playground for testing the MultimodalViewer. Try different document types and settings to see how the viewer adapts to various content formats.',
      },
    },
  },
  render: (args) => (
    <div className="p-6 bg-gray-50 min-h-screen">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Multimodal Viewer Playground</h2>
        <p className="text-gray-600">
          Test different document types and viewer configurations. The viewer supports PDF, text, images, audio, and video files with appropriate controls for each type.
        </p>
      </div>
      <MultimodalViewer {...args} />
    </div>
  ),
};