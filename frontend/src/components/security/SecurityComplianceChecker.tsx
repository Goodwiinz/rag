import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Shield,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  FileText,
  Users,
  Lock,
  Eye,
  Database,
  Server,
  Globe,
  Key,
  Award,
  Target,
  RefreshCw,
  Download,
  Settings,
  Info,
  ExternalLink,
  ChevronRight
} from 'lucide-react';

interface ComplianceCheck {
  id: string;
  name: string;
  description: string;
  category: 'data_protection' | 'access_control' | 'encryption' | 'audit_logging' | 'vulnerability_management' | 'security_policy';
  status: 'pass' | 'fail' | 'warning' | 'pending';
  severity: 'low' | 'medium' | 'high' | 'critical';
  lastChecked: string;
  nextCheck: string;
  details: string;
  recommendations: string[];
  evidence: string[];
  automated: boolean;
  frequency: 'continuous' | 'daily' | 'weekly' | 'monthly' | 'quarterly';
}

interface ComplianceFramework {
  name: string;
  version: string;
  description: string;
  checks: string[];
  overallScore: number;
  status: 'compliant' | 'non_compliant' | 'partial';
  lastAssessment: string;
  nextAssessment: string;
}

interface SecurityMetric {
  name: string;
  value: number;
  target: number;
  unit: string;
  status: 'good' | 'warning' | 'critical';
  trend: 'improving' | 'stable' | 'declining';
  lastUpdated: string;
}

const mockComplianceChecks: ComplianceCheck[] = [
  {
    id: 'check-001',
    name: 'Data Encryption at Rest',
    description: 'Ensure all sensitive data is encrypted when stored in databases',
    category: 'encryption',
    status: 'pass',
    severity: 'critical',
    lastChecked: '2025-10-17T10:30:00Z',
    nextCheck: '2025-10-24T10:30:00Z',
    details: 'All database fields containing PII are encrypted using AES-256 encryption',
    recommendations: [],
    evidence: ['Database schema review', 'Encryption configuration audit'],
    automated: true,
    frequency: 'continuous'
  },
  {
    id: 'check-002',
    name: 'Data Encryption in Transit',
    description: 'Ensure all data transmitted over networks is encrypted using TLS 1.2+',
    category: 'encryption',
    status: 'pass',
    severity: 'critical',
    lastChecked: '2025-10-17T10:25:00Z',
    nextCheck: '2025-10-18T10:25:00Z',
    details: 'All API endpoints use HTTPS with TLS 1.3 encryption',
    recommendations: [],
    evidence: ['SSL/TLS certificate verification', 'Network traffic analysis'],
    automated: true,
    frequency: 'continuous'
  },
  {
    id: 'check-003',
    name: 'Access Control Review',
    description: 'Regular review of user access rights and permissions',
    category: 'access_control',
    status: 'warning',
    severity: 'high',
    lastChecked: '2025-10-14T14:20:00Z',
    nextCheck: '2025-10-21T14:20:00Z',
    details: '3 users have access rights that haven\'t been reviewed in over 90 days',
    recommendations: [
      'Review and update user access rights',
      'Implement quarterly access review process',
      'Automate access review notifications'
    ],
    evidence: ['User access logs', 'Permission matrix review'],
    automated: false,
    frequency: 'monthly'
  },
  {
    id: 'check-004',
    name: 'Security Audit Logging',
    description: 'Comprehensive logging of security events and access attempts',
    category: 'audit_logging',
    status: 'pass',
    severity: 'medium',
    lastChecked: '2025-10-17T09:15:00Z',
    nextCheck: '2025-10-18T09:15:00Z',
    details: 'All security events are logged with timestamps and user context',
    recommendations: [],
    evidence: ['Log file analysis', 'Audit trail verification'],
    automated: true,
    frequency: 'continuous'
  },
  {
    id: 'check-005',
    name: 'Vulnerability Scanning',
    description: 'Regular scanning for security vulnerabilities in dependencies and infrastructure',
    category: 'vulnerability_management',
    status: 'fail',
    severity: 'high',
    lastChecked: '2025-10-16T16:45:00Z',
    nextCheck: '2025-10-17T16:45:00Z',
    details: '2 high-severity vulnerabilities found in third-party dependencies',
    recommendations: [
      'Update vulnerable dependencies to latest secure versions',
      'Implement automated dependency scanning in CI/CD pipeline',
      'Establish vulnerability response process'
    ],
    evidence: ['Dependency scan report', 'Security advisory notifications'],
    automated: true,
    frequency: 'daily'
  },
  {
    id: 'check-006',
    name: 'Data Retention Policy',
    description: 'Compliance with data retention and deletion policies',
    category: 'data_protection',
    status: 'pass',
    severity: 'medium',
    lastChecked: '2025-10-15T11:30:00Z',
    nextCheck: '2025-11-15T11:30:00Z',
    details: 'Data retention policies are implemented and automatically enforced',
    recommendations: [],
    evidence: ['Data retention policy documentation', 'Automated deletion logs'],
    automated: true,
    frequency: 'weekly'
  },
  {
    id: 'check-007',
    name: 'GDPR Compliance',
    description: 'Compliance with General Data Protection Regulation requirements',
    category: 'data_protection',
    status: 'warning',
    severity: 'high',
    lastChecked: '2025-10-14T13:00:00Z',
    nextCheck: '2025-11-14T13:00:00Z',
    details: 'Most GDPR requirements are met, but some documentation needs updating',
    recommendations: [
      'Update privacy policy with recent changes',
      'Document data processing activities',
      'Implement data breach notification procedures'
    ],
    evidence: ['Privacy policy review', 'Data processing inventory'],
    automated: false,
    frequency: 'quarterly'
  },
  {
    id: 'check-008',
    name: 'Security Training',
    description: 'Regular security awareness training for all personnel',
    category: 'security_policy',
    status: 'pending',
    severity: 'medium',
    lastChecked: '2025-10-01T10:00:00Z',
    nextCheck: '2025-11-01T10:00:00Z',
    details: 'Quarterly security training schedule due for renewal',
    recommendations: [
      'Schedule quarterly security training sessions',
      'Update training materials with latest threats',
      'Track training completion for all employees'
    ],
    evidence: ['Training completion records', 'Training material review'],
    automated: false,
    frequency: 'quarterly'
  }
];

const mockFrameworks: ComplianceFramework[] = [
  {
    name: 'SOC 2 Type II',
    version: '2022',
    description: 'Service Organization Control 2 - Security, Availability, Processing Integrity, Confidentiality, Privacy',
    checks: ['check-001', 'check-002', 'check-003', 'check-004', 'check-006'],
    overallScore: 88,
    status: 'compliant',
    lastAssessment: '2025-09-15T00:00:00Z',
    nextAssessment: '2026-09-15T00:00:00Z'
  },
  {
    name: 'GDPR',
    version: '2018',
    description: 'General Data Protection Regulation - EU data protection law',
    checks: ['check-001', 'check-002', 'check-006', 'check-007'],
    overallScore: 75,
    status: 'partial',
    lastAssessment: '2025-10-15T00:00:00Z',
    nextAssessment: '2026-01-15T00:00:00Z'
  },
  {
    name: 'ISO 27001',
    version: '2022',
    description: 'International Organization for Standardization 27001 - Information Security Management',
    checks: ['check-001', 'check-002', 'check-003', 'check-004', 'check-005', 'check-006', 'check-008'],
    overallScore: 82,
    status: 'compliant',
    lastAssessment: '2025-08-20T00:00:00Z',
    nextAssessment: '2026-02-20T00:00:00Z'
  },
  {
    name: 'NIST Cybersecurity Framework',
    version: '1.1',
    description: 'National Institute of Standards and Technology Cybersecurity Framework',
    checks: ['check-001', 'check-002', 'check-004', 'check-005'],
    overallScore: 90,
    status: 'compliant',
    lastAssessment: '2025-10-10T00:00:00Z',
    nextAssessment: '2026-01-10T00:00:00Z'
  }
];

const mockSecurityMetrics: SecurityMetric[] = [
  {
    name: 'Vulnerability Response Time',
    value: 24,
    target: 48,
    unit: 'hours',
    status: 'good',
    trend: 'improving',
    lastUpdated: '2025-10-17T10:30:00Z'
  },
  {
    name: 'Security Incident Rate',
    value: 0.5,
    target: 1.0,
    unit: 'incidents/month',
    status: 'good',
    trend: 'stable',
    lastUpdated: '2025-10-17T10:30:00Z'
  },
  {
    name: 'Compliance Score',
    value: 85,
    target: 90,
    unit: '%',
    status: 'warning',
    trend: 'improving',
    lastUpdated: '2025-10-17T10:30:00Z'
  },
  {
    name: 'Security Training Completion',
    value: 92,
    target: 100,
    unit: '%',
    status: 'good',
    trend: 'stable',
    lastUpdated: '2025-10-17T10:30:00Z'
  }
];

export default function SecurityComplianceChecker() {
  const [checks, setChecks] = useState<ComplianceCheck[]>(mockComplianceChecks);
  const [frameworks, setFrameworks] = useState<ComplianceFramework[]>(mockFrameworks);
  const [metrics] = useState<SecurityMetric[]>(mockSecurityMetrics);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [isScanning, setIsScanning] = useState(false);

  const categoryIcons = {
    data_protection: <Database className="h-4 w-4" />,
    access_control: <Users className="h-4 w-4" />,
    encryption: <Lock className="h-4 w-4" />,
    audit_logging: <FileText className="h-4 w-4" />,
    vulnerability_management: <Shield className="h-4 w-4" />,
    security_policy: <Settings className="h-4 w-4" />
  };

  const statusColors = {
    pass: 'bg-green-100 text-green-700',
    fail: 'bg-red-100 text-red-700',
    warning: 'bg-yellow-100 text-yellow-700',
    pending: 'bg-gray-100 text-gray-700'
  };

  const statusIcons = {
    pass: <CheckCircle className="h-4 w-4 text-green-500" />,
    fail: <XCircle className="h-4 w-4 text-red-500" />,
    warning: <AlertTriangle className="h-4 w-4 text-yellow-500" />,
    pending: <Clock className="h-4 w-4 text-gray-500" />
  };

  const severityColors = {
    low: 'bg-blue-100 text-blue-700',
    medium: 'bg-yellow-100 text-yellow-700',
    high: 'bg-orange-100 text-orange-700',
    critical: 'bg-red-100 text-red-700'
  };

  const filteredChecks = checks.filter(check =>
    selectedCategory === 'all' || check.category === selectedCategory
  );

  const stats = {
    total: checks.length,
    passed: checks.filter(c => c.status === 'pass').length,
    failed: checks.filter(c => c.status === 'fail').length,
    warnings: checks.filter(c => c.status === 'warning').length,
    pending: checks.filter(c => c.status === 'pending').length,
    overallScore: Math.round((checks.filter(c => c.status === 'pass').length / checks.length) * 100)
  };

  const runSecurityScan = async () => {
    setIsScanning(true);

    // Simulate security scan
    await new Promise(resolve => setTimeout(resolve, 3000));

    // Update some check statuses to show scan results
    setChecks(prevChecks =>
      prevChecks.map(check => ({
        ...check,
        lastChecked: new Date().toISOString(),
        ...(check.id === 'check-005' && {
          status: 'pass' as const,
          details: 'All vulnerabilities have been patched',
          recommendations: []
        }),
        ...(check.id === 'check-008' && {
          status: 'pass' as const,
          details: 'Security training completed for all employees',
          recommendations: []
        })
      }))
    );

    setIsScanning(false);
  };

  const exportReport = () => {
    const report = {
      generatedAt: new Date().toISOString(),
      summary: stats,
      frameworks,
      checks,
      metrics
    };

    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `security-compliance-report-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Security & Compliance</h1>
          <p className="text-gray-600">Monitor security posture and compliance status</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={runSecurityScan}
            disabled={isScanning}
            className="flex items-center gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${isScanning ? 'animate-spin' : ''}`} />
            {isScanning ? 'Scanning...' : 'Run Security Scan'}
          </Button>
          <Button onClick={exportReport} className="flex items-center gap-2">
            <Download className="h-4 w-4" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">{stats.total}</p>
                <p className="text-xs text-gray-600">Total Checks</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <div>
                <p className="text-2xl font-bold">{stats.passed}</p>
                <p className="text-xs text-gray-600">Passed</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-500" />
              <div>
                <p className="text-2xl font-bold">{stats.warnings}</p>
                <p className="text-xs text-gray-600">Warnings</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-red-500" />
              <div>
                <p className="text-2xl font-bold">{stats.failed}</p>
                <p className="text-xs text-gray-600">Failed</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-gray-500" />
              <div>
                <p className="text-2xl font-bold">{stats.pending}</p>
                <p className="text-xs text-gray-600">Pending</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-purple-500" />
              <div>
                <p className="text-2xl font-bold">{stats.overallScore}%</p>
                <p className="text-xs text-gray-600">Score</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="checks">Compliance Checks</TabsTrigger>
          <TabsTrigger value="frameworks">Frameworks</TabsTrigger>
          <TabsTrigger value="metrics">Security Metrics</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {/* Framework Status */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {frameworks.map((framework) => (
              <Card key={framework.name}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-base">{framework.name}</CardTitle>
                      <CardDescription>{framework.version}</CardDescription>
                    </div>
                    <div className="text-right">
                      <Badge className={
                        framework.status === 'compliant' ? 'bg-green-100 text-green-700' :
                        framework.status === 'partial' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }>
                        {framework.status.toUpperCase()}
                      </Badge>
                      <div className="text-2xl font-bold mt-1">{framework.overallScore}%</div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-600 mb-3">{framework.description}</p>
                  <div className="flex justify-between text-sm">
                    <span>Last Assessment: {new Date(framework.lastAssessment).toLocaleDateString()}</span>
                    <span>Next: {new Date(framework.nextAssessment).toLocaleDateString()}</span>
                  </div>
                  <Progress value={framework.overallScore} className="mt-2 h-2" />
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Recent Findings */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Recent Security Findings</CardTitle>
              <CardDescription>Latest security and compliance issues that need attention</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {checks.filter(c => c.status === 'fail' || c.status === 'warning').map((check) => (
                  <div key={check.id} className="flex items-start gap-3 p-3 border rounded-lg">
                    <div className="mt-1">
                      {statusIcons[check.status]}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-medium">{check.name}</h4>
                        <Badge className={severityColors[check.severity]}>
                          {check.severity.toUpperCase()}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          {check.category.replace('_', ' ')}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">{check.details}</p>
                      {check.recommendations.length > 0 && (
                        <div>
                          <h5 className="text-sm font-medium mb-1">Recommendations:</h5>
                          <ul className="text-sm space-y-1">
                            {check.recommendations.map((rec, idx) => (
                              <li key={idx} className="flex items-center gap-2">
                                <ChevronRight className="h-3 w-3 text-gray-400" />
                                {rec}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-500">
                        Last checked: {new Date(check.lastChecked).toLocaleDateString()}
                      </div>
                      {check.automated && (
                        <Badge variant="outline" className="text-xs mt-1">
                          Automated
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="checks" className="space-y-4">
          {/* Category Filter */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Compliance Checks</CardTitle>
              <CardDescription>Detailed status of all security and compliance checks</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4 mb-4">
                <span className="text-sm font-medium">Category:</span>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="px-3 py-1 border rounded-md text-sm"
                >
                  <option value="all">All Categories</option>
                  <option value="data_protection">Data Protection</option>
                  <option value="access_control">Access Control</option>
                  <option value="encryption">Encryption</option>
                  <option value="audit_logging">Audit Logging</option>
                  <option value="vulnerability_management">Vulnerability Management</option>
                  <option value="security_policy">Security Policy</option>
                </select>
              </div>

              <div className="space-y-3">
                {filteredChecks.map((check) => (
                  <Card key={check.id}>
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            {statusIcons[check.status]}
                            <h4 className="font-medium">{check.name}</h4>
                            <Badge className={statusColors[check.status]}>
                              {check.status.toUpperCase()}
                            </Badge>
                            <Badge className={severityColors[check.severity]}>
                              {check.severity.toUpperCase()}
                            </Badge>
                            <div className="flex items-center gap-1">
                              {categoryIcons[check.category]}
                              <Badge variant="outline" className="text-xs">
                                {check.category.replace('_', ' ')}
                              </Badge>
                            </div>
                          </div>
                          <p className="text-sm text-gray-600 mb-3">{check.description}</p>

                          <div className="text-sm mb-3">
                            <strong>Details:</strong> {check.details}
                          </div>

                          {check.recommendations.length > 0 && (
                            <div className="mb-3">
                              <h5 className="text-sm font-medium mb-2">Recommendations:</h5>
                              <ul className="text-sm space-y-1">
                                {check.recommendations.map((rec, idx) => (
                                  <li key={idx} className="flex items-center gap-2">
                                    <ChevronRight className="h-3 w-3 text-gray-400" />
                                    {rec}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          <div className="text-xs text-gray-500 space-y-1">
                            <div>
                              <strong>Last Checked:</strong> {new Date(check.lastChecked).toLocaleString()}
                            </div>
                            <div>
                              <strong>Next Check:</strong> {new Date(check.nextCheck).toLocaleString()}
                            </div>
                            <div>
                              <strong>Frequency:</strong> {check.frequency.replace('_', ' ')}
                            </div>
                          </div>
                        </div>

                        <div className="ml-4 text-right">
                          {check.automated && (
                            <Badge variant="outline" className="text-xs mb-2">
                              Automated
                            </Badge>
                          )}
                          <div className="text-xs text-gray-500">
                            Evidence: {check.evidence.length} items
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

        <TabsContent value="frameworks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Compliance Frameworks</CardTitle>
              <CardDescription>Status of various compliance frameworks and standards</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {frameworks.map((framework) => (
                  <Card key={framework.name}>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2 mb-2">
                            <Award className="h-5 w-5 text-blue-500" />
                            <CardTitle className="text-base">{framework.name}</CardTitle>
                            <Badge variant="outline">{framework.version}</Badge>
                            <Badge className={
                              framework.status === 'compliant' ? 'bg-green-100 text-green-700' :
                              framework.status === 'partial' ? 'bg-yellow-100 text-yellow-700' :
                              'bg-red-100 text-red-700'
                            }>
                              {framework.status.replace('_', ' ').toUpperCase()}
                            </Badge>
                          </div>
                          <CardDescription>{framework.description}</CardDescription>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold">{framework.overallScore}%</div>
                          <div className="text-xs text-gray-600">Compliance Score</div>
                          <Progress value={framework.overallScore} className="w-20 h-2 mt-1" />
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        <div className="flex justify-between text-sm">
                          <span>Last Assessment:</span>
                          <span>{new Date(framework.lastAssessment).toLocaleDateString()}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span>Next Assessment:</span>
                          <span>{new Date(framework.nextAssessment).toLocaleDateString()}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span>Applicable Checks:</span>
                          <span>{framework.checks.length}</span>
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
              <CardTitle className="text-lg">Security Metrics</CardTitle>
              <CardDescription>Key performance indicators for security and compliance</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {metrics.map((metric, idx) => (
                  <div key={idx} className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-3 h-3 rounded-full bg-blue-500" />
                        <div>
                          <div className="font-medium">{metric.name}</div>
                          <div className="text-sm text-gray-600">
                            Last updated: {new Date(metric.lastUpdated).toLocaleString()}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center gap-2">
                          <span className="text-2xl font-bold">{metric.value}</span>
                          <span className="text-gray-500">{metric.unit}</span>
                        </div>
                        <div className="text-sm text-gray-600">
                          Target: {metric.target} {metric.unit}
                        </div>
                        <Progress
                          value={(metric.value / metric.target) * 100}
                          className="w-32 h-2 mt-1"
                        />
                        <div className="text-xs text-gray-600 mt-1">
                          {Math.round((metric.value / metric.target) * 100)}% of target
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