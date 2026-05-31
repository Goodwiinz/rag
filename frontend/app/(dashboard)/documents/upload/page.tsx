/**
 * Document upload page
 * Add documents to the knowledge base and track ingestion progress.
 */

'use client';

import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence, MotionConfig } from 'framer-motion';
import { v4 as uuidv4 } from 'uuid';
import {
  Upload,
  UploadCloud,
  FilePlus,
  FileText,
  Image as ImageIcon,
  Music,
  Video,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  ShieldCheck,
  Database,
  ListChecks,
} from 'lucide-react';

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
              title: 'File rejected',
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
          description: 'You can upload up to 10 files at a time.',
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
              title: 'Already uploaded',
              description: `"${file.name}" matches existing document "${existing?.title || existing?.filename}", so it was skipped.`,
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
          currentStep: 'Indexed',
        });
        toast({
          title: 'Document ready',
          description: `${update.result.title} was processed successfully.`,
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
            update.error_message || 'Something went wrong while processing.',
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
        error: error instanceof Error ? error.message : 'Upload failed',
      });
      toast({
        title: 'Upload failed',
        description:
          error instanceof Error ? error.message : 'Something went wrong.',
        variant: 'destructive',
      });
    }
  };

  const uploadAllFiles = async () => {
    if (authLoading) return;
    if (!isAuthenticated || !organization) {
      toast({
        title: 'Sign in required',
        description: 'Sign in to start uploading documents.',
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
      return <FileText aria-hidden="true" className="w-5 h-5" />;
    if (type.includes('image'))
      return <ImageIcon aria-hidden="true" className="w-5 h-5" />;
    if (type.includes('audio'))
      return <Music aria-hidden="true" className="w-5 h-5" />;
    if (type.includes('video'))
      return <Video aria-hidden="true" className="w-5 h-5" />;
    return <FilePlus aria-hidden="true" className="w-5 h-5" />;
  };

  // Status colour resolves to a brand token; it is always paired with a text
  // label and icon so colour is never the only signal.
  const getStatusColor = (status: UploadedFile['status']) => {
    switch (status) {
      case 'completed':
        return 'var(--nous-terra)';
      case 'queued':
      case 'processing':
      case 'uploading':
        return 'var(--nous-helios)';
      case 'failed':
        return 'var(--nous-mars)';
      default:
        return 'var(--muted-foreground)';
    }
  };

  const getStatusLabel = (status: UploadedFile['status']) => {
    switch (status) {
      case 'pending':
        return 'Ready';
      case 'uploading':
        return 'Uploading';
      case 'queued':
        return 'Queued';
      case 'processing':
        return 'Processing';
      case 'completed':
        return 'Indexed';
      case 'failed':
        return 'Failed';
    }
  };

  const fileTypes = ['PDF', 'DOCX', 'TXT', 'JPG', 'PNG', 'MP3', 'MP4'];

  const isActive = (status: UploadedFile['status']) =>
    status === 'uploading' || status === 'queued' || status === 'processing';

  if (!mounted) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="h-20 rounded-xl border border-border bg-card animate-pulse" />
          <div className="h-72 rounded-xl border border-border bg-card animate-pulse" />
        </div>
      </div>
    );
  }

  const pendingCount = uploadedFiles.filter(
    (f) => f.status === 'pending'
  ).length;

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-screen bg-background flex flex-col">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-5xl mx-auto space-y-6">
            {/* Header */}
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl border border-border bg-card shadow-sm"
            >
              <div className="p-6 flex items-center gap-4">
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Upload aria-hidden="true" className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h1 className="text-xl font-semibold text-foreground">
                    Upload documents
                  </h1>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Add files to your knowledge base. PDF, DOCX, TXT, images,
                    audio, and video are supported.
                  </p>
                </div>
              </div>
            </motion.div>

            {/* Dropzone */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="rounded-xl border border-border bg-card shadow-sm overflow-hidden"
            >
              <div className="p-6">
                <div
                  {...getRootProps()}
                  className={cn(
                    'rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card',
                    isDragActive
                      ? 'border-[var(--nous-helios)] bg-primary/5'
                      : 'border-border hover:border-[var(--nous-helios)]',
                    isUploading && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  <input {...getInputProps()} />

                  <div className="space-y-5">
                    <div className="mx-auto w-16 h-16 rounded-xl flex items-center justify-center bg-muted text-primary">
                      <UploadCloud aria-hidden="true" className="w-8 h-8" />
                    </div>

                    <div className="space-y-1.5">
                      <p className="text-base font-medium text-foreground">
                        {isDragActive
                          ? 'Drop your files to add them'
                          : 'Drag and drop files, or click to browse'}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Up to 10 files, 50 MB each.
                      </p>
                    </div>

                    <div className="flex flex-wrap justify-center gap-2 pt-1">
                      {fileTypes.map((ext) => (
                        <span
                          key={ext}
                          className="px-2.5 py-1 rounded-md bg-muted text-xs font-medium text-muted-foreground"
                        >
                          {ext}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Sign-in hint — honest, non-blocking */}
                {!authLoading &&
                  !isAuthenticated &&
                  uploadedFiles.length > 0 && (
                    <p
                      role="status"
                      className="mt-4 text-sm text-muted-foreground"
                    >
                      Sign in to start uploading the files in your queue.
                    </p>
                  )}

                {/* Queue */}
                <AnimatePresence initial={false}>
                  {uploadedFiles.length > 0 && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      className="mt-6"
                    >
                      <div className="flex items-center justify-between border-b border-border pb-4">
                        <div className="flex items-center gap-2">
                          <ListChecks
                            aria-hidden="true"
                            className="w-4 h-4 text-muted-foreground"
                          />
                          <span className="text-sm font-medium text-foreground">
                            Upload queue ({uploadedFiles.length})
                          </span>
                        </div>

                        {pendingCount > 0 && (
                          <button
                            type="button"
                            onClick={uploadAllFiles}
                            disabled={isUploading || !isAuthenticated}
                            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-primary text-[var(--nous-erebus)] transition-colors hover:bg-[var(--nous-helios)] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
                          >
                            <Upload aria-hidden="true" className="w-4 h-4" />
                            {isUploading
                              ? 'Uploading…'
                              : `Upload ${pendingCount} file${pendingCount === 1 ? '' : 's'}`}
                          </button>
                        )}
                      </div>

                      <ul className="mt-4 space-y-3">
                        <AnimatePresence initial={false}>
                          {uploadedFiles.map((file) => (
                            <motion.li
                              key={file.id}
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, y: -6 }}
                              transition={{ duration: 0.18 }}
                              className="rounded-lg p-4 border border-border bg-muted/20 transition-colors hover:bg-muted/30"
                            >
                              <div className="flex items-center justify-between gap-4">
                                <div className="flex items-center gap-3 min-w-0 flex-1">
                                  <div
                                    className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0 bg-card border border-border"
                                    style={{
                                      color: getStatusColor(file.status),
                                    }}
                                  >
                                    {getFileIcon(file.file.type)}
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <p className="text-sm font-medium text-foreground truncate">
                                      {file.file.name}
                                    </p>
                                    <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                                      <span className="tabular-nums">
                                        {formatFileSize(file.file.size)}
                                      </span>
                                      <span
                                        aria-hidden="true"
                                        className="w-1 h-1 rounded-full bg-border"
                                      />
                                      <span
                                        className="inline-flex items-center gap-1.5"
                                        style={{
                                          color: getStatusColor(file.status),
                                        }}
                                      >
                                        <span
                                          aria-hidden="true"
                                          className="w-1.5 h-1.5 rounded-full"
                                          style={{
                                            backgroundColor: getStatusColor(
                                              file.status
                                            ),
                                          }}
                                        />
                                        {getStatusLabel(file.status)}
                                      </span>
                                    </div>
                                  </div>
                                </div>

                                <div className="flex items-center gap-3 shrink-0">
                                  {file.status === 'completed' && (
                                    <CheckCircle2
                                      aria-label="Indexed"
                                      className="w-4 h-4 text-[var(--nous-terra)]"
                                    />
                                  )}
                                  {file.status === 'failed' && (
                                    <AlertTriangle
                                      aria-label="Failed"
                                      className="w-4 h-4 text-[var(--nous-mars)]"
                                    />
                                  )}
                                  {isActive(file.status) && (
                                    <span className="text-xs font-medium tabular-nums text-[var(--nous-helios)]">
                                      {Math.round(file.progress)}%
                                    </span>
                                  )}
                                  {(file.status === 'pending' ||
                                    file.status === 'failed') && (
                                    <button
                                      type="button"
                                      onClick={() => removeFile(file.id)}
                                      aria-label={`Remove ${file.file.name}`}
                                      className="p-2 rounded-lg text-muted-foreground transition-colors hover:bg-[var(--nous-mars)]/10 hover:text-[var(--nous-mars)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
                                    >
                                      <Trash2
                                        aria-hidden="true"
                                        className="w-4 h-4"
                                      />
                                    </button>
                                  )}
                                </div>
                              </div>

                              {/* Progress */}
                              {isActive(file.status) && (
                                <div
                                  className="mt-3 h-1 w-full bg-border rounded-full overflow-hidden"
                                  role="progressbar"
                                  aria-valuenow={Math.round(file.progress)}
                                  aria-valuemin={0}
                                  aria-valuemax={100}
                                  aria-label={`${file.file.name} upload progress`}
                                >
                                  <motion.div
                                    className="h-full rounded-full bg-primary"
                                    initial={{ width: 0 }}
                                    animate={{ width: `${file.progress}%` }}
                                    transition={{ duration: 0.25 }}
                                  />
                                </div>
                              )}

                              {/* Error detail */}
                              {file.status === 'failed' && file.error && (
                                <p
                                  role="alert"
                                  className="mt-3 text-xs text-[var(--nous-mars)]"
                                >
                                  {file.error}
                                </p>
                              )}

                              {/* Metadata chips */}
                              {(file.documentId ||
                                file.qualityScore ||
                                file.securityScan) && (
                                <div className="mt-3 flex flex-wrap gap-2">
                                  {file.status === 'completed' &&
                                    file.documentId && (
                                      <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted text-[11px] text-muted-foreground">
                                        <Database
                                          aria-hidden="true"
                                          className="w-3 h-3"
                                        />
                                        ID {file.documentId}
                                      </span>
                                    )}

                                  {file.qualityScore != null && (
                                    <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted text-[11px] text-muted-foreground">
                                      <Sparkles
                                        aria-hidden="true"
                                        className="w-3 h-3 text-primary"
                                      />
                                      Quality{' '}
                                      {Math.round(file.qualityScore * 100)}%
                                    </span>
                                  )}

                                  {file.securityScan && (
                                    <span
                                      className={cn(
                                        'inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px]',
                                        file.securityScan.scan_status ===
                                          'passed'
                                          ? 'bg-muted text-[var(--nous-terra)]'
                                          : 'bg-[var(--nous-mars)]/10 text-[var(--nous-mars)]'
                                      )}
                                    >
                                      <ShieldCheck
                                        aria-hidden="true"
                                        className="w-3 h-3"
                                      />
                                      Scan {file.securityScan.scan_status}
                                    </span>
                                  )}
                                </div>
                              )}
                            </motion.li>
                          ))}
                        </AnimatePresence>
                      </ul>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </MotionConfig>
  );
}
