/**
 * Document Progress Visualizer
 * Interactive timeline component showing multi-stage document processing progress
 */

'use client';

import React, { useMemo } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  CheckCircle,
  Clock,
  Loader2,
  XCircle,
  AlertCircle,
  Play,
  Pause,
  Square,
  FileText,
  Image,
  Film,
  Music,
  Headphones,
} from 'lucide-react';

import {
  DocumentProcessingState,
  ProcessingStage,
  EnhancedProcessingStage,
} from '@/types/realtime-processing';
import {
  formatDuration,
  formatFileSize,
  formatRelativeTime,
} from '@/lib/format-utils';

interface DocumentProgressVisualizerProps {
  document: DocumentProcessingState;
  showDetails?: boolean;
  interactive?: boolean;
  compact?: boolean;
  className?: string;
}

export const DocumentProgressVisualizer: React.FC<
  DocumentProgressVisualizerProps
> = ({
  document,
  showDetails = true,
  interactive = false,
  compact = false,
  className = '',
}) => {
  const stages = useMemo((): ProcessingStage[] => {
    // Ensure stages are properly ordered
    return [...document.stages].sort((a, b) => {
      if ('stage_order' in a && 'stage_order' in b) {
        return (
          (a as EnhancedProcessingStage).stage_order -
          (b as EnhancedProcessingStage).stage_order
        );
      }
      return 0;
    });
  }, [document.stages]);

  const getStageIcon = (stage: ProcessingStage) => {
    switch (stage.status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'in_progress':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'skipped':
        return <Square className="h-4 w-4 text-muted-foreground" />;
      case 'cancelled':
        return <XCircle className="h-4 w-4 text-orange-500" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStageStatusColor = (stage: ProcessingStage) => {
    switch (stage.status) {
      case 'completed':
        return 'border-green-500 bg-green-50';
      case 'in_progress':
        return 'border-blue-500 bg-blue-50';
      case 'failed':
        return 'border-red-500 bg-red-50';
      case 'skipped':
        return 'border-border bg-gray-50';
      case 'cancelled':
        return 'border-orange-500 bg-orange-50';
      default:
        return 'border-border bg-gray-50';
    }
  };

  const getFileTypeIcon = (fileType: string) => {
    switch (fileType.toLowerCase()) {
      case 'pdf':
        return <FileText className="h-4 w-4 text-red-500" />;
      case 'jpg':
      case 'png':
      case 'jpeg':
        return <Image className="h-4 w-4 text-blue-500" />;
      case 'mp4':
      case 'avi':
      case 'mov':
        return <Film className="h-4 w-4 text-purple-500" />;
      case 'mp3':
      case 'wav':
        return <Music className="h-4 w-4 text-green-500" />;
      case 'txt':
      case 'md':
        return <FileText className="h-4 w-4 text-muted-foreground" />;
      default:
        return <FileText className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusBadgeVariant = (status: ProcessingStage['status']) => {
    switch (status) {
      case 'completed':
        return 'default';
      case 'in_progress':
        return 'secondary';
      case 'failed':
        return 'destructive';
      case 'skipped':
        return 'outline';
      case 'cancelled':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const getDocumentStatusBadgeVariant = (
    status: DocumentProcessingState['status']
  ) => {
    switch (status) {
      case 'completed':
        return 'default';
      case 'processing':
      case 'uploading':
        return 'secondary';
      case 'failed':
        return 'destructive';
      case 'queued':
      case 'paused':
        return 'outline';
      case 'cancelled':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const calculateStageProgress = (stage: ProcessingStage) => {
    if (stage.status === 'completed') return 100;
    if (
      stage.status === 'failed' ||
      stage.status === 'skipped' ||
      stage.status === 'cancelled'
    )
      return 0;
    return stage.progress || 0;
  };

  const calculateOverallProgress = () => {
    if (stages.length === 0) return document.overallProgress;

    // Weight stages by their progress weight or equal weighting if not specified
    const totalWeight = stages.reduce((sum: number, stage: ProcessingStage) => {
      const weight =
        (stage as EnhancedProcessingStage & { progressWeight?: number })
          .progressWeight || 1;
      return sum + weight;
    }, 0);

    const weightedProgress = stages.reduce(
      (sum: number, stage: ProcessingStage) => {
        const weight =
          (stage as EnhancedProcessingStage & { progressWeight?: number })
            .progressWeight || 1;
        const progress = calculateStageProgress(stage);
        return sum + progress * weight;
      },
      0
    );

    return Math.round(weightedProgress / totalWeight);
  };

  const renderTimeline = () => (
    <div className="relative">
      {/* Timeline line */}
      <div className="absolute left-0 top-8 bottom-0 w-0.5 bg-gray-200" />

      {/* Stages */}
      <div className="relative flex justify-between">
        {stages.map((stage: ProcessingStage, index: number) => (
          <div
            key={stage.id}
            className={`relative flex flex-col items-center ${compact ? 'w-12' : 'w-16'}`}
          >
            {/* Stage indicator */}
            <div
              className={`w-8 h-8 rounded-full border-2 flex items-center justify-center transition-all duration-200 ${getStageStatusColor(
                stage
              )}`}
            >
              {getStageIcon(stage)}
            </div>

            {/* Stage name */}
            <p
              className={`text-xs font-medium mt-2 text-center ${
                compact ? 'hidden' : 'block'
              }`}
            >
              {stage.name}
            </p>

            {/* Status badge */}
            {!compact && (
              <Badge
                variant={getStatusBadgeVariant(stage.status)}
                className="mt-2"
              >
                {stage.status.replace('_', ' ')}
              </Badge>
            )}

            {/* Progress indicator */}
            {stage.status === 'in_progress' && (
              <div className="w-full mt-2">
                <Progress
                  value={calculateStageProgress(stage)}
                  className="h-1"
                />
                <p className="text-xs text-muted-foreground text-center mt-1">
                  {calculateStageProgress(stage)}%
                </p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );

  const renderDetailedStages = () => (
    <div className="space-y-4">
      {stages.map((stage: ProcessingStage, index: number) => (
        <Card key={stage.id} className="transition-all duration-200">
          <CardContent className="p-4">
            <div className="flex items-start gap-4">
              {/* Stage icon and status */}
              <div
                className={`w-10 h-10 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${getStageStatusColor(stage)}`}
              >
                {getStageIcon(stage)}
              </div>

              {/* Stage details */}
              <div className="flex-1 space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">{stage.name}</h4>
                    <p className="text-sm text-muted-foreground">
                      {stage.description}
                    </p>
                  </div>
                  <Badge variant={getStatusBadgeVariant(stage.status)}>
                    {stage.status.replace('_', ' ').toUpperCase()}
                  </Badge>
                </div>

                {/* Progress */}
                {stage.status === 'in_progress' && (
                  <div className="space-y-1">
                    <Progress value={calculateStageProgress(stage)} />
                    <p className="text-xs text-muted-foreground">
                      {calculateStageProgress(stage)}% Complete
                    </p>
                  </div>
                )}

                {/* Time information */}
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  {stage.startedAt && (
                    <span>Started: {formatRelativeTime(stage.startedAt)}</span>
                  )}
                  {stage.completedAt && (
                    <span>
                      Completed: {formatRelativeTime(stage.completedAt)}
                    </span>
                  )}
                  {stage.duration && (
                    <span>Duration: {formatDuration(stage.duration)}</span>
                  )}
                </div>

                {/* Error information */}
                {stage.error && (
                  <div className="bg-red-50 border border-red-200 rounded-md p-2">
                    <p className="text-sm text-red-800">{stage.error}</p>
                  </div>
                )}

                {/* Stage metadata */}
                {stage.stage_metadata &&
                  Object.keys(stage.stage_metadata).length > 0 && (
                    <details className="text-xs">
                      <summary className="cursor-pointer font-medium">
                        Metadata
                      </summary>
                      <pre className="mt-2 text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                        {JSON.stringify(stage.stage_metadata, null, 2)}
                      </pre>
                    </details>
                  )}

                {/* Retry information */}
                {(stage as any).retry_count > 0 && (
                  <div className="text-xs text-orange-600">
                    Retries: {(stage as any).retry_count}/
                    {(stage as any).max_retries}
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );

  const renderCompactView = () => (
    <Card className="w-full">
      <CardContent className="p-4">
        <div className="flex items-center gap-4">
          {/* File icon */}
          <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
            {getFileTypeIcon(document.fileType)}
          </div>

          {/* File info */}
          <div className="flex-1 space-y-1">
            <div className="flex items-center justify-between">
              <h4 className="font-medium truncate">{document.filename}</h4>
              <Badge variant={getDocumentStatusBadgeVariant(document.status)}>
                {document.status.toUpperCase()}
              </Badge>
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <span>{formatFileSize(document.metadata.fileSize)}</span>
              <span>•</span>
              <span>{document.fileType.toUpperCase()}</span>
            </div>

            {/* Progress */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span>{document.currentStage.name}</span>
                <span>{document.overallProgress}%</span>
              </div>
              <Progress value={document.overallProgress} className="h-2" />
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {document.status === 'processing' && (
              <Button variant="outline" size="sm">
                <Pause className="h-4 w-4" />
              </Button>
            )}
            {document.actions.retry && document.status === 'failed' && (
              <Button variant="outline" size="sm">
                <Play className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Timeline */}
        <div className="mt-4">{renderTimeline()}</div>
      </CardContent>
    </Card>
  );

  const renderDetailedView = () => (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Processing Progress</CardTitle>
        <CardDescription>
          Multi-stage processing progress for {document.filename}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Overall progress */}
        <div>
          <div className="flex justify-between text-sm mb-2">
            <span>Overall Progress</span>
            <span>{calculateOverallProgress()}%</span>
          </div>
          <Progress value={calculateOverallProgress()} className="h-3" />
        </div>

        {/* Timeline */}
        <div>
          <h4 className="font-medium mb-4">Processing Timeline</h4>
          {renderTimeline()}
        </div>

        {/* Detailed stages */}
        {showDetails && renderDetailedStages()}
      </CardContent>
    </Card>
  );

  return (
    <div className={className}>
      {compact ? renderCompactView() : renderDetailedView()}
    </div>
  );
};

export default DocumentProgressVisualizer;
