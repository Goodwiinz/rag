/**
 * Unit tests for DocumentUploader component
 */

import React from 'react';
import { fireEvent, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import DocumentUploader from '../DocumentUploader';
import { render, createMockFile, createMockFileList, mockFetchResponse, createMockApiResponse } from '../../__tests__/testUtils';

// Mock the API calls
const mockUploadFile = jest.fn();
const mockValidateFile = jest.fn();
const mockGetUploadProgress = jest.fn();

jest.mock('../../services/apiService', () => ({
  uploadFile: mockUploadFile,
  validateFile: mockValidateFile,
  getUploadProgress: mockGetUploadProgress
}));

// Mock react-hot-toast
jest.mock('react-hot-toast', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    loading: jest.fn(),
    dismiss: jest.fn()
  },
  Toaster: () => null
}));

describe('DocumentUploader', () => {
  const defaultProps = {
    onUploadComplete: jest.fn(),
    onUploadError: jest.fn(),
    maxFileSize: 50 * 1024 * 1024, // 50MB
    acceptedFileTypes: ['.pdf', '.txt', '.docx', '.jpg', '.png', '.mp3', '.mp4'],
    maxFiles: 10
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Setup default successful API responses
    mockValidateFile.mockResolvedValue(createMockApiResponse({ valid: true, message: 'File is valid' }));
    mockUploadFile.mockResolvedValue(createMockApiResponse({ id: 'file-1', status: 'uploaded' }));
    mockGetUploadProgress.mockResolvedValue(createMockApiResponse({ progress: 100, status: 'completed' }));
  });

  it('renders without crashing', () => {
    render(<DocumentUploader {...defaultProps} />);

    expect(screen.getByText(/drag and drop/i)).toBeInTheDocument();
    expect(screen.getByText(/browse files/i)).toBeInTheDocument();
    expect(screen.getByText(/pdf, txt, docx, jpg, png, mp3, mp4/i)).toBeInTheDocument();
  });

  it('shows correct file size limit', () => {
    render(<DocumentUploader {...defaultProps} />);

    expect(screen.getByText(/max file size: 50mb/i)).toBeInTheDocument();
  });

  it('shows correct max files limit', () => {
    render(<DocumentUploader {...defaultProps} />);

    expect(screen.getByText(/max files: 10/i)).toBeInTheDocument();
  });

  it('handles file drag and drop', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} />);

    const dropzone = screen.getByTestId('dropzone');
    const file = createMockFile('test.pdf', 'application/pdf');

    await act(async () => {
      fireEvent.dragEnter(dropzone);
      fireEvent.dragOver(dropzone);
      fireEvent.drop(dropzone, {
        dataTransfer: createMockFileList([file])
      });
    });

    await waitFor(() => {
      expect(mockValidateFile).toHaveBeenCalledWith(file);
    });
  });

  it('handles file selection via click', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} />);

    const fileInput = screen.getByLabelText(/upload files/i);
    const file = createMockFile('test.pdf', 'application/pdf');

    // Mock the file input change event
    Object.defineProperty(fileInput, 'files', {
      value: createMockFileList([file]),
      writable: false
    });

    await act(async () => {
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(mockValidateFile).toHaveBeenCalledWith(file);
    });
  });

  it('validates file type', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} />);

    const fileInput = screen.getByLabelText(/upload files/i);
    const invalidFile = createMockFile('test.exe', 'application/x-executable');

    Object.defineProperty(fileInput, 'files', {
      value: createMockFileList([invalidFile]),
      writable: false
    });

    await act(async () => {
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(screen.getByText(/invalid file type/i)).toBeInTheDocument();
    });
  });

  it('validates file size', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} maxFileSize={1024} />); // 1KB limit

    const fileInput = screen.getByLabelText(/upload files/i);
    const largeFile = createMockFile('test.pdf', 'application/pdf', 2048); // 2KB

    Object.defineProperty(fileInput, 'files', {
      value: createMockFileList([largeFile]),
      writable: false
    });

    await act(async () => {
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(screen.getByText(/file too large/i)).toBeInTheDocument();
    });
  });

  it('validates max files limit', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} maxFiles={1} />);

    const file1 = createMockFile('test1.pdf', 'application/pdf');
    const file2 = createMockFile('test2.pdf', 'application/pdf');

    // First file should be accepted
    mockValidateFile.mockResolvedValueOnce(createMockApiResponse({ valid: true, message: 'File is valid' }));
    mockValidateFile.mockResolvedValueOnce(createMockApiResponse({ valid: true, message: 'File is valid' }));

    await act(async () => {
      const fileInput = screen.getByLabelText(/upload files/i);
      Object.defineProperty(fileInput, 'files', {
        value: createMockFileList([file1, file2]),
        writable: false
      });
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(screen.getByText(/maximum number of files exceeded/i)).toBeInTheDocument();
    });
  });

  it('shows upload progress', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} />);

    const file = createMockFile('test.pdf', 'application/pdf');

    // Mock validation success
    mockValidateFile.mockResolvedValue(createMockApiResponse({ valid: true, message: 'File is valid' }));

    // Mock upload progress updates
    mockUploadFile.mockImplementation(() => {
      return new Promise((resolve) => {
        setTimeout(() => resolve(createMockApiResponse({ id: 'file-1', status: 'uploading' })), 100);
      });
    });

    await act(async () => {
      const fileInput = screen.getByLabelText(/upload files/i);
      Object.defineProperty(fileInput, 'files', {
        value: createMockFileList([file]),
        writable: false
      });
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(screen.getByText(/uploading.../i)).toBeInTheDocument();
    });
  });

  it('shows success message on successful upload', async () => {
    const user = userEvent.setup();
    const onUploadComplete = jest.fn();
    render(<DocumentUploader {...defaultProps} onUploadComplete={onUploadComplete} />);

    const file = createMockFile('test.pdf', 'application/pdf');

    mockValidateFile.mockResolvedValue(createMockApiResponse({ valid: true, message: 'File is valid' }));
    mockUploadFile.mockResolvedValue(createMockApiResponse({ id: 'file-1', status: 'uploaded' }));

    await act(async () => {
      const fileInput = screen.getByLabelText(/upload files/i);
      Object.defineProperty(fileInput, 'files', {
        value: createMockFileList([file]),
        writable: false
      });
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(onUploadComplete).toHaveBeenCalledWith([{ id: 'file-1', status: 'uploaded', name: 'test.pdf' }]);
    });
  });

  it('shows error message on upload failure', async () => {
    const user = userEvent.setup();
    const onUploadError = jest.fn();
    render(<DocumentUploader {...defaultProps} onUploadError={onUploadError} />);

    const file = createMockFile('test.pdf', 'application/pdf');

    mockValidateFile.mockResolvedValue(createMockApiResponse({ valid: true, message: 'File is valid' }));
    mockUploadFile.mockRejectedValue(new Error('Upload failed'));

    await act(async () => {
      const fileInput = screen.getByLabelText(/upload files/i);
      Object.defineProperty(fileInput, 'files', {
        value: createMockFileList([file]),
        writable: false
      });
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(onUploadError).toHaveBeenCalled();
    });
  });

  it('allows removing files before upload', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} />);

    const file = createMockFile('test.pdf', 'application/pdf');

    mockValidateFile.mockResolvedValue(createMockApiResponse({ valid: true, message: 'File is valid' }));

    await act(async () => {
      const fileInput = screen.getByLabelText(/upload files/i);
      Object.defineProperty(fileInput, 'files', {
        value: createMockFileList([file]),
        writable: false
      });
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    await act(async () => {
      const removeButton = screen.getByLabelText(/remove test.pdf/i);
      user.click(removeButton);
    });

    await waitFor(() => {
      expect(screen.queryByText('test.pdf')).not.toBeInTheDocument();
    });
  });

  it('shows visual feedback during drag operations', async () => {
    render(<DocumentUploader {...defaultProps} />);

    const dropzone = screen.getByTestId('dropzone');

    await act(async () => {
      fireEvent.dragEnter(dropzone);
    });

    expect(dropzone).toHaveClass('border-blue-500', 'bg-blue-50');

    await act(async () => {
      fireEvent.dragLeave(dropzone);
    });

    expect(dropzone).not.toHaveClass('border-blue-500', 'bg-blue-50');
  });

  it('prevents default drag behavior', async () => {
    render(<DocumentUploader {...defaultProps} />);

    const dropzone = screen.getByTestId('dropzone');
    const preventDefault = jest.fn();

    await act(async () => {
      fireEvent.dragOver(dropzone, { preventDefault });
      fireEvent.drop(dropzone, { preventDefault });
    });

    expect(preventDefault).toHaveBeenCalledTimes(2);
  });

  it('handles keyboard navigation for file input', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} />);

    const dropzone = screen.getByTestId('dropzone');

    await act(async () => {
      dropzone.focus();
      await user.keyboard('{Enter}');
    });

    // Should trigger file input click
    expect(screen.getByLabelText(/upload files/i)).toHaveFocus();
  });

  it('shows loading state during validation', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} />);

    const file = createMockFile('test.pdf', 'application/pdf');

    // Mock slow validation
    mockValidateFile.mockImplementation(() => new Promise(resolve =>
      setTimeout(() => resolve(createMockApiResponse({ valid: true, message: 'File is valid' })), 1000)
    ));

    await act(async () => {
      const fileInput = screen.getByLabelText(/upload files/i);
      Object.defineProperty(fileInput, 'files', {
        value: createMockFileList([file]),
        writable: false
      });
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(screen.getByText(/validating.../i)).toBeInTheDocument();
    });
  });

  it('supports batch upload of multiple files', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} />);

    const files = [
      createMockFile('test1.pdf', 'application/pdf'),
      createMockFile('test2.txt', 'text/plain'),
      createMockFile('test3.jpg', 'image/jpeg')
    ];

    mockValidateFile.mockResolvedValue(createMockApiResponse({ valid: true, message: 'File is valid' }));
    mockUploadFile.mockResolvedValue(createMockApiResponse({ id: 'file-1', status: 'uploaded' }));

    await act(async () => {
      const fileInput = screen.getByLabelText(/upload files/i);
      Object.defineProperty(fileInput, 'files', {
        value: createMockFileList(files),
        writable: false
      });
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(mockValidateFile).toHaveBeenCalledTimes(3);
    });
  });

  it('filters out invalid files from batch upload', async () => {
    const user = userEvent.setup();
    render(<DocumentUploader {...defaultProps} />);

    const validFile = createMockFile('test.pdf', 'application/pdf');
    const invalidFile = createMockFile('test.exe', 'application/x-executable');

    mockValidateFile
      .mockResolvedValueOnce(createMockApiResponse({ valid: true, message: 'File is valid' }))
      .mockResolvedValueOnce(createMockApiResponse({ valid: false, message: 'Invalid file type' }));

    await act(async () => {
      const fileInput = screen.getByLabelText(/upload files/i);
      Object.defineProperty(fileInput, 'files', {
        value: createMockFileList([validFile, invalidFile]),
        writable: false
      });
      fireEvent.change(fileInput);
    });

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
      expect(screen.queryByText('test.exe')).not.toBeInTheDocument();
    });
  });
});