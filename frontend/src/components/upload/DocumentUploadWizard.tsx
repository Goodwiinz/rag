import React, { useState, useCallback, useRef, useEffect } from 'react';
import {
  CloudArrowUpIcon,
  DocumentIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XMarkIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  EyeIcon,
  ClockIcon,
  DocumentTextIcon,
  PhotoIcon,
  MusicalNoteIcon,
  VideoCameraIcon,
} from '@heroicons/react/24/outline';
import { useDropzone } from 'react-dropzone';
import { cn } from '@/lib/utils';
import { useDocumentUpload } from '@/hooks/upload/useDocumentUpload';
import { FileValidationError, validateFileBatch } from '@/utils/fileValidation';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

export interface DocumentUploadWizardProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete?: (documentIds: string[]) => void;
  maxFiles?: number;
  maxFileSize?: number;
  currentQuotaUsed?: number;
  maxQuota?: number;
}

type WizardStep = 'upload' | 'review' | 'processing' | 'complete';

interface FileWithPreview extends File {
  preview?: string;
  id: string;
}

export const DocumentUploadWizard: React.FC<DocumentUploadWizardProps> = ({
  isOpen,
  onClose,
  onComplete,
  maxFiles = 10,
  maxFileSize = 50 * 1024 * 1024, // 50MB
  currentQuotaUsed = 0,
  maxQuota = 5 * 1024 * 1024 * 1024, // 5GB
}) => {
  const [currentStep, setCurrentStep] = useState<WizardStep>('upload');
  const [selectedFiles, setSelectedFiles] = useState<FileWithPreview[]>([]);
  const [validationErrors, setValidationErrors] = useState<FileValidationError[]>([]);
  const [showPreview, setShowPreview] = useState<string | null>(null);
  const [isClosing, setIsClosing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    addToQueue,
    removeFromQueue,
    retryUpload,
    cancelAllUploads,
    queueItems,
    stats,
    isUploading,
    hasActiveUploads,
    allCompleted,
    hasErrors,
    overallProgress,
    uploadSpeed,
    estimatedTimeRemaining,
    formatFileSize,
    formatTime,
    getStatusText,
    getFileIcon,
  } = useDocumentUpload({
    maxFiles,
    maxFileSize,
    currentQuotaUsed,
    maxQuota,
    autoCleanup: false,
  });

  const acceptedTypes = {
    'application/pdf': ['.pdf'],
    'text/plain': ['.txt'],
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'audio/mpeg': ['.mp3'],
    'audio/wav': ['.wav'],
    'video/mp4': ['.mp4'],
    'video/quicktime': ['.mov'],
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
      // Clear previous validation errors
      setValidationErrors([]);

      // Create files with preview
      const filesWithPreview: FileWithPreview[] = acceptedFiles.map(file => ({
        ...file,
        id: Math.random().toString(36).substr(2, 9),
        preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
      }));

      // Validate files
      const validation = validateFileBatch(
        [...acceptedFiles, ...rejectedFiles.map(r => r.file)],
        selectedFiles.length,
        currentQuotaUsed,
        {
          maxFileSize,
          maxFiles,
          allowedTypes: Object.keys(acceptedTypes),
          maxQuota,
        }
      );

      if (validation.errors.length > 0) {
        setValidationErrors(validation.errors);
      }

      // Only add valid files
      const validFiles = filesWithPreview.filter(file => {
        const fileValidation = validation.errors.find(error =>
          error.details?.fileName === file.name
        );
        return !fileValidation;
      });

      setSelectedFiles(prev => [...prev, ...validFiles].slice(0, maxFiles));
    }, [selectedFiles, currentQuotaUsed, maxFileSize, maxFiles, maxQuota]),
    accept: acceptedTypes,
    maxFiles: maxFiles - selectedFiles.length,
    maxSize: maxFileSize,
    multiple: true,
  });

  const handleNext = useCallback(() => {
    switch (currentStep) {
      case 'upload':
        if (selectedFiles.length > 0) {
          setCurrentStep('review');
        }
        break;
      case 'review':
        setCurrentStep('processing');
        handleStartUpload();
        break;
      case 'processing':
        if (allCompleted) {
          setCurrentStep('complete');
        }
        break;
      case 'complete':
        handleClose();
        break;
    }
  }, [currentStep, selectedFiles, allCompleted]);

  const handlePrevious = useCallback(() => {
    switch (currentStep) {
      case 'review':
        setCurrentStep('upload');
        break;
      case 'processing':
        if (!hasActiveUploads) {
          setCurrentStep('review');
        }
        break;
    }
  }, [currentStep, hasActiveUploads]);

  const handleStartUpload = useCallback(() => {
    const result = addToQueue(selectedFiles);
    if (result.errors.length > 0) {
      setValidationErrors(result.errors);
    }
  }, [selectedFiles, addToQueue]);

  const handleClose = useCallback(() => {
    if (hasActiveUploads) {
      if (!confirm('Uploads are still in progress. Are you sure you want to close?')) {
        return;
      }
    }

    setIsClosing(true);

    // Cleanup
    selectedFiles.forEach(file => {
      if (file.preview) {
        URL.revokeObjectURL(file.preview);
      }
    });

    setSelectedFiles([]);
    setValidationErrors([]);
    setCurrentStep('upload');
    setShowPreview(null);
    setIsClosing(false);

    // Cancel uploads if still active
    if (hasActiveUploads) {
      cancelAllUploads();
    }

    onClose();

    // Call completion callback
    if (onComplete && allCompleted) {
      const completedDocumentIds = queueItems
        .filter(item => item.status === 'completed' && item.documentId)
        .map(item => item.documentId!);
      if (completedDocumentIds.length > 0) {
        onComplete(completedDocumentIds);
      }
    }
  }, [hasActiveUploads, selectedFiles, onClose, onComplete, allCompleted, queueItems, cancelAllUploads]);

  const removeFile = useCallback((fileId: string) => {
    setSelectedFiles(prev => prev.filter(file => file.id !== fileId));
    removeFromQueue(fileId);
  }, [removeFromQueue]);

  const retryFile = useCallback((fileId: string) => {
    retryUpload(fileId);
  }, [retryUpload]);

  const getStepTitle = useCallback((): string => {
    switch (currentStep) {
      case 'upload':
        return 'Select Files to Upload';
      case 'review':
        return 'Review Files';
      case 'processing':
        return 'Processing Files';
      case 'complete':
        return 'Upload Complete';
      default:
        return '';
    }
  }, [currentStep]);

  const getStepDescription = useCallback((): string => {
    switch (currentStep) {
      case 'upload':
        return 'Drag and drop files or click to browse';
      case 'review':
        return `Review ${selectedFiles.length} file(s) before uploading`;
      case 'processing':
        return 'Your files are being processed and will be available shortly';
      case 'complete':
        return `${stats.completedFiles} of ${stats.totalFiles} files uploaded successfully`;
      default:
        return '';
    }
  }, [currentStep, selectedFiles.length, stats]);

  const canGoNext = useCallback((): boolean => {
    switch (currentStep) {
      case 'upload':
        return selectedFiles.length > 0 && validationErrors.length === 0;
      case 'review':
        return true;
      case 'processing':
        return allCompleted;
      case 'complete':
        return true;
      default:
        return false;
    }
  }, [currentStep, selectedFiles, validationErrors, allCompleted]);

  const canGoPrevious = useCallback((): boolean => {
    switch (currentStep) {
      case 'upload':
        return false;
      case 'review':
        return true;
      case 'processing':
        return !hasActiveUploads;
      case 'complete':
        return false;
      default:
        return false;
    }
  }, [currentStep, hasActiveUploads]);

  // Cleanup previews on unmount
  useEffect(() => {
    return () => {
      selectedFiles.forEach(file => {
        if (file.preview) {
          URL.revokeObjectURL(file.preview);
        }
      });
    };
  }, [selectedFiles]);

  if (!isOpen) return null;

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold">
            {getStepTitle()}
          </DialogTitle>
          <p className="text-sm text-muted-foreground mt-1">
            {getStepDescription()}
          </p>
        </DialogHeader>

        {/* Progress Steps */}
        <div className="flex items-center justify-center space-x-2 py-4">
          {(['upload', 'review', 'processing', 'complete'] as WizardStep[]).map((step, index) => (
            <React.Fragment key={step}>
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium",
                  currentStep === step
                    ? "bg-primary text-primary-foreground"
                    : currentStepIndex(step) < currentStepIndex(currentStep)
                    ? "bg-green-500 text-white"
                    : "bg-muted text-muted-foreground"
                )}
              >
                {currentStepIndex(step) < currentStepIndex(currentStep) ? (
                  <CheckCircleIcon className="w-4 h-4" />
                ) : (
                  index + 1
                )}
              </div>
              {index < 3 && (
                <div
                  className={cn(
                    "w-12 h-0.5",
                    currentStepIndex(step) < currentStepIndex(currentStep)
                      ? "bg-green-500"
                      : "bg-muted"
                  )}
                />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Step Content */}
        <div className="flex-1 overflow-y-auto">
          {currentStep === 'upload' && (
            <div className="space-y-6">
              {/* Validation Errors */}
              {validationErrors.length > 0 && (
                <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
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
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setValidationErrors([])}
                        className="mt-3 text-destructive/70 hover:text-destructive"
                      >
                        Dismiss errors
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Drop Zone */}
              <div
                {...getRootProps()}
                className={cn(
                  "relative border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors",
                  "hover:border-primary hover:bg-primary/5",
                  "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
                  isDragActive && "border-primary bg-primary/10"
                )}
              >
                <input {...getInputProps()} />

                <div className="flex flex-col items-center space-y-4">
                  <div className="p-6 bg-primary/10 rounded-full">
                    <CloudArrowUpIcon className="h-12 w-12 text-primary" />
                  </div>

                  <div>
                    <p className="text-lg font-medium text-foreground">
                      {isDragActive
                        ? 'Drop files here...'
                        : 'Drag & drop files here, or click to select'
                      }
                    </p>
                    <p className="text-sm text-muted-foreground mt-2">
                      Maximum {maxFiles} files, up to {formatFileSize(maxFileSize)} each
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Supported formats: PDF, TXT, JPG, PNG, MP3, WAV, MP4, MOV
                    </p>
                  </div>

                  <Button
                    type="button"
                    variant="outline"
                    onClick={(e) => {
                      e.stopPropagation();
                      fileInputRef.current?.click();
                    }}
                  >
                    <DocumentIcon className="h-4 w-4 mr-2" />
                    Browse Files
                  </Button>
                </div>
              </div>

              {/* Selected Files */}
              {selectedFiles.length > 0 && (
                <div>
                  <h3 className="text-lg font-medium text-foreground mb-4">
                    Selected Files ({selectedFiles.length})
                  </h3>

                  <div className="space-y-2 max-h-60 overflow-y-auto">
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
                              className="h-10 w-10 object-cover rounded cursor-pointer"
                              onClick={() => setShowPreview(file.preview!)}
                            />
                          ) : (
                            <div className="h-10 w-10 bg-muted rounded flex items-center justify-center text-lg">
                              {getFileIcon(file)}
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

                        <div className="flex items-center space-x-2">
                          {file.preview && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setShowPreview(file.preview!)}
                            >
                              <EyeIcon className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeFile(file.id)}
                            className="text-muted-foreground hover:text-destructive"
                          >
                            <XMarkIcon className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {currentStep === 'review' && (
            <div className="space-y-6">
              <div className="grid gap-4">
                {selectedFiles.map((file) => (
                  <div
                    key={file.id}
                    className="flex items-center justify-between p-4 bg-card border rounded-lg"
                  >
                    <div className="flex items-center space-x-3 flex-1 min-w-0">
                      {file.preview ? (
                        <img
                          src={file.preview}
                          alt={file.name}
                          className="h-12 w-12 object-cover rounded cursor-pointer"
                          onClick={() => setShowPreview(file.preview!)}
                        />
                      ) : (
                        <div className="h-12 w-12 bg-muted rounded flex items-center justify-center text-xl">
                          {getFileIcon(file)}
                        </div>
                      )}

                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-foreground truncate">
                          {file.name}
                        </p>
                        <div className="flex items-center space-x-2 mt-1">
                          <Badge variant="secondary" className="text-xs">
                            {getFileTypeCategory(file)}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {formatFileSize(file.size)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      {file.preview && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setShowPreview(file.preview!)}
                        >
                          <EyeIcon className="h-4 w-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeFile(file.id)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <XMarkIcon className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Upload Summary */}
              <div className="p-4 bg-muted/50 rounded-lg">
                <h4 className="font-medium text-foreground mb-2">Upload Summary</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Total Files:</span>
                    <span className="ml-2 font-medium">{selectedFiles.length}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Total Size:</span>
                    <span className="ml-2 font-medium">
                      {formatFileSize(selectedFiles.reduce((sum, file) => sum + file.size, 0))}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {currentStep === 'processing' && (
            <div className="space-y-6">
              {/* Overall Progress */}
              <div className="p-6 bg-card border rounded-lg">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-foreground">
                    Overall Progress
                  </h3>
                  <span className="text-sm text-muted-foreground">
                    {overallProgress}% Complete
                  </span>
                </div>

                <div className="w-full bg-secondary rounded-full h-3 mb-4">
                  <div
                    className="bg-primary h-3 rounded-full transition-all duration-300"
                    style={{ width: `${overallProgress}%` }}
                  />
                </div>

                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div className="text-center">
                    <div className="text-lg font-medium text-green-600">
                      {stats.completedFiles}
                    </div>
                    <div className="text-muted-foreground">Completed</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-medium text-blue-600">
                      {stats.processingFiles}
                    </div>
                    <div className="text-muted-foreground">Processing</div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-medium text-red-600">
                      {stats.failedFiles}
                    </div>
                    <div className="text-muted-foreground">Failed</div>
                  </div>
                </div>
              </div>

              {/* Individual File Progress */}
              <div className="space-y-3 max-h-80 overflow-y-auto">
                {queueItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-4 bg-card border rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2 flex-1 min-w-0">
                        <div className="text-lg">
                          {getFileIcon(item.file)}
                        </div>
                        <span className="text-sm font-medium text-foreground truncate">
                          {item.file.name}
                        </span>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Badge
                          variant={
                            item.status === 'completed' ? 'default' :
                            item.status === 'error' ? 'destructive' :
                            item.status === 'processing' ? 'secondary' :
                            'outline'
                          }
                          className="text-xs"
                        >
                          {getStatusText(item.status)}
                        </Badge>

                        {item.status === 'error' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => retryFile(item.id)}
                          >
                            Retry
                          </Button>
                        )}
                      </div>
                    </div>

                    {item.status !== 'completed' && item.status !== 'error' && (
                      <div className="w-full bg-secondary rounded-full h-2">
                        <div
                          className="bg-primary h-2 rounded-full transition-all duration-300"
                          style={{ width: `${item.progress}%` }}
                        />
                      </div>
                    )}

                    {item.error && (
                      <p className="text-xs text-destructive mt-2">
                        {item.error}
                      </p>
                    )}
                  </div>
                ))}
              </div>

              {/* Upload Stats */}
              {isUploading && (
                <div className="flex items-center justify-center space-x-4 text-sm text-muted-foreground">
                  <div className="flex items-center space-x-1">
                    <ClockIcon className="h-4 w-4" />
                    <span>{estimatedTimeRemaining}</span>
                  </div>
                  <div className="flex items-center space-x-1">
                    <span>{uploadSpeed}</span>
                  </div>
                </div>
              )}
            </div>
          )}

          {currentStep === 'complete' && (
            <div className="space-y-6 text-center">
              <div className="p-8">
                <CheckCircleIcon className="h-16 w-16 text-green-500 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-foreground mb-2">
                  Upload Complete!
                </h3>
                <p className="text-muted-foreground">
                  {stats.completedFiles} of {stats.totalFiles} files have been successfully uploaded and processed.
                </p>

                {hasErrors && (
                  <div className="mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
                    <p className="text-sm text-destructive">
                      {stats.failedFiles} file(s) failed to process. You can retry them from the document library.
                    </p>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4 max-w-md mx-auto">
                <div className="p-4 bg-card border rounded-lg">
                  <div className="text-2xl font-bold text-green-600">
                    {stats.completedFiles}
                  </div>
                  <div className="text-sm text-muted-foreground">Successful</div>
                </div>
                <div className="p-4 bg-card border rounded-lg">
                  <div className="text-2xl font-bold text-red-600">
                    {stats.failedFiles}
                  </div>
                  <div className="text-sm text-muted-foreground">Failed</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-4 border-t">
          <div className="flex items-center space-x-2">
            {canGoPrevious() && (
              <Button
                variant="outline"
                onClick={handlePrevious}
                disabled={hasActiveUploads}
              >
                <ArrowLeftIcon className="h-4 w-4 mr-2" />
                Previous
              </Button>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={isClosing}
            >
              {currentStep === 'processing' && hasActiveUploads ? 'Close Anyway' : 'Cancel'}
            </Button>

            {canGoNext() && (
              <Button onClick={handleNext} disabled={isClosing}>
                {currentStep === 'complete' ? 'Done' : (
                  <>
                    Next
                    <ArrowRightIcon className="h-4 w-4 ml-2" />
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>

      {/* Image Preview Dialog */}
      {showPreview && (
        <Dialog open={!!showPreview} onOpenChange={() => setShowPreview(null)}>
          <DialogContent className="max-w-4xl">
            <DialogHeader>
              <DialogTitle>Image Preview</DialogTitle>
            </DialogHeader>
            <img
              src={showPreview}
              alt="Preview"
              className="w-full h-auto max-h-[70vh] object-contain rounded"
            />
          </DialogContent>
        </Dialog>
      )}
    </Dialog>
  );
};

// Helper functions
const currentStepIndex = (step: WizardStep): number => {
  switch (step) {
    case 'upload': return 0;
    case 'review': return 1;
    case 'processing': return 2;
    case 'complete': return 3;
    default: return 0;
  }
};

const getErrorMessage = (error: FileValidationError): string => {
  switch (error.code) {
    case 'FILE_TOO_LARGE':
      return `${error.details?.fileName || 'File'} is too large`;
    case 'UNSUPPORTED_TYPE':
      return `${error.details?.fileName || 'File'} type not supported`;
    case 'TOO_MANY_FILES':
      return 'Too many files selected';
    case 'QUOTA_EXCEEDED':
      return 'Storage quota exceeded';
    case 'INVALID_NAME':
      return 'Invalid file name';
    default:
      return error.message;
  }
};

const getFileTypeCategory = (file: File): string => {
  if (file.type === 'application/pdf') return 'PDF';
  if (file.type === 'text/plain') return 'Text';
  if (file.type.startsWith('image/')) return 'Image';
  if (file.type.startsWith('audio/')) return 'Audio';
  if (file.type.startsWith('video/')) return 'Video';
  return 'Other';
};

export default DocumentUploadWizard;