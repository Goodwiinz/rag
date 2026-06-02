/**
 * Document Upload Page
 * Document upload interface
 */

'use client';

import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { v4 as uuidv4 } from 'uuid';
import {
  Terminal,
  Activity,
  ArrowRight,
  ChevronLeft,
  Database,
  Cpu,
  Network,
  Loader2,
  Upload,
  UploadCloud,
  FilePlus,
  FileText,
  Image as ImageIcon,
  Music,
  Video,
  Trash2,
  CheckCircle,
  AlertTriangle,
  Sparkles,
  ShieldCheck,
} from 'lucide-react';
import Link from 'next/link';

import { useToast } from '@/hooks/use-toast';
import {
  enhancedDocumentService,
  DocumentUploadRequest,
  WebSocketProgressUpdate,
} from '@/services/enhancedDocumentService';
import { api } from '@/services/api-client';
import { useAuthStore } from '@/stores/authStore';
import { cn } from '@/lib/utils';

async function computeSHA256(file: File): Promise<string> {
  const buffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

interface UploadedFile {
  id: string;
  file: File;
  request: DocumentUploadRequest;
  status:
    | 'pending'
    | 'uploading'
    | 'queued'
    | 'processing'
    | 'completed'
    | 'failed';
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
  const {
    user,
    organization,
    isAuthenticated,
    isLoading: authLoading,
  } = useAuthStore();

  const [mounted, setMounted] = useState(false);
  const [terminalText, setTerminalText] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Terminal typing effect
  useEffect(() => {
    // Effect removed for cleaner UI
  }, []);

  const getDefaultRequest = (file: File): DocumentUploadRequest => ({
    title: file.name.replace(/\.[^/.]+$/, ''),
    description: '',
    tags: [],
    is_public: false,
    processing_priority: 'normal',
    enable_quality_check: true,
    custom_metadata: {},
  });

  const onDrop = useCallback(
    async (acceptedFiles: File[], rejectedFiles: any[]) => {
      if (rejectedFiles.length > 0) {
        rejectedFiles.forEach(({ file, errors }) => {
          errors.forEach((error: any) => {
            toast({
              title: 'Upload error',
              description: `${file.name}: ${error.message}`,
              variant: 'destructive',
            });
          });
        });
        return;
      }

      if (uploadedFiles.length + acceptedFiles.length > 10) {
        toast({
          title: 'Too many files',
          description: 'Maximum 10 files allowed per upload session',
          variant: 'destructive',
        });
        return;
      }

      const newFiles: UploadedFile[] = [];

      for (const file of acceptedFiles) {
        const validation = enhancedDocumentService.validateFile(file);

        if (!validation.isValid) {
          toast({
            title: 'Unsupported file',
            description: validation.errors.join(', '),
            variant: 'destructive',
          });
          continue;
        }

        // Pre-upload duplicate check via content hash
        try {
          const sha256 = await computeSHA256(file);
          const response: any = await api.post('/documents/check-duplicate', {
            sha256,
          });
          const data = response?.data ?? response;
          if (data?.exists) {
            const existing = data.document;
            toast({
              title: 'Duplicate file',
              description: `"${file.name}" matches existing document "${existing?.title || existing?.filename}" — skipped.`,
              variant: 'destructive',
            });
            continue;
          }
        } catch {
          // If check fails (e.g. not authenticated), allow upload — server-side check is the fallback
        }

        newFiles.push({
          id: uuidv4(),
          file,
          request: getDefaultRequest(file),
          status: 'pending' as const,
          progress: 0,
          currentStep: 'Ready to upload',
        });
      }

      if (newFiles.length > 0) {
        setUploadedFiles((prev) => [...prev, ...newFiles]);
      }
    },
    [uploadedFiles.length, toast]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        ['.docx'],
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
    setUploadedFiles((prev) =>
      prev.map((file) => (file.id === fileId ? { ...file, ...updates } : file))
    );
  };

  const handleProgressUpdate =
    (fileId: string) => (update: WebSocketProgressUpdate) => {
      updateFileStatus(fileId, {
        progress: update.progress_percentage || 0,
        currentStep: update.current_step || 'Processing',
        error: update.error_message,
      });

      if (update.type === 'upload_complete' && update.result) {
        updateFileStatus(fileId, {
          status: 'completed',
          result: update.result,
          documentId: update.result.document_id,
          jobId: update.result.job_id,
          progress: 100,
          currentStep: 'Complete',
        });
        toast({
          title: 'Document processed',
          description: `${update.result.title} processed successfully`,
        });
      }

      if (update.type === 'error') {
        updateFileStatus(fileId, {
          status: 'failed',
          error: update.error_message || 'Processing failed',
        });
        toast({
          title: 'Processing failed',
          description:
            update.error_message || 'An error occurred during ingestion',
          variant: 'destructive',
        });
      }
    };

  const uploadFile = async (uploadedFile: UploadedFile) => {
    try {
      updateFileStatus(uploadedFile.id, {
        status: 'uploading',
        progress: 0,
        currentStep: 'Uploading',
      });

      const result = await enhancedDocumentService.uploadDocument(
        uploadedFile.file,
        uploadedFile.request,
        handleProgressUpdate(uploadedFile.id)
      );
      const { response, websocket } = result;

      updateFileStatus(uploadedFile.id, {
        status: 'queued',
        uploadId: response.upload_id,
        jobId: response.job_id,
        qualityScore: response.quality_score,
        securityScan: response.security_scan_result,
        websocket,
      });
    } catch (error) {
      updateFileStatus(uploadedFile.id, {
        status: 'failed',
        error: error instanceof Error ? error.message : 'Uplink failed',
      });
      toast({
        title: 'Upload Failed',
        description:
          error instanceof Error ? error.message : 'An error occurred',
        variant: 'destructive',
      });
    }
  };

  const uploadAllFiles = async () => {
    if (authLoading) return;
    if (!isAuthenticated || !organization) {
      toast({
        title: 'Auth Required',
        description: 'Authenticate to initialize ingestion.',
        variant: 'destructive',
      });
      return;
    }

    setIsUploading(true);
    const pendingFiles = uploadedFiles.filter((f) => f.status === 'pending');

    for (const file of pendingFiles) {
      await uploadFile(file);
      await new Promise((resolve) => setTimeout(resolve, 500));
    }

    setIsUploading(false);
  };

  const removeFile = (fileId: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== fileId));
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const getFileIcon = (type: string) => {
    if (
      type.includes('pdf') ||
      type.includes('text') ||
      type.includes('document')
    )
      return <FileText className="w-5 h-5" />;
    if (type.includes('image')) return <ImageIcon className="w-5 h-5" />;
    if (type.includes('audio')) return <Music className="w-5 h-5" />;
    if (type.includes('video')) return <Video className="w-5 h-5" />;
    return <FilePlus className="w-5 h-5" />;
  };

  const getStatusColor = (status: UploadedFile['status']) => {
    switch (status) {
      case 'completed':
        return 'var(--nous-sol)';
      case 'queued':
      case 'processing':
      case 'uploading':
        return 'var(--nous-helios)';
      case 'failed':
        return 'var(--error-red)';
      default:
        return 'var(--nous-fg-3)';
    }
  };

  const fileTypes = [
    { ext: 'PDF', color: 'var(--error-red)' },
    { ext: 'DOCX', color: 'var(--nous-helios)' },
    { ext: 'TXT', color: 'var(--nous-fg-3)' },
    { ext: 'JPG', color: 'var(--nous-helios)' },
    { ext: 'PNG', color: 'var(--nous-sol)' },
    { ext: 'MP3', color: '#a855f7' },
    { ext: 'MP4', color: 'var(--nous-helios)' },
  ];

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[var(--nous-bg-1)] relative overflow-hidden flex flex-col">
      <div className="flex-1 overflow-y-auto nous-scrollbar relative z-10 p-6">
        <div className="max-w-5xl mx-auto space-y-8">
          {/* Page Title */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-4 px-2"
          >
            <div className="p-2 rounded-lg bg-[var(--nous-sol)]/10 border border-[var(--nous-sol)]/20">
              <Upload className="h-6 w-6 text-[var(--nous-sol)]" />
            </div>
            <div>
              <h1 className="text-xl font-mono font-bold text-[var(--nous-fg-1)] tracking-tighter uppercase">
                Upload Documents
              </h1>
              <p className="text-[9px] font-mono text-[var(--nous-fg-3)] uppercase tracking-[0.2em] mt-0.5">
                Supported formats: PDF, DOCX, TXT, Images, Audio, Video
              </p>
            </div>
          </motion.div>

          {/* Main Terminal Window */}
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="rounded-2xl border border-[var(--nous-border-1)] bg-[var(--nous-bg-2)]/80 backdrop-blur-xl overflow-hidden shadow-2xl relative"
          >
            {/* Upload queue */}
            <div className="absolute top-0 left-6 bottom-0 w-[1px] bg-gradient-to-b from-[var(--nous-sol)]/20 via-[var(--nous-border-1)] to-transparent pointer-events-none" />

            <div className="p-8 pl-14">
              <div
                {...getRootProps()}
                className={cn(
                  'relative border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-300',
                  isDragActive
                    ? 'border-[var(--nous-sol)] bg-[var(--nous-sol)]/5 scale-[1.01]'
                    : 'border-[var(--nous-border-1)] hover:border-[var(--nous-border-2)]',
                  isUploading && 'opacity-50 cursor-not-allowed'
                )}
              >
                <input {...getInputProps()} />

                <motion.div
                  animate={{ y: isDragActive ? -5 : 0 }}
                  className="space-y-6"
                >
                  <div className="mx-auto w-20 h-20 rounded-2xl flex items-center justify-center bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] relative group">
                    <UploadCloud
                      className={cn(
                        'w-10 h-10 transition-colors duration-300',
                        isDragActive
                          ? 'text-[var(--nous-sol)]'
                          : 'text-[var(--nous-fg-3)]'
                      )}
                    />
                    <div className="absolute inset-0 rounded-2xl border border-[var(--nous-sol)]/50 scale-110 opacity-0 group-hover:opacity-100 group-hover:scale-100 transition-all duration-500" />
                  </div>

                  <div className="space-y-2">
                    <p className="text-sm font-mono font-bold tracking-widest text-[var(--nous-fg-1)] uppercase">
                      {isDragActive
                        ? 'Drop files now'
                        : 'Drag & drop files or click to browse'}
                    </p>
                    <p className="text-[10px] text-[var(--nous-fg-3)] font-mono uppercase tracking-widest">
                      Max file size: 50MB • Up to 10 files at once
                    </p>
                  </div>

                  {/* File Type Badges */}
                  <div className="flex flex-wrap justify-center gap-2 pt-4">
                    {fileTypes.map((type) => (
                      <span
                        key={type.ext}
                        className="px-2.5 py-1 rounded bg-[var(--nous-bg-1)] border border-[var(--nous-border-1)] text-[9px] font-mono font-bold tracking-widest transition-colors hover:border-[var(--nous-sol)]/30"
                        style={{ color: type.color }}
                      >
                        {type.ext}
                      </span>
                    ))}
                  </div>
                </motion.div>
              </div>

              {/* File Queue */}
              <AnimatePresence>
                {uploadedFiles.length > 0 && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-10 space-y-4"
                  >
                    <div className="flex items-center justify-between border-b border-[var(--nous-border-1)] pb-4">
                      <div className="flex items-center gap-2">
                        <Activity className="w-3.5 h-3.5 text-[var(--nous-helios)]" />
                        <span className="text-[10px] font-mono font-bold text-[var(--nous-fg-3)] uppercase tracking-widest">
                          Queue ({uploadedFiles.length})
                        </span>
                      </div>

                      {uploadedFiles.some((f) => f.status === 'pending') && (
                        <button
                          onClick={uploadAllFiles}
                          disabled={isUploading || !isAuthenticated}
                          className="flex items-center gap-2 px-5 py-2 rounded-lg font-mono text-[10px] font-bold uppercase transition-all bg-[var(--nous-sol)] text-[var(--nous-bg-1)] hover:shadow-[0_0_20px_var(--nous-sol-glow)] disabled:opacity-50"
                        >
                          {isUploading ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Processing...
                            </>
                          ) : (
                            <>
                              <Upload className="w-3.5 h-3.5" />
                              INITIATE_UPLINK
                            </>
                          )}
                        </button>
                      )}
                    </div>

                    <div className="space-y-3">
                      {uploadedFiles.map((file, index) => (
                        <motion.div
                          key={file.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 10 }}
                          transition={{ delay: index * 0.05 }}
                          className="rounded-xl p-4 bg-[var(--nous-bg-1)]/50 border border-[var(--nous-border-1)] group hover:border-[var(--nous-border-2)] transition-all"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4 min-w-0 flex-1">
                              <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 bg-[var(--nous-bg-2)] border border-[var(--nous-border-1)] transition-colors group-hover:border-[var(--nous-sol)]/30"
                                style={{ color: getStatusColor(file.status) }}
                              >
                                {getFileIcon(file.file.type)}
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="text-[13px] font-mono font-bold text-[var(--nous-fg-1)] truncate uppercase tracking-tight">
                                  {file.file.name}
                                </p>
                                <div className="flex items-center gap-3 mt-1 text-[9px] font-mono uppercase tracking-widest text-[var(--nous-fg-3)]">
                                  <span>{formatFileSize(file.file.size)}</span>
                                  <span className="w-1 h-1 rounded-full bg-[var(--nous-border-1)]" />
                                  <span
                                    className="flex items-center gap-1.5"
                                    style={{
                                      color: getStatusColor(file.status),
                                    }}
                                  >
                                    <span
                                      className={cn(
                                        'w-1.5 h-1.5 rounded-full',
                                        file.status === 'processing' ||
                                          file.status === 'queued'
                                          ? 'animate-pulse'
                                          : ''
                                      )}
                                      style={{
                                        backgroundColor: getStatusColor(
                                          file.status
                                        ),
                                      }}
                                    />
                                    {file.currentStep}
                                  </span>
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-3">
                              {file.status === 'completed' && (
                                <CheckCircle className="w-4 h-4 text-[var(--nous-sol)]" />
                              )}
                              {file.status === 'failed' && (
                                <AlertTriangle className="w-4 h-4 text-[var(--error-red)]" />
                              )}
                              {(file.status === 'uploading' ||
                                file.status === 'queued' ||
                                file.status === 'processing') && (
                                <div className="flex items-center gap-2">
                                  <span className="text-[9px] font-mono text-[var(--nous-helios)] font-bold">
                                    {Math.round(file.progress)}%
                                  </span>
                                  <Loader2 className="w-4 h-4 text-[var(--nous-helios)] animate-spin" />
                                </div>
                              )}
                              {(file.status === 'pending' ||
                                file.status === 'failed') && (
                                <button
                                  onClick={() => removeFile(file.id)}
                                  className="p-2 rounded-lg hover:bg-[var(--error-red)]/10 text-[var(--nous-fg-3)] hover:text-[var(--error-red)] transition-colors border border-transparent hover:border-[var(--error-red)]/30"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Progress Line */}
                          {(file.status === 'uploading' ||
                            file.status === 'queued' ||
                            file.status === 'processing') && (
                            <div className="mt-4">
                              <div className="h-0.5 w-full bg-[var(--nous-border-1)] rounded-full overflow-hidden">
                                <motion.div
                                  className="h-full bg-gradient-to-r from-[var(--nous-helios)] to-[var(--nous-sol)] shadow-[0_0_10px_var(--nous-helios)]"
                                  initial={{ width: 0 }}
                                  animate={{ width: `${file.progress}%` }}
                                  transition={{ duration: 0.3 }}
                                />
                              </div>
                            </div>
                          )}

                          {/* Detail Panels (Success/Failure/Quality) */}
                          <div className="mt-3 flex flex-wrap gap-2">
                            {file.status === 'completed' && file.documentId && (
                              <div className="px-2 py-1 rounded bg-[var(--nous-sol)]/5 border border-[var(--nous-sol)]/20 text-[8px] font-mono text-[var(--nous-sol)] flex items-center gap-1.5 uppercase">
                                <Database className="w-3 h-3" />
                                NODE_ID: {file.documentId}
                              </div>
                            )}

                            {file.qualityScore && (
                              <div className="px-2 py-1 rounded bg-[var(--nous-helios)]/5 border border-[var(--nous-helios)]/20 text-[8px] font-mono text-[var(--nous-helios)] flex items-center gap-1.5 uppercase">
                                <Sparkles className="w-3 h-3" />
                                SCORE: {Math.round(file.qualityScore * 100)}%
                              </div>
                            )}

                            {file.securityScan && (
                              <div
                                className={cn(
                                  'px-2 py-1 rounded border text-[8px] font-mono flex items-center gap-1.5 uppercase',
                                  file.securityScan.scan_status === 'passed'
                                    ? 'bg-[var(--nous-sol)]/5 border-[var(--nous-sol)]/20 text-[var(--nous-sol)]'
                                    : 'bg-[var(--error-red)]/5 border-[var(--error-red)]/20 text-[var(--error-red)]'
                                )}
                              >
                                <ShieldCheck className="w-3 h-3" />
                                SCAN: {file.securityScan.scan_status}
                              </div>
                            )}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
