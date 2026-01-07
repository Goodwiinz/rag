/**
 * Document Progress Visualizer Components
 *
 * Specialized components for visualizing multi-stage document processing
 * progress with file-type specific stages and animations.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  DocumentTextIcon,
  PhotoIcon,
  FilmIcon,
  MusicalNoteIcon,
  QueueListIcon,
  CpuChipIcon,
  CircleStackIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClockIcon,
  ArrowPathIcon,
  PauseIcon,
  PlayIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { DocumentProcessingState, ProcessingStage } from '@/types/realtime-processing';
import { cn } from '@/lib/utils';
import { formatDuration, formatFileSize } from '@/utils/formatUtils';

interface DocumentProgressVisualizerProps {
  document: DocumentProcessingState;
  compact?: boolean;
  showDetails?: boolean;
  showTimeline?: boolean;
  animated?: boolean;
  className?: string;
}

interface StageIconProps {
  stage: ProcessingStage;
  isActive: boolean;
  isCompleted: boolean;
  hasError: boolean;
  size?: 'sm' | 'md' | 'lg';
}

interface TimelineProps {
  stages: ProcessingStage[];
  currentStage: ProcessingStage;
  compact?: boolean;
}

interface FileTypeInfoProps {
  fileType: DocumentProcessingState['fileType'];
  metadata: DocumentProcessingState['metadata'];
}

interface ProgressBarProps {
  progress: number;
  showPercentage?: boolean;
  animated?: boolean;
  size?: 'sm' | 'md' | 'lg';
  color?: 'blue' | 'green' | 'yellow' | 'red';
}

interface StageDetailsProps {
  stage: ProcessingStage;
  isActive: boolean;
  isCompleted: boolean;
  showDuration?: boolean;
}

// File type configurations with stage definitions
const fileTypeConfigs = {
  pdf: {
    icon: DocumentTextIcon,
    label: 'PDF Document',
    stages: [
      { id: 'upload', name: 'Upload', description: 'Uploading file to server' },
      { id: 'validation', name: 'Validation', description: 'Validating PDF format' },
      { id: 'ocr', name: 'OCR Processing', description: 'Extracting text from images' },
      { id: 'parsing', name: 'Content Parsing', description: 'Parsing document structure' },
      { id: 'embedding', name: 'Vector Embedding', description: 'Creating vector embeddings' },
      { id: 'indexing', name: 'Indexing', description: 'Indexing in search engine' },
      { id: 'completed', name: 'Completed', description: 'Processing complete' },
    ],
    color: 'text-red-500',
  },
  txt: {
    icon: DocumentTextIcon,
    label: 'Text Document',
    stages: [
      { id: 'upload', name: 'Upload', description: 'Uploading file to server' },
      { id: 'validation', name: 'Validation', description: 'Validating text format' },
      { id: 'parsing', name: 'Content Parsing', description: 'Parsing text content' },
      { id: 'chunking', name: 'Text Chunking', description: 'Splitting into chunks' },
      { id: 'embedding', name: 'Vector Embedding', description: 'Creating vector embeddings' },
      { id: 'indexing', name: 'Indexing', description: 'Indexing in search engine' },
      { id: 'completed', name: 'Completed', description: 'Processing complete' },
    ],
    color: 'text-blue-500',
  },
  jpg: {
    icon: PhotoIcon,
    label: 'Image Document',
    stages: [
      { id: 'upload', name: 'Upload', description: 'Uploading file to server' },
      { id: 'validation', name: 'Validation', description: 'Validating image format' },
      { id: 'ocr', name: 'OCR Processing', description: 'Extracting text from image' },
      { id: 'analysis', name: 'Image Analysis', description: 'Analyzing image content' },
      { id: 'embedding', name: 'Vector Embedding', description: 'Creating vector embeddings' },
      { id: 'indexing', name: 'Indexing', description: 'Indexing in search engine' },
      { id: 'completed', name: 'Completed', description: 'Processing complete' },
    ],
    color: 'text-green-500',
  },
  png: {
    icon: PhotoIcon,
    label: 'Image Document',
    stages: [
      { id: 'upload', name: 'Upload', description: 'Uploading file to server' },
      { id: 'validation', name: 'Validation', description: 'Validating image format' },
      { id: 'ocr', name: 'OCR Processing', description: 'Extracting text from image' },
      { id: 'analysis', name: 'Image Analysis', description: 'Analyzing image content' },
      { id: 'embedding', name: 'Vector Embedding', description: 'Creating vector embeddings' },
      { id: 'indexing', name: 'Indexing', description: 'Indexing in search engine' },
      { id: 'completed', name: 'Completed', description: 'Processing complete' },
    ],
    color: 'text-green-500',
  },
  mp3: {
    icon: MusicalNoteIcon,
    label: 'Audio Document',
    stages: [
      { id: 'upload', name: 'Upload', description: 'Uploading file to server' },
      { id: 'validation', name: 'Validation', description: 'Validating audio format' },
      { id: 'transcription', name: 'Transcription', description: 'Transcribing audio to text' },
      { id: 'processing', name: 'Audio Processing', description: 'Processing audio features' },
      { id: 'embedding', name: 'Vector Embedding', description: 'Creating vector embeddings' },
      { id: 'indexing', name: 'Indexing', description: 'Indexing in search engine' },
      { id: 'completed', name: 'Completed', description: 'Processing complete' },
    ],
    color: 'text-purple-500',
  },
  mp4: {
    icon: FilmIcon,
    label: 'Video Document',
    stages: [
      { id: 'upload', name: 'Upload', description: 'Uploading file to server' },
      { id: 'validation', name: 'Validation', description: 'Validating video format' },
      { id: 'frame_extraction', name: 'Frame Extraction', description: 'Extracting video frames' },
      { id: 'audio_extraction', name: 'Audio Extraction', description: 'Extracting audio track' },
      { id: 'transcription', name: 'Transcription', description: 'Transcribing audio to text' },
      { id: 'analysis', name: 'Content Analysis', description: 'Analyzing video content' },
      { id: 'embedding', name: 'Vector Embedding', description: 'Creating vector embeddings' },
      { id: 'indexing', name: 'Indexing', description: 'Indexing in search engine' },
      { id: 'completed', name: 'Completed', description: 'Processing complete' },
    ],
    color: 'text-orange-500',
  },
} as const;

// Helper Components
const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  showPercentage = true,
  animated = true,
  size = 'md',
  color = 'blue'
}) => {
  const sizeClasses = {
    sm: 'h-1',
    md: 'h-2',
    lg: 'h-3',
  };

  const colorClasses = {
    blue: 'bg-blue-500',
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
  };

  return (
    <div className="w-full">
      <div className={cn(
        'bg-gray-200 rounded-full overflow-hidden',
        sizeClasses[size]
      )}>
        <motion.div
          className={cn(
            'h-full rounded-full',
            colorClasses[color]
          )}
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: animated ? 0.5 : 0 }}
        />
      </div>
      {showPercentage && (
        <div className="mt-1 text-xs text-gray-600 text-right">
          {Math.round(progress)}%
        </div>
      )}
    </div>
  );
};

const StageIcon: React.FC<StageIconProps> = ({
  stage,
  isActive,
  isCompleted,
  hasError,
  size = 'md'
}) => {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-8 h-8',
    lg: 'w-10 h-10',
  };

  const iconSizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  };

  const getStageIcon = (stageId: string) => {
    switch (stageId) {
      case 'upload':
      case 'validation':
        return QueueListIcon;
      case 'ocr':
      case 'transcription':
      case 'frame_extraction':
      case 'audio_extraction':
        return CpuChipIcon;
      case 'parsing':
      case 'chunking':
      case 'analysis':
      case 'processing':
        return DocumentTextIcon;
      case 'embedding':
        return CircleStackIcon;
      case 'indexing':
        return CircleStackIcon;
      case 'completed':
        return CheckCircleIcon;
      default:
        return ClockIcon;
    }
  };

  const Icon = getStageIcon(stage.id);

  return (
    <div className={cn(
      'relative flex items-center justify-center rounded-full border-2',
      sizeClasses[size],
      isCompleted ? 'border-green-500 bg-green-500' :
      hasError ? 'border-red-500 bg-red-500' :
      isActive ? 'border-blue-500 bg-blue-500' : 'border-gray-300 bg-white'
    )}>
      <AnimatePresence mode="wait">
        {isCompleted ? (
          <motion.div
            key="check"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            className="text-white"
          >
            <svg className={iconSizeClasses[size]} fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          </motion.div>
        ) : hasError ? (
          <motion.div
            key="error"
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            className="text-white"
          >
            <ExclamationTriangleIcon className={iconSizeClasses[size]} />
          </motion.div>
        ) : isActive ? (
          <motion.div
            key="active"
            animate={{ rotate: 360 }}
            transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          >
            <Icon className={cn(iconSizeClasses[size], 'text-white')} />
          </motion.div>
        ) : (
          <Icon className={cn(iconSizeClasses[size], 'text-gray-400')} />
        )}
      </AnimatePresence>

      {isActive && (
        <motion.div
          className="absolute inset-0 rounded-full border-2 border-blue-300"
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
      )}
    </div>
  );
};

const Timeline: React.FC<TimelineProps> = ({ stages, currentStage, compact = false }) => {
  const currentIndex = stages.findIndex(s => s.id === currentStage.id);

  return (
    <div className="relative">
      {/* Timeline line */}
      <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-gray-200 -translate-y-1/2" />

      {/* Stage nodes */}
      <div className="relative flex justify-between">
        {stages.map((stage, index) => {
          const isActive = stage.id === currentStage.id;
          const isCompleted = stage.status === 'completed';
          const hasError = stage.status === 'failed';

          return (
            <div key={stage.id} className="relative flex flex-col items-center">
              <StageIcon
                stage={stage}
                isActive={isActive}
                isCompleted={isCompleted}
                hasError={hasError}
                size={compact ? 'sm' : 'md'}
              />

              {!compact && (
                <div className="mt-2 text-center">
                  <div className="text-xs font-medium text-gray-900">
                    {stage.name}
                  </div>
                  {isActive && (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="text-xs text-blue-600 mt-1"
                    >
                      {stage.progress}% complete
                    </motion.div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const FileTypeInfo: React.FC<FileTypeInfoProps> = ({ fileType, metadata }) => {
  const config = fileTypeConfigs[fileType];
  const Icon = config.icon;

  return (
    <div className="flex items-center space-x-3">
      <div className={cn('p-2 rounded-lg bg-gray-100', config.color)}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <div className="text-sm font-medium text-gray-900">
          {config.label}
        </div>
        <div className="text-xs text-gray-500">
          {formatFileSize(metadata.fileSize)}
          {metadata.pageCount && ` • ${metadata.pageCount} pages`}
          {metadata.duration && ` • ${formatDuration(metadata.duration)}`}
        </div>
      </div>
    </div>
  );
};

const StageDetails: React.FC<StageDetailsProps> = ({
  stage,
  isActive,
  isCompleted,
  showDuration = true
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        'p-3 rounded-lg border',
        'border-gray-200',
        isActive ? 'bg-blue-50 border-blue-200' :
        isCompleted ? 'bg-green-50 border-green-200' : 'bg-gray-50'
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2">
            <h4 className="text-sm font-medium text-gray-900">
              {stage.name}
            </h4>
            {isActive && (
              <motion.div
                className="w-2 h-2 bg-blue-500 rounded-full"
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 1, repeat: Infinity }}
              />
            )}
          </div>
          <p className="text-xs text-gray-600 mt-1">
            {stage.description}
          </p>
          {stage.error && (
            <p className="text-xs text-red-600 mt-1">
              Error: {stage.error}
            </p>
          )}
        </div>
        <div className="text-right">
          <div className="text-sm font-medium text-gray-900">
            {stage.progress}%
          </div>
          {showDuration && stage.duration && (
            <div className="text-xs text-gray-500">
              {formatDuration(stage.duration)}
            </div>
          )}
        </div>
      </div>

      {isActive && stage.progress > 0 && (
        <div className="mt-2">
          <ProgressBar
            progress={stage.progress}
            showPercentage={false}
            size="sm"
            color="blue"
          />
        </div>
      )}
    </motion.div>
  );
};

// Main Component
export const DocumentProgressVisualizer: React.FC<DocumentProgressVisualizerProps> = ({
  document,
  compact = false,
  showDetails = true,
  showTimeline = true,
  animated = true,
  className
}) => {
  const [expandedStage, setExpandedStage] = useState<string | null>(null);
  const config = fileTypeConfigs[document.fileType];

  // Get file type specific stages
  const fileTypeStages = useMemo(() => {
    return config.stages.map(stageDef => {
      const stage = document.stages.find(s => s.id === stageDef.id);
      return {
        id: stageDef.id,
        name: stageDef.name,
        description: stageDef.description,
        progress: stage?.progress || 0,
        status: stage?.status || 'pending',
        startedAt: stage?.startedAt,
        completedAt: stage?.completedAt,
        duration: stage?.duration,
        error: stage?.error,
      } as ProcessingStage;
    });
  }, [document.stages, document.fileType]);

  const currentStageIndex = fileTypeStages.findIndex(s => s.id === document.currentStage.id);
  const overallProgress = document.overallProgress;

  return (
    <div className={cn(
      'bg-white rounded-lg border border-gray-200 shadow-sm',
      className
    )}>
      {/* Header */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <FileTypeInfo
            fileType={document.fileType}
            metadata={document.metadata}
          />
          <div className="text-right">
            <div className="text-lg font-semibold text-gray-900">
              {overallProgress}%
            </div>
            <div className="text-xs text-gray-500">
              {document.currentStage.name}
            </div>
          </div>
        </div>

        {/* Overall Progress */}
        <div className="mt-3">
          <ProgressBar
            progress={overallProgress}
            animated={animated}
            color={document.status === 'failed' ? 'red' : 'blue'}
          />
        </div>
      </div>

      {/* Timeline */}
      {showTimeline && (
        <div className="p-4 border-b border-gray-200">
          <Timeline
            stages={fileTypeStages}
            currentStage={document.currentStage}
            compact={compact}
          />
        </div>
      )}

      {/* Stage Details */}
      {showDetails && (
        <div className="p-4">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">
            Processing Stages
          </h3>
          <div className="space-y-2">
            {fileTypeStages.map((stage, index) => {
              const isActive = stage.id === document.currentStage.id;
              const isCompleted = stage.status === 'completed';
              const isExpanded = expandedStage === stage.id;

              return (
                <div key={stage.id}>
                  <motion.div
                    className="cursor-pointer"
                    onClick={() => setExpandedStage(isExpanded ? null : stage.id)}
                  >
                    <StageDetails
                      stage={stage}
                      isActive={isActive}
                      isCompleted={isCompleted}
                    />
                  </motion.div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <div>
            Started: {new Date(document.metadata.uploadStartedAt).toLocaleTimeString()}
          </div>
          {document.metadata.estimatedTimeRemaining && (
            <div>
              Est. remaining: {formatDuration(document.metadata.estimatedTimeRemaining)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DocumentProgressVisualizer;