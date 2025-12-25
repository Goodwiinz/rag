/**
 * Document Upload Page
 * Terminal Observatory themed document upload interface
 */

'use client';

import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { v4 as uuidv4 } from 'uuid';
import {
  CloudArrowUpIcon,
  DocumentPlusIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowUpTrayIcon,
  TrashIcon,
  Cog6ToothIcon,
  DocumentTextIcon,
  PhotoIcon,
  MusicalNoteIcon,
  VideoCameraIcon,
  SparklesIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline';

import { useToast } from '@/hooks/use-toast';
import { enhancedDocumentService, DocumentUploadRequest, WebSocketProgressUpdate } from '@/services/enhancedDocumentService';
import { mockDocumentService } from '@/services/mockDocumentService';
import { useAuthStore } from '@/stores/authStore';

// Terminal Observatory Theme Constants
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';
const CYAN = '#00d4ff';
const TERMINAL_BG = '#0d1117';

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
}

export default function DocumentUploadPage() {
  const { toast } = useToast();
  const { user, token, organization, isAuthenticated, isLoading: authLoading } = useAuthStore();

  const [mounted, setMounted] = useState(false);
  const [terminalText, setTerminalText] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Terminal typing effect
  useEffect(() => {
    if (!mounted) return;
    const fullText = 'DOCUMENT INGESTION TERMINAL';
    let index = 0;
    const interval = setInterval(() => {
      if (index <= fullText.length) {
        setTerminalText(fullText.slice(0, index));
        index++;
      } else {
        clearInterval(interval);
      }
    }, 40);
    return () => clearInterval(interval);
  }, [mounted]);

  const getDefaultRequest = (file: File): DocumentUploadRequest => ({
    title: file.name.replace(/\.[^/.]+$/, ''),
    description: '',
    tags: [],
    is_public: false,
    processing_priority: 'normal',
    enable_quality_check: true,
    custom_metadata: {}
  });

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
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

    if (uploadedFiles.length + acceptedFiles.length > 10) {
      toast({
        title: "Too many files",
        description: "Maximum 10 files allowed per upload session",
        variant: "destructive"
      });
      return;
    }

    const newFiles: UploadedFile[] = acceptedFiles.map(file => {
      let validation;
      try {
        validation = enhancedDocumentService.validateFile(file);
      } catch (error) {
        validation = mockDocumentService.validateFile(file);
      }

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
        status: 'pending' as const,
        progress: 0,
        currentStep: 'Ready for upload',
      };
    }).filter(Boolean) as UploadedFile[];

    setUploadedFiles(prev => [...prev, ...newFiles]);
  }, [uploadedFiles.length, toast]);

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
    },
    maxSize: 50 * 1024 * 1024,
    multiple: true,
    disabled: isUploading,
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
      toast({ title: "Upload completed", description: `${update.result.title} processed successfully` });
    }

    if (update.type === 'error') {
      updateFileStatus(fileId, {
        status: 'failed',
        error: update.error_message || 'Processing failed'
      });
      toast({
        title: "Upload failed",
        description: update.error_message || 'An error occurred',
        variant: "destructive"
      });
    }
  };

  const uploadFile = async (uploadedFile: UploadedFile) => {
    try {
      updateFileStatus(uploadedFile.id, {
        status: 'uploading',
        progress: 0,
        currentStep: 'Initializing upload'
      });

      let response, websocket;
      try {
        const result = await enhancedDocumentService.uploadDocument(
          uploadedFile.file,
          uploadedFile.request,
          handleProgressUpdate(uploadedFile.id)
        );
        response = result.response;
        websocket = result.websocket;
      } catch (error) {
        const result = await mockDocumentService.uploadDocument(
          uploadedFile.file,
          uploadedFile.request,
          handleProgressUpdate(uploadedFile.id)
        );
        response = result.response;
        websocket = result.websocket;
      }

      updateFileStatus(uploadedFile.id, {
        status: 'processing',
        uploadId: response.upload_id,
        jobId: response.job_id,
        qualityScore: response.quality_score,
        securityScan: response.security_scan_result,
        websocket
      });
    } catch (error) {
      updateFileStatus(uploadedFile.id, {
        status: 'failed',
        error: error instanceof Error ? error.message : 'Upload failed'
      });
      toast({
        title: "Upload failed",
        description: error instanceof Error ? error.message : 'An error occurred',
        variant: "destructive"
      });
    }
  };

  const uploadAllFiles = async () => {
    if (authLoading) {
      toast({ title: "Please wait", description: "Verifying authentication..." });
      return;
    }
    if (!isAuthenticated || !token || !organization) {
      toast({ title: "Authentication Required", description: "Please log in to upload documents.", variant: "destructive" });
      return;
    }

    setIsUploading(true);
    const pendingFiles = uploadedFiles.filter(f => f.status === 'pending');

    for (const file of pendingFiles) {
      await uploadFile(file);
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    setIsUploading(false);
  };

  const removeFile = (fileId: string) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const getFileIcon = (type: string) => {
    if (type.includes('pdf') || type.includes('text') || type.includes('document'))
      return <DocumentTextIcon className="w-5 h-5" />;
    if (type.includes('image')) return <PhotoIcon className="w-5 h-5" />;
    if (type.includes('audio')) return <MusicalNoteIcon className="w-5 h-5" />;
    if (type.includes('video')) return <VideoCameraIcon className="w-5 h-5" />;
    return <DocumentPlusIcon className="w-5 h-5" />;
  };

  const getStatusColor = (status: UploadedFile['status']) => {
    switch (status) {
      case 'completed': return PHOSPHOR_GREEN;
      case 'processing':
      case 'uploading': return CYAN;
      case 'failed': return '#ff4757';
      default: return '#6b7280';
    }
  };

  const fileTypes = [
    { ext: 'PDF', color: '#ff4757' },
    { ext: 'DOCX', color: '#3b82f6' },
    { ext: 'TXT', color: '#6b7280' },
    { ext: 'JPG', color: AMBER },
    { ext: 'PNG', color: PHOSPHOR_GREEN },
    { ext: 'MP3', color: '#a855f7' },
    { ext: 'MP4', color: CYAN },
  ];

  if (!mounted) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="text-gray-500 font-mono">Initializing terminal...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] relative overflow-hidden">
      {/* CRT Scanlines */}
      <div
        className="fixed inset-0 pointer-events-none z-50 opacity-[0.03]"
        style={{
          background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 255, 159, 0.03) 2px, rgba(0, 255, 159, 0.03) 4px)',
        }}
      />

      {/* Grid Background */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(${PHOSPHOR_GREEN} 1px, transparent 1px), linear-gradient(90deg, ${PHOSPHOR_GREEN} 1px, transparent 1px)`,
          backgroundSize: '50px 50px',
        }}
      />

      <div className="relative z-10 p-6 max-w-5xl mx-auto">
        {/* Terminal Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-10"
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <div
              className="w-12 h-12 rounded-lg flex items-center justify-center"
              style={{
                background: `linear-gradient(135deg, ${PHOSPHOR_GREEN}20, ${PHOSPHOR_GREEN}05)`,
                border: `1px solid ${PHOSPHOR_GREEN}30`
              }}
            >
              <ArrowUpTrayIcon className="w-6 h-6" style={{ color: PHOSPHOR_GREEN }} />
            </div>
            <h1
              className="text-3xl font-mono font-bold tracking-wider"
              style={{ color: PHOSPHOR_GREEN }}
            >
              {terminalText}<span className="animate-pulse">_</span>
            </h1>
          </div>
          <p className="text-gray-500 font-mono text-sm max-w-xl mx-auto">
            Upload documents for AI-powered processing, entity extraction, and knowledge graph integration.
          </p>
        </motion.div>

        {/* Terminal Window */}
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="rounded-xl overflow-hidden"
          style={{
            background: TERMINAL_BG,
            border: '1px solid #21262d',
            boxShadow: `0 0 60px ${PHOSPHOR_GREEN}08`
          }}
        >
          {/* Window Chrome */}
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{
              background: 'linear-gradient(180deg, #161b22 0%, #0d1117 100%)',
              borderBottom: '1px solid #21262d'
            }}
          >
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-[#ff5f57]" />
              <div className="w-3 h-3 rounded-full bg-[#febc2e]" />
              <div className="w-3 h-3 rounded-full bg-[#28c840]" />
            </div>
            <span className="text-gray-500 font-mono text-xs">upload_handler.exe</span>
            <div className="flex items-center gap-3 text-xs text-gray-500 font-mono">
              {isAuthenticated ? (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-green-500" />
                  AUTHENTICATED
                </span>
              ) : (
                <span className="flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500" />
                  NOT AUTHENTICATED
                </span>
              )}
            </div>
          </div>

          {/* Upload Zone */}
          <div className="p-6">
            <div
              {...getRootProps()}
              className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-300 ${
                isDragActive ? 'scale-[1.01]' : ''
              } ${isUploading ? 'opacity-50 cursor-not-allowed' : ''}`}
              style={{
                borderColor: isDragActive ? PHOSPHOR_GREEN : '#21262d',
                background: isDragActive ? `${PHOSPHOR_GREEN}05` : 'transparent',
              }}
            >
              <input {...getInputProps()} />

              <motion.div
                animate={{ y: isDragActive ? -5 : 0 }}
                className="space-y-4"
              >
                <div
                  className="mx-auto w-16 h-16 rounded-xl flex items-center justify-center"
                  style={{
                    background: `linear-gradient(135deg, ${PHOSPHOR_GREEN}15, transparent)`,
                    border: `1px solid ${PHOSPHOR_GREEN}30`
                  }}
                >
                  <CloudArrowUpIcon className="w-8 h-8" style={{ color: PHOSPHOR_GREEN }} />
                </div>

                <div>
                  <p className="text-lg font-mono" style={{ color: isDragActive ? PHOSPHOR_GREEN : '#e6edf3' }}>
                    {isDragActive ? '[ RELEASE TO UPLOAD ]' : 'Drop files here or click to browse'}
                  </p>
                  <p className="text-sm text-gray-500 font-mono mt-1">
                    Maximum file size: 50MB • Up to 10 files
                  </p>
                </div>

                {/* File Type Badges */}
                <div className="flex flex-wrap justify-center gap-2 mt-4">
                  {fileTypes.map((type) => (
                    <span
                      key={type.ext}
                      className="px-2 py-1 rounded text-xs font-mono"
                      style={{
                        background: `${type.color}15`,
                        color: type.color,
                        border: `1px solid ${type.color}30`
                      }}
                    >
                      {type.ext}
                    </span>
                  ))}
                </div>
              </motion.div>
            </div>

            {/* File List */}
            <AnimatePresence>
              {uploadedFiles.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-6 space-y-3"
                >
                  {/* Header */}
                  <div className="flex items-center justify-between px-2">
                    <span className="text-sm font-mono text-gray-400">
                      {uploadedFiles.length} file{uploadedFiles.length > 1 ? 's' : ''} queued
                    </span>
                    {uploadedFiles.some(f => f.status === 'pending') && (
                      <button
                        onClick={uploadAllFiles}
                        disabled={isUploading || !isAuthenticated}
                        className="flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-sm transition-all disabled:opacity-50"
                        style={{
                          background: `linear-gradient(135deg, ${PHOSPHOR_GREEN}20, ${PHOSPHOR_GREEN}10)`,
                          border: `1px solid ${PHOSPHOR_GREEN}50`,
                          color: PHOSPHOR_GREEN,
                        }}
                      >
                        {isUploading ? (
                          <>
                            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                            UPLOADING...
                          </>
                        ) : (
                          <>
                            <ArrowUpTrayIcon className="w-4 h-4" />
                            UPLOAD ALL
                          </>
                        )}
                      </button>
                    )}
                  </div>

                  {/* File Items */}
                  {uploadedFiles.map((file, index) => (
                    <motion.div
                      key={file.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 20 }}
                      transition={{ delay: index * 0.05 }}
                      className="rounded-lg p-4"
                      style={{
                        background: '#161b22',
                        border: `1px solid ${getStatusColor(file.status)}30`,
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <div
                            className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                            style={{
                              background: `${getStatusColor(file.status)}15`,
                              color: getStatusColor(file.status)
                            }}
                          >
                            {getFileIcon(file.file.type)}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-mono text-gray-200 truncate">
                              {file.file.name}
                            </p>
                            <div className="flex items-center gap-3 text-xs font-mono text-gray-500">
                              <span>{formatFileSize(file.file.size)}</span>
                              <span>•</span>
                              <span style={{ color: getStatusColor(file.status) }}>
                                {file.currentStep}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {file.status === 'completed' && (
                            <CheckCircleIcon className="w-5 h-5" style={{ color: PHOSPHOR_GREEN }} />
                          )}
                          {file.status === 'failed' && (
                            <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />
                          )}
                          {(file.status === 'uploading' || file.status === 'processing') && (
                            <div
                              className="w-5 h-5 border-2 border-t-transparent rounded-full animate-spin"
                              style={{ borderColor: `${CYAN} transparent ${CYAN} ${CYAN}` }}
                            />
                          )}
                          {(file.status === 'pending' || file.status === 'failed') && (
                            <button
                              onClick={() => removeFile(file.id)}
                              className="p-1 rounded hover:bg-white/10 transition-colors"
                            >
                              <TrashIcon className="w-4 h-4 text-gray-500 hover:text-red-400" />
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Progress Bar */}
                      {(file.status === 'uploading' || file.status === 'processing') && (
                        <div className="mt-3">
                          <div className="flex justify-between text-xs font-mono text-gray-500 mb-1">
                            <span>{file.currentStep}</span>
                            <span>{Math.round(file.progress)}%</span>
                          </div>
                          <div className="h-1 rounded-full bg-gray-800 overflow-hidden">
                            <motion.div
                              className="h-full rounded-full"
                              style={{ background: `linear-gradient(90deg, ${CYAN}, ${PHOSPHOR_GREEN})` }}
                              initial={{ width: 0 }}
                              animate={{ width: `${file.progress}%` }}
                              transition={{ duration: 0.3 }}
                            />
                          </div>
                        </div>
                      )}

                      {/* Success Info */}
                      {file.status === 'completed' && file.documentId && (
                        <div
                          className="mt-3 p-2 rounded text-xs font-mono"
                          style={{
                            background: `${PHOSPHOR_GREEN}10`,
                            border: `1px solid ${PHOSPHOR_GREEN}20`
                          }}
                        >
                          <span className="text-gray-400">Document ID:</span>{' '}
                          <span style={{ color: PHOSPHOR_GREEN }}>{file.documentId}</span>
                        </div>
                      )}

                      {/* Error Info */}
                      {file.status === 'failed' && file.error && (
                        <div className="mt-3 p-2 rounded text-xs font-mono bg-red-500/10 border border-red-500/20 text-red-400">
                          {file.error}
                        </div>
                      )}

                      {/* Quality Score */}
                      {file.qualityScore && (
                        <div className="mt-3 flex items-center gap-2 text-xs font-mono">
                          <SparklesIcon className="w-4 h-4" style={{ color: AMBER }} />
                          <span className="text-gray-400">Quality Score:</span>
                          <span style={{ color: AMBER }}>{Math.round(file.qualityScore * 100)}%</span>
                        </div>
                      )}

                      {/* Security Scan */}
                      {file.securityScan && (
                        <div className="mt-2 flex items-center gap-2 text-xs font-mono">
                          <ShieldCheckIcon className="w-4 h-4" style={{ color: file.securityScan.scan_status === 'passed' ? PHOSPHOR_GREEN : '#ff4757' }} />
                          <span className="text-gray-400">Security:</span>
                          <span style={{ color: file.securityScan.scan_status === 'passed' ? PHOSPHOR_GREEN : '#ff4757' }}>
                            {file.securityScan.scan_status.toUpperCase()}
                          </span>
                        </div>
                      )}
                    </motion.div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* Feature Cards */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8"
        >
          {[
            {
              icon: SparklesIcon,
              title: 'AI PROCESSING',
              desc: 'Automatic entity extraction and classification',
              color: PHOSPHOR_GREEN,
            },
            {
              icon: ShieldCheckIcon,
              title: 'SECURITY SCAN',
              desc: 'Files are scanned for malware and threats',
              color: AMBER,
            },
            {
              icon: DocumentPlusIcon,
              title: 'KNOWLEDGE GRAPH',
              desc: 'Documents integrated into semantic network',
              color: CYAN,
            },
          ].map((feature, index) => (
            <div
              key={feature.title}
              className="p-4 rounded-xl"
              style={{
                background: `linear-gradient(135deg, ${feature.color}08, transparent)`,
                border: `1px solid ${feature.color}20`,
              }}
            >
              <feature.icon className="w-6 h-6 mb-3" style={{ color: feature.color }} />
              <h3 className="font-mono text-sm font-medium text-gray-200 mb-1">
                {feature.title}
              </h3>
              <p className="text-xs text-gray-500 font-mono">
                {feature.desc}
              </p>
            </div>
          ))}
        </motion.div>
      </div>
    </div>
  );
}
