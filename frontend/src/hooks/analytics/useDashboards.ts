import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useCallback } from 'react';
import { dashboardApi } from '@/services/analytics';
import { useAnalyticsStore } from '@/store/analytics';
import { Dashboard, Widget } from '@/store/analytics';

// Hook for fetching dashboards
export const useDashboards = () => {
  const { setLoading, setError, setDashboards } = useAnalyticsStore();

  return useQuery({
    queryKey: ['dashboards'],
    queryFn: () => dashboardApi.getDashboards(),
    staleTime: 30000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for fetching a single dashboard
export const useDashboard = (dashboardId: string) => {
  const { setLoading, setError } = useAnalyticsStore();

  return useQuery({
    queryKey: ['dashboard', dashboardId],
    queryFn: () => dashboardApi.getDashboard(dashboardId),
    enabled: !!dashboardId,
    staleTime: 30000,
    onSettled: () => {
      setLoading(false);
    },
  });
};

// Hook for creating dashboards
export const useCreateDashboard = () => {
  const queryClient = useQueryClient();
  const { setError, createDashboard } = useAnalyticsStore();

  return useMutation({
    mutationFn: (dashboard: Omit<Dashboard, 'id' | 'createdAt' | 'updatedAt'>) =>
      dashboardApi.createDashboard(dashboard),
  });
};

// Hook for updating dashboards
export const useUpdateDashboard = () => {
  const queryClient = useQueryClient();
  const { setError, updateDashboard } = useAnalyticsStore();

  return useMutation({
    mutationFn: ({ dashboardId, updates }: { dashboardId: string; updates: Partial<Dashboard> }) =>
      dashboardApi.updateDashboard(dashboardId, updates),
  });
};

// Hook for deleting dashboards
export const useDeleteDashboard = () => {
  const queryClient = useQueryClient();
  const { setError, deleteDashboard } = useAnalyticsStore();

  return useMutation({
    mutationFn: (dashboardId: string) => dashboardApi.deleteDashboard(dashboardId),
  });
};

// Hook for duplicating dashboards
export const useDuplicateDashboard = () => {
  const queryClient = useQueryClient();
  const { setError, duplicateDashboard } = useAnalyticsStore();

  return useMutation({
    mutationFn: ({ dashboardId, name }: { dashboardId: string; name: string }) =>
      dashboardApi.duplicateDashboard(dashboardId, name),
  });
};

// Hook for dashboard management
export const useDashboardManager = (dashboardId?: string) => {
  const {
    dashboards,
    activeDashboard,
    setActiveDashboard,
    addWidget,
    updateWidget,
    removeWidget,
    moveWidget,
    refreshWidget,
    setWidgetData,
  } = useAnalyticsStore();

  const [isCreating, setIsCreating] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const currentDashboard = dashboardId
    ? dashboards.find(d => d.id === dashboardId)
    : activeDashboard
      ? dashboards.find(d => d.id === activeDashboard)
      : null;

  const switchDashboard = useCallback((id: string) => {
    setActiveDashboard(id);
  }, [setActiveDashboard]);

  const createNewDashboard = useCallback(async (dashboard: Omit<Dashboard, 'id' | 'createdAt' | 'updatedAt'>) => {
    setIsCreating(true);
    try {
      // The actual creation is handled by the useCreateDashboard mutation
      console.log('Creating new dashboard:', dashboard);
    } finally {
      setIsCreating(false);
    }
  }, []);

  const startEditing = useCallback(() => {
    setIsEditing(true);
  }, []);

  const stopEditing = useCallback(() => {
    setIsEditing(false);
  }, []);

  const addWidgetToDashboard = useCallback((widget: Omit<Widget, 'id' | 'lastUpdated' | 'isRefreshing'>) => {
    if (currentDashboard) {
      addWidget(currentDashboard.id, widget);
    }
  }, [currentDashboard, addWidget]);

  const updateWidgetInDashboard = useCallback((widgetId: string, updates: Partial<Widget>) => {
    updateWidget(widgetId, updates);
  }, [updateWidget]);

  const removeWidgetFromDashboard = useCallback((widgetId: string) => {
    removeWidget(widgetId);
  }, [removeWidget]);

  const moveWidgetInDashboard = useCallback((widgetId: string, position: { x: number; y: number; width: number; height: number }) => {
    moveWidget(widgetId, position);
  }, [moveWidget]);

  const refreshWidgetInDashboard = useCallback((widgetId: string) => {
    refreshWidget(widgetId);
  }, [refreshWidget]);

  const updateWidgetData = useCallback((widgetId: string, data: any) => {
    setWidgetData(widgetId, data);
  }, [setWidgetData]);

  return {
    // Dashboard data
    dashboards,
    currentDashboard,
    activeDashboard,

    // Dashboard actions
    switchDashboard,
    createNewDashboard,
    startEditing,
    stopEditing,

    // Widget actions
    addWidgetToDashboard,
    updateWidgetInDashboard,
    removeWidgetFromDashboard,
    moveWidgetInDashboard,
    refreshWidgetInDashboard,
    updateWidgetData,

    // State
    isCreating,
    isEditing,
    hasActiveDashboard: !!currentDashboard,
    widgetCount: currentDashboard?.widgets.length || 0,
  };
};

// Hook for widget data fetching
export const useWidgetData = (widgetId: string, config?: any) => {
  const { setWidgetData, refreshWidget } = useAnalyticsStore();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchWidgetData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // This would call the appropriate API based on widget type and config
      console.log(`Fetching data for widget ${widgetId}`, config);

      // Mock data for now
      const mockData = {
        metric: { value: 1234, trend: 'up' },
        chart: { data: [1, 2, 3, 4, 5] },
        table: { rows: [{ id: 1, name: 'Test' }] },
      };

      setWidgetData(widgetId, mockData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }, [widgetId, config, setWidgetData]);

  const refreshData = useCallback(() => {
    refreshWidget(widgetId);
    fetchWidgetData();
  }, [widgetId, refreshWidget, fetchWidgetData]);

  return {
    data: null, // This would come from the store
    isLoading,
    error,
    refetch: fetchWidgetData,
    refresh: refreshData,
  };
};

// Hook for dashboard templates
export const useDashboardTemplates = () => {
  const [templates, setTemplates] = useState<Dashboard[]>([]);

  const loadTemplates = useCallback(async () => {
    // This would fetch templates from the API
    const mockTemplates: Dashboard[] = [
      {
        id: 'template-overview',
        name: 'Overview Dashboard',
        description: 'General overview of system metrics',
        widgets: [],
        layout: 'grid',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        isPublic: true,
        tags: ['overview', 'general'],
      },
      {
        id: 'template-performance',
        name: 'Performance Dashboard',
        description: 'Performance monitoring and metrics',
        widgets: [],
        layout: 'grid',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        isPublic: true,
        tags: ['performance', 'monitoring'],
      },
    ];

    setTemplates(mockTemplates);
  }, []);

  const createFromTemplate = useCallback(async (templateId: string, name: string) => {
    const template = templates.find(t => t.id === templateId);
    if (!template) {
      throw new Error('Template not found');
    }

    // Create a new dashboard from the template
    const newDashboard: Omit<Dashboard, 'id' | 'createdAt' | 'updatedAt'> = {
      name,
      description: template.description,
      widgets: template.widgets.map(widget => ({
        ...widget,
        id: `widget_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      })),
      layout: template.layout,
      isPublic: false,
      tags: [...template.tags],
    };

    return newDashboard;
  }, [templates]);

  return {
    templates,
    loadTemplates,
    createFromTemplate,
  };
};

// Hook for dashboard sharing
export const useDashboardSharing = (dashboardId: string) => {
  const { updateDashboard } = useAnalyticsStore();
  const [isSharing, setIsSharing] = useState(false);
  const [shareUrl, setShareUrl] = useState<string | null>(null);

  const generateShareUrl = useCallback(async () => {
    setIsSharing(true);
    try {
      // This would call an API to generate a share link
      const url = `${window.location.origin}/analytics/shared/${dashboardId}`;
      setShareUrl(url);

      // Update dashboard to make it public
      updateDashboard(dashboardId, { isPublic: true });
    } catch (error: any) {
      console.error('Error generating share URL:', error);
    } finally {
      setIsSharing(false);
    }
  }, [dashboardId, updateDashboard]);

  const disableSharing = useCallback(async () => {
    try {
      updateDashboard(dashboardId, { isPublic: false });
      setShareUrl(null);
    } catch (error: any) {
      console.error('Error disabling sharing:', error);
    }
  }, [dashboardId, updateDashboard]);

  return {
    isSharing,
    shareUrl,
    generateShareUrl,
    disableSharing,
    canShare: true,
  };
};