import React from 'react';
import { useState } from 'react';
import {
  PlusIcon,
  PlayIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  DocumentTextIcon,
  ChartBarIcon,
  CogIcon,
  EyeIcon,
  TrashIcon,
  ArrowPathIcon,
  FunnelIcon,
  CalendarIcon,
} from '@heroicons/react/24/outline';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils';
import {
  useEvaluations,
  useCreateEvaluation,
  useRunEvaluation,
  useDeleteEvaluation,
} from '@/hooks/useEvaluation';
import type { Evaluation as EvaluationType } from '@/types';

export const EvaluationManagement: React.FC = () => {
  const [selectedEvaluation, setSelectedEvaluation] = useState<string | null>(
    null
  );
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const { data: evaluations, isLoading, error } = useEvaluations();
  const createEvaluationMutation = useCreateEvaluation();
  const runEvaluationMutation = useRunEvaluation();
  const deleteEvaluationMutation = useDeleteEvaluation();

  const handleCreateEvaluation = async (data: {
    name: string;
    description: string;
    dataset_id: string;
    evaluation_type: string;
  }) => {
    try {
      await createEvaluationMutation.mutateAsync({
        name: data.name,
        description: data.description,
        dataset_id: data.dataset_id,
        evaluation_type: data.evaluation_type as any,
        config: {
          metrics: ['answer_relevancy', 'faithfulness', 'contextual_relevancy'],
          thresholds: {
            answer_relevancy: 70,
            faithfulness: 90,
            contextual_relevancy: 70,
          },
        },
      });
      setShowCreateDialog(false);
    } catch (error) {
      console.error('Failed to create evaluation:', error);
    }
  };

  const handleRunEvaluation = async (evaluationId: string) => {
    try {
      await runEvaluationMutation.mutateAsync(evaluationId);
    } catch (error) {
      console.error('Failed to run evaluation:', error);
    }
  };

  const handleDeleteEvaluation = async (evaluationId: string) => {
    if (window.confirm('Are you sure you want to delete this evaluation?')) {
      try {
        await deleteEvaluationMutation.mutateAsync(evaluationId);
      } catch (error) {
        console.error('Failed to delete evaluation:', error);
      }
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return CheckCircleIcon;
      case 'running':
        return ArrowPathIcon;
      case 'failed':
        return ExclamationTriangleIcon;
      default:
        return ClockIcon;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-[var(--nous-terra)] bg-[var(--nous-terra)]/10';
      case 'running':
        return 'text-primary bg-primary/10';
      case 'failed':
        return 'text-[var(--nous-mars)] bg-[var(--nous-mars)]/10';
      default:
        return 'text-foreground bg-muted';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'rag_triad':
        return ChartBarIcon;
      case 'performance':
        return ClockIcon;
      case 'quality':
        return CheckCircleIcon;
      default:
        return DocumentTextIcon;
    }
  };

  const filteredEvaluations =
    evaluations?.filter((evaluation) => {
      const matchesStatus =
        filterStatus === 'all' || evaluation.status === filterStatus;
      const matchesType =
        filterType === 'all' || evaluation.evaluation_type === filterType;
      const matchesSearch =
        evaluation.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        evaluation.description
          ?.toLowerCase()
          .includes(searchQuery.toLowerCase());
      return matchesStatus && matchesType && matchesSearch;
    }) || [];

  const evaluationStats = {
    total: evaluations?.length || 0,
    completed: evaluations?.filter((e) => e.status === 'completed').length || 0,
    running: evaluations?.filter((e) => e.status === 'running').length || 0,
    failed: evaluations?.filter((e) => e.status === 'failed').length || 0,
  };

  if (error) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center text-[var(--nous-mars)]" role="alert">
            <ExclamationTriangleIcon
              className="h-12 w-12 mx-auto mb-4"
              aria-hidden="true"
            />
            <h3 className="text-lg font-medium mb-2">
              Error Loading Evaluations
            </h3>
            <p className="text-sm">
              Failed to load evaluations. Please try again.
            </p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => window.location.reload()}
            >
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Evaluation Management
          </h1>
          <p className="text-foreground mt-1">
            Create, manage, and run system evaluations
          </p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogTrigger asChild>
            <Button>
              <PlusIcon className="h-4 w-4 mr-2" aria-hidden="true" />
              New Evaluation
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Create New Evaluation</DialogTitle>
            </DialogHeader>
            <CreateEvaluationForm
              onSubmit={handleCreateEvaluation}
              onCancel={() => setShowCreateDialog(false)}
            />
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">
                  Total Evaluations
                </p>
                <p className="text-2xl font-bold">{evaluationStats.total}</p>
              </div>
              <DocumentTextIcon
                className="h-8 w-8 text-muted-foreground"
                aria-hidden="true"
              />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Completed</p>
                <p className="text-2xl font-bold text-[var(--nous-terra)]">
                  {evaluationStats.completed}
                </p>
              </div>
              <CheckCircleIcon
                className="h-8 w-8 text-[var(--nous-terra)]"
                aria-hidden="true"
              />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Running</p>
                <p className="text-2xl font-bold text-primary">
                  {evaluationStats.running}
                </p>
              </div>
              <ArrowPathIcon
                className="h-8 w-8 text-primary"
                aria-hidden="true"
              />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">Failed</p>
                <p className="text-2xl font-bold text-[var(--nous-mars)]">
                  {evaluationStats.failed}
                </p>
              </div>
              <ExclamationTriangleIcon
                className="h-8 w-8 text-[var(--nous-mars)]"
                aria-hidden="true"
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search evaluations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full"
              />
            </div>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-full md:w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="completed">Completed</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
              </SelectContent>
            </Select>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-full md:w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="rag_triad">RAG Triad</SelectItem>
                <SelectItem value="performance">Performance</SelectItem>
                <SelectItem value="quality">Quality</SelectItem>
                <SelectItem value="comprehensive">Comprehensive</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Evaluations List */}
      <Card>
        <CardHeader>
          <CardTitle>Evaluations ({filteredEvaluations.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center h-32">
              <Spinner size="lg" className="text-primary" />
            </div>
          ) : filteredEvaluations.length === 0 ? (
            <div className="text-center py-12">
              <DocumentTextIcon
                className="h-12 w-12 text-muted-foreground mx-auto mb-4"
                aria-hidden="true"
              />
              <h3 className="text-lg font-medium text-foreground mb-2">
                No evaluations found
              </h3>
              <p className="text-foreground mb-4">
                {searchQuery || filterStatus !== 'all' || filterType !== 'all'
                  ? 'Try adjusting your filters or search query'
                  : 'Get started by creating your first evaluation'}
              </p>
              {!searchQuery &&
                filterStatus === 'all' &&
                filterType === 'all' && (
                  <Button onClick={() => setShowCreateDialog(true)}>
                    <PlusIcon className="h-4 w-4 mr-2" aria-hidden="true" />
                    Create Evaluation
                  </Button>
                )}
            </div>
          ) : (
            <div className="space-y-4">
              {filteredEvaluations.map((evaluation) => {
                const StatusIcon = getStatusIcon(evaluation.status);
                const TypeIcon = getTypeIcon(evaluation.evaluation_type);

                return (
                  <div
                    key={evaluation.id}
                    className={cn(
                      'border rounded-lg p-4 hover:bg-muted transition-colors',
                      selectedEvaluation === evaluation.id &&
                        'border-primary bg-primary/5'
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          {React.createElement(TypeIcon, {
                            className: 'h-5 w-5 text-muted-foreground',
                            'aria-hidden': 'true',
                          })}
                          <h3 className="text-lg font-medium text-foreground">
                            {evaluation.name}
                          </h3>
                          <Badge className={getStatusColor(evaluation.status)}>
                            {React.createElement(StatusIcon, {
                              className: 'h-3 w-3 mr-1',
                              'aria-hidden': 'true',
                            })}
                            {evaluation.status}
                          </Badge>
                          <Badge variant="outline" className="capitalize">
                            {evaluation.evaluation_type.replace('_', ' ')}
                          </Badge>
                        </div>
                        {evaluation.description && (
                          <p className="text-foreground mb-3">
                            {evaluation.description}
                          </p>
                        )}
                        <div className="flex items-center space-x-6 text-sm text-muted-foreground">
                          <div className="flex items-center">
                            <CalendarIcon
                              className="h-4 w-4 mr-1"
                              aria-hidden="true"
                            />
                            Created{' '}
                            {new Date(
                              evaluation.created_at
                            ).toLocaleDateString()}
                          </div>
                          {evaluation.last_run && (
                            <div className="flex items-center">
                              <ClockIcon
                                className="h-4 w-4 mr-1"
                                aria-hidden="true"
                              />
                              Last run{' '}
                              {new Date(
                                evaluation.last_run.started_at
                              ).toLocaleDateString()}
                            </div>
                          )}
                          {evaluation.last_run?.results_summary && (
                            <div className="flex items-center">
                              <ChartBarIcon
                                className="h-4 w-4 mr-1"
                                aria-hidden="true"
                              />
                              Score:{' '}
                              {evaluation.last_run.results_summary.average_score.toFixed(
                                1
                              )}
                              % ({evaluation.last_run.results_summary.pass_rate}
                              % pass rate)
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2 ml-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedEvaluation(evaluation.id)}
                          aria-label="View evaluation"
                        >
                          <EyeIcon className="h-4 w-4" aria-hidden="true" />
                        </Button>
                        {evaluation.status !== 'running' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRunEvaluation(evaluation.id)}
                            disabled={runEvaluationMutation.isPending}
                            aria-label="Run evaluation"
                          >
                            <PlayIcon className="h-4 w-4" aria-hidden="true" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteEvaluation(evaluation.id)}
                          disabled={deleteEvaluationMutation.isPending}
                          aria-label="Delete evaluation"
                        >
                          <TrashIcon className="h-4 w-4" aria-hidden="true" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

// Create Evaluation Form Component
interface CreateEvaluationFormProps {
  onSubmit: (data: {
    name: string;
    description: string;
    dataset_id: string;
    evaluation_type: string;
  }) => void;
  onCancel: () => void;
}

const CreateEvaluationForm: React.FC<CreateEvaluationFormProps> = ({
  onSubmit,
  onCancel,
}) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    dataset_id: '',
    evaluation_type: '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.name && formData.dataset_id && formData.evaluation_type) {
      onSubmit(formData);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">
          Name *
        </label>
        <Input
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="Enter evaluation name"
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">
          Description
        </label>
        <Input
          value={formData.description}
          onChange={(e) =>
            setFormData({ ...formData, description: e.target.value })
          }
          placeholder="Enter evaluation description"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">
          Dataset *
        </label>
        <Select
          value={formData.dataset_id}
          onValueChange={(value) =>
            setFormData({ ...formData, dataset_id: value })
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="Select dataset" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="dataset-1">Sample Dataset 1</SelectItem>
            <SelectItem value="dataset-2">Sample Dataset 2</SelectItem>
            <SelectItem value="dataset-3">Sample Dataset 3</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div>
        <label className="block text-sm font-medium text-foreground mb-1">
          Evaluation Type *
        </label>
        <Select
          value={formData.evaluation_type}
          onValueChange={(value) =>
            setFormData({ ...formData, evaluation_type: value })
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="Select evaluation type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="rag_triad">RAG Triad</SelectItem>
            <SelectItem value="performance">Performance</SelectItem>
            <SelectItem value="quality">Quality</SelectItem>
            <SelectItem value="comprehensive">Comprehensive</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">Create Evaluation</Button>
      </div>
    </form>
  );
};

export default EvaluationManagement;
