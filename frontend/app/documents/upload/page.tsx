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
  UploadCloud,
  FilePlus,
  X,
  CheckCircle,
  AlertTriangle,
  Upload,
  Trash2,
  Settings,
  FileText,
  Image as ImageIcon,
  Music,
  Video,
  Sparkles,
  ShieldCheck,
  Terminal,
  Activity,
  ArrowRight,
  Database,
  Cpu,
  Network,
  Loader2
} from 'lucide-react';

import { useToast } from '@/hooks/use-toast';
import { enhancedDocumentService, DocumentUploadRequest, WebSocketProgressUpdate } from '@/services/enhancedDocumentService';
import { mockDocumentService } from '@/services/mockDocumentService';
import { useAuthStore } from '@/stores/authStore';
import { cn } from '@/lib/utils';

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
    const fullText = 'DOCUMENT_INGESTION_TERMINAL';
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
            title: "Transmission Error",
            description: `${file.name}: ${error.message}`,
            variant: "destructive"
          });
        });
      });
      return;
    }

    if (uploadedFiles.length + acceptedFiles.length > 10) {
      toast({
        title: "Queue Overload",
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
          title: "Incompatible Payload",
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
        currentStep: 'Ready for ingestion',
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
        currentStep: 'Synchronized'
      });
      toast({ title: "Node Ingested", description: `${update.result.title} processed successfully` });
    }

    if (update.type === 'error') {
      updateFileStatus(fileId, {
        status: 'failed',
        error: update.error_message || 'Processing failed'
      });
      toast({
        title: "Protocol Breach",
        description: update.error_message || 'An error occurred during ingestion',
        variant: "destructive"
      });
    }
  };

  const uploadFile = async (uploadedFile: UploadedFile) => {
    try {
      updateFileStatus(uploadedFile.id, {
        status: 'uploading',
        progress: 0,
        currentStep: 'Establishing uplink'
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
        error: error instanceof Error ? error.message : 'Uplink failed'
      });
      toast({
        title: "Upload Failed",
        description: error instanceof Error ? error.message : 'An error occurred',
        variant: "destructive"
      });
    }
  };

  const uploadAllFiles = async () => {
    if (authLoading) return;
    if (!isAuthenticated || !token || !organization) {
      toast({ title: "Auth Required", description: "Authenticate to initialize ingestion.", variant: "destructive" });
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
      return <FileText className="w-5 h-5" />;
    if (type.includes('image')) return <ImageIcon className="w-5 h-5" />;
    if (type.includes('audio')) return <Music className="w-5 h-5" />;
    if (type.includes('video')) return <Video className="w-5 h-5" />;
    return <FilePlus className="w-5 h-5" />;
  };

  const getStatusColor = (status: UploadedFile['status']) => {
    switch (status) {
      case 'completed': return 'var(--phosphor-green)';
      case 'processing':
      case 'uploading': return 'var(--cyan)';
      case 'failed': return 'var(--error-red)';
      default: return 'var(--terminal-text-muted)';
    }
  };

  const fileTypes = [
    { ext: 'PDF', color: 'var(--error-red)' },
    { ext: 'DOCX', color: 'var(--cyan)' },
    { ext: 'TXT', color: 'var(--terminal-text-dim)' },
    { ext: 'JPG', color: 'var(--amber-gold)' },
    { ext: 'PNG', color: 'var(--phosphor-green)' },
    { ext: 'MP3', color: '#a855f7' },
    { ext: 'MP4', color: 'var(--cyan)' },
  ];

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[var(--terminal-bg)] relative overflow-hidden flex flex-col star-field terminal-grid noise-texture">
      {/* Navigation Header */}
      <nav className="relative z-40 border-b border-[var(--terminal-border)] bg-[var(--terminal-bg)]/80 backdrop-blur-xl h-14 shrink-0">
        <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20">
              <Terminal className="w-4 h-4 text-[var(--phosphor-green)]" />
            </div>
            <div className="flex flex-col">
              <span className="font-mono font-bold text-[var(--terminal-text)] text-sm uppercase tracking-tighter leading-none">INGEST_CORE</span>
              <span className="font-mono text-[9px] text-[var(--terminal-text-dim)] uppercase tracking-widest leading-none mt-0.5">Terminal Observatory</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button 
              onClick={() => window.location.href = '/documents'}
              className="px-3 py-1.5 rounded-lg border border-[var(--terminal-border)] bg-[var(--terminal-surface)] text-[10px] font-mono text-[var(--terminal-text-muted)] hover:text-[var(--phosphor-green)] hover:border-[var(--phosphor-green)]/30 transition-all uppercase tracking-widest font-bold"
            >
              Back_to_registry
            </button>
          </div>
        </div>
      </nav>

      <div className="flex-1 overflow-y-auto terminal-scrollbar relative z-10 p-6">
        <div className="max-w-5xl mx-auto space-y-8">
          {/* Page Title */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-4 px-2"
          >
            <div className="p-2 rounded-lg bg-[var(--phosphor-green)]/10 border border-[var(--phosphor-green)]/20">
              <Upload className="h-6 w-6 text-[var(--phosphor-green)]" />
            </div>
            <div>
              <h1 className="text-xl font-mono font-bold text-[var(--terminal-text)] tracking-tighter uppercase">
                {terminalText}<span className="animate-pulse">_</span>
              </h1>
              <p className="text-[9px] font-mono text-[var(--terminal-text-dim)] uppercase tracking-[0.2em] mt-0.5">
                Neural Data Ingestion :: Channel Secure
              </p>
            </div>
          </motion.div>

          {/* Main Terminal Window */}
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="rounded-2xl border border-[var(--terminal-border)] bg-[var(--terminal-surface)]/80 backdrop-blur-xl overflow-hidden shadow-2xl relative"
          >
            {/* Transmission Line */}
            <div className="absolute top-0 left-6 bottom-0 w-[1px] bg-gradient-to-b from-[var(--phosphor-green)]/20 via-[var(--terminal-border)] to-transparent pointer-events-none" />

            <div className="p-8 pl-14">
              <div
                {...getRootProps()}
                className={cn(
                  "relative border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-all duration-300",
                  isDragActive ? "border-[var(--phosphor-green)] bg-[var(--phosphor-green)]/5 scale-[1.01]" : "border-[var(--terminal-border)] hover:border-[var(--terminal-border-muted)]",
                  isUploading && "opacity-50 cursor-not-allowed"
                )}
              >
                <input {...getInputProps()} />

                <motion.div
                  animate={{ y: isDragActive ? -5 : 0 }}
                  className="space-y-6"
                >
                  <div className="mx-auto w-20 h-20 rounded-2xl flex items-center justify-center bg-[var(--terminal-bg)] border border-[var(--terminal-border)] relative group">
                    <UploadCloud className={cn(
                      "w-10 h-10 transition-colors duration-300",
                      isDragActive ? "text-[var(--phosphor-green)]" : "text-[var(--terminal-text-dim)]"
                    )} />
                    <div className="absolute inset-0 rounded-2xl border border-[var(--phosphor-green)]/50 scale-110 opacity-0 group-hover:opacity-100 group-hover:scale-100 transition-all duration-500" />
                  </div>

                  <div className="space-y-2">
                    <p className="text-sm font-mono font-bold tracking-widest text-[var(--terminal-text)] uppercase">
                      {isDragActive ? '[ RELEASE_FOR_INGESTION ]' : 'Drop_nodes_here_or_click_to_initialize'}
                    </p>
                    <p className="text-[10px] text-[var(--terminal-text-muted)] font-mono uppercase tracking-widest">
                      Payload Limit: 50MB • Max Units: 10 per cycle
                    </p>
                  </div>

                  {/* File Type Badges */}
                  <div className="flex flex-wrap justify-center gap-2 pt-4">
                    {fileTypes.map((type) => (
                      <span
                        key={type.ext}
                        className="px-2.5 py-1 rounded bg-[var(--terminal-bg)] border border-[var(--terminal-border)] text-[9px] font-mono font-bold tracking-widest transition-colors hover:border-[var(--phosphor-green)]/30"
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
                    <div className="flex items-center justify-between border-b border-[var(--terminal-border)] pb-4">
                      <div className="flex items-center gap-2">
                        <Activity className="w-3.5 h-3.5 text-[var(--amber-gold)]" />
                        <span className="text-[10px] font-mono font-bold text-[var(--terminal-text-dim)] uppercase tracking-widest">
                          Transmission_Queue ({uploadedFiles.length})
                        </span>
                      </div>
                      
                      {uploadedFiles.some(f => f.status === 'pending') && (
                        <button
                          onClick={uploadAllFiles}
                          disabled={isUploading || !isAuthenticated}
                          className="flex items-center gap-2 px-5 py-2 rounded-lg font-mono text-[10px] font-bold uppercase transition-all bg-[var(--phosphor-green)] text-[var(--terminal-bg)] hover:shadow-[0_0_20px_var(--phosphor-green-glow)] disabled:opacity-50"
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
                          className="rounded-xl p-4 bg-[var(--terminal-bg)]/50 border border-[var(--terminal-border)] group hover:border-[var(--terminal-border-muted)] transition-all"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4 min-w-0 flex-1">
                              <div
                                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 bg-[var(--terminal-surface)] border border-[var(--terminal-border)] transition-colors group-hover:border-[var(--phosphor-green)]/30"
                                style={{ color: getStatusColor(file.status) }}
                              >
                                {getFileIcon(file.file.type)}
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="text-[13px] font-mono font-bold text-[var(--terminal-text)] truncate uppercase tracking-tight">
                                  {file.file.name}
                                </p>
                                <div className="flex items-center gap-3 mt-1 text-[9px] font-mono uppercase tracking-widest text-[var(--terminal-text-muted)]">
                                  <span>{formatFileSize(file.file.size)}</span>
                                  <span className="w-1 h-1 rounded-full bg-[var(--terminal-border)]" />
                                  <span className="flex items-center gap-1.5" style={{ color: getStatusColor(file.status) }}>
                                    <span className={cn("w-1.5 h-1.5 rounded-full", file.status === 'processing' ? "animate-pulse" : "")} style={{ backgroundColor: getStatusColor(file.status) }} />
                                    {file.currentStep}
                                  </span>
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-3">
                              {file.status === 'completed' && (
                                <CheckCircle className="w-4 h-4 text-[var(--phosphor-green)]" />
                              )}
                              {file.status === 'failed' && (
                                <AlertTriangle className="w-4 h-4 text-[var(--error-red)]" />
                              )}
                              {(file.status === 'uploading' || file.status === 'processing') && (
                                <div className="flex items-center gap-2">
                                  <span className="text-[9px] font-mono text-[var(--cyan)] font-bold">{Math.round(file.progress)}%</span>
                                  <Loader2 className="w-4 h-4 text-[var(--cyan)] animate-spin" />
                                </div>
                              )}
                              {(file.status === 'pending' || file.status === 'failed') && (
                                <button
                                  onClick={() => removeFile(file.id)}
                                  className="p-2 rounded-lg hover:bg-[var(--error-red)]/10 text-[var(--terminal-text-muted)] hover:text-[var(--error-red)] transition-colors border border-transparent hover:border-[var(--error-red)]/30"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Progress Line */}
                          {(file.status === 'uploading' || file.status === 'processing') && (
                            <div className="mt-4">
                              <div className="h-0.5 w-full bg-[var(--terminal-border)] rounded-full overflow-hidden">
                                <motion.div
                                  className="h-full bg-gradient-to-r from-[var(--cyan)] to-[var(--phosphor-green)] shadow-[0_0_10px_var(--cyan)]"
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
                              <div className="px-2 py-1 rounded bg-[var(--phosphor-green)]/5 border border-[var(--phosphor-green)]/20 text-[8px] font-mono text-[var(--phosphor-green)] flex items-center gap-1.5 uppercase">
                                <Database className="w-3 h-3" />
                                NODE_ID: {file.documentId}
                              </div>
                            )}
                            
                            {file.qualityScore && (
                              <div className="px-2 py-1 rounded bg-[var(--amber-gold)]/5 border border-[var(--amber-gold)]/20 text-[8px] font-mono text-[var(--amber-gold)] flex items-center gap-1.5 uppercase">
                                <Sparkles className="w-3 h-3" />
                                SCORE: {Math.round(file.qualityScore * 100)}%
                              </div>
                            )}

                            {file.securityScan && (
                              <div className={cn(
                                "px-2 py-1 rounded border text-[8px] font-mono flex items-center gap-1.5 uppercase",
                                file.securityScan.scan_status === 'passed' 
                                  ? "bg-[var(--phosphor-green)]/5 border-[var(--phosphor-green)]/20 text-[var(--phosphor-green)]" 
                                  : "bg-[var(--error-red)]/5 border-[var(--error-red)]/20 text-[var(--error-red)]"
                              )}>
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

          {/* Feature Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
            {[
              {
                icon: Cpu,
                title: 'NEURAL_INGESTION',
                desc: 'Automatic entity extraction and contextual linking',
                color: 'var(--phosphor-green)',
              },
              {
                icon: ShieldCheck,
                title: 'ZERO_TRUST_SCAN',
                desc: 'Payload validation and threat neutralizing protocols',
                color: 'var(--amber-gold)',
              },
              {
                icon: Network,
                title: 'SEMANTIC_GRID',
                desc: 'Node integration into distributed knowledge graph',
                color: 'var(--cyan)',
              },
            ].map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 + (index * 0.1) }}
                className="p-5 rounded-2xl bg-[var(--terminal-surface)] border border-[var(--terminal-border)] group hover:border-[var(--terminal-border-muted)] transition-all"
              >
                <div className="mb-4 p-2 w-fit rounded-lg bg-[var(--terminal-bg)] border border-[var(--terminal-border)] transition-colors group-hover:border-[var(--phosphor-green)]/30" style={{ color: feature.color }}>
                  <feature.icon className="w-5 h-5" />
                </div>
                <h3 className="font-mono text-[11px] font-bold text-[var(--terminal-text)] mb-2 uppercase tracking-widest">
                  {feature.title}
                </h3>
                <p className="text-[10px] text-[var(--terminal-text-dim)] font-mono uppercase tracking-tight leading-relaxed">
                  {feature.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      {/* Status Bar Footer */}
      <footer className="border-t border-[var(--terminal-border)] bg-[var(--terminal-bg)]/90 backdrop-blur-sm p-2 shrink-0">
        <div className="max-w-7xl mx-auto flex items-center justify-between text-[9px] font-mono text-[var(--terminal-text-muted)] uppercase tracking-wider">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className={cn("w-1.5 h-1.5 rounded-full bg-[var(--phosphor-green)]", isUploading ? "animate-ping" : "")} />
              {isUploading ? "TRANSMISSION_ACTIVE" : "TERMINAL_STANDBY"}
            </span>
            <span className="hidden sm:inline">BITRATE: 4.2 MBPS</span>
          </div>
          <div className="flex items-center gap-4">
            <span>UPLINK: SECURE_TLS_1.3</span>
            <span>BUILD: v2.0.1-INGEST</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
