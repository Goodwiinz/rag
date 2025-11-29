import React, { useState, useMemo, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Button,
  ButtonProps,
} from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Separator } from '@/components/ui/separator';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Play,
  Pause,
  Square,
  Plus,
  Edit,
  Trash2,
  Copy,
  Download,
  Upload,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Calendar,
  AlertTriangle,
  FileText,
  Settings,
  BarChart3,
  Users,
  Zap,
  Target,
  List,
  Filter,
  Search,
  MoreHorizontal,
  ChevronRight,
  ChevronDown,
  Eye,
  Save,
} from 'lucide-react';

// Types
interface TestCase {
  id: string;
  name: string;
  description: string;
  query: string;
  expectedAnswer?: string;
  expectedContext?: string[];
  category: string;
  difficulty: 'easy' | 'medium' | 'hard';
  priority: 'low' | 'medium' | 'high';
  tags: string[];
  metrics: {
    answerRelevancy: { min: number; target: number; weight: number };
    faithfulness: { min: number; target: number; weight: number };
    contextualRelevancy: { min: number; target: number; weight: number };
  };
  created: string;
  updated: string;
  createdBy: string;
}

interface TestSuite {
  id: string;
  name: string;
  description: string;
  version: string;
  status: 'draft' | 'active' | 'archived';
  category: string;
  testCases: string[]; // Test case IDs
  schedule?: {
    enabled: boolean;
    frequency: 'hourly' | 'daily' | 'weekly' | 'monthly';
    timezone: string;
    nextRun: string;
  };
  settings: {
    timeout: number;
    retries: number;
    parallel: boolean;
    maxConcurrency: number;
    notificationOnFailure: boolean;
    notificationOnSuccess: boolean;
  };
  permissions: {
    view: string[];
    edit: string[];
    run: string[];
  };
  created: string;
  updated: string;
  createdBy: string;
  lastRun?: string;
  lastRunStatus?: 'success' | 'failure' | 'running';
  lastRunResults?: TestResults;
}

interface TestResults {
  totalTests: number;
  passedTests: number;
  failedTests: number;
  skippedTests: number;
  duration: number;
  averageMetrics: {
    answerRelevancy: number;
    faithfulness: number;
    contextualRelevancy: number;
  };
  individualResults: {
    testCaseId: string;
    status: 'passed' | 'failed' | 'skipped';
    metrics: {
      answerRelevancy: number;
      faithfulness: number;
      contextualRelevancy: number;
    };
    actualAnswer: string;
    actualContext: string[];
    errors: string[];
    duration: number;
  }[];
  startedAt: string;
  completedAt: string;
}

interface TestTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  testCases: Partial<TestCase>[];
  settings: Partial<TestSuite['settings']>;
}

// Mock data
const mockTestCases: TestCase[] = [
  {
    id: 'tc-001',
    name: 'Basic factual query about company revenue',
    description: 'Test if the system can accurately retrieve and answer basic factual questions',
    query: 'What was the company\'s revenue in the last fiscal year?',
    expectedAnswer: 'Should provide specific revenue figures with proper context',
    category: 'factual',
    difficulty: 'easy',
    priority: 'high',
    tags: ['revenue', 'financial', 'basic'],
    metrics: {
      answerRelevancy: { min: 70, target: 85, weight: 1.0 },
      faithfulness: { min: 90, target: 95, weight: 1.2 },
      contextualRelevancy: { min: 70, target: 85, weight: 0.8 },
    },
    created: '2025-10-01T10:00:00Z',
    updated: '2025-10-15T14:30:00Z',
    createdBy: 'john.doe',
  },
  {
    id: 'tc-002',
    name: 'Multi-step reasoning about market trends',
    description: 'Test complex reasoning requiring synthesis of multiple information sources',
    query: 'Based on recent market trends and our performance, what strategies should we consider for Q1?',
    category: 'reasoning',
    difficulty: 'hard',
    priority: 'high',
    tags: ['strategy', 'market-analysis', 'planning'],
    metrics: {
      answerRelevancy: { min: 70, target: 80, weight: 1.0 },
      faithfulness: { min: 85, target: 90, weight: 1.0 },
      contextualRelevancy: { min: 70, target: 80, weight: 1.0 },
    },
    created: '2025-10-02T11:15:00Z',
    updated: '2025-10-14T16:45:00Z',
    createdBy: 'jane.smith',
  },
  {
    id: 'tc-003',
    name: 'Document-specific content retrieval',
    description: 'Test ability to retrieve and synthesize information from specific documents',
    query: 'According to the Q3 financial report, what were the main drivers of revenue growth?',
    category: 'document-specific',
    difficulty: 'medium',
    priority: 'medium',
    tags: ['financial-report', 'revenue-growth', 'Q3'],
    metrics: {
      answerRelevancy: { min: 70, target: 85, weight: 1.0 },
      faithfulness: { min: 90, target: 95, weight: 1.5 },
      contextualRelevancy: { min: 75, target: 90, weight: 1.0 },
    },
    created: '2025-10-03T09:30:00Z',
    updated: '2025-10-13T12:00:00Z',
    createdBy: 'mike.johnson',
  },
];

const mockTestSuites: TestSuite[] = [
  {
    id: 'ts-001',
    name: 'Core RAG Functionality',
    description: 'Basic functionality tests for core RAG capabilities',
    version: '1.2.0',
    status: 'active',
    category: 'core',
    testCases: ['tc-001', 'tc-002', 'tc-003'],
    schedule: {
      enabled: true,
      frequency: 'daily',
      timezone: 'UTC',
      nextRun: '2025-10-17T00:00:00Z',
    },
    settings: {
      timeout: 30000,
      retries: 2,
      parallel: true,
      maxConcurrency: 5,
      notificationOnFailure: true,
      notificationOnSuccess: false,
    },
    permissions: {
      view: ['team-a', 'team-b'],
      edit: ['team-a'],
      run: ['team-a', 'qa-team'],
    },
    created: '2025-10-01T08:00:00Z',
    updated: '2025-10-15T16:00:00Z',
    createdBy: 'john.doe',
    lastRun: '2025-10-16T08:00:00Z',
    lastRunStatus: 'success',
  },
  {
    id: 'ts-002',
    name: 'Advanced Reasoning Tests',
    description: 'Complex reasoning and multi-step query tests',
    version: '0.9.0',
    status: 'draft',
    category: 'advanced',
    testCases: ['tc-002'],
    settings: {
      timeout: 60000,
      retries: 3,
      parallel: false,
      maxConcurrency: 1,
      notificationOnFailure: true,
      notificationOnSuccess: true,
    },
    permissions: {
      view: ['team-a'],
      edit: ['team-a'],
      run: ['team-a'],
    },
    created: '2025-10-10T10:00:00Z',
    updated: '2025-10-15T15:30:00Z',
    createdBy: 'jane.smith',
  },
];

const mockTestTemplates: TestTemplate[] = [
  {
    id: 'tt-001',
    name: 'Basic RAG Validation',
    description: 'Template for basic RAG functionality testing',
    category: 'basic',
    testCases: [
      {
        name: 'Simple factual query',
        query: 'What is the company\'s mission statement?',
        category: 'factual',
        difficulty: 'easy',
        priority: 'high',
      },
      {
        name: 'Document retrieval',
        query: 'Find information about product features',
        category: 'document-specific',
        difficulty: 'medium',
        priority: 'medium',
      },
    ],
    settings: {
      timeout: 30000,
      retries: 2,
      parallel: true,
      maxConcurrency: 3,
    },
  },
];

const EvaluationTestSuiteManagement: React.FC<EvaluationTestSuiteManagementProps> = ({
  onSuiteRun,
  onSuiteEdit,
  onTestCaseEdit,
  className,
}) => {
  const [testSuites] = useState<TestSuite[]>(mockTestSuites);
  const [testCases] = useState<TestCase[]>(mockTestCases);
  const [testTemplates] = useState<TestTemplate[]>(mockTestTemplates);
  const [selectedSuite, setSelectedSuite] = useState<TestSuite | null>(null);
  const [selectedTestCase, setSelectedTestCase] = useState<TestCase | null>(null);
  const [activeTab, setActiveTab] = useState('suites');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [isCreateSuiteOpen, setIsCreateSuiteOpen] = useState(false);
  const [isCreateTestCaseOpen, setIsCreateTestCaseOpen] = useState(false);
  const [isRunningSuite, setIsRunningSuite] = useState<string | null>(null);

  // Filter and search logic
  const filteredSuites = useMemo(() => {
    return testSuites.filter(suite => {
      const matchesSearch = suite.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           suite.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory = filterCategory === 'all' || suite.category === filterCategory;
      const matchesStatus = filterStatus === 'all' || suite.status === filterStatus;
      return matchesSearch && matchesCategory && matchesStatus;
    });
  }, [testSuites, searchTerm, filterCategory, filterStatus]);

  const filteredTestCases = useMemo(() => {
    return testCases.filter(testCase => {
      const matchesSearch = testCase.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           testCase.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           testCase.query.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory = filterCategory === 'all' || testCase.category === filterCategory;
      return matchesSearch && matchesCategory;
    });
  }, [testCases, searchTerm, filterCategory]);

  // Run test suite
  const runTestSuite = useCallback(async (suite: TestSuite) => {
    setIsRunningSuite(suite.id);

    // Simulate test run
    setTimeout(() => {
      setIsRunningSuite(null);
      onSuiteRun?.(suite);
    }, 3000);
  }, [onSuiteRun]);

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failure':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'running':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'failure':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'running':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'draft':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      case 'active':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'archived':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Test Suite Management</h2>
          <p className="text-gray-600 dark:text-gray-400">Manage evaluation test suites and test cases</p>
        </div>
        <div className="flex items-center space-x-2">
          <Dialog open={isCreateTestCaseOpen} onOpenChange={setIsCreateTestCaseOpen}>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Plus className="h-4 w-4 mr-2" />
                Test Case
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Create Test Case</DialogTitle>
                <DialogDescription>
                  Add a new test case to your evaluation suite
                </DialogDescription>
              </DialogHeader>
              <TestCaseForm
                onSubmit={(testCase) => {
                  console.log('Creating test case:', testCase);
                  setIsCreateTestCaseOpen(false);
                }}
                onCancel={() => setIsCreateTestCaseOpen(false)}
              />
            </DialogContent>
          </Dialog>

          <Dialog open={isCreateSuiteOpen} onOpenChange={setIsCreateSuiteOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Test Suite
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Create Test Suite</DialogTitle>
                <DialogDescription>
                  Create a new test suite to organize your test cases
                </DialogDescription>
              </DialogHeader>
              <TestSuiteForm
                testCases={testCases}
                onSubmit={(suite) => {
                  console.log('Creating test suite:', suite);
                  setIsCreateSuiteOpen(false);
                }}
                onCancel={() => setIsCreateSuiteOpen(false)}
              />
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center space-x-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search test suites and cases..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            <Select value={filterCategory} onValueChange={setFilterCategory}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                <SelectItem value="core">Core</SelectItem>
                <SelectItem value="advanced">Advanced</SelectItem>
                <SelectItem value="factual">Factual</SelectItem>
                <SelectItem value="reasoning">Reasoning</SelectItem>
                <SelectItem value="document-specific">Document Specific</SelectItem>
              </SelectContent>
            </Select>
            {activeTab === 'suites' && (
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="w-32">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="draft">Draft</SelectItem>
                  <SelectItem value="archived">Archived</SelectItem>
                </SelectContent>
              </Select>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="suites" className="flex items-center space-x-2">
            <List className="h-4 w-4" />
            <span>Test Suites</span>
          </TabsTrigger>
          <TabsTrigger value="cases" className="flex items-center space-x-2">
            <FileText className="h-4 w-4" />
            <span>Test Cases</span>
          </TabsTrigger>
          <TabsTrigger value="templates" className="flex items-center space-x-2">
            <Copy className="h-4 w-4" />
            <span>Templates</span>
          </TabsTrigger>
          <TabsTrigger value="results" className="flex items-center space-x-2">
            <BarChart3 className="h-4 w-4" />
            <span>Results</span>
          </TabsTrigger>
        </TabsList>

        {/* Test Suites Tab */}
        <TabsContent value="suites" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredSuites.map(suite => (
              <Card key={suite.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">{suite.name}</CardTitle>
                      <CardDescription className="mt-1">{suite.description}</CardDescription>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => setSelectedSuite(suite)}>
                          <Eye className="h-4 w-4 mr-2" />
                          View Details
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => onSuiteEdit?.(suite)}>
                          <Edit className="h-4 w-4 mr-2" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => runTestSuite(suite)}>
                          <Play className="h-4 w-4 mr-2" />
                          Run
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem>
                          <Download className="h-4 w-4 mr-2" />
                          Export
                        </DropdownMenuItem>
                        <DropdownMenuItem className="text-red-600">
                          <Trash2 className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Badge className={getStatusColor(suite.status)}>
                        {suite.status}
                      </Badge>
                      <Badge variant="outline">v{suite.version}</Badge>
                      <Badge variant="secondary">{suite.category}</Badge>
                    </div>
                    <div className="flex items-center space-x-2 text-sm text-gray-500">
                      <FileText className="h-4 w-4" />
                      <span>{suite.testCases.length} tests</span>
                    </div>
                  </div>

                  {suite.schedule?.enabled && (
                    <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
                      <Calendar className="h-4 w-4" />
                      <span>Runs {suite.schedule.frequency}</span>
                      <span>• Next: {new Date(suite.schedule.nextRun).toLocaleDateString()}</span>
                    </div>
                  )}

                  {suite.lastRun && (
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center space-x-2">
                        {getStatusIcon(suite.lastRunStatus || 'unknown')}
                        <span className="text-gray-600 dark:text-gray-400">
                          Last run: {new Date(suite.lastRun).toLocaleDateString()}
                        </span>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => runTestSuite(suite)}
                        disabled={isRunningSuite === suite.id}
                      >
                        {isRunningSuite === suite.id ? (
                          <>
                            <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                            Running...
                          </>
                        ) : (
                          <>
                            <Play className="h-4 w-4 mr-2" />
                            Run
                          </>
                        )}
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Test Cases Tab */}
        <TabsContent value="cases" className="space-y-4">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Difficulty</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTestCases.map(testCase => (
                  <TableRow key={testCase.id}>
                    <TableCell>
                      <div>
                        <div className="font-medium">{testCase.name}</div>
                        <div className="text-sm text-gray-500 line-clamp-1">
                          {testCase.description}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{testCase.category}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={testCase.difficulty === 'easy' ? 'default' :
                                testCase.difficulty === 'medium' ? 'secondary' : 'destructive'}
                      >
                        {testCase.difficulty}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={testCase.priority === 'high' ? 'destructive' :
                                testCase.priority === 'medium' ? 'default' : 'secondary'}
                      >
                        {testCase.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {new Date(testCase.created).toLocaleDateString()}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setSelectedTestCase(testCase)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onTestCaseEdit?.(testCase)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {testTemplates.map(template => (
              <Card key={template.id} className="hover:shadow-md transition-shadow">
                <CardHeader>
                  <CardTitle className="text-lg">{template.name}</CardTitle>
                  <CardDescription>{template.description}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Badge variant="outline">{template.category}</Badge>
                    <div className="text-sm text-gray-500">
                      {template.testCases.length} test cases
                    </div>
                  </div>
                  <div className="flex space-x-2">
                    <Button variant="outline" size="sm" className="flex-1">
                      <Copy className="h-4 w-4 mr-2" />
                      Use Template
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Eye className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Results Tab */}
        <TabsContent value="results" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Test Results</CardTitle>
              <CardDescription>View and analyze recent test execution results</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-gray-500">
                <BarChart3 className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No recent test results to display</p>
                <p className="text-sm">Run a test suite to see results here</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Test Case Detail Dialog */}
      {selectedTestCase && (
        <Dialog open={!!selectedTestCase} onOpenChange={() => setSelectedTestCase(null)}>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle>{selectedTestCase.name}</DialogTitle>
              <DialogDescription>{selectedTestCase.description}</DialogDescription>
            </DialogHeader>
            <ScrollArea className="max-h-96">
              <div className="space-y-4">
                <div>
                  <Label className="text-sm font-medium">Query</Label>
                  <div className="mt-1 p-3 bg-gray-50 dark:bg-gray-800 rounded-md">
                    {selectedTestCase.query}
                  </div>
                </div>

                {selectedTestCase.expectedAnswer && (
                  <div>
                    <Label className="text-sm font-medium">Expected Answer</Label>
                    <div className="mt-1 p-3 bg-gray-50 dark:bg-gray-800 rounded-md">
                      {selectedTestCase.expectedAnswer}
                    </div>
                  </div>
                )}

                <div>
                  <Label className="text-sm font-medium">Metrics Configuration</Label>
                  <div className="mt-2 space-y-2">
                    {Object.entries(selectedTestCase.metrics).map(([metric, config]) => (
                      <div key={metric} className="flex items-center justify-between p-2 border rounded">
                        <span className="font-medium capitalize">{metric.replace(/([A-Z])/g, ' $1').trim()}</span>
                        <div className="flex items-center space-x-4 text-sm">
                          <span>Min: {config.min}%</span>
                          <span>Target: {config.target}%</span>
                          <span>Weight: {config.weight}x</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <Badge variant="outline">{selectedTestCase.category}</Badge>
                  <Badge variant={selectedTestCase.difficulty === 'easy' ? 'default' :
                                  selectedTestCase.difficulty === 'medium' ? 'secondary' : 'destructive'}>
                    {selectedTestCase.difficulty}
                  </Badge>
                  <Badge variant={selectedTestCase.priority === 'high' ? 'destructive' :
                                  selectedTestCase.priority === 'medium' ? 'default' : 'secondary'}>
                    {selectedTestCase.priority}
                  </Badge>
                </div>
              </div>
            </ScrollArea>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

// Test Suite Form Component
const TestSuiteForm: React.FC<TestSuiteFormProps> = ({ testCases, onSubmit, onCancel }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    category: 'core',
    selectedTestCases: [] as string[],
    scheduleEnabled: false,
    frequency: 'daily',
    timeout: 30000,
    retries: 2,
    parallel: true,
    maxConcurrency: 5,
    notificationOnFailure: true,
    notificationOnSuccess: false,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      ...formData,
      testCases: formData.selectedTestCases,
      schedule: formData.scheduleEnabled ? {
        enabled: true,
        frequency: formData.frequency as any,
        timezone: 'UTC',
        nextRun: new Date().toISOString(),
      } : undefined,
    } as any);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="suite-name">Name</Label>
        <Input
          id="suite-name"
          value={formData.name}
          onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
          placeholder="Enter test suite name"
          required
        />
      </div>

      <div>
        <Label htmlFor="suite-description">Description</Label>
        <Textarea
          id="suite-description"
          value={formData.description}
          onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
          placeholder="Describe the purpose of this test suite"
          rows={3}
        />
      </div>

      <div>
        <Label htmlFor="suite-category">Category</Label>
        <Select value={formData.category} onValueChange={(value) => setFormData(prev => ({ ...prev, category: value }))}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="core">Core</SelectItem>
            <SelectItem value="advanced">Advanced</SelectItem>
            <SelectItem value="regression">Regression</SelectItem>
            <SelectItem value="performance">Performance</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="schedule-enabled"
          checked={formData.scheduleEnabled}
          onCheckedChange={(checked) => setFormData(prev => ({ ...prev, scheduleEnabled: checked }))}
        />
        <Label htmlFor="schedule-enabled">Enable scheduled runs</Label>
      </div>

      {formData.scheduleEnabled && (
        <div>
          <Label htmlFor="frequency">Frequency</Label>
          <Select value={formData.frequency} onValueChange={(value) => setFormData(prev => ({ ...prev, frequency: value }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hourly">Hourly</SelectItem>
              <SelectItem value="daily">Daily</SelectItem>
              <SelectItem value="weekly">Weekly</SelectItem>
              <SelectItem value="monthly">Monthly</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <Save className="h-4 w-4 mr-2" />
          Create Test Suite
        </Button>
      </div>
    </form>
  );
};

// Test Case Form Component
const TestCaseForm: React.FC<TestCaseFormProps> = ({ onSubmit, onCancel }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    query: '',
    expectedAnswer: '',
    category: 'factual',
    difficulty: 'medium' as const,
    priority: 'medium' as const,
    tags: '',
    answerRelevancyMin: 70,
    answerRelevancyTarget: 85,
    answerRelevancyWeight: 1.0,
    faithfulnessMin: 90,
    faithfulnessTarget: 95,
    faithfulnessWeight: 1.2,
    contextualRelevancyMin: 70,
    contextualRelevancyTarget: 85,
    contextualRelevancyWeight: 0.8,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      ...formData,
      tags: formData.tags.split(',').map(tag => tag.trim()).filter(Boolean),
      metrics: {
        answerRelevancy: {
          min: formData.answerRelevancyMin,
          target: formData.answerRelevancyTarget,
          weight: formData.answerRelevancyWeight,
        },
        faithfulness: {
          min: formData.faithfulnessMin,
          target: formData.faithfulnessTarget,
          weight: formData.faithfulnessWeight,
        },
        contextualRelevancy: {
          min: formData.contextualRelevancyMin,
          target: formData.contextualRelevancyTarget,
          weight: formData.contextualRelevancyWeight,
        },
      },
    } as any);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <Label htmlFor="test-name">Name</Label>
        <Input
          id="test-name"
          value={formData.name}
          onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
          placeholder="Enter test case name"
          required
        />
      </div>

      <div>
        <Label htmlFor="test-description">Description</Label>
        <Textarea
          id="test-description"
          value={formData.description}
          onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
          placeholder="Describe what this test case validates"
          rows={2}
        />
      </div>

      <div>
        <Label htmlFor="test-query">Query</Label>
        <Textarea
          id="test-query"
          value={formData.query}
          onChange={(e) => setFormData(prev => ({ ...prev, query: e.target.value }))}
          placeholder="Enter the test query"
          rows={2}
          required
        />
      </div>

      <div>
        <Label htmlFor="expected-answer">Expected Answer (Optional)</Label>
        <Textarea
          id="expected-answer"
          value={formData.expectedAnswer}
          onChange={(e) => setFormData(prev => ({ ...prev, expectedAnswer: e.target.value }))}
          placeholder="Describe the expected answer"
          rows={2}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label htmlFor="test-category">Category</Label>
          <Select value={formData.category} onValueChange={(value) => setFormData(prev => ({ ...prev, category: value }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="factual">Factual</SelectItem>
              <SelectItem value="reasoning">Reasoning</SelectItem>
              <SelectItem value="document-specific">Document Specific</SelectItem>
              <SelectItem value="multimodal">Multimodal</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div>
          <Label htmlFor="test-difficulty">Difficulty</Label>
          <Select value={formData.difficulty} onValueChange={(value: any) => setFormData(prev => ({ ...prev, difficulty: value }))}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="easy">Easy</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="hard">Hard</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex justify-end space-x-2 pt-4">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit">
          <Save className="h-4 w-4 mr-2" />
          Create Test Case
        </Button>
      </div>
    </form>
  );
};

export default EvaluationTestSuiteManagement;

interface EvaluationTestSuiteManagementProps {
  onSuiteRun?: (suite: TestSuite) => void;
  onSuiteEdit?: (suite: TestSuite) => void;
  onTestCaseEdit?: (testCase: TestCase) => void;
  className?: string;
}

interface TestSuiteFormProps {
  testCases: TestCase[];
  onSubmit: (suite: Partial<TestSuite>) => void;
  onCancel: () => void;
}

interface TestCaseFormProps {
  onSubmit: (testCase: Partial<TestCase>) => void;
  onCancel: () => void;
}