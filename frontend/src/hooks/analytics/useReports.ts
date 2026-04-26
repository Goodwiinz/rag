import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useCallback } from 'react';
import { reportApi } from '@/services/analytics';
import { useAnalyticsStore } from '@/store/analytics';
import { Report } from '@/store/analytics';

// Hook for fetching reports
export const useReports = () => {
  const { setLoading, setError, setReports } = useAnalyticsStore();

  return useQuery({
    queryKey: ['reports'],
    queryFn: () => reportApi.getReports(),
    staleTime: 30000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for fetching a single report
export const useReport = (reportId: string) => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['report', reportId],
    queryFn: () => reportApi.getReport(reportId),
    enabled: !!reportId,
    staleTime: 30000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for creating reports
export const useCreateReport = () => {
  const queryClient = useQueryClient();
  const { setError, createReport } = useAnalyticsStore();

  return useMutation({
    mutationFn: (report: Omit<Report, 'id'>) => reportApi.createReport(report),
    onSuccess: (data) => {
      createReport(data);
      queryClient.setQueryData(['report', data.id], data);
    },
  });
};

// Hook for updating reports
export const useUpdateReport = () => {
  const queryClient = useQueryClient();
  const { setError, updateReport } = useAnalyticsStore();

  return useMutation({
    mutationFn: ({ reportId, updates }: { reportId: string; updates: Partial<Report> }) =>
      reportApi.updateReport(reportId, updates),
    onSuccess: (data) => {
      updateReport(data);
      queryClient.setQueryData(['report', data.id], data);
    },
  });
};

// Hook for deleting reports
export const useDeleteReport = () => {
  const queryClient = useQueryClient();
  const { setError, deleteReport } = useAnalyticsStore();

  return useMutation({
    mutationFn: (reportId: string) => reportApi.deleteReport(reportId),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['report', reportId] });
      deleteReport(reportId);
    },
  });
};

// Hook for generating reports
export const useGenerateReport = () => {
  const { setError, setGeneratingReport } = useAnalyticsStore();

  return useMutation({
    mutationFn: ({ reportId, format }: { reportId: string; format?: 'pdf' | 'csv' | 'json' }) =>
      reportApi.generateReport(reportId, format),
    onMutate: () => {
      setGeneratingReport(true);
    },
    onSettled: () => {
      setGeneratingReport(false);
    },
  });
};

// Hook for report templates
export const useReportTemplates = () => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['report-templates'],
    queryFn: () => reportApi.getReportTemplates(),
    staleTime: 300000, // 5 minutes
    onSuccess: () => {
      setError(null);
    },
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for report scheduling
export const useScheduleReport = () => {
  const queryClient = useQueryClient();
  const { setError } = useAnalyticsStore();

  return useMutation({
    mutationFn: ({ reportId, schedule }: { reportId: string; schedule: { frequency: 'daily' | 'weekly' | 'monthly'; time: string; enabled: boolean } }) =>
      reportApi.scheduleReport(reportId, schedule),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['report', variables.reportId] });
    },
  });
};

// Hook for report history
export const useReportHistory = (reportId: string) => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['report-history', reportId],
    queryFn: () => reportApi.getReportHistory(reportId),
    enabled: !!reportId,
    staleTime: 60000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for report management
export const useReportManager = () => {
  const { reports, isGeneratingReport } = useAnalyticsStore();
  const [selectedReports, setSelectedReports] = useState<string[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [editingReport, setEditingReport] = useState<string | null>(null);

  const toggleReportSelection = useCallback((reportId: string) => {
    setSelectedReports(prev =>
      prev.includes(reportId)
        ? prev.filter(id => id !== reportId)
        : [...prev, reportId]
    );
  }, []);

  const selectAllReports = useCallback(() => {
    setSelectedReports(reports.map(r => r.id));
  }, [reports]);

  const clearSelection = useCallback(() => {
    setSelectedReports([]);
  }, []);

  const startCreating = useCallback(() => {
    setIsCreating(true);
    setEditingReport(null);
  }, []);

  const startEditing = useCallback((reportId: string) => {
    setEditingReport(reportId);
    setIsCreating(false);
  }, []);

  const stopEditing = useCallback(() => {
    setEditingReport(null);
    setIsCreating(false);
  }, []);

  const generateSelectedReports = useCallback(async (format: 'pdf' | 'csv' | 'json') => {
    // This would generate reports for all selected reports
    console.log(`Generating ${selectedReports.length} reports in ${format} format`);
  }, [selectedReports]);

  const deleteSelectedReports = useCallback(async () => {
    // This would delete all selected reports
    console.log(`Deleting ${selectedReports.length} reports`);
    setSelectedReports([]);
  }, [selectedReports]);

  return {
    // Report data
    reports,
    isGeneratingReport,

    // Selection
    selectedReports,
    toggleReportSelection,
    selectAllReports,
    clearSelection,

    // Creation/Editing
    isCreating,
    editingReport,
    startCreating,
    startEditing,
    stopEditing,

    // Bulk actions
    generateSelectedReports,
    deleteSelectedReports,

    // State helpers
    hasSelection: selectedReports.length > 0,
    allSelected: selectedReports.length === reports.length && reports.length > 0,
    selectedCount: selectedReports.length,
  };
};

// Hook for report builder
export const useReportBuilder = (templateId?: string) => {
  const [config, setConfig] = useState({
    name: '',
    type: 'summary' as 'summary' | 'detailed' | 'custom',
    format: 'pdf' as 'pdf' | 'csv' | 'json',
    recipients: [] as string[],
    includeCharts: true,
    includeTables: true,
    dateRange: {
      start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
      end: new Date().toISOString(),
    },
    filters: {} as Record<string, any>,
    customSections: [] as Array<{
      id: string;
      type: 'text' | 'chart' | 'table' | 'metric';
      title: string;
      config: any;
    }>,
  });

  const [isPreviewing, setIsPreviewing] = useState(false);

  const updateConfig = useCallback((key: string, value: any) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  }, []);

  const updateNestedConfig = useCallback((path: string[], value: any) => {
    setConfig(prev => {
      const newConfig = { ...prev };
      let current: any = newConfig;

      for (let i = 0; i < path.length - 1; i++) {
        current[path[i]] = { ...current[path[i]] };
        current = current[path[i]];
      }

      current[path[path.length - 1]] = value;
      return newConfig;
    });
  }, []);

  const addCustomSection = useCallback((section: any) => {
    setConfig(prev => ({
      ...prev,
      customSections: [...prev.customSections, { ...section, id: `section_${Date.now()}` }]
    }));
  }, []);

  const updateCustomSection = useCallback((sectionId: string, updates: any) => {
    setConfig(prev => ({
      ...prev,
      customSections: prev.customSections.map(section =>
        section.id === sectionId ? { ...section, ...updates } : section
      )
    }));
  }, []);

  const removeCustomSection = useCallback((sectionId: string) => {
    setConfig(prev => ({
      ...prev,
      customSections: prev.customSections.filter(section => section.id !== sectionId)
    }));
  }, []);

  const previewReport = useCallback(async () => {
    setIsPreviewing(true);
    try {
      // This would generate a preview of the report
      console.log('Generating report preview with config:', config);
    } catch (error) {
      console.error('Error generating preview:', error);
    } finally {
      setIsPreviewing(false);
    }
  }, [config]);

  const resetConfig = useCallback(() => {
    setConfig({
      name: '',
      type: 'summary',
      format: 'pdf',
      recipients: [],
      includeCharts: true,
      includeTables: true,
      dateRange: {
        start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
        end: new Date().toISOString(),
      },
      filters: {},
      customSections: [],
    });
  }, []);

  return {
    config,
    isPreviewing,
    updateConfig,
    updateNestedConfig,
    addCustomSection,
    updateCustomSection,
    removeCustomSection,
    previewReport,
    resetConfig,
  };
};

// Hook for report export
export const useReportExport = () => {
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);

  const exportReport = useCallback(async (
    reportId: string,
    format: 'pdf' | 'csv' | 'json',
    options?: {
      includeRawData?: boolean;
      compression?: boolean;
    }
  ) => {
    setIsExporting(true);
    setExportProgress(0);

    try {
      // Simulate progress updates
      const progressInterval = setInterval(() => {
        setExportProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 500);

      const result = await reportApi.generateReport(reportId, format);

      clearInterval(progressInterval);
      setExportProgress(100);

      // Trigger download
      const link = document.createElement('a');
      link.href = result.downloadUrl;
      link.download = `report_${reportId}_${Date.now()}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      return result;
    } catch (error: any) {
      console.error('Export error:', error);
      throw error;
    } finally {
      setIsExporting(false);
      setExportProgress(0);
    }
  }, []);

  return {
    exportReport,
    isExporting,
    exportProgress,
  };
};