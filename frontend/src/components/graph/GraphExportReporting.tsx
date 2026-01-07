import React, { useState, useCallback, useMemo } from 'react';
import {
  DocumentArrowDownIcon,
  TableCellsIcon,
  ChartBarIcon,
  DocumentTextIcon,
  CalendarIcon,
  FunnelIcon,
  EyeIcon,
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
  ClockIcon,
  ShareIcon,
  BookmarkIcon,
  CogIcon,
} from '@heroicons/react/24/outline';
import { Entity, Relationship } from '@/types/search';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

interface GraphExportReportingProps {
  entities: Entity[];
  relationships: Relationship[];
  documents?: any[];
  className?: string;
}

interface ExportFormat {
  id: string;
  name: string;
  description: string;
  extension: string;
  mimeType: string;
  icon: React.ComponentType<{ className?: string }>;
  supportedData: ('entities' | 'relationships' | 'statistics' | 'insights' | 'details')[];
  maxSize?: number; // MB
}

interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  sections: ReportSection[];
  icon: React.ComponentType<{ className?: string }>;
}

interface ReportSection {
  id: string;
  title: string;
  type: 'overview' | 'statistics' | 'visualization' | 'recommendations' | 'details';
  required: boolean;
  config?: Record<string, any>;
}

interface ExportJob {
  id: string;
  format: string;
  template?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  fileName: string;
  fileSize?: number;
  downloadUrl?: string;
  createdAt: number;
  completedAt?: number;
  error?: string;
}

interface ScheduledReport {
  id: string;
  name: string;
  template: string;
  format: string;
  schedule: 'daily' | 'weekly' | 'monthly';
  recipients: string[];
  enabled: boolean;
  lastRun?: number;
  nextRun?: number;
}

export const GraphExportReporting: React.FC<GraphExportReportingProps> = ({
  entities = [],
  relationships = [],
  documents = [],
  className,
}) => {
  const [selectedFormat, setSelectedFormat] = useState<string>('json');
  const [selectedTemplate, setSelectedTemplate] = useState<string>('comprehensive');
  const [exportJobs, setExportJobs] = useState<ExportJob[]>([]);
  const [scheduledReports, setScheduledReports] = useState<ScheduledReport[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [showScheduleDialog, setShowScheduleDialog] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  // Define supported export formats
  const exportFormats: ExportFormat[] = [
    {
      id: 'json',
      name: 'JSON',
      description: 'Raw data in JSON format for programmatic use',
      extension: '.json',
      mimeType: 'application/json',
      icon: DocumentArrowDownIcon,
      supportedData: ['entities', 'relationships', 'statistics'],
      maxSize: 100,
    },
    {
      id: 'csv',
      name: 'CSV',
      description: 'Tabular data for spreadsheet applications',
      extension: '.csv',
      mimeType: 'text/csv',
      icon: TableCellsIcon,
      supportedData: ['entities', 'relationships'],
      maxSize: 50,
    },
    {
      id: 'excel',
      name: 'Excel',
      description: 'Rich spreadsheet with multiple sheets',
      extension: '.xlsx',
      mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      icon: TableCellsIcon,
      supportedData: ['entities', 'relationships', 'statistics'],
      maxSize: 25,
    },
    {
      id: 'pdf',
      name: 'PDF Report',
      description: 'Formatted report for sharing and printing',
      extension: '.pdf',
      mimeType: 'application/pdf',
      icon: DocumentTextIcon,
      supportedData: ['statistics', 'insights', 'details'],
      maxSize: 20,
    },
    {
      id: 'graphml',
      name: 'GraphML',
      description: 'Graph visualization format for network analysis tools',
      extension: '.graphml',
      mimeType: 'application/xml',
      icon: ShareIcon,
      supportedData: ['entities', 'relationships'],
      maxSize: 50,
    },
    {
      id: 'gexf',
      name: 'GEXF',
      description: 'Gephi Exchange Format for network visualization',
      extension: '.gexf',
      mimeType: 'application/xml',
      icon: ChartBarIcon,
      supportedData: ['entities', 'relationships'],
      maxSize: 50,
    },
  ];

  // Define report templates
  const reportTemplates: ReportTemplate[] = [
    {
      id: 'comprehensive',
      name: 'Comprehensive Report',
      description: 'Complete graph analysis with all metrics and insights',
      sections: [
        { id: 'overview', title: 'Executive Summary', type: 'overview', required: true },
        { id: 'statistics', title: 'Graph Statistics', type: 'statistics', required: true },
        { id: 'visualization', title: 'Visual Analysis', type: 'visualization', required: true },
        { id: 'recommendations', title: 'Recommendations', type: 'recommendations', required: true },
        { id: 'details', title: 'Detailed Metrics', type: 'details', required: false },
      ],
      icon: DocumentTextIcon,
    },
    {
      id: 'executive',
      name: 'Executive Summary',
      description: 'High-level overview for stakeholders',
      sections: [
        { id: 'overview', title: 'Executive Summary', type: 'overview', required: true },
        { id: 'statistics', title: 'Key Metrics', type: 'statistics', required: true },
        { id: 'recommendations', title: 'Strategic Insights', type: 'recommendations', required: true },
      ],
      icon: ChartBarIcon,
    },
    {
      id: 'technical',
      name: 'Technical Analysis',
      description: 'Detailed technical metrics for analysts',
      sections: [
        { id: 'statistics', title: 'Graph Metrics', type: 'statistics', required: true },
        { id: 'visualization', title: 'Network Analysis', type: 'visualization', required: true },
        { id: 'details', title: 'Detailed Calculations', type: 'details', required: true },
      ],
      icon: CogIcon,
    },
    {
      id: 'data-export',
      name: 'Data Export',
      description: 'Raw data export for further analysis',
      sections: [
        { id: 'details', title: 'Raw Data', type: 'details', required: true },
      ],
      icon: DocumentArrowDownIcon,
    },
  ];

  // Calculate graph statistics
  const graphStatistics = useMemo(() => {
    const totalEntities = entities.length;
    const totalRelationships = relationships.length;
    const entityTypes = Array.from(new Set(entities.map(e => e.type)));
    const relationshipTypes = Array.from(new Set(relationships.map(r => r.relationship_type)));

    const avgDegree = totalEntities > 0
      ? relationships.reduce((sum, rel) => sum + 2, 0) / totalEntities
      : 0;

    const maxDegree = entities.reduce((max, entity) => {
      const degree = relationships.filter(r =>
        r.source_entity_id === entity.id || r.target_entity_id === entity.id
      ).length;
      return Math.max(max, degree);
    }, 0);

    return {
      totalEntities,
      totalRelationships,
      entityTypes: entityTypes.length,
      relationshipTypes: relationshipTypes.length,
      avgDegree: avgDegree.toFixed(2),
      maxDegree,
      avgConfidence: entities.length > 0
        ? (entities.reduce((sum, e) => sum + e.confidence, 0) / entities.length * 100).toFixed(1)
        : 0,
    };
  }, [entities, relationships]);

  // Generate export data
  const generateExportData = useCallback((format: string, template?: string) => {
    const data = {
      entities,
      relationships,
      statistics: graphStatistics,
      metadata: {
        exportedAt: new Date().toISOString(),
        totalEntities: entities.length,
        totalRelationships: relationships.length,
        template,
        format,
      },
    };

    switch (format) {
      case 'json':
        return JSON.stringify(data, null, 2);

      case 'csv':
        if (template === 'data-export') {
          // Generate CSV for entities
          const headers = ['id', 'name', 'type', 'confidence', 'mentions', 'first_seen', 'last_seen'];
          const rows = entities.map(entity => [
            entity.id,
            entity.name,
            entity.type,
            entity.confidence.toString(),
            entity.mentions.toString(),
            entity.first_seen,
            entity.last_seen,
          ]);
          return [headers, ...rows].map(row => row.join(',')).join('\n');
        }
        break;

      case 'graphml':
        // Generate GraphML format
        return `<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns/graphml">
  <key id="label" for="node" attr.name="label" attr.type="string"/>
  <key id="type" for="node" attr.name="type" attr.type="string"/>
  <key id="confidence" for="node" attr.name="confidence" attr.type="double"/>
  <graph id="G" edgedefault="undirected">
    ${entities.map(entity => `
      <node id="${entity.id}">
        <data key="label">${entity.name}</data>
        <data key="type">${entity.type}</data>
        <data key="confidence">${entity.confidence}</data>
      </node>`).join('')}
    ${relationships.map(rel => `
      <edge source="${rel.source_entity_id}" target="${rel.target_entity_id}">
        <data key="label">${rel.relationship_type}</data>
        <data key="confidence">${rel.confidence}</data>
      </edge>`).join('')}
  </graph>
</graphml>`;

      case 'pdf':
        // In a real implementation, this would generate a PDF
        return `PDF Report - ${template || 'Standard'}\n\nEntities: ${entities.length}\nRelationships: ${relationships.length}\n\nGenerated at: ${new Date().toISOString()}`;

      default:
        return JSON.stringify(data, null, 2);
    }

    return JSON.stringify(data, null, 2);
  }, [entities, relationships, graphStatistics]);

  // Start export process
  const startExport = useCallback(async () => {
    setIsExporting(true);

    const jobId = `export-${Date.now()}`;
    const formatConfig = exportFormats.find(f => f.id === selectedFormat);
    const templateConfig = reportTemplates.find(t => t.id === selectedTemplate);

    const job: ExportJob = {
      id: jobId,
      format: selectedFormat,
      template: selectedTemplate,
      status: 'pending',
      progress: 0,
      fileName: `graph-export-${selectedFormat}-${Date.now()}${formatConfig?.extension}`,
      createdAt: Date.now(),
    };

    setExportJobs(prev => [job, ...prev]);

    try {
      // Simulate export process
      for (let i = 0; i <= 100; i += 10) {
        await new Promise(resolve => setTimeout(resolve, 200));
        setExportJobs(prev => prev.map(j =>
          j.id === jobId
            ? { ...j, status: 'processing' as const, progress: i }
            : j
        ));
      }

      // Generate the data
      const exportData = generateExportData(selectedFormat, selectedTemplate);
      const blob = new Blob([exportData], { type: formatConfig?.mimeType });
      const url = URL.createObjectURL(blob);

      // Complete the job
      setExportJobs(prev => prev.map(j =>
        j.id === jobId
          ? {
              ...j,
              status: 'completed' as const,
              progress: 100,
              completedAt: Date.now(),
              downloadUrl: url,
              fileSize: blob.size,
            }
          : j
      ));

    } catch (error) {
      setExportJobs(prev => prev.map(j =>
        j.id === jobId
          ? {
              ...j,
              status: 'failed' as const,
              error: 'Export failed',
            }
          : j
      ));
    } finally {
      setIsExporting(false);
    }
  }, [selectedFormat, selectedTemplate, exportFormats, reportTemplates, generateExportData]);

  // Download exported file
  const downloadFile = useCallback((job: ExportJob) => {
    if (job.downloadUrl) {
      const a = document.createElement('a');
      a.href = job.downloadUrl;
      a.download = job.fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  }, []);

  // Get format icon
  const getFormatIcon = (formatId: string) => {
    const format = exportFormats.find(f => f.id === formatId);
    return format?.icon || DocumentArrowDownIcon;
  };

  // Get template icon
  const getTemplateIcon = (templateId: string) => {
    const template = reportTemplates.find(t => t.id === templateId);
    return template?.icon || DocumentTextIcon;
  };

  // Get status color
  const getStatusColor = (status: ExportJob['status']) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-50';
      case 'processing':
        return 'text-blue-600 bg-blue-50';
      case 'failed':
        return 'text-red-600 bg-red-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  const currentFormat = exportFormats.find(f => f.id === selectedFormat);
  const currentTemplate = reportTemplates.find(t => t.id === selectedTemplate);
  const FormatIcon = getFormatIcon(selectedFormat);
  const TemplateIcon = getTemplateIcon(selectedTemplate);

  return (
    <div className={cn("space-y-6", className)}>
      {/* Export Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center">
            <DocumentArrowDownIcon className="h-5 w-5 mr-2" />
            Graph Export & Reporting
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {/* Statistics Overview */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-gray-50 rounded-lg">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{graphStatistics.totalEntities}</div>
                <div className="text-sm text-gray-500">Entities</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{graphStatistics.totalRelationships}</div>
                <div className="text-sm text-gray-500">Relationships</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{graphStatistics.entityTypes}</div>
                <div className="text-sm text-gray-500">Entity Types</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{graphStatistics.avgConfidence}%</div>
                <div className="text-sm text-gray-500">Avg Confidence</div>
              </div>
            </div>

            {/* Format Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Export Format
              </label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {exportFormats.map(format => {
                  const FormatIcon = format.icon;
                  return (
                    <div
                      key={format.id}
                      className={cn(
                        "border rounded-lg p-4 cursor-pointer hover:border-blue-500 transition-colors",
                        selectedFormat === format.id ? "border-blue-500 bg-blue-50" : "border-gray-200"
                      )}
                      onClick={() => setSelectedFormat(format.id)}
                    >
                      <div className="flex items-center space-x-3">
                        <FormatIcon className="h-6 w-6 text-blue-600" />
                        <div>
                          <div className="font-medium">{format.name}</div>
                          <div className="text-xs text-gray-500">{format.extension}</div>
                        </div>
                      </div>
                      <div className="mt-2 text-xs text-gray-600">
                        {format.description}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Template Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Report Template
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {reportTemplates.map(template => {
                  const TemplateIcon = template.icon;
                  return (
                    <div
                      key={template.id}
                      className={cn(
                        "border rounded-lg p-4 cursor-pointer hover:border-blue-500 transition-colors",
                        selectedTemplate === template.id ? "border-blue-500 bg-blue-50" : "border-gray-200"
                      )}
                      onClick={() => setSelectedTemplate(template.id)}
                    >
                      <div className="flex items-center space-x-3">
                        <TemplateIcon className="h-5 w-5 text-blue-600" />
                        <div>
                          <div className="font-medium">{template.name}</div>
                          <div className="text-xs text-gray-500">
                            {template.sections.length} sections
                          </div>
                        </div>
                      </div>
                      <div className="mt-2 text-xs text-gray-600">
                        {template.description}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Export Button */}
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-600">
                {currentFormat && (
                  <span>
                    {currentFormat.maxSize && `Max size: ${currentFormat.maxSize}MB • `}
                    Supports: {currentFormat.supportedData.join(', ')}
                  </span>
                )}
              </div>
              <Button
                onClick={startExport}
                disabled={isExporting}
                size="lg"
                className="flex items-center space-x-2"
              >
                {isExporting ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                ) : (
                  <FormatIcon className="h-4 w-4" />
                )}
                <span>
                  {isExporting ? 'Exporting...' : `Export as ${currentFormat?.name}`}
                </span>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Export Jobs */}
      {exportJobs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Export History</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExportJobs([])}
              >
                Clear All
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {exportJobs.map(job => {
                const FormatIcon = getFormatIcon(job.format);
                const statusColor = getStatusColor(job.status);

                return (
                  <div key={job.id} className="flex items-center justify-between p-4 border rounded-lg">
                    <div className="flex items-center space-x-3">
                      <FormatIcon className="h-5 w-5 text-gray-400" />
                      <div>
                        <div className="font-medium">{job.fileName}</div>
                        <div className="flex items-center space-x-2 text-sm text-gray-500">
                          <span>{job.format.toUpperCase()}</span>
                          {job.template && <span>• {job.template}</span>}
                          <span>• {new Date(job.createdAt).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      <div className="text-right">
                        <div className={cn("text-sm font-medium", statusColor)}>
                          {job.status}
                        </div>
                        {job.fileSize && (
                          <div className="text-xs text-gray-500">
                            {(job.fileSize / 1024 / 1024).toFixed(2)} MB
                          </div>
                        )}
                      </div>

                      {job.status === 'processing' && (
                        <div className="w-24">
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div
                              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                              style={{ width: `${job.progress}%` }}
                            />
                          </div>
                        </div>
                      )}

                      {job.status === 'completed' && (
                        <Button
                          size="sm"
                          onClick={() => downloadFile(job)}
                          className="flex items-center space-x-1"
                        >
                          <DocumentArrowDownIcon className="h-4 w-4" />
                          Download
                        </Button>
                      )}

                      {job.status === 'failed' && (
                        <Button variant="outline" size="sm" onClick={() => setExportJobs(prev => prev.filter(j => j.id !== job.id))}>
                          Retry
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Preview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <EyeIcon className="h-5 w-5 mr-2" />
              Export Preview
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowPreview(!showPreview)}
            >
              {showPreview ? 'Hide' : 'Show'} Preview
            </Button>
          </CardTitle>
        </CardHeader>
        {showPreview && (
          <CardContent>
            <div className="space-y-4">
              <div className="p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium mb-2">Current Selection</h4>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="font-medium">Format:</span> {currentFormat?.name}
                  </div>
                  <div>
                    <span className="font-medium">Template:</span> {currentTemplate?.name}
                  </div>
                  <div>
                    <span className="font-medium">Entities:</span> {entities.length}
                  </div>
                  <div>
                    <span className="font-medium">Relationships:</span> {relationships.length}
                  </div>
                </div>
              </div>

              <div className="p-4 bg-gray-50 rounded-lg">
                <h4 className="font-medium mb-2">Sample Content</h4>
                <pre className="text-xs bg-white p-3 rounded border overflow-auto max-h-64">
                  {generateExportData(selectedFormat, selectedTemplate).substring(0, 500)}
                  {generateExportData(selectedFormat, selectedTemplate).length > 500 && '\n...'}
                </pre>
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Scheduled Reports */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center">
              <CalendarIcon className="h-5 w-5 mr-2" />
              Scheduled Reports
            </div>
            <Button
              onClick={() => setShowScheduleDialog(true)}
              size="sm"
            >
              Schedule New Report
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {scheduledReports.length === 0 ? (
            <div className="text-center py-8">
              <CalendarIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">No scheduled reports yet.</p>
              <Button variant="outline" size="sm" onClick={() => setShowScheduleDialog(true)} className="mt-4">
                Create First Scheduled Report
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {scheduledReports.map(report => (
                <div key={report.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center space-x-3">
                    <TemplateIcon className="h-5 w-5 text-blue-600" />
                    <div>
                      <div className="font-medium">{report.name}</div>
                      <div className="flex items-center space-x-2 text-sm text-gray-500">
                        <span>{report.format.toUpperCase()}</span>
                        <span>•</span>
                        <span className="capitalize">{report.schedule}</span>
                        <span>•</span>
                        <span>{report.recipients.length} recipients</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Badge variant={report.enabled ? "default" : "secondary"}>
                      {report.enabled ? 'Enabled' : 'Disabled'}
                    </Badge>
                    {report.lastRun && (
                      <span className="text-xs text-gray-500">
                        Last: {new Date(report.lastRun).toLocaleDateString()}
                      </span>
                    )}
                    <Button variant="ghost" size="sm">
                      <CogIcon className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Schedule Report Dialog */}
      {showScheduleDialog && (
        <Dialog open={showScheduleDialog} onOpenChange={setShowScheduleDialog}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Schedule New Report</DialogTitle>
            </DialogHeader>
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Report Name</label>
                <input
                  type="text"
                  placeholder="Monthly Knowledge Graph Report"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Template</label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Select template" />
                    </SelectTrigger>
                    <SelectContent>
                      {reportTemplates.map(template => (
                        <SelectItem key={template.id} value={template.id}>
                          {template.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Format</label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Select format" />
                    </SelectTrigger>
                    <SelectContent>
                      {exportFormats.filter(f => f.supportedData.includes('statistics')).map(format => (
                        <SelectItem key={format.id} value={format.id}>
                          {format.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Schedule</label>
                <Select>
                  <SelectTrigger>
                    <SelectValue placeholder="Select frequency" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">Daily</SelectItem>
                    <SelectItem value="weekly">Weekly</SelectItem>
                    <SelectItem value="monthly">Monthly</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Recipients</label>
                <input
                  type="email"
                  placeholder="Enter email addresses (comma-separated)"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>

              <div className="flex items-center space-x-2">
                <label className="flex items-center">
                  <input type="checkbox" className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                  <span className="text-sm text-gray-700">Enable scheduled report</span>
                </label>
              </div>

              <div className="flex justify-end space-x-3">
                <Button variant="outline" onClick={() => setShowScheduleDialog(false)}>
                  Cancel
                </Button>
                <Button onClick={() => {
                  // In a real implementation, this would save the scheduled report
                  console.log('Would save scheduled report');
                  setShowScheduleDialog(false);
                }}>
                  Create Schedule
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
};

export default GraphExportReporting;