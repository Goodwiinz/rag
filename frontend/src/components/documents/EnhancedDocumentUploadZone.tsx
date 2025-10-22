/**
 * Enhanced Document Upload Zone
 * Advanced drag-and-drop upload component with real-time progress tracking,
 * quality assessment, security scanning, and knowledge graph integration
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  CloudArrowUpIcon,
  DocumentPlusIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ShieldCheckIcon,
  SparklesIcon,
  ChartBarIcon,
  ArrowPathIcon,
  EyeIcon,
  TrashIcon
} from '@heroicons/react/24/outline';
import { v4 as uuidv4 } from 'uuid';

import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';

import { enhancedDocumentService, DocumentUploadRequest, WebSocketProgressUpdate } from '@/services/enhancedDocumentService';

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
}

interface EnhancedDocumentUploadZoneProps {
  onUploadComplete?: (documentId: string, result: any) => void;
  onUploadError?: (error: string, file: UploadedFile) => void;
  maxFiles?: number;
  className?: string;
}

export const EnhancedDocumentUploadZone: React.FC<EnhancedDocumentUploadZoneProps> = ({
  onUploadComplete,
  onUploadError,
  maxFiles = 10,
  className
}) => {
  const { toast } = useToast();
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedTab, setSelectedTab] = useState('upload');
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

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (uploadedFiles.length + acceptedFiles.length > maxFiles) {
      toast({
        title: "Too many files",
        description: `Maximum ${maxFiles} files allowed per upload session`,
        variant: "destructive"
      });
      return;
    }

    const newFiles: UploadedFile[] = acceptedFiles.map(file => {
      const validation = enhancedDocumentService.validateFile(file);
      if (!validation.isValid) {
        toast({
          title: "Invalid file",
          description: validation.errors.join(', '),
          variant: "destructive"
        });
        return null;
      }

      return {
        id: uuidv4(),
        file,
        request: getDefaultRequest(file),
        status: 'pending',
        progress: 0,
        currentStep: 'Waiting to upload'
      };
    }).filter(Boolean) as UploadedFile[];

    setUploadedFiles(prev => [...prev, ...newFiles]);
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
      'video/quicktime': ['.mov']
    },
    maxSize: 50 * 1024 * 1024, // 50MB
    multiple: true,
    disabled: isUploading
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
    try {
      updateFileStatus(uploadedFile.id, {
        status: 'uploading',
        progress: 0,
        currentStep: 'Starting upload'
      });

      const abortController = new AbortController();
      abortControllers.current.set(uploadedFile.id, abortController);

      const { response, websocket } = await enhancedDocumentService.uploadDocument(
        uploadedFile.file,
        uploadedFile.request,
        handleProgressUpdate(uploadedFile.id)
      );

      updateFileStatus(uploadedFile.id, {
        status: 'processing',
        uploadId: response.upload_id,
        jobId: response.job_id,
        qualityScore: response.quality_score,
        securityScan: response.security_scan_result,
        websocket
      });

    } catch (error) {
      console.error('Upload failed:', error);
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
    setIsUploading(true);

    const pendingFiles = uploadedFiles.filter(f => f.status === 'pending');

    for (const file of pendingFiles) {
      await uploadFile(file);
      // Small delay between uploads to prevent overwhelming the server
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    setIsUploading(false);
  };

  const cancelUpload = async (fileId: string) => {
    const file = uploadedFiles.find(f => f.id === fileId);
    if (!file) return;

    // Cancel the upload via API
    if (file.uploadId) {
      try {
        await enhancedDocumentService.cancelUpload(file.uploadId);
      } catch (error) {
        console.error('Failed to cancel upload:', error);
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
      abortControllers.current.forEach(controller => controller.abort());
    };
  }, []);

  return (
    <div className={cn("w-full max-w-4xl mx-auto", className)}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CloudArrowUpIcon className="h-6 w-6" />
            Enhanced Document Upload
          </CardTitle>
          <CardDescription>
            Upload documents with automatic processing, entity extraction, and knowledge graph integration
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={selectedTab} onValueChange={setSelectedTab}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="upload">Upload Files</TabsTrigger>
              <TabsTrigger value="configure">Configure</TabsTrigger>
              <TabsTrigger value="progress">Progress</TabsTrigger>
            </TabsList>

            <TabsContent value="upload" className="space-y-4">
              {/* Dropzone */}
              <div
                {...getRootProps()}
                className={cn(
                  "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
                  isDragActive
                    ? "border-blue-400 bg-blue-50"
                    : "border-gray-300 hover:border-gray-400",
                  isUploading && "opacity-50 cursor-not-allowed"
                )}
              >
                <input {...getInputProps()} />
                <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
                <p className="mt-2 text-lg font-medium text-gray-900">
                  {isDragActive ? 'Drop files here' : 'Drag & drop files here'}
                </p>
                <p className="text-sm text-gray-500">
                  or click to select files
                </p>
                <p className="text-xs text-gray-400 mt-2">
                  Supports: PDF, TXT, DOCX, JPG, PNG, MP3, WAV, MP4, MOV (max 50MB each)
                </p>
              </div>

              {/* File List */}
              {uploadedFiles.length > 0 && (
                <div className="space-y-2">
                  <h3 className="font-medium text-sm text-gray-700">
                    Files to Upload ({uploadedFiles.length})
                  </h3>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {uploadedFiles.map((file) => (
                      <div
                        key={file.id}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                      >
                        <div className="flex items-center space-x-3">
                          <span className="text-xl">{getFileIcon(file.file)}</span>
                          <div>
                            <p className="font-medium text-sm">{file.file.name}</p>
                            <p className="text-xs text-gray-500">
                              {formatFileSize(file.file.size)} • {file.request.processing_priority} priority
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          {getStatusIcon(file.status)}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeFile(file.id)}
                            disabled={file.status === 'processing' || file.status === 'uploading'}
                          >
                            <XMarkIcon className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <Button
                    onClick={uploadAllFiles}
                    disabled={isUploading || uploadedFiles.every(f => f.status !== 'pending')}
                    className="w-full"
                  >
                    {isUploading ? (
                      <>
                        <ClockIcon className="mr-2 h-4 w-4 animate-spin" />
                        Uploading...
                      </>
                    ) : (
                      <>
                        <CloudArrowUpIcon className="mr-2 h-4 w-4" />
                        Upload All Files
                      </>
                    )}
                  </Button>
                </div>
              )}
            </TabsContent>

            <TabsContent value="configure" className="space-y-4">
              <div className="space-y-4 max-h-80 overflow-y-auto">
                {uploadedFiles.map((file) => (
                  <Card key={file.id}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm font-medium">
                          {file.file.name}
                        </CardTitle>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFile(file.id)}
                        >
                          <XMarkIcon className="h-4 w-4" />
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div>
                        <Label htmlFor={`title-${file.id}`}>Title</Label>
                        <Input
                          id={`title-${file.id}`}
                          value={file.request.title}
                          onChange={(e) => updateFileRequest(file.id, { title: e.target.value })}
                          placeholder="Document title"
                        />
                      </div>

                      <div>
                        <Label htmlFor={`description-${file.id}`}>Description</Label>
                        <Textarea
                          id={`description-${file.id}`}
                          value={file.request.description || ''}
                          onChange={(e) => updateFileRequest(file.id, { description: e.target.value })}
                          placeholder="Document description (optional)"
                          rows={2}
                        />
                      </div>

                      <div>
                        <Label htmlFor={`tags-${file.id}`}>Tags</Label>
                        <Input
                          id={`tags-${file.id}`}
                          value={file.request.tags?.join(', ') || ''}
                          onChange={(e) => updateFileRequest(file.id, {
                            tags: e.target.value.split(',').map(tag => tag.trim()).filter(Boolean)
                          })}
                          placeholder="tag1, tag2, tag3"
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label htmlFor={`priority-${file.id}`}>Priority</Label>
                          <Select
                            value={file.request.processing_priority}
                            onValueChange={(value: any) => updateFileRequest(file.id, { processing_priority: value })}
                          >
                            <SelectTrigger>
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

                        <div className="flex items-center space-x-2">
                          <Switch
                            id={`public-${file.id}`}
                            checked={file.request.is_public || false}
                            onCheckedChange={(checked) => updateFileRequest(file.id, { is_public: checked })}
                          />
                          <Label htmlFor={`public-${file.id}`}>Public</Label>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Switch
                          id={`quality-${file.id}`}
                          checked={file.request.enable_quality_check}
                          onCheckedChange={(checked) => updateFileRequest(file.id, { enable_quality_check: checked })}
                        />
                        <Label htmlFor={`quality-${file.id}`}>Enable quality assessment</Label>
                      </div>

                      <div className="text-xs text-gray-500">
                        Estimated processing time: {enhancedDocumentService.estimateProcessingTime(file.file)}s
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="progress" className="space-y-4">
              <div className="space-y-4">
                {uploadedFiles.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    No files uploaded yet
                  </div>
                ) : (
                  uploadedFiles.map((file) => (
                    <Card key={file.id}>
                      <CardContent className="pt-6">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center space-x-3">
                            {getStatusIcon(file.status)}
                            <div>
                              <p className="font-medium text-sm">{file.file.name}</p>
                              <p className="text-xs text-gray-500">{file.currentStep}</p>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <span className="text-sm font-medium">{Math.round(file.progress)}%</span>
                            {(file.status === 'uploading' || file.status === 'processing') && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => cancelUpload(file.id)}
                              >
                                <XMarkIcon className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </div>

                        <Progress value={file.progress} className="mb-2" />

                        {file.error && (
                          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                            {file.error}
                          </div>
                        )}

                        {file.qualityScore && (
                          <div className="mt-2 flex items-center space-x-2">
                            <SparklesIcon className="h-4 w-4 text-yellow-500" />
                            <span className="text-sm">Quality Score: {Math.round(file.qualityScore * 100)}%</span>
                          </div>
                        )}

                        {file.securityScan && (
                          <div className="mt-2 flex items-center space-x-2">
                            <ShieldCheckIcon className={cn(
                              "h-4 w-4",
                              file.securityScan.scan_status === 'passed' ? 'text-green-500' : 'text-red-500'
                            )} />
                            <span className="text-sm">Security: {file.securityScan.scan_status}</span>
                          </div>
                        )}

                        {file.result && (
                          <div className="mt-2 flex items-center space-x-2">
                            <CheckCircleIcon className="h-4 w-4 text-green-500" />
                            <span className="text-sm">Processing completed</span>
                            <Button variant="ghost" size="sm">
                              <EyeIcon className="h-4 w-4 mr-1" />
                              View Details
                            </Button>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};