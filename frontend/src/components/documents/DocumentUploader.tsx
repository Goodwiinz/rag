import React, { useState, useCallback, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import { PaperClipIcon, XMarkIcon, CloudArrowUpIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { validateFileBatch, ValidationResult, FileValidationError } from '@/utils/fileValidation';
import { UPLOAD_LIMITS } from '@/types';

interface FileWithPreview extends File {
  preview?: string;
  id: string;
}

interface DocumentUploaderProps {
  onFilesSelected: (files: File[]) => void;
  onFilesRemoved: (fileIds: string[]) => void;
  onValidationErrors?: (errors: FileValidationError[]) => void;
  currentQuotaUsed?: number; // in bytes
  maxQuota?: number; // in bytes
  maxFiles?: number;
  maxSize?: number; // in bytes
  acceptedTypes?: string[];
  className?: string;
}

const DEFAULT_ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'text/plain': ['.txt'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'audio/mpeg': ['.mp3'],
  'video/mp4': ['.mp4'],
};

export const DocumentUploader: React.FC<DocumentUploaderProps> = ({
  onFilesSelected,
  onFilesRemoved,
  onValidationErrors,
  currentQuotaUsed = 0,
  maxQuota = 5 * 1024 * 1024 * 1024, // 5GB
  maxFiles = UPLOAD_LIMITS.MAX_FILES_PER_UPLOAD,
  maxSize = UPLOAD_LIMITS.MAX_FILE_SIZE_MB * 1024 * 1024, // 50MB
  acceptedTypes = Object.keys(DEFAULT_ACCEPTED_TYPES),
  className,
}) => {
  const [selectedFiles, setSelectedFiles] = useState<FileWithPreview[]>([]);
  const [validationErrors, setValidationErrors] = useState<FileValidationError[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    // Clear previous validation errors
    setValidationErrors([]);

    // Validate all files (accepted and rejected)
    const allFiles = [...acceptedFiles, ...rejectedFiles.map(r => r.file)];
    const validation: ValidationResult = validateFileBatch(
      allFiles,
      selectedFiles.length,
      currentQuotaUsed,
      {
        maxFileSize: maxSize,
        maxFiles,
        allowedTypes: acceptedTypes,
        maxQuota,
      }
    );

    // Handle validation errors
    if (validation.errors.length > 0) {
      setValidationErrors(validation.errors);
      onValidationErrors?.(validation.errors);
      console.error('File validation errors:', validation.errors);
    }

    // Only proceed with valid files
    const validFiles = acceptedFiles.filter(file => {
      const fileValidation = validation.errors.find(error =>
        error.details?.fileName === file.name
      );
      return !fileValidation;
    });

    // Process valid files
    const filesWithPreview: FileWithPreview[] = validFiles.map(file => ({
      ...file,
      id: Math.random().toString(36).substr(2, 9),
      preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
    }));

    const newFiles = [...selectedFiles, ...filesWithPreview].slice(0, maxFiles);
    setSelectedFiles(newFiles);

    if (filesWithPreview.length > 0) {
      onFilesSelected(filesWithPreview);
    }

    // Handle rejected files from react-dropzone
    if (rejectedFiles.length > 0) {
      rejectedFiles.forEach(({ file, errors }) => {
        console.error(`Rejected file: ${file.name}`, errors);
      });
    }
  }, [selectedFiles, maxFiles, currentQuotaUsed, maxSize, acceptedTypes, maxQuota, onFilesSelected, onValidationErrors]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: DEFAULT_ACCEPTED_TYPES,
    maxFiles,
    maxSize,
    multiple: true,
  });

  const removeFile = (fileId: string) => {
    const newFiles = selectedFiles.filter(file => file.id !== fileId);
    setSelectedFiles(newFiles);
    onFilesRemoved([fileId]);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (fileType: string) => {
    if (fileType === 'application/pdf') return '📄';
    if (fileType === 'text/plain') return '📝';
    if (fileType.startsWith('image/')) return '🖼️';
    if (fileType.startsWith('audio/')) return '🎵';
    if (fileType.startsWith('video/')) return '🎥';
    return '📎';
  };

  const clearValidationErrors = () => {
    setValidationErrors([]);
  };

  const getErrorMessage = (error: FileValidationError): string => {
    switch (error.code) {
      case 'FILE_TOO_LARGE':
        return `${error.details?.fileName || 'File'} is too large (${formatFileSize(error.details?.actualSize || 0)} > ${formatFileSize(error.details?.maxSize || 0)})`;
      case 'UNSUPPORTED_TYPE':
        return `${error.details?.fileName || 'File'} type not supported (${error.details?.fileType || 'unknown'})`;
      case 'TOO_MANY_FILES':
        return `Too many files (${error.details?.currentCount || 0} + ${error.details?.newFilesCount || 0} > ${error.details?.maxFiles || 0})`;
      case 'QUOTA_EXCEEDED':
        return `Storage quota exceeded (${formatFileSize(error.details?.currentQuotaUsed || 0)} + ${formatFileSize(error.details?.newFilesSize || 0)} > ${formatFileSize(error.details?.maxQuota || 0)})`;
      case 'INVALID_NAME':
        return `${error.message} ${error.details?.fileName ? `(${error.details.fileName})` : ''}`;
      default:
        return error.message;
    }
  };

  return (
    <div className={cn("w-full max-w-4xl mx-auto", className)}>
      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
          <div className="flex items-start space-x-3">
            <ExclamationTriangleIcon className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-medium text-destructive">
                Upload Validation Errors
              </h4>
              <ul className="mt-2 text-sm text-destructive/80 space-y-1">
                {validationErrors.map((error, index) => (
                  <li key={index} className="flex items-start space-x-2">
                    <span className="text-destructive/60 mt-1">•</span>
                    <span>{getErrorMessage(error)}</span>
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={clearValidationErrors}
                className="mt-3 text-sm text-destructive/70 hover:text-destructive transition-colors"
              >
                Dismiss errors
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={cn(
          "relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
          "hover:border-primary hover:bg-primary/5",
          "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
          isDragActive && "border-primary bg-primary/10",
          dragActive && "border-primary bg-primary/20"
        )}
        onDragEnter={() => setDragActive(true)}
        onDragLeave={() => setDragActive(false)}
      >
        <input {...getInputProps()} />

        <div className="flex flex-col items-center space-y-4">
          <div className="p-4 bg-primary/10 rounded-full">
            <CloudArrowUpIcon className="h-8 w-8 text-primary" />
          </div>

          <div>
            <p className="text-lg font-medium text-foreground">
              {isDragActive
                ? 'Drop files here...'
                : 'Drag & drop files here, or click to select'
              }
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              Maximum {maxFiles} files, up to {formatFileSize(maxSize)} each
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Supported formats: PDF, TXT, JPG, PNG, MP3, MP4
            </p>
          </div>

          <button
            type="button"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-primary-foreground bg-primary hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
          >
            <PaperClipIcon className="h-4 w-4 mr-2" />
            Browse Files
          </button>
        </div>
      </div>

      {/* Selected Files List */}
      {selectedFiles.length > 0 && (
        <div className="mt-6">
          <h3 className="text-lg font-medium text-foreground mb-4">
            Selected Files ({selectedFiles.length})
          </h3>

          <div className="space-y-2">
            {selectedFiles.map((file) => (
              <div
                key={file.id}
                className="flex items-center justify-between p-4 bg-card border rounded-lg hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  {file.preview ? (
                    <img
                      src={file.preview}
                      alt={file.name}
                      className="h-10 w-10 object-cover rounded"
                      onLoad={() => { URL.revokeObjectURL(file.preview!); }}
                    />
                  ) : (
                    <div className="h-10 w-10 bg-muted rounded flex items-center justify-center text-lg">
                      {getFileIcon(file.type)}
                    </div>
                  )}

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">
                      {file.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(file.size)} • {file.type || 'Unknown type'}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => removeFile(file.id)}
                  className="ml-3 p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-full transition-colors"
                  aria-label={`Remove ${file.name}`}
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end space-x-3 mt-6">
            <button
              type="button"
              onClick={() => {
                setSelectedFiles([]);
                onFilesRemoved(selectedFiles.map(f => f.id));
              }}
              className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Clear All
            </button>

            <button
              type="button"
              disabled={selectedFiles.length === 0}
              className="px-6 py-2 text-sm font-medium text-primary-foreground bg-primary hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
              onClick={() => {
                // This will be handled by the parent component
                console.log('Uploading files:', selectedFiles);
              }}
            >
              Upload {selectedFiles.length} {selectedFiles.length === 1 ? 'File' : 'Files'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentUploader;