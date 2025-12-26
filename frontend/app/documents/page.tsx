/**
 * Documents List Page
 * Terminal Observatory themed document management interface
 */

'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import {
  DocumentTextIcon,
  FolderIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ArrowUpTrayIcon,
  EyeIcon,
  TrashIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  DocumentArrowDownIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';

import { useAuthStore } from '@/stores/authStore';

// Terminal Observatory Theme Constants
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';
const CYAN = '#00d4ff';
const TERMINAL_BG = '#0d1117';

interface Document {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  updated_at: string;
  tags: string[];
  entities_count?: number;
}

// Mock documents for demo
const mockDocuments: Document[] = [
  {
    id: '1',
    title: 'RAG System Architecture',
    filename: 'rag_architecture.pdf',
    file_type: 'application/pdf',
    file_size: 2456789,
    status: 'completed',
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:35:00Z',
    tags: ['architecture', 'technical'],
    entities_count: 47,
  },
  {
    id: '2',
    title: 'Machine Learning Best Practices',
    filename: 'ml_best_practices.pdf',
    file_type: 'application/pdf',
    file_size: 1234567,
    status: 'completed',
    created_at: '2024-01-14T09:00:00Z',
    updated_at: '2024-01-14T09:12:00Z',
    tags: ['ml', 'guide'],
    entities_count: 32,
  },
  {
    id: '3',
    title: 'Neural Network Fundamentals',
    filename: 'nn_fundamentals.docx',
    file_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    file_size: 987654,
    status: 'processing',
    created_at: '2024-01-16T14:20:00Z',
    updated_at: '2024-01-16T14:20:00Z',
    tags: ['neural-networks'],
  },
  {
    id: '4',
    title: 'Data Pipeline Documentation',
    filename: 'data_pipeline.txt',
    file_type: 'text/plain',
    file_size: 45678,
    status: 'completed',
    created_at: '2024-01-13T16:45:00Z',
    updated_at: '2024-01-13T16:46:00Z',
    tags: ['data', 'pipeline'],
    entities_count: 18,
  },
  {
    id: '5',
    title: 'API Reference Guide',
    filename: 'api_reference.pdf',
    file_type: 'application/pdf',
    file_size: 3456789,
    status: 'failed',
    created_at: '2024-01-12T11:00:00Z',
    updated_at: '2024-01-12T11:05:00Z',
    tags: ['api', 'reference'],
  },
];

export default function DocumentsPage() {
  const { isAuthenticated } = useAuthStore();
  const [mounted, setMounted] = useState(false);
  const [terminalText, setTerminalText] = useState('');
  const [documents, setDocuments] = useState<Document[]>(mockDocuments);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showFilters, setShowFilters] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Terminal typing effect
  useEffect(() => {
    if (!mounted) return;
    const fullText = 'DOCUMENT REPOSITORY';
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

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getFileTypeIcon = (type: string) => {
    if (type.includes('pdf')) return { icon: '📄', color: '#ff4757' };
    if (type.includes('document') || type.includes('docx')) return { icon: '📝', color: '#3b82f6' };
    if (type.includes('text')) return { icon: '📃', color: '#6b7280' };
    if (type.includes('image')) return { icon: '🖼️', color: AMBER };
    if (type.includes('audio')) return { icon: '🎵', color: '#a855f7' };
    if (type.includes('video')) return { icon: '🎥', color: CYAN };
    return { icon: '📎', color: '#6b7280' };
  };

  const getStatusConfig = (status: Document['status']) => {
    switch (status) {
      case 'completed':
        return { color: PHOSPHOR_GREEN, label: 'INDEXED', icon: CheckCircleIcon };
      case 'processing':
        return { color: CYAN, label: 'PROCESSING', icon: ArrowPathIcon };
      case 'failed':
        return { color: '#ff4757', label: 'FAILED', icon: ExclamationTriangleIcon };
      default:
        return { color: '#6b7280', label: 'PENDING', icon: ClockIcon };
    }
  };

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         doc.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         doc.tags.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesStatus = statusFilter === 'all' || doc.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const stats = {
    total: documents.length,
    indexed: documents.filter(d => d.status === 'completed').length,
    processing: documents.filter(d => d.status === 'processing').length,
    failed: documents.filter(d => d.status === 'failed').length,
  };

  if (!mounted) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="text-gray-500 font-mono">Loading repository...</div>
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

      <div className="relative z-10 p-6 max-w-6xl mx-auto">
        {/* Terminal Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <div
              className="w-12 h-12 rounded-lg flex items-center justify-center"
              style={{
                background: `linear-gradient(135deg, ${PHOSPHOR_GREEN}20, ${PHOSPHOR_GREEN}05)`,
                border: `1px solid ${PHOSPHOR_GREEN}30`
              }}
            >
              <FolderIcon className="w-6 h-6" style={{ color: PHOSPHOR_GREEN }} />
            </div>
            <h1
              className="text-3xl font-mono font-bold tracking-wider"
              style={{ color: PHOSPHOR_GREEN }}
            >
              {terminalText}<span className="animate-pulse">_</span>
            </h1>
          </div>
          <p className="text-gray-500 font-mono text-sm">
            Manage and explore your indexed documents in the knowledge base.
          </p>
        </motion.div>

        {/* Stats Bar */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6"
        >
          {[
            { label: 'TOTAL', value: stats.total, color: '#e6edf3' },
            { label: 'INDEXED', value: stats.indexed, color: PHOSPHOR_GREEN },
            { label: 'PROCESSING', value: stats.processing, color: CYAN },
            { label: 'FAILED', value: stats.failed, color: '#ff4757' },
          ].map((stat) => (
            <div
              key={stat.label}
              className="p-3 rounded-lg text-center"
              style={{
                background: `${stat.color}08`,
                border: `1px solid ${stat.color}20`,
              }}
            >
              <div className="text-2xl font-mono font-bold" style={{ color: stat.color }}>
                {stat.value}
              </div>
              <div className="text-xs font-mono text-gray-500">{stat.label}</div>
            </div>
          ))}
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
            <span className="text-gray-500 font-mono text-xs">document_manager.exe</span>
            <Link
              href="/documents/upload"
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg font-mono text-xs transition-all"
              style={{
                background: `linear-gradient(135deg, ${PHOSPHOR_GREEN}20, ${PHOSPHOR_GREEN}10)`,
                border: `1px solid ${PHOSPHOR_GREEN}50`,
                color: PHOSPHOR_GREEN,
              }}
            >
              <ArrowUpTrayIcon className="w-3.5 h-3.5" />
              UPLOAD
            </Link>
          </div>

          {/* Search & Filters */}
          <div className="p-4 border-b" style={{ borderColor: '#21262d' }}>
            <div className="flex flex-col md:flex-row gap-3">
              {/* Search Input */}
              <div className="flex-1 relative">
                <MagnifyingGlassIcon
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                  style={{ color: PHOSPHOR_GREEN }}
                />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search documents..."
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg font-mono text-sm bg-transparent outline-none transition-all"
                  style={{
                    border: `1px solid #21262d`,
                    color: '#e6edf3',
                  }}
                />
              </div>

              {/* Status Filter */}
              <div className="relative">
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-mono text-xs transition-all"
                  style={{
                    background: '#161b22',
                    border: `1px solid #21262d`,
                    color: '#e6edf3',
                  }}
                >
                  <FunnelIcon className="w-4 h-4" />
                  {statusFilter === 'all' ? 'ALL STATUS' : statusFilter.toUpperCase()}
                  <ChevronDownIcon className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
                </button>

                <AnimatePresence>
                  {showFilters && (
                    <motion.div
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="absolute right-0 mt-2 w-40 rounded-lg overflow-hidden z-20"
                      style={{
                        background: '#161b22',
                        border: `1px solid #21262d`,
                      }}
                    >
                      {['all', 'completed', 'processing', 'pending', 'failed'].map((status) => (
                        <button
                          key={status}
                          onClick={() => {
                            setStatusFilter(status);
                            setShowFilters(false);
                          }}
                          className={`w-full px-4 py-2 text-left font-mono text-xs transition-all hover:bg-white/5 ${
                            statusFilter === status ? 'text-[#00ff9f]' : 'text-gray-400'
                          }`}
                        >
                          {status.toUpperCase()}
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>

          {/* Documents List */}
          <div className="p-4">
            {filteredDocuments.length === 0 ? (
              <div className="text-center py-12">
                <DocumentTextIcon className="w-12 h-12 mx-auto mb-4 text-gray-600" />
                <p className="text-gray-500 font-mono text-sm">No documents found</p>
                <Link
                  href="/documents/upload"
                  className="inline-flex items-center gap-2 mt-4 px-4 py-2 rounded-lg font-mono text-sm"
                  style={{
                    background: `${PHOSPHOR_GREEN}15`,
                    border: `1px solid ${PHOSPHOR_GREEN}30`,
                    color: PHOSPHOR_GREEN,
                  }}
                >
                  <ArrowUpTrayIcon className="w-4 h-4" />
                  Upload your first document
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredDocuments.map((doc, index) => {
                  const fileType = getFileTypeIcon(doc.file_type);
                  const status = getStatusConfig(doc.status);
                  const StatusIcon = status.icon;

                  return (
                    <motion.div
                      key={doc.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="group rounded-lg p-4 transition-all hover:bg-white/[0.02]"
                      style={{
                        background: '#161b22',
                        border: '1px solid #21262d',
                      }}
                    >
                      <div className="flex items-center gap-4">
                        {/* File Icon */}
                        <div
                          className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-xl"
                          style={{
                            background: `${fileType.color}15`,
                          }}
                        >
                          {fileType.icon}
                        </div>

                        {/* Document Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="font-mono text-sm text-gray-200 truncate">
                              {doc.title}
                            </h3>
                            {doc.entities_count && (
                              <span
                                className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono"
                                style={{
                                  background: `${AMBER}15`,
                                  color: AMBER,
                                }}
                              >
                                <SparklesIcon className="w-3 h-3" />
                                {doc.entities_count}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-xs font-mono text-gray-500">
                            <span>{doc.filename}</span>
                            <span>•</span>
                            <span>{formatFileSize(doc.file_size)}</span>
                            <span>•</span>
                            <span>{formatDate(doc.created_at)}</span>
                          </div>
                          {doc.tags.length > 0 && (
                            <div className="flex items-center gap-1 mt-2">
                              {doc.tags.map((tag) => (
                                <span
                                  key={tag}
                                  className="px-2 py-0.5 rounded text-xs font-mono"
                                  style={{
                                    background: '#21262d',
                                    color: '#8b949e',
                                  }}
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Status Badge */}
                        <div
                          className="flex items-center gap-1.5 px-2.5 py-1 rounded font-mono text-xs"
                          style={{
                            background: `${status.color}15`,
                            color: status.color,
                          }}
                        >
                          <StatusIcon className={`w-3.5 h-3.5 ${doc.status === 'processing' ? 'animate-spin' : ''}`} />
                          {status.label}
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                            title="View document"
                          >
                            <EyeIcon className="w-4 h-4 text-gray-400 hover:text-white" />
                          </button>
                          <button
                            className="p-2 rounded-lg hover:bg-white/10 transition-colors"
                            title="Download"
                          >
                            <DocumentArrowDownIcon className="w-4 h-4 text-gray-400 hover:text-white" />
                          </button>
                          <button
                            className="p-2 rounded-lg hover:bg-red-500/20 transition-colors"
                            title="Delete"
                          >
                            <TrashIcon className="w-4 h-4 text-gray-400 hover:text-red-400" />
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
