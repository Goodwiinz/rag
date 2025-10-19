import React, { useState, useMemo, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
} from 'recharts';
import {
  Users,
  UserCheck,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Play,
  Pause,
  Square,
  RefreshCw,
  Settings,
  Plus,
  Edit,
  Trash2,
  Eye,
  Filter,
  Search,
  Info,
  Calendar,
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
  Star,
  FileText,
  Zap,
  Target,
  Activity,
  TrendingUp,
  TrendingDown,
  ChevronDown,
  ChevronUp,
  Mail,
  Bell,
  Award,
  BarChart3,
  PieChart as PieChartIcon,
  User,
  Filter as FilterIcon,
  Shield,
  Globe,
  FileCheck,
} from 'lucide-react';

// Types
interface EvaluationTask {
  id: string;
  title: string;
  description: string;
  type: 'query_evaluation' | 'response_quality' | 'content_review' | 'usability_test' | 'accuracy_check' | 'compliance_review';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'pending' | 'assigned' | 'in_progress' | 'completed' | 'cancelled';
  workflow: {
    type: 'individual' | 'pairwise' | 'panel' | 'crowdsource';
    reviewers: string[];
    minReviewers: number;
    maxReviewers: number;
    consensusRequired: boolean;
    blindReview: boolean;
  };
  criteria: {
    dimensions: EvaluationDimension[];
    scoring: 'scale_1_5' | 'scale_1_10' | 'binary' | 'custom';
    weights: Record<string, number>;
    passingScore: number;
    guidelines: string[];
  };
  content: {
    queries: string[];
    responses: ResponseData[];
    documents: DocumentData[];
    testCases: TestCaseData[];
  };
  scheduling: {
    deadline?: string;
    estimatedDuration: number; // minutes
    autoAssignment: boolean;
    reminderSettings: {
      enabled: boolean;
      frequency: 'daily' | 'weekly' | 'custom';
      reminders: string[];
    };
  };
  compensation: {
    enabled: boolean;
    method: 'fixed' | 'hourly' | 'per_evaluation';
    rate?: number;
    budget?: number;
  };
  created: string;
  updated: string;
  createdBy: string;
  assignedTo?: string[];
  completedAt?: string;
  metadata: {
    version: string;
    tags: string[];
    department: string;
    project: string;
  };
}

interface EvaluationDimension {
  id: string;
  name: string;
  description: string;
  type: 'quality' | 'accuracy' | 'relevance' | 'clarity' | 'completeness' | 'usability' | 'performance';
  weight: number;
  required: boolean;
  guidelines: string[];
}

interface EvaluationResponse {
  id: string;
  taskId: string;
  reviewerId: string;
  reviewerName: string;
  reviewerRole: string;
  response: {
    overallScore: number;
    dimensionScores: Record<string, number>;
    comments: Record<string, string>;
    confidence: number;
    timeSpent: number; // minutes
  };
  status: 'draft' | 'submitted' | 'reviewed' | 'accepted' | 'rejected';
  submittedAt: string;
  reviewedAt?: string;
  reviewedBy?: string;
  metadata: {
    userAgent: string;
    ipAddress: string;
    deviceInfo: string;
  };
}

interface ResponseData {
  id: string;
  query: string;
  answer: string;
  sources: Array<{
    id: string;
    title: string;
    snippet: string;
    confidence: number;
  }>;
  timestamp: string;
  userId: string;
  sessionId: string;
}

interface DocumentData {
  id: string;
  title: string;
  filename: string;
  content: string;
  metadata: Record<string, any>;
}

interface TestCaseData {
  id: string;
  name: string;
  description: string;
  expectedOutcome: string;
  steps: string[];
}

interface HumanEvaluationDashboard {
  timeRange: '1d' | '7d' | '30d' | '90d';
  summary: {
    totalTasks: number;
    pendingTasks: number;
    inProgressTasks: number;
    completedTasks: number;
    averageScore: number;
    totalEvaluators: number;
    activeEvaluators: number;
    averageTimePerEvaluation: number; // minutes
  };
  performance: {
    evaluatorPerformance: Array<{
      evaluatorId: string;
      evaluatorName: string;
      totalEvaluations: number;
      averageScore: number;
      averageTime: number;
      reliability: number;
      lastActivity: string;
    }>;
    taskPerformance: Array<{
      taskId: string;
      taskName: string;
      averageScore: number;
      consensusRate: number;
      evaluationCount: number;
    }>;
  };
  quality: {
    interRaterReliability: number;
    consistency: number;
    feedbackQuality: number;
    completionRate: number;
    satisfaction: number;
  };
  trends: {
    evaluationsOverTime: Array<{
      date: string;
      count: number;
      averageScore: number;
      completionTime: number;
    }>;
    scoreDistribution: Array<{
      range: string;
      count: number;
      percentage: number;
    }>;
  };
}

// Mock data
const mockEvaluationTasks: EvaluationTask[] = [
  {
    id: 'task-001',
    title: 'Query Answer Quality Assessment',
    description: 'Evaluate the quality, accuracy, and completeness of AI-generated answers for a set of test queries',
    type: 'query_evaluation',
    priority: 'high',
    status: 'completed',
    workflow: {
      type: 'panel',
      reviewers: ['reviewer-001', 'reviewer-002', 'reviewer-003'],
      minReviewers: 2,
      maxReviewers: 3,
      consensusRequired: true,
      blindReview: false,
    },
    criteria: {
      dimensions: [
        {
          id: 'accuracy',
          name: 'Factual Accuracy',
          description: 'How factually correct the answer is',
          type: 'accuracy',
          weight: 0.4,
          required: true,
          guidelines: ['Check all facts against source documents', 'Verify no hallucinations', 'Cross-reference with provided sources'],
        },
        {
          id: 'relevance',
          name: 'Answer Relevancy',
          description: 'How well the answer addresses the user query',
          type: 'relevance',
          weight: 0.3,
          required: true,
          guidelines: ['Assess if answer directly addresses the question', 'Check for unnecessary information', 'Evaluate completeness of response'],
        },
        {
          id: 'clarity',
          name: 'Clarity and Readability',
          description: 'How clear and easy to understand the answer is',
          type: 'clarity',
          weight: 0.2,
          required: true,
          guidelines: ['Check for proper grammar and syntax', 'Evaluate structure and organization', 'Assess technical terminology'],
        },
        {
          id: 'completeness',
          name: 'Completeness',
          description: 'How complete the answer is given the available context',
          type: 'completeness',
          weight: 0.1,
          required: false,
          guidelines: ['Ensure all aspects of the question are addressed', 'Check for missing information', 'Evaluate depth of response'],
        },
      ],
      scoring: 'scale_1_5',
      weights: {
        accuracy: 0.4,
        relevance: 0.3,
        clarity: 0.2,
        completeness: 0.1,
      },
      passingScore: 3.0,
      guidelines: [
        'Provide specific feedback for scores below 3',
        'Focus on factual accuracy above all',
        'Consider the context and limitations of the system',
        'Use concrete examples in your evaluation',
      ],
    },
    content: {
      queries: [
        'What were the main revenue drivers for Q3 2024?',
        'How does our RAG system handle multimodal queries?',
        'What are the top 3 security risks in our current implementation?',
      ],
      responses: [],
      documents: [],
      testCases: [],
    },
    scheduling: {
      deadline: '2025-10-15T17:00:00Z',
      estimatedDuration: 45,
      autoAssignment: true,
      reminderSettings: {
        enabled: true,
        frequency: 'daily',
        reminders: ['2 days before deadline', '1 day before deadline', '4 hours before deadline'],
      },
    },
    compensation: {
      enabled: true,
      method: 'per_evaluation',
      rate: 25,
      budget: 500,
    },
    created: '2025-10-01T00:00:00Z',
    updated: '2025-10-14T16:30:00Z',
    createdBy: 'qa-manager',
    assignedTo: ['reviewer-001', 'reviewer-002', 'reviewer-003'],
    completedAt: '2025-10-14T15:45:00Z',
    metadata: {
      version: '1.0',
      tags: ['query-evaluation', 'quality-assessment'],
      department: 'Quality Assurance',
      project: 'RAG System Evaluation',
    },
  },
  {
    id: 'task-002',
    title: 'User Experience Feedback Collection',
    description: 'Collect and analyze user feedback on the RAG system interface and functionality',
    type: 'usability_test',
    priority: 'medium',
    status: 'in_progress',
    workflow: {
      type: 'individual',
      reviewers: ['user-001', 'user-002'],
      minReviewers: 1,
      maxReviewers: 2,
      consensusRequired: false,
      blindReview: false,
    },
    criteria: {
      dimensions: [
        {
          id: 'usability',
          name: 'Usability',
          description: 'How easy the system is to use and navigate',
          type: 'usability',
          weight: 0.4,
          required: true,
          guidelines: ['Evaluate interface intuitiveness', 'Check navigation flow', 'Assess learning curve'],
        },
        {
          id: 'performance',
          name: 'Performance',
          description: 'System speed and responsiveness',
          type: 'performance',
          weight: 0.3,
          required: true,
          guidelines: ['Test response times', 'Evaluate system stability', 'Check resource usage'],
        },
        {
          id: 'satisfaction',
          name: 'User Satisfaction',
          description: 'Overall satisfaction with the system',
          type: 'usability',
          weight: 0.3,
          required: true,
          guidelines: ['Gather overall impressions', 'Compare to alternatives', 'Assess value provided'],
        },
      ],
      scoring: 'scale_1_5',
      weights: {
        usability: 0.4,
        performance: 0.3,
        satisfaction: 0.3,
      },
      passingScore: 3.5,
      guidelines: [
        'Focus on user experience and system performance',
        'Provide specific examples of issues encountered',
        'Consider the target user profile',
        'Include suggestions for improvement',
      ],
    },
    content: {
      queries: [],
      responses: [],
      documents: [],
      testCases: [
        {
          id: 'tc-001',
          name: 'Document Upload Workflow',
          description: 'Test the document upload and processing workflow',
          expectedOutcome: 'Users can easily upload documents and track processing status',
          steps: ['Navigate to upload section', 'Select files', 'Monitor processing', 'Verify results'],
        },
      ],
    },
    scheduling: {
      deadline: '2025-10-20T17:00:00Z',
      estimatedDuration: 30,
      autoAssignment: true,
      reminderSettings: {
        enabled: true,
        frequency: 'weekly',
        reminders: ['1 week before deadline', '3 days before deadline', '1 day before deadline'],
      },
    },
    compensation: {
      enabled: false,
      method: 'fixed',
      budget: 200,
    },
    created: '2025-10-10T09:00:00Z',
    updated: '2025-10-16T14:20:00Z',
    createdBy: 'ux-lead',
    assignedTo: ['user-001', 'user-002'],
    metadata: {
      version: '1.0',
      tags: ['usability', 'user-feedback', 'ux-testing'],
      department: 'User Experience',
      project: 'RAG System Interface',
    },
  },
  {
    id: 'task-003',
    title: 'Content Accuracy Verification',
    description: 'Verify the accuracy and factual correctness of system-generated content',
    type: 'accuracy_check',
    priority: 'high',
    status: 'pending',
    workflow: {
      type: 'pairwise',
      reviewers: ['expert-001', 'expert-002'],
      minReviewers: 2,
      maxReviewers: 2,
      consensusRequired: true,
      blindReview: true,
    },
    criteria: {
      dimensions: [
        {
          id: 'factual_accuracy',
          name: 'Factual Accuracy',
          description: 'Verification of factual claims against sources',
          type: 'accuracy',
          weight: 0.6,
          required: true,
          guidelines: ['Cross-reference with source documents', 'Verify all statistical claims', 'Check for misinterpretations'],
        },
        {
          id: 'source_citation',
          name: 'Source Citation Quality',
          description: 'Quality and appropriateness of source citations',
          type: 'quality',
          weight: 0.4,
          required: true,
          guidelines: ['Verify all claims are cited', 'Check citation formatting', 'Assess source relevance'],
        },
      ],
      scoring: 'scale_1_10',
      weights: {
        factual_accuracy: 0.6,
        source_citation: 0.4,
      },
      passingScore: 7.0,
      guidelines: [
        'Prioritize factual accuracy above all else',
        'Require source citations for all claims',
        'Use domain expertise to evaluate accuracy',
        'Flag any potentially misleading information',
      ],
    },
    content: {
      queries: [],
      responses: [],
      documents: [],
      testCases: [],
    },
    scheduling: {
      deadline: '2025-10-25T17:00:00Z',
      estimatedDuration: 60,
      autoAssignment: false,
      reminderSettings: {
        enabled: true,
        frequency: 'custom',
        reminders: ['1 week before deadline'],
      },
    },
    compensation: {
      enabled: true,
      method: 'hourly',
      rate: 50,
      budget: 1000,
    },
    created: '2025-10-15T11:30:00Z',
    updated: '2025-10-15T11:30:00Z',
    createdBy: 'content-lead',
    metadata: {
      version: '1.0',
      tags: ['accuracy', 'fact-checking', 'expert-review'],
      department: 'Content',
      project: 'Content Quality',
    },
  },
];

const mockResponses: EvaluationResponse[] = [
  {
    id: 'resp-001',
    taskId: 'task-001',
    reviewerId: 'reviewer-001',
    reviewerName: 'John Smith',
    reviewerRole: 'Senior QA Analyst',
    response: {
      overallScore: 4.2,
      dimensionScores: {
        accuracy: 4.0,
        relevance: 4.5,
        clarity: 4.0,
        completeness: 4.5,
      },
      comments: {
        accuracy: 'Generally accurate with minor factual errors. Most information aligns with source documents.',
        relevance: 'Well-addressed the user query with relevant context from multiple sources.',
        clarity: 'Clear and well-structured answer with proper terminology.',
        completeness: 'Comprehensive response covering all aspects of the question.',
      },
      confidence: 0.85,
      timeSpent: 42,
    },
    status: 'submitted',
    submittedAt: '2025-10-14T15:30:00Z',
    reviewedAt: '2025-10-14T16:00:00Z',
    reviewedBy: 'qa-manager',
    metadata: {
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      ipAddress: '192.168.1.100',
      deviceInfo: 'Windows 10, Chrome 118.0',
    },
  },
  {
    id: 'resp-002',
    taskId: 'task-001',
    reviewerId: 'reviewer-002',
    reviewerName: 'Jane Doe',
    reviewerRole: 'QA Specialist',
    response: {
      overallScore: 3.8,
      dimensionScores: {
        accuracy: 3.5,
        relevance: 4.0,
        clarity: 4.0,
        completeness: 3.5,
      },
      comments: {
        accuracy: 'Some minor factual discrepancies detected. Cross-referencing needed for certain claims.',
        relevance: 'Good relevance to query with appropriate source selection.',
        clarity: 'Well-written and easy to understand.',
        completeness: 'Could be more comprehensive in certain areas.',
      },
      confidence: 0.80,
      timeSpent: 48,
    },
    status: 'submitted',
    submittedAt: '2025-10-14T15:45:00Z',
    reviewedAt: '2025-10-14T16:15:00Z',
    reviewedBy: 'qa-manager',
    metadata: {
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
      ipAddress: '192.168.1.101',
      deviceInfo: 'macOS, Safari 16.0',
    },
  },
  {
    id: 'resp-003',
    taskId: 'task-001',
    reviewerId: 'reviewer-003',
    reviewerName: 'Bob Johnson',
    reviewerRole: 'Domain Expert',
    response: {
      overallScore: 4.5,
      dimensionScores: {
        accuracy: 4.5,
        relevance: 4.5,
        clarity: 4.0,
        completeness: 5.0,
      },
      comments: {
        accuracy: 'Excellent factual accuracy with proper source attribution.',
        relevance: 'Highly relevant answer that directly addresses user needs.',
        clarity: 'Clear, concise communication with appropriate technical detail.',
        completeness: 'Thorough and comprehensive response covering all query aspects.',
      },
      confidence: 0.95,
      timeSpent: 38,
    },
    status: 'accepted',
    submittedAt: '2025-10-14T15:20:00Z',
    reviewedAt: '2025-10-14T16:10:00Z',
    reviewedBy: 'qa-manager',
    metadata: {
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      ipAddress: '192.168.1.102',
      deviceInfo: 'Windows 11, Edge 118.0',
    },
  },
];

const mockDashboard: HumanEvaluationDashboard = {
  timeRange: '30d',
  summary: {
    totalTasks: mockEvaluationTasks.length,
    pendingTasks: mockEvaluationTasks.filter(t => t.status === 'pending').length,
    inProgressTasks: mockEvaluationTasks.filter(t => t.status === 'in_progress').length,
    completedTasks: mockEvaluationTasks.filter(t => t.status === 'completed').length,
    averageScore: 4.17,
    totalEvaluators: 8,
    activeEvaluators: 6,
    averageTimePerEvaluation: 43,
  },
  performance: {
    evaluatorPerformance: [
      {
        evaluatorId: 'reviewer-001',
        evaluatorName: 'John Smith',
        totalEvaluations: 15,
        averageScore: 4.1,
        averageTime: 42,
        reliability: 0.92,
        lastActivity: '2025-10-17T12:00:00Z',
      },
      {
        evaluatorId: 'reviewer-002',
        evaluatorName: 'Jane Doe',
        totalEvaluations: 12,
        averageScore: 3.9,
        averageTime: 45,
        reliability: 0.88,
        lastActivity: '2025-10-16T16:30:00Z',
      },
      {
        evaluatorId: 'expert-001',
        evaluatorName: 'Domain Expert',
        totalEvaluations: 8,
        averageScore: 4.4,
        averageTime: 40,
        reliability: 0.95,
        lastActivity: '2025-10-17T10:15:00Z',
      },
    ],
    taskPerformance: [
      {
        taskId: 'task-001',
        taskName: 'Query Answer Quality Assessment',
        averageScore: 4.17,
        consensusRate: 0.85,
        evaluationCount: 3,
      },
      {
        taskId: 'task-002',
        taskName: 'User Experience Feedback Collection',
        averageScore: 0,
        consensusRate: 0,
        evaluationCount: 0,
      },
    ],
  },
  quality: {
    interRaterReliability: 0.87,
    consistency: 0.82,
    feedbackQuality: 0.91,
    completionRate: 0.94,
    satisfaction: 4.2,
  },
  trends: {
    evaluationsOverTime: Array.from({ length: 30 }, (_, i) => {
      const date = new Date();
      date.setDate(date.getDate() - i);
      return {
        date: date.toLocaleDateString(),
        count: Math.floor(Math.random() * 5) + 1,
        averageScore: 3.8 + Math.random() * 0.8,
        completionTime: 40 + Math.random() * 15,
      };
    }),
    scoreDistribution: [
      { range: '5.0', count: 15, percentage: 25 },
      { range: '4.0-4.9', count: 28, percentage: 47 },
      { range: '3.0-3.9', count: 12, percentage: 20 },
      { range: '2.0-2.9', count: 5, percentage: 8 },
    ],
  },
};

const taskTypes = [
  { id: 'query_evaluation', name: 'Query Evaluation', description: 'Evaluate AI-generated answers' },
  { id: 'response_quality', name: 'Response Quality', description: 'Assess overall response quality' },
  { id: 'content_review', name: 'Content Review', description: 'Review content for accuracy and completeness' },
  { id: 'usability_test', name: 'Usability Test', description: 'Test system usability and user experience' },
  { id: 'accuracy_check', name: 'Accuracy Check', description: 'Verify factual accuracy' },
  { id: 'compliance_review', name: 'Compliance Review', description: 'Review for compliance requirements' },
];

const workflowTypes = [
  { id: 'individual', name: 'Individual Review', description: 'Single evaluator per task' },
  { id: 'pairwise', name: 'Pairwise Review', description: 'Two evaluators per task' },
  { id: 'panel', name: 'Panel Review', description: 'Multiple evaluators per task' },
  { id: 'crowdsource', name: 'Crowdsourced Review', description: 'Open to all evaluators' },
];

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

const HumanEvaluationWorkflows: React.FC<HumanEvaluationWorkflowsProps> = ({
  onTaskCreate,
  onTaskUpdate,
  onTaskDelete,
  onEvaluationSubmit,
  onTaskAssign,
  className,
}) => {
  const [evaluationTasks, setEvaluationTasks] = useState<EvaluationTask[]>(mockEvaluationTasks);
  const [evaluationResponses, setEvaluationResponses] = useState<EvaluationResponse[]>(mockResponses);
  const [dashboard, setDashboard] = useState<HumanEvaluationDashboard>(mockDashboard);
  const [selectedTask, setSelectedTask] = useState<EvaluationTask | null>(null);
  const [selectedResponse, setSelectedResponse] = useState<EvaluationResponse | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [timeRange, setTimeRange] = useState('30d');
  const [isCreateTaskDialogOpen, setIsCreateTaskDialogOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<EvaluationTask | null>(null);
  const [filterType, setFilterType] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterPriority, setFilterPriority] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  // Update dashboard when time range changes
  React.useEffect(() => {
    setDashboard(prev => ({
      ...prev,
      timeRange: timeRange as HumanEvaluationDashboard['timeRange'],
    }));
  }, [timeRange]);

  // Filter tasks
  const filteredTasks = useMemo(() => {
    return evaluationTasks.filter(task => {
      const matchesSearch = task.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           task.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesType = filterType === 'all' || task.type === filterType;
      const matchesStatus = filterStatus === 'all' || task.status === filterStatus;
      const matchesPriority = filterPriority === 'all' || task.priority === filterPriority;
      return matchesSearch && matchesType && matchesStatus && matchesPriority;
    });
  }, [evaluationTasks, searchTerm, filterType, filterStatus, filterPriority]);

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800 border-green-200';
      case 'in_progress': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'assigned': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'pending': return 'bg-gray-100 text-gray-800 border-gray-200';
      case 'cancelled': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'in_progress': return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'assigned': return <Users className="h-4 w-4 text-purple-500" />;
      case 'pending': return <Clock className="h-4 w-4 text-gray-500" />;
      case 'cancelled': return <XCircle className="h-4 w-4 text-red-500" />;
      default: return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  // Get priority color
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'bg-red-100 text-red-800 border-red-200';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low': return 'bg-blue-100 text-blue-800 border-blue-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  // Get type icon
  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'query_evaluation': return <Target className="h-4 w-4" />;
      case 'response_quality': return <Star className="h-4 w-4" />;
      case 'content_review': return <FileText className="h-4 w-4" />;
      case 'usability_test': return <UserCheck className="h-4 w-4" />;
      case 'accuracy_check': return <Shield className="h-4 w-4" />;
      case 'compliance_review': return <Globe className="h-4 w-4" />;
      default: return <CheckCircle className="h-4 w-4" />;
    }
  };

  // Get workflow icon
  const getWorkflowIcon = (type: string) => {
    switch (type) {
      case 'individual': return <Users className="h-4 w-4" />;
      case 'pairwise': return <Users className="h-4 w-4" />;
      case 'panel': return <Users className="h-4 w-4" />;
      case 'crowdsource': return <Users className="h-4 w-4" />;
      default: return <Users className="h-4 w-4" />;
    }
  };

  // Assign evaluators to task
  const assignEvaluators = useCallback((taskId: string, evaluatorIds: string[]) => {
    setEvaluationTasks(prev => prev.map(task =>
      task.id === taskId
        ? { ...task, assignedTo: evaluatorIds, updated: new Date().toISOString() }
        : task
    ));
    onTaskAssign?.(taskId, evaluatorIds);
  }, [onTaskAssign]);

  // Submit evaluation response
  const submitEvaluation = useCallback((responseData: Partial<EvaluationResponse>) => {
    const newResponse: EvaluationResponse = {
      id: `resp-${Date.now()}`,
      taskId: responseData.taskId || '',
      reviewerId: 'current-user',
      reviewerName: 'Current User',
      reviewerRole: 'Evaluator',
      response: responseData.response || {
        overallScore: 0,
        dimensionScores: {},
        comments: {},
        confidence: 0.5,
        timeSpent: 0,
      },
      status: 'draft',
      submittedAt: new Date().toISOString(),
      metadata: {
        userAgent: navigator.userAgent,
        ipAddress: '127.0.0.1',
        deviceInfo: 'Unknown',
      },
    };
    setEvaluationResponses(prev => [...prev, newResponse]);
    onEvaluationSubmit?.(newResponse);
  }, [onEvaluationSubmit]);

  // Delete task
  const handleDeleteTask = useCallback((taskId: string) => {
    setEvaluationTasks(prev => prev.filter(task => task.id !== taskId));
    onTaskDelete?.(taskId);
  }, [onTaskDelete]);

  // Save task
  const handleSaveTask = useCallback((taskData: Partial<EvaluationTask>) => {
    if (editingTask) {
      // Update existing task
      setEvaluationTasks(prev => prev.map(task =>
        task.id === editingTask.id
          ? { ...task, ...taskData, updated: new Date().toISOString() }
          : task
      ));
      setEditingTask(null);
    } else {
      // Create new task
      const newTask: EvaluationTask = {
        id: `task-${Date.now()}`,
        title: taskData.title || 'New Evaluation Task',
        description: taskData.description || '',
        type: taskData.type || 'query_evaluation',
        priority: taskData.priority || 'medium',
        status: 'pending',
        workflow: {
          type: 'individual',
          reviewers: [],
          minReviewers: 1,
          maxReviewers: 1,
          consensusRequired: false,
          blindReview: false,
        },
        criteria: {
          dimensions: [],
          scoring: 'scale_1_5',
          weights: {},
          passingScore: 3.0,
          guidelines: [],
        },
        content: {
          queries: [],
          responses: [],
          documents: [],
          testCases: [],
        },
        scheduling: {
          estimatedDuration: 30,
          autoAssignment: true,
          reminderSettings: {
            enabled: true,
            frequency: 'weekly',
            reminders: [],
          },
        },
        compensation: {
          enabled: false,
          method: 'fixed',
          budget: 0,
        },
        created: new Date().toISOString(),
        updated: new Date().toISOString(),
        createdBy: 'current-user',
        metadata: {
          version: '1.0',
          tags: [],
          department: 'Quality Assurance',
          project: 'RAG System Evaluation',
        },
      };
      setEvaluationTasks(prev => [...prev, newTask]);
      onTaskCreate?.(newTask);
    }
    setIsCreateTaskDialogOpen(false);
  }, [editingTask, onTaskCreate]);

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Human Evaluation Workflows</h2>
          <p className="text-gray-600 dark:text-gray-400">Manage human evaluation tasks and workflows for quality assurance</p>
        </div>
        <div className="flex items-center space-x-2">
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1d">Last 24 hours</SelectItem>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Dialog open={isCreateTaskDialogOpen} onOpenChange={setIsCreateTaskDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Task
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl">
              <DialogHeader>
                <DialogTitle>{editingTask ? 'Edit Evaluation Task' : 'Create Evaluation Task'}</DialogTitle>
                <DialogDescription>
                  Configure human evaluation tasks and workflows
                </DialogDescription>
              </DialogHeader>
              <EvaluationTaskForm
                task={editingTask}
                onSubmit={handleSaveTask}
                onCancel={() => {
                  setIsCreateTaskDialogOpen(false);
                  setEditingTask(null);
                }}
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Evaluation Overview */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Activity className="h-5 w-5 text-blue-500" />
              <div>
                <div className="text-2xl font-bold">{dashboard.summary.totalTasks}</div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Total Tasks</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <div>
                <div className="text-2xl font-bold">{dashboard.summary.completedTasks}</div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Completed</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Users className="h-5 w-5 text-purple-500" />
              <div>
                <div className="text-2xl font-bold">{dashboard.summary.totalEvaluators}</div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Evaluators</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <TrendingUp className="h-5 w-5 text-green-500" />
              <div>
                <div className="text-2xl font-bold">{dashboard.summary.averageScore.toFixed(1)}</div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Avg Score</div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Clock className="h-5 w-5 text-orange-500" />
              <div>
                <div className="text-2xl font-bold">{dashboard.summary.averageTimePerEvaluation.toFixed(0)}m</div>
                <div className="text-sm text-gray-600 dark:text-gray-400">Avg Time</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview" className="flex items-center space-x-2">
            <BarChart3 className="h-4 w-4" />
            <span>Overview</span>
          </TabsTrigger>
          <TabsTrigger value="tasks" className="flex items-center space-x-2">
            <FileText className="h-4 w-4" />
            <span>Tasks</span>
          </TabsTrigger>
          <TabsTrigger value="evaluators" className="flex items-center space-x-2">
            <Users className="h-4 w-4" />
            <span>Evaluators</span>
          </TabsTrigger>
          <TabsTrigger value="quality" className="flex items-center space-x-2">
            <Shield className="h-4 w-4" />
            <span>Quality Metrics</span>
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Evaluation Trends</CardTitle>
                <CardDescription>Number of evaluations and average scores over time</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={dashboard.trends.evaluationsOverTime}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                      <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                      <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Legend />
                      <Bar yAxisId="left" dataKey="count" fill="#3b82f6" />
                      <Line yAxisId="right" type="monotone" dataKey="averageScore" stroke="#10b981" strokeWidth={2} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Score Distribution</CardTitle>
                <CardDescription>How evaluation scores are distributed</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={dashboard.trends.scoreDistribution}
                        cx="50%"
                        cy="50%"
                        labelLine={false}
                        label={(entry) => `${entry.range} (${entry.percentage}%)`}
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="count"
                      >
                        {dashboard.trends.scoreDistribution.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Quality Metrics</CardTitle>
              <CardDescription>Key quality indicators for the evaluation system</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Inter-Rater Reliability</span>
                    <span className="text-sm font-bold">{(dashboard.quality.interRaterReliability * 100).toFixed(0)}%</span>
                  </div>
                  <Progress value={dashboard.quality.interRaterReliability * 100} className="h-2" />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Consistency</span>
                    <span className="text-sm font-bold">{(dashboard.quality.consistency * 100).toFixed(0)}%</span>
                  </div>
                  <Progress value={dashboard.quality.consistency * 100} className="h-2" />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Feedback Quality</span>
                    <span className="text-sm font-bold">{(dashboard.quality.feedbackQuality * 100).toFixed(0)}%</span>
                  </div>
                  <Progress value={dashboard.quality.feedbackQuality * 100} className="h-2" />
                </div>
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">Completion Rate</span>
                    <span className="text-sm font-bold">{(dashboard.quality.completionRate * 100).toFixed(0)}%</span>
                  </div>
                  <Progress value={dashboard.quality.completionRate * 100} className="h-2" />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tasks Tab */}
        <TabsContent value="tasks" className="space-y-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center space-x-4 mb-4">
                <div className="flex-1">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      placeholder="Search evaluation tasks..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                </div>
                <Select value={filterType} onValueChange={setFilterType}>
                  <SelectTrigger className="w-40">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    {taskTypes.map(type => (
                      <SelectItem key={type.id} value={type.id}>
                        {type.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={filterStatus} onValueChange={setFilterStatus}>
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="assigned">Assigned</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="cancelled">Cancelled</SelectItem>
                  </SelectContent>
                </Select>
                <Select value={filterPriority} onValueChange={setFilterPriority}>
                  <SelectTrigger className="w-32">
                    <SelectValue placeholder="Priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Priorities</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-3">
                {filteredTasks.map(task => {
                  const taskType = taskTypes.find(t => t.id === task.type);
                  const workflowType = workflowTypes.find(w => w.id === task.workflow.type);
                  const lastResult = evaluationResponses.find(r => r.taskId === task.id);
                  const assignedEvaluators = task.assignedTo || [];

                  return (
                    <Card key={task.id} className="hover:shadow-md transition-shadow">
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between">
                          <div className="flex items-start space-x-3">
                            {getStatusIcon(task.status)}
                            <div>
                              <CardTitle className="text-lg">{task.title}</CardTitle>
                              <CardDescription className="mt-1">{task.description}</CardDescription>
                            </div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Badge className={getPriorityColor(task.priority)}>
                              {task.priority}
                            </Badge>
                            <Badge variant="outline">{taskType?.name}</Badge>
                            <Badge variant="outline">{workflowType?.name}</Badge>
                          </div>
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div>
                            <div className="text-sm font-medium text-gray-600 dark:text-gray-400">Status</div>
                            <div className="flex items-center space-x-2">
                              {getStatusIcon(task.status)}
                              <span className="capitalize">{task.status.replace('_', ' ')}</span>
                            </div>
                          </div>
                          <div>
                            <div className="text-sm font-medium text-gray-600 dark:text-gray-400">Priority</div>
                            <div className="flex items-center space-x-2">
                              <div className={`w-3 h-3 rounded-full ${getPriorityColor(task.priority)} opacity-50`}></div>
                              <span className="capitalize">{task.priority}</span>
                            </div>
                          </div>
                          <div>
                            <div className="text-sm font-medium text-gray-600 dark:text-gray-400">Reviewers</div>
                            <div className="text-sm">
                              {assignedEvaluators.length}/{task.workflow.minReviewers}-{task.workflow.maxReviewers}
                            </div>
                          </div>
                        </div>

                        {task.scheduling.deadline && (
                          <div className="flex items-center space-x-2 text-sm">
                            <Calendar className="h-4 w-4 text-orange-500" />
                            <span>Deadline: {new Date(task.scheduling.deadline).toLocaleDateString()}</span>
                          </div>
                        )}

                        {task.compensation.enabled && (
                          <div className="flex items-center space-x-2 text-sm">
                            <Zap className="h-4 w-4 text-green-500" />
                            <span>
                              {task.compensation.method === 'per_evaluation' ? `$${task.compensation.rate}/evaluation` :
                               task.compensation.method === 'hourly' ? `$${task.compensation.rate}/hour` :
                               `Fixed: $${task.compensation.budget}`}
                            </span>
                          </div>
                        )}

                        {lastResult && (
                          <div className="border rounded-lg p-3 bg-gray-50 dark:bg-gray-800">
                            <div className="flex items-center justify-between mb-2">
                              <div className="text-sm font-medium">Latest Result</div>
                              <div className="text-sm font-bold">{lastResult.response.overallScore.toFixed(1)}/5</div>
                            </div>
                            <div className="text-xs text-gray-500">
                              By {lastResult.reviewerName} • {new Date(lastResult.submittedAt).toLocaleDateString()}
                            </div>
                          </div>
                        )}
                      </CardContent>

                      <div className="flex items-center justify-between">
                        <div className="flex flex-wrap gap-1">
                          {task.metadata.tags.map(tag => (
                            <Badge key={tag} variant="outline" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </div>
                        <div className="flex items-center space-x-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedTask(task)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingTask(task);
                              setIsCreateTaskDialogOpen(true);
                            }}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteTask(task.id)}
                            className="text-red-600"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Evaluators Tab */}
        <TabsContent value="evaluators" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Evaluator Performance</CardTitle>
              <CardDescription>Individual evaluator performance and reliability metrics</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {dashboard.performance.evaluatorPerformance.map(evaluator => (
                  <div key={evaluator.evaluatorId} className="flex items-center justify-between p-3 border rounded-lg">
                    <div className="flex items-center space-x-3">
                      <Users className="h-5 w-5 text-blue-500" />
                      <div>
                        <div className="font-medium">{evaluator.evaluatorName}</div>
                        <div className="text-sm text-gray-500">
                          {evaluator.totalEvaluations} evaluations • {evaluator.averageScore.toFixed(1)}/5 avg score
                        </div>
                        <div className="text-xs text-gray-400">
                          Reliability: {(evaluator.reliability * 100).toFixed(0)}%
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-bold">{evaluator.averageScore.toFixed(1)}/5</div>
                      <div className="text-xs text-gray-500">{evaluator.averageTime.toFixed(0)} min/eval</div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Evaluation Insights</CardTitle>
              <CardDescription>Key insights from human evaluations</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <h5 className="font-medium text-blue-800 dark:text-blue-200 mb-2">Top Performing Evaluators</h5>
                  <div className="space-y-2">
                    {dashboard.performance.evaluatorPerformance
                      .sort((a, b) => b.averageScore - a.averageScore)
                      .slice(0, 3)
                      .map((evaluator, index) => (
                        <div key={evaluator.evaluatorId} className="flex items-center justify-between text-sm">
                          <div>
                            <span className="font-medium">{index + 1}. {evaluator.evaluatorName}</span>
                            <span className="text-gray-600">
                              {evaluator.totalEvaluations} evaluations • {evaluator.averageScore.toFixed(1)}/5 avg
                            </span>
                          </div>
                          <div className="font-bold">{evaluator.reliability > 0.9 ? 'Excellent' : evaluator.reliability > 0.8 ? 'Good' : 'Needs Improvement'}</div>
                        </div>
                      ))}
                  </div>
                </div>

                <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <h5 className="font-medium text-green-800 dark:text-green-200 mb-2">Quality Improvements Needed</h5>
                  <div className="text-sm text-green-700">
                    Consider additional training for evaluators with scores below 4.0
                  </div>
                  <div className="text-sm text-green-600">
                    Implement calibration sessions to improve inter-rater reliability
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Quality Metrics Tab */}
        <TabsContent value="quality" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Evaluation Quality Trends</CardTitle>
                <CardDescription>Quality metrics over time periods</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={dashboard.trends.evaluationsOverTime}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                      <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                      <YAxis yAxisId="right" tick={{ fontSize: 12 }} />
                      <Tooltip />
                      <Legend />
                      <Line yAxisId="left" type="monotone" dataKey="count" stroke="#3b82f6" />
                      <Line yAxisId="right" type="monotone" dataKey="averageScore" stroke="#10b981" strokeWidth={2} />
                      <Line yAxisId="right" type="monotone" dataKey="completionTime" stroke="#f59e0b" strokeWidth={2} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Dimension Analysis</CardTitle>
                <CardDescription>Performance across evaluation dimensions</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart data={(mockEvaluationTasks[0]?.criteria.dimensions || []).map(dim => ({
                      dimension: dim.name,
                      score: 4.0 + Math.random() * 1.0, // Mock score data
                    }))}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 10 }} />
                      <PolarRadiusAxis angle={90} domain={[0, 5]} tick={{ fontSize: 10 }} />
                      <Radar
                        name="Score"
                        dataKey="score"
                        stroke="#3b82f6"
                        fill="#3b82f620"
                        fillOpacity={0.3}
                        strokeWidth={2}
                      />
                    </RadarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Consistency Analysis</CardTitle>
              <CardDescription>Inter-rater reliability and evaluation consistency</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="text-center p-4">
                  <div className="text-3xl font-bold text-blue-600">{(dashboard.quality.interRaterReliability * 100).toFixed(0)}%</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Inter-Rater Reliability</div>
                  <div className="text-xs text-gray-500">
                    Above 0.80 is considered good
                  </div>
                </div>
                <div className="text-center p-4">
                  <div className="text-3xl font-bold text-green-600">{(dashboard.quality.consistency * 100).toFixed(0)}%</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">Evaluation Consistency</div>
                  <div className="text-xs text-gray-500">
                    Above 0.75 is considered good
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

// Evaluation Task Form Component
const EvaluationTaskForm: React.FC<EvaluationTaskFormProps> = ({ task, onSubmit, onCancel }) => {
  const [formData, setFormData] = useState({
    title: task?.title || '',
    description: task?.description || '',
    type: task?.type || 'query_evaluation',
    priority: task?.priority || 'medium',
    workflowType: task?.workflow.type || 'individual',
    minReviewers: task?.workflow.minReviewers || 1,
    maxReviewers: task?.workflow.maxReviewers || 1,
    consensusRequired: task?.workflow.consensusRequired || false,
    blindReview: task?.workflow.blindReview || false,
    deadline: task?.scheduling?.deadline?.slice(0, 16) || '',
    estimatedDuration: task?.scheduling?.estimatedDuration || 30,
    autoAssignment: task?.scheduling?.autoAssignment ?? true,
    reminderEnabled: task?.scheduling?.reminderSettings?.enabled || false,
    reminderFrequency: task?.scheduling?.reminderSettings?.frequency || 'weekly',
    passThreshold: task?.criteria.passingScore || 3.0,
    failThreshold: 0, // Default value since this property doesn't exist in the interface
    scoring: task?.criteria.scoring || 'scale_1_5',
    compensationEnabled: task?.compensation?.enabled || false,
    compensationMethod: task?.compensation?.method || 'fixed',
    compensationRate: task?.compensation?.rate || 0,
    compensationBudget: task?.compensation?.budget || 0,
    isActive: task?.status === 'assigned' || task?.status === 'in_progress',
    tags: task?.metadata.tags?.join(', ') || '',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const taskData: Partial<EvaluationTask> = {
      title: formData.title,
      description: formData.description,
      type: formData.type as any,
      priority: formData.priority as any,
      status: formData.isActive ? 'assigned' : 'pending',
      workflow: {
        type: formData.workflowType as any,
        reviewers: [],
        minReviewers: formData.minReviewers,
        maxReviewers: formData.maxReviewers,
        consensusRequired: formData.consensusRequired,
        blindReview: formData.blindReview,
      },
      criteria: {
        dimensions: [], // Would be populated by a dimension builder
        scoring: formData.scoring as any,
        weights: {},
        passingScore: formData.passThreshold,
        guidelines: [],
      },
      content: {
        queries: [], // Would be populated by content selector
        responses: [],
        documents: [],
        testCases: [],
      },
      scheduling: {
        deadline: formData.deadline ? new Date(formData.deadline).toISOString() : undefined,
        estimatedDuration: formData.estimatedDuration,
        autoAssignment: formData.autoAssignment,
        reminderSettings: {
          enabled: formData.reminderEnabled,
          frequency: formData.reminderFrequency as any,
          reminders: [],
        },
      },
      compensation: {
        enabled: formData.compensationEnabled,
        method: formData.compensationMethod as any,
        rate: formData.compensationRate,
        budget: formData.compensationBudget,
      },
      metadata: {
        version: '1.0',
        tags: formData.tags.split(',').map(t => t.trim()).filter(Boolean),
        department: 'Quality Assurance',
        project: 'RAG System Evaluation',
      },
    };

    onSubmit(taskData);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <Label htmlFor="task-title">Task Title *</Label>
          <Input
            id="task-title"
            value={formData.title}
            onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
            placeholder="Enter evaluation task title"
            required
          />
        </div>
        <div>
          <Label htmlFor="task-priority">Priority *</Label>
          <Select value={formData.priority} onValueChange={(value) => setFormData(prev => ({ ...prev, priority: value as typeof formData.priority }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="urgent">Urgent</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div>
        <Label htmlFor="task-description">Description</Label>
        <Textarea
          id="task-description"
          value={formData.description}
          onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
          placeholder="Describe what this evaluation task accomplishes"
          rows={3}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <Label htmlFor="task-type">Evaluation Type *</Label>
          <Select value={formData.type} onValueChange={(value) => setFormData(prev => ({ ...prev, type: value as typeof formData.type }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {taskTypes.map(type => (
                <SelectItem key={type.id} value={type.id}>
                  {type.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="workflow-type">Workflow Type *</Label>
          <Select value={formData.workflowType} onValueChange={(value) => setFormData(prev => ({ ...prev, workflowType: value as typeof formData.workflowType }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {workflowTypes.map(type => (
                <SelectItem key={type.id} value={type.id}>
                  {type.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label htmlFor="estimated-duration">Estimated Duration (minutes)</Label>
          <Input
            id="estimated-duration"
            type="number"
            min="5"
            max="120"
            value={formData.estimatedDuration}
            onChange={(e) => setFormData(prev => ({ ...prev, estimatedDuration: parseInt(e.target.value) }))}
          />
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Review Configuration</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label htmlFor="min-reviewers">Minimum Reviewers</Label>
            <Input
              id="min-reviewers"
              type="number"
              min="1"
              value={formData.minReviewers}
              onChange={(e) => setFormData(prev => ({ ...prev, minReviewers: parseInt(e.target.value) }))}
            />
          </div>
          <div>
            <Label htmlFor="max-reviewers">Maximum Reviewers</Label>
            <Input
              id="max-reviewers"
              type="number"
              min="1"
              max="10"
              value={formData.maxReviewers}
              onChange={(e) => setFormData(prev => ({ ...prev, maxReviewers: parseInt(e.target.value) }))}
            />
          </div>
          <div className="flex items-center space-x-2 mt-6">
            <Switch
              id="consensus-required"
              checked={formData.consensusRequired}
              onCheckedChange={(checked) => setFormData(prev => ({ ...prev, consensusRequired: checked }))}
            />
            <Label htmlFor="consensus-required">Consensus Required</Label>
          </div>
          <div className="flex items-center space-x-2 mt-2">
            <Switch
              id="blind-review"
              checked={formData.blindReview}
              onCheckedChange={(checked) => setFormData(prev => ({ ...prev, blindReview: checked }))}
            />
            <Label htmlFor="blind-review">Blind Review</Label>
          </div>
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Scoring Configuration</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <Label htmlFor="scoring">Scoring Method</Label>
            <Select value={formData.scoring} onValueChange={(value) => setFormData(prev => ({ ...prev, scoring: value as typeof formData.scoring }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="scale_1_5">1-5 Scale</SelectItem>
                <SelectItem value="scale_1_10">1-10 Scale</SelectItem>
                <SelectItem value="binary">Binary (Pass/Fail)</SelectItem>
                <SelectItem value="custom">Custom</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="pass-threshold">Pass Threshold</Label>
            <Input
              id="pass-threshold"
              type="number"
              min="0"
              max="5"
              step="0.5"
              value={formData.passThreshold}
              onChange={(e) => setFormData(prev => ({ ...prev, passThreshold: parseFloat(e.target.value) }))}
            />
          </div>
          <div>
            <Label htmlFor="fail-threshold">Fail Threshold</Label>
            <Input
              id="fail-threshold"
              type="number"
              min="0"
              max="5"
              step="0.5"
              value={formData.failThreshold}
              onChange={(e) => setFormData(prev => ({ ...prev, failThreshold: parseFloat(e.target.value) }))}
            />
          </div>
        </div>
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Scheduling & Deadlines</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="deadline">Deadline</Label>
            <Input
              id="deadline"
              type="datetime-local"
              value={formData.deadline}
              onChange={(e) => setFormData(prev => ({ ...prev, deadline: e.target.value }))}
            />
          </div>
          <div>
            <Label htmlFor="auto-assignment">Auto Assignment</Label>
            <Switch
              id="auto-assignment"
              checked={formData.autoAssignment}
              onCheckedChange={(checked) => setFormData(prev => ({ ...prev, autoAssignment: checked }))}
            />
          </div>
        </div>
        <div className="flex items-center space-x-2 mt-4">
          <Switch
            id="reminder-enabled"
            checked={formData.reminderEnabled}
            onCheckedChange={(checked) => setFormData(prev => ({ ...prev, reminderEnabled: checked }))}
          />
          <Label htmlFor="reminder-enabled">Enable Reminders</Label>
        </div>
        {formData.reminderEnabled && (
          <div className="mt-2">
            <Select value={formData.reminderFrequency} onValueChange={(value) => setFormData(prev => ({ ...prev, reminderFrequency: value as typeof formData.reminderFrequency }))}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
                <SelectItem value="custom">Custom</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      <div className="border rounded-lg p-4">
        <h4 className="font-medium mb-3">Compensation</h4>
        <div className="flex items-center space-x-2 mb-4">
          <Switch
            id="compensation-enabled"
            checked={formData.compensationEnabled}
            onCheckedChange={(checked) => setFormData(prev => ({ ...prev, compensationEnabled: checked }))}
          />
          <Label htmlFor="compensation-enabled">Enable Compensation</Label>
        </div>
        {formData.compensationEnabled && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <Label htmlFor="compensation-method">Method</Label>
                <Select value={formData.compensationMethod} onValueChange={(value) => setFormData(prev => ({ ...prev, compensationMethod: value as typeof formData.compensationMethod }))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fixed">Fixed Rate</SelectItem>
                    <SelectItem value="hourly">Hourly Rate</SelectItem>
                    <SelectItem value="per_evaluation">Per Evaluation</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="compensation-rate">Rate / Budget</Label>
                {formData.compensationMethod === 'per_evaluation' ? (
                  <Input
                    id="compensation-rate"
                    type="number"
                    min="1"
                    max="500"
                    value={formData.compensationRate || ''}
                    onChange={(e) => setFormData(prev => ({ ...prev, compensationRate: parseFloat(e.target.value) }))}
                    placeholder="25"
                  />
                ) : formData.compensationMethod === 'hourly' ? (
                  <Input
                    id="compensation-rate"
                    type="number"
                    min="10"
                    max="200"
                    value={formData.compensationRate || ''}
                    onChange={(e) => setFormData(prev => ({ ...prev, compensationRate: parseFloat(e.target.value) }))}
                    placeholder="50"
                  />
                ) : (
                  <Input
                    id="compensation-budget"
                    type="number"
                    min="50"
                    max="10000"
                    value={formData.compensationBudget || ''}
                    onChange={(e) => setFormData(prev => ({ ...prev, compensationBudget: parseInt(e.target.value) }))}
                    placeholder="500"
                  />
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center space-x-2">
        <Label htmlFor="tags">Tags</Label>
        <Input
          id="tags"
          value={formData.tags}
          onChange={(e) => setFormData(prev => ({ ...prev, tags: e.target.value }))}
          placeholder="e.g., quality, automated, expert-review"
        />
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <FileCheck className="h-4 w-4 mr-2" />
          {task ? 'Update Task' : 'Create Task'}
        </Button>
      </div>
    </form>
  );
};

export default HumanEvaluationWorkflows;

interface HumanEvaluationWorkflowsProps {
  onTaskCreate?: (task: EvaluationTask) => void;
  onTaskUpdate?: (task: EvaluationTask) => void;
  onTaskDelete?: (taskId: string) => void;
  onEvaluationSubmit?: (response: EvaluationResponse) => void;
  onTaskAssign?: (taskId: string, evaluatorIds: string[]) => void;
  className?: string;
}

interface EvaluationTaskFormProps {
  task?: EvaluationTask | null;
  onSubmit: (task: Partial<EvaluationTask>) => void;
  onCancel: () => void;
}