import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Shield,
  Scale,
  FileCheck,
  AlertTriangle,
  CheckCircle,
  Clock,
  Users,
  BookOpen,
  Gavel,
  Award,
  TrendingUp,
  BarChart3,
  Download,
  Upload,
  Search,
  Filter,
  Settings,
  Eye,
  EyeOff,
  Calendar,
  Target,
  Flag,
  Lock,
  Unlock,
  RefreshCw,
  ChevronRight,
  Info,
  ExternalLink,
  FileText,
  Database,
  Activity
} from 'lucide-react';

interface CompliancePolicy {
  id: string;
  name: string;
  description: string;
  category: 'data_privacy' | 'security' | 'quality' | 'ethical_ai' | 'industry_regulation' | 'internal_policy';
  type: 'mandatory' | 'recommended' | 'guideline';
  status: 'active' | 'draft' | 'deprecated' | 'under_review';
  version: string;
  lastUpdated: string;
  nextReview: string;
  owner: string;
  approvers: string[];
  requirements: {
    controls: string[];
    checks: string[];
    documentation: string[];
    frequency: 'continuous' | 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'annually';
  };
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  complianceScore: number;
  violations: number;
  lastAudit: string;
}

interface QualityStandard {
  id: string;
  name: string;
  framework: 'ISO' | 'SOC' | 'GDPR' | 'HIPAA' | 'NIST' | 'internal';
  description: string;
  category: 'process' | 'technical' | 'documentation' | 'security' | 'privacy';
  maturityLevel: number;
  targetLevel: number;
  status: 'compliant' | 'non_compliant' | 'in_progress' | 'not_assessed';
  lastAssessment: string;
  nextAssessment: string;
  evidence: {
    documents: string[];
    tests: string[];
    metrics: string[];
  };
  gaps: string[];
  remediationPlan?: {
    actions: string[];
    owner: string;
    dueDate: string;
    status: 'pending' | 'in_progress' | 'completed';
  };
}

interface AuditReport {
  id: string;
  title: string;
  type: 'internal' | 'external' | 'regulatory' | 'security' | 'quality';
  status: 'scheduled' | 'in_progress' | 'completed' | 'failed';
  startDate: string;
  endDate: string;
  auditor: string;
  scope: string[];
  findings: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    total: number;
  };
  complianceScore: number;
  recommendations: string[];
  evidenceRequired: string[];
  reportUrl?: string;
}

interface GovernanceMetric {
  name: string;
  current: number;
  target: number;
  trend: 'improving' | 'declining' | 'stable';
  lastUpdated: string;
  category: 'compliance' | 'quality' | 'security' | 'risk';
}

const mockPolicies: CompliancePolicy[] = [
  {
    id: 'pol-001',
    name: 'Data Privacy and Protection Policy',
    description: 'Comprehensive policy for handling user data in accordance with GDPR and CCPA requirements',
    category: 'data_privacy',
    type: 'mandatory',
    status: 'active',
    version: '2.1',
    lastUpdated: '2025-01-10T00:00:00Z',
    nextReview: '2025-04-10T00:00:00Z',
    owner: 'Data Protection Officer',
    approvers: ['CEO', 'CTO', 'Legal Counsel'],
    requirements: {
      controls: ['Data encryption at rest and in transit', 'Access controls and authentication', 'Data minimization principles'],
      checks: ['Quarterly privacy impact assessments', 'Annual data protection audits', 'Monthly access reviews'],
      documentation: ['Data processing records', 'Privacy notices', 'Data breach procedures'],
      frequency: 'quarterly'
    },
    riskLevel: 'critical',
    complianceScore: 94,
    violations: 2,
    lastAudit: '2025-01-15T00:00:00Z'
  },
  {
    id: 'pol-002',
    name: 'AI Ethics and Responsible AI Framework',
    description: 'Guidelines for ethical development and deployment of AI systems',
    category: 'ethical_ai',
    type: 'mandatory',
    status: 'active',
    version: '1.3',
    lastUpdated: '2025-01-08T00:00:00Z',
    nextReview: '2025-07-08T00:00:00Z',
    owner: 'AI Ethics Committee',
    approvers: ['Head of AI', 'Chief Ethics Officer'],
    requirements: {
      controls: ['Bias detection and mitigation', 'Transparency in AI decisions', 'Human oversight mechanisms'],
      checks: ['Monthly bias audits', 'Quarterly fairness assessments', 'Annual ethics reviews'],
      documentation: ['Model documentation', 'Ethical impact assessments', 'Transparency reports'],
      frequency: 'monthly'
    },
    riskLevel: 'high',
    complianceScore: 87,
    violations: 5,
    lastAudit: '2025-01-12T00:00:00Z'
  },
  {
    id: 'pol-003',
    name: 'Quality Management System',
    description: 'ISO 9001 aligned quality management processes and procedures',
    category: 'quality',
    type: 'mandatory',
    status: 'active',
    version: '3.0',
    lastUpdated: '2025-01-05T00:00:00Z',
    nextReview: '2025-04-05T00:00:00Z',
    owner: 'Quality Manager',
    approvers: ['COO', 'Head of QA'],
    requirements: {
      controls: ['Documented quality procedures', 'Continuous improvement processes', 'Customer feedback systems'],
      checks: ['Monthly quality metrics review', 'Quarterly internal audits', 'Annual management review'],
      documentation: ['Quality manual', 'Procedures', 'Work instructions', 'Quality records'],
      frequency: 'monthly'
    },
    riskLevel: 'medium',
    complianceScore: 91,
    violations: 3,
    lastAudit: '2025-01-18T00:00:00Z'
  },
  {
    id: 'pol-004',
    name: 'Information Security Management',
    description: 'Security controls and procedures based on ISO 27001 framework',
    category: 'security',
    type: 'mandatory',
    status: 'under_review',
    version: '2.2',
    lastUpdated: '2025-01-15T00:00:00Z',
    nextReview: '2025-02-15T00:00:00Z',
    owner: 'CISO',
    approvers: ['CTO', 'Security Committee'],
    requirements: {
      controls: ['Access management', 'Incident response', 'Business continuity', 'Risk assessment'],
      checks: ['Vulnerability scanning', 'Penetration testing', 'Security awareness training'],
      documentation: ['Security policies', 'Risk assessments', 'Incident reports'],
      frequency: 'continuous'
    },
    riskLevel: 'critical',
    complianceScore: 96,
    violations: 1,
    lastAudit: '2025-01-16T00:00:00Z'
  }
];

const mockStandards: QualityStandard[] = [
  {
    id: 'std-001',
    name: 'ISO 9001:2015 Quality Management',
    framework: 'ISO',
    description: 'Quality management system requirements for consistent service delivery',
    category: 'process',
    maturityLevel: 3,
    targetLevel: 4,
    status: 'in_progress',
    lastAssessment: '2025-01-10T00:00:00Z',
    nextAssessment: '2025-04-10T00:00:00Z',
    evidence: {
      documents: ['Quality Manual', 'Process Documentation'],
      tests: ['Internal Audits', 'Process Effectiveness Tests'],
      metrics: ['Customer Satisfaction', 'Process Efficiency']
    },
    gaps: ['Enhanced risk-based thinking', 'Improved documentation control'],
    remediationPlan: {
      actions: ['Update risk assessment procedures', 'Implement document management system'],
      owner: 'Quality Manager',
      dueDate: '2025-03-31T00:00:00Z',
      status: 'in_progress'
    }
  },
  {
    id: 'std-002',
    name: 'SOC 2 Type II Compliance',
    framework: 'SOC',
    description: 'Security, availability, processing integrity, confidentiality, and privacy controls',
    category: 'security',
    maturityLevel: 4,
    targetLevel: 4,
    status: 'compliant',
    lastAssessment: '2025-01-05T00:00:00Z',
    nextAssessment: '2025-07-05T00:00:00Z',
    evidence: {
      documents: ['Security Policies', 'Control Documentation'],
      tests: ['Independent Auditor Tests', 'Control Effectiveness Testing'],
      metrics: ['Control Coverage', 'Exception Rates']
    },
    gaps: []
  },
  {
    id: 'std-003',
    name: 'GDPR Compliance',
    framework: 'GDPR',
    description: 'General Data Protection Regulation compliance for EU user data',
    category: 'privacy',
    maturityLevel: 4,
    targetLevel: 4,
    status: 'compliant',
    lastAssessment: '2025-01-08T00:00:00Z',
    nextAssessment: '2025-04-08T00:00:00Z',
    evidence: {
      documents: ['Privacy Policy', 'Data Processing Agreement'],
      tests: ['Data Protection Impact Assessment', 'Consent Management Testing'],
      metrics: ['Data Subject Requests', 'Breach Response Time']
    },
    gaps: []
  }
];

const mockAudits: AuditReport[] = [
  {
    id: 'audit-001',
    title: 'Q1 2025 Internal Quality Audit',
    type: 'internal',
    status: 'completed',
    startDate: '2025-01-08T00:00:00Z',
    endDate: '2025-01-12T00:00:00Z',
    auditor: 'Internal Audit Team',
    scope: ['Quality Management System', 'Document Control', 'Process Effectiveness'],
    findings: {
      critical: 0,
      high: 2,
      medium: 5,
      low: 8,
      total: 15
    },
    complianceScore: 89,
    recommendations: [
      'Strengthen document version control procedures',
      'Enhance customer feedback collection mechanisms',
      'Improve process performance monitoring'
    ],
    evidenceRequired: [
      'Updated process documentation',
      'Customer feedback reports',
      'Performance metrics data'
    ],
    reportUrl: '/reports/q1-2025-quality-audit.pdf'
  },
  {
    id: 'audit-002',
    title: 'Annual External Security Audit',
    type: 'external',
    status: 'scheduled',
    startDate: '2025-02-01T00:00:00Z',
    endDate: '2025-02-14T00:00:00Z',
    auditor: 'Independent Security Firm',
    scope: ['Network Security', 'Application Security', 'Access Controls'],
    findings: {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      total: 0
    },
    complianceScore: 0,
    recommendations: [],
    evidenceRequired: [
      'Network architecture diagrams',
      'Security configurations',
      'Access control matrices'
    ]
  },
  {
    id: 'audit-003',
    title: 'Data Protection Impact Assessment',
    type: 'regulatory',
    status: 'in_progress',
    startDate: '2025-01-15T00:00:00Z',
    endDate: '2025-01-25T00:00:00Z',
    auditor: 'Data Protection Officer',
    scope: ['Personal Data Processing', 'Data Subject Rights', 'Cross-border Transfers'],
    findings: {
      critical: 0,
      high: 1,
      medium: 3,
      low: 2,
      total: 6
    },
    complianceScore: 92,
    recommendations: [
      'Update privacy notices for better transparency',
      'Strengthen data subject rights processes'
    ],
    evidenceRequired: [
      'Updated privacy notices',
      'Data subject request procedures'
    ]
  }
];

const mockMetrics: GovernanceMetric[] = [
  { name: 'Overall Compliance Score', current: 92, target: 95, trend: 'improving', lastUpdated: '2025-01-18T10:30:00Z', category: 'compliance' },
  { name: 'Policy Coverage', current: 87, target: 100, trend: 'stable', lastUpdated: '2025-01-18T10:30:00Z', category: 'compliance' },
  { name: 'Audit Findings Resolution', current: 78, target: 90, trend: 'improving', lastUpdated: '2025-01-18T10:30:00Z', category: 'quality' },
  { name: 'Security Controls Maturity', current: 4.2, target: 5.0, trend: 'improving', lastUpdated: '2025-01-18T10:30:00Z', category: 'security' },
  { name: 'Risk Mitigation Coverage', current: 85, target: 95, trend: 'stable', lastUpdated: '2025-01-18T10:30:00Z', category: 'risk' }
];

export default function QualityGovernanceCompliance() {
  const [policies, setPolicies] = useState<CompliancePolicy[]>(mockPolicies);
  const [standards, setStandards] = useState<QualityStandard[]>(mockStandards);
  const [audits, setAudits] = useState<AuditReport[]>(mockAudits);
  const [metrics] = useState<GovernanceMetric[]>(mockMetrics);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [activeTab, setActiveTab] = useState('overview');

  const categoryColors = {
    data_privacy: 'bg-blue-500',
    security: 'bg-red-500',
    quality: 'bg-green-500',
    ethical_ai: 'bg-purple-500',
    industry_regulation: 'bg-orange-500',
    internal_policy: 'bg-gray-500'
  };

  const statusColors = {
    active: 'bg-green-100 text-green-700',
    draft: 'bg-gray-100 text-gray-700',
    deprecated: 'bg-red-100 text-red-700',
    under_review: 'bg-yellow-100 text-yellow-700',
    compliant: 'bg-green-100 text-green-700',
    non_compliant: 'bg-red-100 text-red-700',
    in_progress: 'bg-blue-100 text-blue-700',
    not_assessed: 'bg-gray-100 text-gray-700'
  };

  const riskColors = {
    low: 'bg-green-100 text-green-700',
    medium: 'bg-yellow-100 text-yellow-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700'
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'improving':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'declining':
        return <TrendingUp className="h-4 w-4 text-red-500 rotate-180" />;
      default:
        return <Activity className="h-4 w-4 text-gray-500" />;
    }
  };

  const filteredPolicies = policies.filter(policy =>
    selectedCategory === 'all' || policy.category === selectedCategory
  );

  const stats = {
    totalPolicies: policies.length,
    activePolicies: policies.filter(p => p.status === 'active').length,
    avgCompliance: policies.length > 0 ? Math.round(policies.reduce((acc, p) => acc + p.complianceScore, 0) / policies.length) : 0,
    totalViolations: policies.reduce((acc, p) => acc + p.violations, 0),
    criticalRisks: policies.filter(p => p.riskLevel === 'critical').length,
    upcomingAudits: audits.filter(a => a.status === 'scheduled').length
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Quality Governance & Compliance</h1>
          <p className="text-gray-600">Policies, standards, and compliance management for quality assurance</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="flex items-center gap-2">
            <Download className="h-4 w-4" />
            Export Reports
          </Button>
          <Button className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Schedule Audit
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <FileCheck className="h-4 w-4 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">{stats.totalPolicies}</p>
                <p className="text-xs text-gray-600">Total Policies</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <div>
                <p className="text-2xl font-bold">{stats.activePolicies}</p>
                <p className="text-xs text-gray-600">Active</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-purple-500" />
              <div>
                <p className="text-2xl font-bold">{stats.avgCompliance}%</p>
                <p className="text-xs text-gray-600">Avg Compliance</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
              <div>
                <p className="text-2xl font-bold">{stats.totalViolations}</p>
                <p className="text-xs text-gray-600">Violations</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Flag className="h-4 w-4 text-orange-500" />
              <div>
                <p className="text-2xl font-bold">{stats.criticalRisks}</p>
                <p className="text-xs text-gray-600">Critical Risks</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-indigo-500" />
              <div>
                <p className="text-2xl font-bold">{stats.upcomingAudits}</p>
                <p className="text-xs text-gray-600">Upcoming Audits</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="policies">Policies</TabsTrigger>
          <TabsTrigger value="standards">Standards</TabsTrigger>
          <TabsTrigger value="audits">Audits</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {/* Compliance Dashboard */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Compliance Status</CardTitle>
                <CardDescription>Overall compliance across all policy categories</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {Object.entries(
                    policies.reduce((acc, policy) => {
                      const category = policy.category;
                      if (!acc[category]) {
                        acc[category] = { total: 0, compliant: 0 };
                      }
                      acc[category]!.total++;
                      if (policy.complianceScore >= 90) {
                        acc[category]!.compliant++;
                      }
                      return acc;
                    }, {} as Record<string, { total: number; compliant: number }>)
                  ).map(([category, data]) => (
                    <div key={category} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${categoryColors[category as keyof typeof categoryColors]}`} />
                        <span className="text-sm font-medium capitalize">
                          {category.replace('_', ' ')}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Progress
                          value={(data.compliant / data.total) * 100}
                          className="w-20 h-2"
                        />
                        <span className="text-sm text-gray-600">
                          {data.compliant}/{data.total}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Upcoming Audits</CardTitle>
                <CardDescription>Scheduled audits and assessments</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {audits.filter(a => a.status === 'scheduled' || a.status === 'in_progress').map((audit) => (
                    <div key={audit.id} className="p-3 border rounded-lg">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-medium">{audit.title}</h4>
                          <p className="text-sm text-gray-600">{audit.auditor}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant="outline">{audit.type}</Badge>
                            <Badge className={audit.status === 'in_progress' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}>
                              {audit.status.replace('_', ' ').toUpperCase()}
                            </Badge>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-medium">
                            {new Date(audit.startDate).toLocaleDateString()}
                          </div>
                          <div className="text-xs text-gray-600">
                            {Math.ceil((new Date(audit.endDate).getTime() - new Date(audit.startDate).getTime()) / (1000 * 60 * 60 * 24))} days
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Violations */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Policy Violations</CardTitle>
              <CardDescription>Recent compliance violations and remediation status</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {policies.filter(p => p.violations > 0).map((policy) => (
                  <div key={policy.id} className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <AlertTriangle className="h-5 w-5 text-red-500" />
                      <div>
                        <div className="font-medium">{policy.name}</div>
                        <div className="text-sm text-gray-600">
                          {policy.violations} violations • Last audit: {new Date(policy.lastAudit).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={riskColors[policy.riskLevel]}>
                        {policy.riskLevel.toUpperCase()}
                      </Badge>
                      <Button variant="outline" size="sm">
                        View Details
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="policies" className="space-y-4">
          {/* Policy Filters */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Policy Management</CardTitle>
              <CardDescription>Organizational policies and compliance requirements</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4 mb-4">
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4" />
                  <span className="text-sm font-medium">Category:</span>
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="px-3 py-1 border rounded-md text-sm"
                  >
                    <option value="all">All Categories</option>
                    <option value="data_privacy">Data Privacy</option>
                    <option value="security">Security</option>
                    <option value="quality">Quality</option>
                    <option value="ethical_ai">Ethical AI</option>
                    <option value="industry_regulation">Industry Regulation</option>
                    <option value="internal_policy">Internal Policy</option>
                  </select>
                </div>
              </div>

              <div className="space-y-4">
                {filteredPolicies.map((policy) => (
                  <Card key={policy.id}>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            <div className={`w-3 h-3 rounded-full ${categoryColors[policy.category]}`} />
                            <CardTitle className="text-base">{policy.name}</CardTitle>
                            <Badge className={statusColors[policy.status]}>
                              {policy.status.replace('_', ' ').toUpperCase()}
                            </Badge>
                            <Badge className={riskColors[policy.riskLevel]}>
                              {policy.riskLevel.toUpperCase()} RISK
                            </Badge>
                          </div>
                          <CardDescription>{policy.description}</CardDescription>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold">{policy.complianceScore}%</div>
                          <div className="text-xs text-gray-600">Compliance</div>
                          <Progress value={policy.complianceScore} className="w-16 h-2 mt-1" />
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="font-medium">Version:</span> {policy.version}
                        </div>
                        <div>
                          <span className="font-medium">Owner:</span> {policy.owner}
                        </div>
                        <div>
                          <span className="font-medium">Next Review:</span> {new Date(policy.nextReview).toLocaleDateString()}
                        </div>
                        <div>
                          <span className="font-medium">Violations:</span>
                          <span className={policy.violations > 0 ? 'text-red-600 font-medium' : ''}>
                            {' '}{policy.violations}
                          </span>
                        </div>
                      </div>
                      {policy.violations > 0 && (
                        <Alert className="mt-4">
                          <AlertTriangle className="h-4 w-4" />
                          <AlertTitle>Compliance Issues</AlertTitle>
                          <AlertDescription>
                            This policy has {policy.violations} reported violations requiring attention.
                          </AlertDescription>
                        </Alert>
                      )}
                      <div className="flex justify-between items-center mt-4 pt-4 border-t">
                        <div className="text-xs text-gray-500">
                          Last updated: {new Date(policy.lastUpdated).toLocaleDateString()}
                        </div>
                        <div className="flex gap-2">
                          <Button variant="outline" size="sm">
                            <Eye className="h-4 w-4 mr-1" />
                            View
                          </Button>
                          <Button variant="outline" size="sm">
                            <Settings className="h-4 w-4 mr-1" />
                            Edit
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="standards" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Quality Standards & Frameworks</CardTitle>
              <CardDescription>Compliance with industry standards and quality frameworks</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {standards.map((standard) => (
                  <Card key={standard.id}>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <Award className="h-5 w-5 text-blue-500" />
                            <CardTitle className="text-base">{standard.name}</CardTitle>
                            <Badge variant="outline">{standard.framework}</Badge>
                            <Badge className={statusColors[standard.status]}>
                              {standard.status.replace('_', ' ').toUpperCase()}
                            </Badge>
                          </div>
                          <CardDescription>{standard.description}</CardDescription>
                        </div>
                        <div className="text-right">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-gray-600">Maturity:</span>
                            <div className="flex items-center gap-1">
                              {[...Array(5)].map((_, i) => (
                                <div
                                  key={i}
                                  className={`w-2 h-2 rounded-full ${
                                    i < standard.maturityLevel ? 'bg-green-500' : 'bg-gray-300'
                                  }`}
                                />
                              ))}
                              <span className="text-sm font-medium ml-1">
                                {standard.maturityLevel}/{standard.targetLevel}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                          <div>
                            <span className="font-medium">Category:</span> {standard.category}
                          </div>
                          <div>
                            <span className="font-medium">Last Assessment:</span> {new Date(standard.lastAssessment).toLocaleDateString()}
                          </div>
                        </div>

                        {standard.gaps.length > 0 && (
                          <div>
                            <h4 className="font-medium text-sm mb-2">Identified Gaps:</h4>
                            <ul className="text-sm space-y-1">
                              {standard.gaps.map((gap, idx) => (
                                <li key={idx} className="flex items-center gap-2">
                                  <div className="w-1.5 h-1.5 bg-orange-500 rounded-full" />
                                  {gap}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {standard.remediationPlan && (
                          <div className="p-3 bg-yellow-50 rounded">
                            <h4 className="font-medium text-sm mb-1">Remediation Plan</h4>
                            <div className="text-sm text-gray-700">
                              <div>Owner: {standard.remediationPlan.owner}</div>
                              <div>Due: {new Date(standard.remediationPlan.dueDate).toLocaleDateString()}</div>
                              <div>Status: {standard.remediationPlan.status.replace('_', ' ')}</div>
                            </div>
                          </div>
                        )}

                        <div className="flex justify-between items-center pt-3 border-t">
                          <div className="text-xs text-gray-500">
                            Next assessment: {new Date(standard.nextAssessment).toLocaleDateString()}
                          </div>
                          <div className="flex gap-2">
                            <Button variant="outline" size="sm">
                              View Evidence
                            </Button>
                            {standard.status !== 'compliant' && (
                              <Button size="sm">
                                Improve Compliance
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audits" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Audit Management</CardTitle>
              <CardDescription>Internal and external audit reports and findings</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {audits.map((audit) => (
                  <Card key={audit.id}>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <Gavel className="h-5 w-5 text-purple-500" />
                            <CardTitle className="text-base">{audit.title}</CardTitle>
                            <Badge variant="outline">{audit.type}</Badge>
                            <Badge className={audit.status === 'completed' ? 'bg-green-100 text-green-700' : audit.status === 'in_progress' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}>
                              {audit.status.replace('_', ' ').toUpperCase()}
                            </Badge>
                          </div>
                          <CardDescription>
                            Auditor: {audit.auditor} •
                            {new Date(audit.startDate).toLocaleDateString()} - {new Date(audit.endDate).toLocaleDateString()}
                          </CardDescription>
                        </div>
                        {audit.status === 'completed' && (
                          <div className="text-right">
                            <div className="text-2xl font-bold">{audit.complianceScore}%</div>
                            <div className="text-xs text-gray-600">Compliance Score</div>
                          </div>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {audit.status === 'completed' && (
                          <>
                            <div>
                              <h4 className="font-medium text-sm mb-2">Audit Findings</h4>
                              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <div className="text-center p-2 bg-red-50 rounded">
                                  <div className="text-lg font-bold text-red-600">{audit.findings.critical}</div>
                                  <div className="text-xs text-gray-600">Critical</div>
                                </div>
                                <div className="text-center p-2 bg-orange-50 rounded">
                                  <div className="text-lg font-bold text-orange-600">{audit.findings.high}</div>
                                  <div className="text-xs text-gray-600">High</div>
                                </div>
                                <div className="text-center p-2 bg-yellow-50 rounded">
                                  <div className="text-lg font-bold text-yellow-600">{audit.findings.medium}</div>
                                  <div className="text-xs text-gray-600">Medium</div>
                                </div>
                                <div className="text-center p-2 bg-blue-50 rounded">
                                  <div className="text-lg font-bold text-blue-600">{audit.findings.low}</div>
                                  <div className="text-xs text-gray-600">Low</div>
                                </div>
                              </div>
                            </div>

                            {audit.recommendations.length > 0 && (
                              <div>
                                <h4 className="font-medium text-sm mb-2">Key Recommendations</h4>
                                <ul className="text-sm space-y-1">
                                  {audit.recommendations.slice(0, 3).map((rec, idx) => (
                                    <li key={idx} className="flex items-center gap-2">
                                      <ChevronRight className="h-3 w-3 text-gray-400" />
                                      {rec}
                                    </li>
                                  ))}
                                  {audit.recommendations.length > 3 && (
                                    <li className="text-gray-500">
                                      ...and {audit.recommendations.length - 3} more
                                    </li>
                                  )}
                                </ul>
                              </div>
                            )}
                          </>
                        )}

                        <div className="flex justify-between items-center pt-3 border-t">
                          <div className="text-sm text-gray-600">
                            <span className="font-medium">Scope:</span> {audit.scope.join(', ')}
                          </div>
                          <div className="flex gap-2">
                            {audit.reportUrl && (
                              <Button variant="outline" size="sm">
                                <Download className="h-4 w-4 mr-1" />
                                Download Report
                              </Button>
                            )}
                            <Button variant="outline" size="sm">
                              View Details
                            </Button>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="metrics" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Governance Metrics</CardTitle>
              <CardDescription>Key performance indicators for governance and compliance</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {metrics.map((metric, idx) => (
                  <div key={idx} className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {getTrendIcon(metric.trend)}
                        <div>
                          <div className="font-medium">{metric.name}</div>
                          <div className="text-sm text-gray-600">
                            Last updated: {new Date(metric.lastUpdated).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center gap-2">
                          <span className="text-2xl font-bold">
                            {metric.category === 'security' ? metric.current.toFixed(1) : metric.current}
                          </span>
                          <span className="text-gray-500">
                            / {metric.category === 'security' ? metric.target.toFixed(1) : metric.target}
                          </span>
                        </div>
                        <Progress
                          value={(metric.current / metric.target) * 100}
                          className="w-32 h-2 mt-1"
                        />
                        <div className="text-xs text-gray-600 mt-1">
                          {Math.round((metric.current / metric.target) * 100)}% of target
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}