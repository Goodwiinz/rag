import React, { useState } from 'react';
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
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { useEvaluations, useCreateEvaluation, useRunEvaluation, useDeleteEvaluation } from '@/hooks/useEvaluation';
import type { Evaluation as EvaluationType } from '@/types';

export const EvaluationManagement: React.FC = () => {
  const [selectedEvaluation, setSelectedEvaluation] = useState<string | null>(null);
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
        return 'text-green-600 bg-green-50';
      case 'running':
        return 'text-blue-600 bg-blue-50';
      case 'failed':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
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

  const filteredEvaluations = evaluations?.filter(evaluation => {
    const matchesStatus = filterStatus === 'all' || evaluation.status === filterStatus;
    const matchesType = filterType === 'all' || evaluation.evaluation_type === filterType;
    const matchesSearch = evaluation.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         (evaluation.description?.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesStatus && matchesType && matchesSearch;
  }) || [];

  const evaluationStats = {
    total: evaluations?.length || 0,
    completed: evaluations?.filter(e => e.status === 'completed').length || 0,
    running: evaluations?.filter(e => e.status === 'running').length || 0,
    failed: evaluations?.filter(e => e.status === 'failed').length || 0,
  };

  if (error) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="text-center text-red-600">
            <ExclamationTriangleIcon className="h-12 w-12 mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">Error Loading Evaluations</h3>
            <p className="text-sm">Failed to load evaluations. Please try again.</p>
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
          <h1 className="text-2xl font-bold text-gray-900">Evaluation Management</h1>
          <p className="text-gray-600 mt-1">Create, manage, and run system evaluations</p>
        </div>
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogTrigger asChild>
            <Button>
              <PlusIcon className="h-4 w-4 mr-2" />
              New Evaluation
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>Create New Evaluation</DialogTitle>
            </DialogHeader>
            <CreateEvaluationForm onSubmit={handleCreateEvaluation} onCancel={() => setShowCreateDialog(false)} />
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Evaluations</p>
                <p className="text-2xl font-bold">{evaluationStats.total}</p>
              </div>
              <DocumentTextIcon className="h-8 w-8 text-gray-400" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Completed</p>
                <p className="text-2xl font-bold text-green-600">{evaluationStats.completed}</p>
              </div>
              <CheckCircleIcon className="h-8 w-8 text-green-400" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Running</p>
                <p className="text-2xl font-bold text-blue-600">{evaluationStats.running}</p>
              </div>
              <ArrowPathIcon className="h-8 w-8 text-blue-400" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Failed</p>
                <p className="text-2xl font-bold text-red-600">{evaluationStats.failed}</p>
              </div>
              <ExclamationTriangleIcon className="h-8 w-8 text-red-400" />
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
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : filteredEvaluations.length === 0 ? (
            <div className="text-center py-12">
              <DocumentTextIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No evaluations found</h3>
              <p className="text-gray-600 mb-4">
                {searchQuery || filterStatus !== 'all' || filterType !== 'all'
                  ? 'Try adjusting your filters or search query'
                  : 'Get started by creating your first evaluation'}
              </p>
              {!searchQuery && filterStatus === 'all' && filterType === 'all' && (
                <Button onClick={() => setShowCreateDialog(true)}>
                  <PlusIcon className="h-4 w-4 mr-2" />
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
                      "border rounded-lg p-4 hover:bg-gray-50 transition-colors",
                      selectedEvaluation === evaluation.id && "border-blue-500 bg-blue-50"
                    )}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          {React.createElement(TypeIcon, { className: "h-5 w-5 text-gray-500" })}
                          <h3 className="text-lg font-medium text-gray-900">{evaluation.name}</h3>
                          <Badge className={getStatusColor(evaluation.status)}>
                            {React.createElement(StatusIcon, { className: "h-3 w-3 mr-1" })}
                            {evaluation.status}
                          </Badge>
                          <Badge variant="outline" className="capitalize">
                            {evaluation.evaluation_type.replace('_', ' ')}
                          </Badge>
                        </div>
                        {evaluation.description && (
                          <p className="text-gray-600 mb-3">{evaluation.description}</p>
                        )}
                        <div className="flex items-center space-x-6 text-sm text-gray-500">
                          <div className="flex items-center">
                            <CalendarIcon className="h-4 w-4 mr-1" />
                            Created {new Date(evaluation.created_at).toLocaleDateString()}
                          </div>
                          {evaluation.last_run && (
                            <div className="flex items-center">
                              <ClockIcon className="h-4 w-4 mr-1" />
                              Last run {new Date(evaluation.last_run.started_at).toLocaleDateString()}
                            </div>
                          )}
                          {evaluation.last_run?.results_summary && (
                            <div className="flex items-center">
                              <ChartBarIcon className="h-4 w-4 mr-1" />
                              Score: {evaluation.last_run.results_summary.average_score.toFixed(1)}%
                              ({evaluation.last_run.results_summary.pass_rate}% pass rate)
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2 ml-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedEvaluation(evaluation.id)}
                        >
                          <EyeIcon className="h-4 w-4" />
                        </Button>
                        {evaluation.status !== 'running' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRunEvaluation(evaluation.id)}
                            disabled={runEvaluationMutation.isLoading}
                          >
                            <PlayIcon className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteEvaluation(evaluation.id)}
                          disabled={deleteEvaluationMutation.isLoading}
                        >
                          <TrashIcon className="h-4 w-4" />
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

const CreateEvaluationForm: React.FC<CreateEvaluationFormProps> = ({ onSubmit, onCancel }) => {
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
        <label className="block text-sm font-medium text-gray-700 mb-1">
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
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Description
        </label>
        <Input
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          placeholder="Enter evaluation description"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Dataset *
        </label>
        <Select value={formData.dataset_id} onValueChange={(value) => setFormData({ ...formData, dataset_id: value })}>
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
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Evaluation Type *
        </label>
        <Select value={formData.evaluation_type} onValueChange={(value) => setFormData({ ...formData, evaluation_type: value })}>
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
        <Button type="submit">
          Create Evaluation
        </Button>
      </div>
    </form>
  );
};

export default EvaluationManagement;