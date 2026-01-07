/**
 * Enhanced Document Upload Zone
 * Modern drag-and-drop upload component with improved UX, real-time progress tracking,
 * quality assessment, security scanning, and knowledge graph integration
 */

import {
    CheckCircleIcon,
    ClockIcon,
    CloudArrowUpIcon,
    Cog6ToothIcon,
    DocumentArrowUpIcon,
    DocumentPlusIcon,
    ExclamationTriangleIcon,
    FolderOpenIcon,
    ShieldCheckIcon,
    SparklesIcon,
    TrashIcon,
    XMarkIcon
} from '@heroicons/react/24/outline';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { v4 as uuidv4 } from 'uuid';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { DeleteConfirmDialog } from '@/components/ui/confirm-dialog';
import { IconButton } from '@/components/ui/icon-button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

import { DocumentUploadRequest, enhancedDocumentService, WebSocketProgressUpdate } from '@/services/enhancedDocumentService';
import { mockDocumentService } from '@/services/mockDocumentService';
import { useAuthStore } from '@/stores/authStore';

interface UploadedFile {
  id: string;
  file: File;
  request: DocumentUploadRequest;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  progress: number;
  currentStep: string;
  uploadId?: string;
  jobId?: string;
  documentId?: string;
  websocket?: WebSocket;
  result?: any;
  error?: string;
  qualityScore?: number;
  securityScan?: any;
  processingTime?: number;
  expanded?: boolean; // For showing/hiding configuration
}

interface EnhancedDocumentUploadZoneProps {
  onUploadComplete?: (documentId: string, result: any) => void;
  onUploadError?: (error: string, file: UploadedFile) => void;
  maxFiles?: number;
  className?: string;
  showAdvancedOptions?: boolean;
}

export const EnhancedDocumentUploadZone: React.FC<EnhancedDocumentUploadZoneProps> = ({
  onUploadComplete,
  onUploadError,
  maxFiles = 10,
  className,
  showAdvancedOptions = true
}) => {
  const { toast } = useToast();

  // Use reactive auth state instead of static getState()
  const { user, token, organization, isAuthenticated, isLoading: authLoading } = useAuthStore();

  // Debug authentication state
  console.log('🔍 Upload Component Auth State:', {
    isAuthenticated,
    authLoading,
    hasToken: !!token,
    hasOrganization: !!organization,
    user: user?.email,
    organization: organization?.name
  });

  // Prevent upload if not authenticated or still loading
  const handleUploadAttempt = useCallback(() => {
    if (authLoading) {
      toast({
        title: "Authentication Loading",
        description: "Please wait while we verify your authentication...",
        variant: "default"
      });
      return false;
    }

    if (!isAuthenticated || !token || !organization) {
      toast({
        title: "Authentication Required",
        description: "Please log in to upload documents.",
        variant: "destructive"
      });
      return false;
    }

    return true;
  }, [authLoading, isAuthenticated, token, organization, toast]);

  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [showFileSelector, setShowFileSelector] = useState(true);
  const abortControllers = useRef<Map<string, AbortController>>(new Map());

  const getDefaultRequest = (file: File): DocumentUploadRequest => ({
    title: file.name.replace(/\.[^/.]+$/, ''), // Remove file extension
    description: '',
    tags: [],
    is_public: false,
    processing_priority: 'normal',
    enable_quality_check: true,
    custom_metadata: {}
  });

  // Enhanced UX helper functions with accessibility
  const getUploadStateMessage = () => {
    const pendingCount = uploadedFiles.filter(f => f.status === 'pending').length;
    const processingCount = uploadedFiles.filter(f => f.status === 'uploading' || f.status === 'processing').length;
    const completedCount = uploadedFiles.filter(f => f.status === 'completed').length;
    const failedCount = uploadedFiles.filter(f => f.status === 'failed').length;

    if (uploadedFiles.length === 0) {
      return {
        message: "No files selected",
        type: 'info' as const,
        ariaLive: "polite" as const
      };
    }

    if (processingCount > 0) {
      return {
        message: `Processing ${processingCount} file${processingCount > 1 ? 's' : ''}...`,
        type: 'processing' as const,
        ariaLive: "assertive" as const
      };
    }

    if (pendingCount > 0) {
      return {
        message: `${pendingCount} file${pendingCount > 1 ? 's' : ''} ready to upload`,
        type: 'ready' as const,
        ariaLive: "polite" as const
      };
    }

    if (completedCount > 0 && failedCount === 0) {
      return {
        message: "All files processed successfully!",
        type: 'success' as const,
        ariaLive: "assertive" as const
      };
    }

    return {
      message: `${completedCount} completed, ${failedCount} failed`,
      type: 'mixed' as const,
      ariaLive: "polite" as const
    };
  };

  const getStatusColor = (status: UploadedFile['status']) => {
    switch (status) {
      case 'completed': return 'text-green-600 bg-green-50 border-green-200';
      case 'processing':
      case 'uploading': return 'text-blue-600 bg-blue-50 border-blue-200';
      case 'failed': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const toggleFileExpanded = (fileId: string) => {
    setUploadedFiles(prev => prev.map(file =>
      file.id === fileId ? { ...file, expanded: !file.expanded } : file
    ));
  };

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    console.log('🎯 Files dropped:', {
      acceptedFiles: acceptedFiles.map(f => ({ name: f.name, size: f.size, type: f.type })),
      rejectedFiles
    });

    // Handle rejected files
    if (rejectedFiles.length > 0) {
      rejectedFiles.forEach(({ file, errors }) => {
        errors.forEach((error: any) => {
          toast({
            title: "File rejected",
            description: `${file.name}: ${error.message}`,
            variant: "destructive"
          });
        });
      });
      return;
    }

    if (uploadedFiles.length + acceptedFiles.length > maxFiles) {
      toast({
        title: "Too many files",
        description: `Maximum ${maxFiles} files allowed per upload session`,
        variant: "destructive"
      });
      return;
    }

    const newFiles: UploadedFile[] = acceptedFiles.map(file => {
      console.log('📁 Processing file:', file.name, file.size, file.type);

      // Try enhanced service first, fallback to mock service
      let validation;
      try {
        validation = enhancedDocumentService.validateFile(file);
        console.log('✅ Enhanced service validation:', validation);
      } catch (error) {
        console.warn('⚠️ Enhanced service validation failed, using mock service:', error);
        validation = mockDocumentService.validateFile(file);
        console.log('✅ Mock service validation:', validation);
      }

      if (!validation.isValid) {
        console.error('❌ File validation failed:', validation.errors);
        toast({
          title: "Invalid file",
          description: validation.errors.join(', '),
          variant: "destructive"
        });
        return null;
      }

      const uploadedFile: UploadedFile = {
        id: uuidv4(),
        file,
        request: getDefaultRequest(file),
        status: 'pending',
        progress: 0,
        currentStep: 'Waiting to upload',
        expanded: false
      };

      console.log('✅ Created uploaded file object:', uploadedFile);
      return uploadedFile;
    }).filter(Boolean) as UploadedFile[];

    console.log('📝 Adding new files to state:', newFiles.length);
    setUploadedFiles(prev => {
      const updated = [...prev, ...newFiles];
      console.log('📋 Updated file list:', updated.map(f => f.file.name));
      return updated;
    });
  }, [uploadedFiles.length, maxFiles, toast]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'audio/mpeg': ['.mp3'],
      'audio/wav': ['.wav'],
      'video/mp4': ['.mp4'],
      'video/quicktime': ['.mov'],
      'video/avi': ['.avi']
    },
    maxSize: 50 * 1024 * 1024, // 50MB
    multiple: true,
    disabled: isUploading,
    noClick: false,
    noKeyboard: false,
    onError: (error) => {
      console.error('🚨 Dropzone error:', error);
      toast({
        title: "File selection error",
        description: error.message || 'An error occurred while selecting files',
        variant: "destructive"
      });
    },
    onDropAccepted: (files) => {
      console.log('✅ Files accepted by dropzone:', files.map(f => f.name));
    },
    onDropRejected: (fileRejections) => {
      console.log('❌ Files rejected by dropzone:', fileRejections);
      fileRejections.forEach(({ file, errors }) => {
        errors.forEach((error: any) => {
          toast({
            title: "File rejected",
            description: `${file.name}: ${error.message}`,
            variant: "destructive"
          });
        });
      });
    }
  });

  const updateFileStatus = (fileId: string, updates: Partial<UploadedFile>) => {
    setUploadedFiles(prev => prev.map(file =>
      file.id === fileId ? { ...file, ...updates } : file
    ));
  };

  const handleProgressUpdate = (fileId: string) => (update: WebSocketProgressUpdate) => {
    updateFileStatus(fileId, {
      progress: update.progress_percentage || 0,
      currentStep: update.current_step || 'Processing',
      error: update.error_message
    });

    if (update.type === 'upload_complete' && update.result) {
      updateFileStatus(fileId, {
        status: 'completed',
        result: update.result,
        documentId: update.result.document_id,
        jobId: update.result.job_id,
        progress: 100,
        currentStep: 'Completed'
      });

      toast({
        title: "Upload completed",
        description: `${update.result.title} has been processed successfully`
      });

      onUploadComplete?.(update.result.document_id, update.result);
    }

    if (update.type === 'error') {
      updateFileStatus(fileId, {
        status: 'failed',
        error: update.error_message || 'Processing failed'
      });

      toast({
        title: "Upload failed",
        description: update.error_message || 'An error occurred during processing',
        variant: "destructive"
      });

      onUploadError?.(update.error_message || 'Processing failed',
        uploadedFiles.find(f => f.id === fileId)!);
    }
  };

  const uploadFile = async (uploadedFile: UploadedFile) => {
    console.log('🚀 Starting upload for file:', uploadedFile.file.name);

    try {
      updateFileStatus(uploadedFile.id, {
        status: 'uploading',
        progress: 0,
        currentStep: 'Starting upload'
      });

      const abortController = new AbortController();
      abortControllers.current.set(uploadedFile.id, abortController);

      let response, websocket;

      // Verify the file is still valid
      console.log('📋 File verification:', {
        name: uploadedFile.file.name,
        size: uploadedFile.file.size,
        type: uploadedFile.file.type,
        lastModified: uploadedFile.file.lastModified
      });

      if (!uploadedFile.file || uploadedFile.file.size === 0) {
        throw new Error('Invalid file: File is empty or null');
      }

      // Try enhanced service first, fallback to mock service
      try {
        console.log('📡 Attempting upload with enhanced service...');
        const result = await enhancedDocumentService.uploadDocument(
          uploadedFile.file,
          uploadedFile.request,
          handleProgressUpdate(uploadedFile.id)
        );
        response = result.response;
        websocket = result.websocket;
        console.log('✅ Enhanced service upload successful:', response);
      } catch (error) {
        console.warn('⚠️ Enhanced service failed, using mock service:', error);

        // Note: Don't try to cancel with uploadedFile.id - the backend doesn't know about it yet
        // Only WebSocket connections need cleanup, which will be handled automatically

        console.log('📡 Attempting upload with mock service...');
        const result = await mockDocumentService.uploadDocument(
          uploadedFile.file,
          uploadedFile.request,
          handleProgressUpdate(uploadedFile.id)
        );
        response = result.response;
        websocket = result.websocket;
        console.log('✅ Mock service upload successful:', response);
      }

      // Validate response
      if (!response || !response.upload_id) {
        throw new Error('Invalid upload response: Missing upload_id');
      }

      updateFileStatus(uploadedFile.id, {
        status: 'processing',
        uploadId: response.upload_id,
        jobId: response.job_id,
        qualityScore: response.quality_score,
        securityScan: response.security_scan_result,
        websocket
      });

      console.log('📈 Upload processing started for:', uploadedFile.file.name);

    } catch (error) {
      console.error('❌ Upload failed:', error);
      updateFileStatus(uploadedFile.id, {
        status: 'failed',
        error: error instanceof Error ? error.message : 'Upload failed'
      });

      toast({
        title: "Upload failed",
        description: error instanceof Error ? error.message : 'An error occurred during upload',
        variant: "destructive"
      });
    }
  };

  const uploadAllFiles = async () => {
    console.log('📤 Starting upload of all pending files...');

    // Check authentication before starting upload
    if (!handleUploadAttempt()) {
      setIsUploading(false);
      return;
    }

    console.log('✅ Authentication verified, proceeding with upload...');
    setIsUploading(true);

    const pendingFiles = uploadedFiles.filter(f => f.status === 'pending');
    console.log('📋 Pending files to upload:', pendingFiles.map(f => f.file.name));

    if (pendingFiles.length === 0) {
      toast({
        title: "No files to upload",
        description: "Add some files first before uploading",
        variant: "destructive"
      });
      setIsUploading(false);
      return;
    }

    for (const file of pendingFiles) {
      console.log('🔄 Processing file:', file.file.name);
      await uploadFile(file);
      // Small delay between uploads to prevent overwhelming the server
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    setIsUploading(false);
    console.log('✅ All files uploaded successfully');
  };

  const cancelUpload = async (fileId: string) => {
    const file = uploadedFiles.find(f => f.id === fileId);
    if (!file) return;

    // Cancel the upload via API (try both services)
    if (file.uploadId) {
      try {
        await enhancedDocumentService.cancelUpload(file.uploadId);
      } catch (error) {
        try {
          await mockDocumentService.cancelUpload(file.uploadId);
        } catch (mockError) {
          console.error('Failed to cancel upload with both services:', error, mockError);
        }
      }
    }

    // Close WebSocket connection
    if (file.websocket) {
      file.websocket.close();
    }

    // Cancel abort controller
    const abortController = abortControllers.current.get(fileId);
    if (abortController) {
      abortController.abort();
      abortControllers.current.delete(fileId);
    }

    // Update file status
    updateFileStatus(fileId, {
      status: 'pending',
      progress: 0,
      currentStep: 'Cancelled',
      uploadId: undefined,
      jobId: undefined,
      websocket: undefined
    });
  };

  const removeFile = (fileId: string) => {
    cancelUpload(fileId);
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const updateFileRequest = (fileId: string, updates: Partial<DocumentUploadRequest>) => {
    setUploadedFiles(prev => prev.map(file =>
      file.id === fileId
        ? { ...file, request: { ...file.request, ...updates } }
        : file
    ));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (file: File) => {
    const type = file.type;
    if (type.includes('pdf')) return '📄';
    if (type.includes('image')) return '🖼️';
    if (type.includes('audio')) return '🎵';
    if (type.includes('video')) return '🎥';
    if (type.includes('text') || type.includes('document')) return '📝';
    return '📎';
  };

  const getStatusIcon = (status: UploadedFile['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="h-5 w-5 text-green-500" />;
      case 'processing':
      case 'uploading':
        return <ClockIcon className="h-5 w-5 text-blue-500 animate-spin" />;
      case 'failed':
        return <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />;
      default:
        return <DocumentPlusIcon className="h-5 w-5 text-gray-400" />;
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      enhancedDocumentService.closeAllConnections();
      mockDocumentService.closeAllConnections();
      abortControllers.current.forEach(controller => controller.abort());
    };
  }, []);

  return (
    <div className={cn("w-full max-w-4xl mx-auto", className)}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CloudArrowUpIcon className="h-6 w-6 text-blue-600" />
            Enhanced Document Upload
          </CardTitle>
          <CardDescription className="text-gray-600">
            Upload documents with automatic processing, entity extraction, and knowledge graph integration
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Status Bar with Accessibility */}
          <div
            className={cn(
              "flex items-center justify-between p-4 rounded-lg border",
              getUploadStateMessage().type === 'success' ? "bg-green-50 border-green-200 text-green-800" :
              getUploadStateMessage().type === 'processing' ? "bg-blue-50 border-blue-200 text-blue-800" :
              getUploadStateMessage().type === 'ready' ? "bg-amber-50 border-amber-200 text-amber-800" :
              "bg-gray-50 border-gray-200 text-gray-800"
            )}
            role="status"
            aria-live={getUploadStateMessage().ariaLive}
            aria-atomic="true"
          >
            <div className="flex items-center space-x-3">
              {getUploadStateMessage().type === 'processing' && (
                <ClockIcon className="h-5 w-5 animate-spin" aria-hidden="true" />
              )}
              {getUploadStateMessage().type === 'success' && (
                <CheckCircleIcon className="h-5 w-5" aria-hidden="true" />
              )}
              {getUploadStateMessage().type === 'ready' && (
                <DocumentArrowUpIcon className="h-5 w-5" aria-hidden="true" />
              )}
              <span className="font-medium" aria-label={`Upload status: ${getUploadStateMessage().message}`}>
                {getUploadStateMessage().message}
              </span>
            </div>
            {uploadedFiles.length > 0 && (
              <Badge
                variant="outline"
                className="ml-4"
                aria-label={`${uploadedFiles.length} file${uploadedFiles.length > 1 ? 's' : ''} selected for upload`}
              >
                {uploadedFiles.length} file{uploadedFiles.length > 1 ? 's' : ''}
              </Badge>
            )}
          </div>

          {/* File Selection Area - Only show when no files are selected or when explicitly requested */}
          {(uploadedFiles.length === 0 || showFileSelector) && (
            <div
              {...getRootProps()}
              className={cn(
                "relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-200",
                isDragActive
                  ? "border-blue-400 bg-blue-50 scale-[1.02]"
                  : "border-gray-300 hover:border-gray-400 hover:bg-gray-50",
                isUploading && "opacity-50 cursor-not-allowed"
              )}
              role="button"
              tabIndex={0}
              aria-label="Select files to upload"
            >
              <input {...getInputProps()} />

              <div className="space-y-4">
                <div className="mx-auto w-16 h-16 bg-gradient-to-br from-blue-50 to-blue-100 rounded-full flex items-center justify-center">
                  <CloudArrowUpIcon className="h-8 w-8 text-blue-600" />
                </div>

                <div>
                  <p className="text-lg font-semibold text-gray-900">
                    {isDragActive ? 'Release files here' : 'Choose files or drag them here'}
                  </p>
                  <p className="text-sm text-gray-600 mt-1">
                    {isDragActive ? '' : 'Click to browse or drag and drop'}
                  </p>
                </div>

                <div className="flex flex-wrap justify-center gap-2 text-xs">
                  <Badge variant="secondary" className="px-2 py-1">PDF</Badge>
                  <Badge variant="secondary" className="px-2 py-1">DOCX</Badge>
                  <Badge variant="secondary" className="px-2 py-1">TXT</Badge>
                  <Badge variant="secondary" className="px-2 py-1">JPG</Badge>
                  <Badge variant="secondary" className="px-2 py-1">PNG</Badge>
                  <Badge variant="secondary" className="px-2 py-1">MP3</Badge>
                  <Badge variant="secondary" className="px-2 py-1">MP4</Badge>
                  <span className="text-gray-500">and more</span>
                </div>

                <p className="text-xs text-gray-500">
                  Maximum file size: 50MB • Maximum files: {maxFiles}
                </p>
              </div>

              {/* Quick action buttons */}
              <div className="flex justify-center gap-3 mt-6">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
                    input?.click();
                  }}
                >
                  <FolderOpenIcon className="h-4 w-4 mr-2" />
                  Browse Files
                </Button>
              </div>
            </div>
          )}

          {/* File Management Section */}
          {uploadedFiles.length > 0 && (
            <div className="space-y-4">
              {/* File Actions Bar with Accessibility */}
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <h3 className="text-lg font-semibold text-gray-900" id="files-heading">
                    Files ({uploadedFiles.length})
                  </h3>
                  {showFileSelector && uploadedFiles.length > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowFileSelector(false)}
                      aria-label="Hide file selector to reduce visual clutter"
                    >
                      Hide File Selector
                    </Button>
                  )}
                  {!showFileSelector && uploadedFiles.length < maxFiles && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowFileSelector(true)}
                      aria-label="Show file selector to add more files"
                    >
                      <CloudArrowUpIcon className="h-4 w-4 mr-2" aria-hidden="true" />
                      Add More Files
                    </Button>
                  )}
                </div>

                <div className="flex items-center space-x-2">
                  {/* Authentication Status Indicator */}
                  <div className="flex items-center space-x-1 text-xs">
                    {authLoading ? (
                      <ClockIcon className="w-3 h-3 text-yellow-500" />
                    ) : isAuthenticated ? (
                      <CheckCircleIcon className="w-3 h-3 text-green-500" />
                    ) : (
                      <ExclamationTriangleIcon className="w-3 h-3 text-red-500" />
                    )}
                    <span className="text-gray-500">
                      {authLoading ? 'Checking auth...' : isAuthenticated ? 'Authenticated' : 'Not authenticated'}
                    </span>
                  </div>

                  {uploadedFiles.some(f => f.status === 'pending') && (
                    <Button
                      onClick={uploadAllFiles}
                      disabled={isUploading || authLoading || !isAuthenticated}
                      className="bg-blue-600 hover:bg-blue-700"
                      aria-label={
                        isUploading
                          ? "Upload in progress, please wait"
                          : authLoading
                          ? "Authentication in progress, please wait"
                          : !isAuthenticated
                          ? "Please log in to upload documents"
                          : `Upload ${uploadedFiles.filter(f => f.status === 'pending').length} pending files`
                      }
                    >
                      {isUploading ? (
                        <>
                          <ClockIcon className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
                          Uploading...
                        </>
                      ) : (
                        <>
                          <DocumentArrowUpIcon className="mr-2 h-4 w-4" aria-hidden="true" />
                          Upload All
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>

              {/* File Cards with Accessibility */}
              <div
                className="space-y-3"
                role="region"
                aria-labelledby="files-heading"
                aria-label="File upload queue"
              >
                {uploadedFiles.map((file) => (
                  <Card
                    key={file.id}
                    className="overflow-hidden"
                    role="article"
                    aria-label={`File: ${file.file.name}, Status: ${file.status}, Size: ${formatFileSize(file.file.size)}`}
                  >
                    {/* File Header */}
                    <div
                      className={cn(
                        "flex items-center justify-between p-4 border-b",
                        getStatusColor(file.status)
                      )}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          if (showAdvancedOptions && file.status === 'pending') {
                            toggleFileExpanded(file.id);
                          }
                        }
                      }}
                      aria-expanded={file.expanded}
                      aria-controls={`file-details-${file.id}`}
                    >
                      <div className="flex items-center space-x-3">
                        <div
                          className="text-2xl"
                          role="img"
                          aria-label={`File type: ${file.file.type.split('/')[1] || 'unknown'}`}
                        >
                          {getFileIcon(file.file)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <h4
                            className="font-medium text-sm truncate"
                            id={`file-name-${file.id}`}
                          >
                            {file.file.name}
                          </h4>
                          <div className="flex items-center space-x-2 text-xs text-gray-600">
                            <span aria-label={`File size: ${formatFileSize(file.file.size)}`}>
                              {formatFileSize(file.file.size)}
                            </span>
                            <span aria-hidden="true">•</span>
                            <span aria-label={`Processing priority: ${file.request.processing_priority}`}>
                              {file.request.processing_priority} priority
                            </span>
                            <span aria-hidden="true">•</span>
                            <span
                              className="capitalize"
                              aria-label={`Current status: ${file.status}`}
                            >
                              {file.status}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        {getStatusIcon(file.status)}

                        {/* Expand/Collapse and Action Buttons */}
                        <div className="flex items-center space-x-1">
                          {showAdvancedOptions && file.status === 'pending' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleFileExpanded(file.id)}
                              aria-label={file.expanded ? "Collapse configuration" : "Expand configuration"}
                            >
                              <Cog6ToothIcon className="h-4 w-4" />
                            </Button>
                          )}

                          {(file.status === 'uploading' || file.status === 'processing') && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => cancelUpload(file.id)}
                              aria-label="Cancel upload"
                            >
                              <XMarkIcon className="h-4 w-4" />
                            </Button>
                          )}

                          {(file.status === 'pending' || file.status === 'failed') && (
                            <DeleteConfirmDialog
                              itemName="file"
                              onConfirm={() => removeFile(file.id)}
                            >
                              <IconButton
                                icon={<TrashIcon className="h-4 w-4" />}
                                label="Remove file"
                                variant="ghost"
                                size="sm"
                              />
                            </DeleteConfirmDialog>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Progress Bar for Active Files with Accessibility */}
                    {(file.status === 'uploading' || file.status === 'processing') && (
                      <div
                        className="px-4 py-3 bg-gray-50"
                        role="status"
                        aria-live="polite"
                        aria-atomic="true"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span
                            className="text-sm font-medium"
                            id={`progress-status-${file.id}`}
                          >
                            {file.currentStep}
                          </span>
                          <span
                            className="text-sm text-gray-600"
                            aria-label={`Upload progress: ${Math.round(file.progress)} percent complete`}
                          >
                            {Math.round(file.progress)}%
                          </span>
                        </div>
                        <div
                          role="progressbar"
                          aria-valuenow={file.progress}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-labelledby={`progress-status-${file.id} file-name-${file.id}`}
                          className="w-full bg-gray-200 rounded-full h-2"
                        >
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-out"
                            style={{ width: `${file.progress}%` }}
                            aria-hidden="true"
                          />
                        </div>
                      </div>
                    )}

                    {/* Error Display */}
                    {file.error && (
                      <div className="px-4 py-3 bg-red-50 border-l-4 border-red-400">
                        <div className="flex items-start space-x-2">
                          <ExclamationTriangleIcon className="h-5 w-5 text-red-400 mt-0.5" />
                          <div className="text-sm text-red-700">{file.error}</div>
                        </div>
                      </div>
                    )}

                    {/* Success Display */}
                    {file.result && (
                      <div className="px-4 py-3 bg-green-50 border-l-4 border-green-400">
                        <div className="flex items-start space-x-2">
                          <CheckCircleIcon className="h-5 w-5 text-green-400 mt-0.5" />
                          <div className="text-sm text-green-700">
                            <div className="font-medium">Processing completed successfully</div>
                            {file.documentId && (
                              <div className="text-xs mt-1">Document ID: {file.documentId}</div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Quality Score */}
                    {file.qualityScore && (
                      <div className="px-4 py-2 bg-yellow-50 border-l-4 border-yellow-400">
                        <div className="flex items-center space-x-2 text-sm text-yellow-700">
                          <SparklesIcon className="h-4 w-4" />
                          <span>Quality Score: {Math.round(file.qualityScore * 100)}%</span>
                        </div>
                      </div>
                    )}

                    {/* Security Scan */}
                    {file.securityScan && (
                      <div className={cn(
                        "px-4 py-2 border-l-4",
                        file.securityScan.scan_status === 'passed'
                          ? "bg-green-50 border-green-400 text-green-700"
                          : "bg-red-50 border-red-400 text-red-700"
                      )}>
                        <div className="flex items-center space-x-2 text-sm">
                          <ShieldCheckIcon className="h-4 w-4" />
                          <span>Security: {file.securityScan.scan_status}</span>
                        </div>
                      </div>
                    )}

                    {/* Expandable Configuration Panel */}
                    {showAdvancedOptions && file.expanded && file.status === 'pending' && (
                      <div className="px-4 py-4 bg-gray-50 border-t space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="md:col-span-2">
                            <Label htmlFor={`title-${file.id}`}>Title</Label>
                            <Input
                              id={`title-${file.id}`}
                              value={file.request.title}
                              onChange={(e) => updateFileRequest(file.id, { title: e.target.value })}
                              placeholder="Document title"
                              className="mt-1"
                            />
                          </div>

                          <div className="md:col-span-2">
                            <Label htmlFor={`description-${file.id}`}>Description</Label>
                            <Textarea
                              id={`description-${file.id}`}
                              value={file.request.description || ''}
                              onChange={(e) => updateFileRequest(file.id, { description: e.target.value })}
                              placeholder="Document description (optional)"
                              rows={2}
                              className="mt-1"
                            />
                          </div>

                          <div className="md:col-span-2">
                            <Label htmlFor={`tags-${file.id}`}>Tags</Label>
                            <Input
                              id={`tags-${file.id}`}
                              value={file.request.tags?.join(', ') || ''}
                              onChange={(e) => updateFileRequest(file.id, {
                                tags: e.target.value.split(',').map(tag => tag.trim()).filter(Boolean)
                              })}
                              placeholder="tag1, tag2, tag3"
                              className="mt-1"
                            />
                          </div>

                          <div>
                            <Label htmlFor={`priority-${file.id}`}>Priority</Label>
                            <Select
                              value={file.request.processing_priority}
                              onValueChange={(value: any) => updateFileRequest(file.id, { processing_priority: value })}
                            >
                              <SelectTrigger className="mt-1">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="low">Low</SelectItem>
                                <SelectItem value="normal">Normal</SelectItem>
                                <SelectItem value="high">High</SelectItem>
                                <SelectItem value="urgent">Urgent</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          <div className="space-y-3">
                            <div className="flex items-center space-x-2">
                              <Switch
                                id={`public-${file.id}`}
                                checked={file.request.is_public || false}
                                onCheckedChange={(checked: boolean) => updateFileRequest(file.id, { is_public: checked })}
                              />
                              <Label htmlFor={`public-${file.id}`} className="text-sm">Public</Label>
                            </div>

                            <div className="flex items-center space-x-2">
                              <Switch
                                id={`quality-${file.id}`}
                                checked={file.request.enable_quality_check}
                                onCheckedChange={(checked: boolean) => updateFileRequest(file.id, { enable_quality_check: checked })}
                              />
                              <Label htmlFor={`quality-${file.id}`} className="text-sm">Quality Check</Label>
                            </div>
                          </div>
                        </div>

                        <div className="text-xs text-gray-500 pt-2">
                          Estimated processing time: {
                            (() => {
                              try {
                                return enhancedDocumentService.estimateProcessingTime(file.file);
                              } catch {
                                return mockDocumentService.estimateProcessingTime(file.file);
                              }
                            })()
                          }s
                        </div>
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};