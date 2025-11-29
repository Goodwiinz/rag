import React, { Suspense } from 'react';
import { createBrowserRouter, RouterProvider, Navigate, Outlet } from 'react-router-dom';
import { PageSkeleton } from '@/components/common/PageSkeleton';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { ProtectedRoute } from '@/components/common/ProtectedRoute';
import { AppLayout } from '@/components/layout/AppLayout';
import { useAuth } from '@/hooks/useAuth';

// Lazy loaded page components
const DashboardPage = React.lazy(() => import('@/pages/DashboardPage'));
const DocumentsPage = React.lazy(() => import('@/pages/documents/DocumentsPage'));
const DocumentDetailPage = React.lazy(() => import('@/pages/documents/DocumentDetailPage'));
const SearchPage = React.lazy(() => import('@/pages/search/SearchPage'));
const KnowledgeGraphPage = React.lazy(() => import('@/pages/graph/KnowledgeGraphPage'));

const AnalyticsOverviewPage = React.lazy(() => import('@/pages/analytics/AnalyticsOverviewPage'));
const PerformanceAnalyticsPage = React.lazy(() => import('@/pages/analytics/PerformanceAnalyticsPage'));
const UsageAnalyticsPage = React.lazy(() => import('@/pages/analytics/UsageAnalyticsPage'));

const EvaluationManagementPage = React.lazy(() => import('@/pages/evaluation/EvaluationManagementPage'));
const CreateEvaluationPage = React.lazy(() => import('@/pages/evaluation/CreateEvaluationPage'));
const EvaluationDetailsPage = React.lazy(() => import('@/pages/evaluation/EvaluationDetailsPage'));
const CompareEvaluationsPage = React.lazy(() => import('@/pages/evaluation/CompareEvaluationsPage'));

const ABTestingDashboardPage = React.lazy(() => import('@/pages/ab-testing/ABTestingDashboardPage'));
const CreateExperimentPage = React.lazy(() => import('@/pages/ab-testing/CreateExperimentPage'));
const ExperimentDetailsPage = React.lazy(() => import('@/pages/ab-testing/ExperimentDetailsPage'));

const SearchAnalyticsPage = React.lazy(() => import('@/pages/search-analytics/SearchAnalyticsPage'));

const SystemMonitoringPage = React.lazy(() => import('@/pages/monitoring/SystemMonitoringPage'));
const AlertManagementPage = React.lazy(() => import('@/pages/monitoring/AlertManagementPage'));

const UserSettingsPage = React.lazy(() => import('@/pages/settings/UserSettingsPage'));
const OrganizationSettingsPage = React.lazy(() => import('@/pages/settings/OrganizationSettingsPage'));
const APIKeyManagementPage = React.lazy(() => import('@/pages/settings/APIKeyManagementPage'));

const LoginPage = React.lazy(() => import('@/pages/auth/LoginPage'));
const NotFoundPage = React.lazy(() => import('@/pages/error/NotFoundPage'));

// Suspense wrapper for lazy loading
const LazyWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Suspense fallback={<PageSkeleton />}>
    <ErrorBoundary>{children}</ErrorBoundary>
  </Suspense>
);


// Root redirect component that checks auth
const RootRedirect = () => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return <Navigate to={isAuthenticated ? "/" : "/login"} replace />;
};

// Documents routes
const documentRoutes = {
  path: 'documents',
  children: [
    {
      index: true,
      element: (
        <LazyWrapper>
          <DocumentsPage />
        </LazyWrapper>
      ),
    },
    {
      path: ':id',
      element: (
        <LazyWrapper>
          <DocumentDetailPage />
        </LazyWrapper>
      ),
    },
  ],
};

// Search routes
const searchRoutes = {
  path: 'search',
  children: [
    {
      index: true,
      element: (
        <LazyWrapper>
          <SearchPage />
        </LazyWrapper>
      ),
    },
  ],
};

// Knowledge Graph routes
const graphRoutes = {
  path: 'graph',
  children: [
    {
      index: true,
      element: (
        <LazyWrapper>
          <KnowledgeGraphPage />
        </LazyWrapper>
      ),
    },
  ],
};

// Analytics routes
const analyticsRoutes = {
  path: 'analytics',
  children: [
    {
      index: true,
      element: <Navigate to="/analytics/overview" replace />,
    },
    {
      path: 'overview',
      element: (
        <LazyWrapper>
          <AnalyticsOverviewPage />
        </LazyWrapper>
      ),
    },
    {
      path: 'performance',
      element: (
        <LazyWrapper>
          <PerformanceAnalyticsPage />
        </LazyWrapper>
      ),
    },
    {
      path: 'usage',
      element: (
        <LazyWrapper>
          <UsageAnalyticsPage />
        </LazyWrapper>
      ),
    },
  ],
};

// Evaluation routes
const evaluationRoutes = {
  path: 'evaluation',
  children: [
    {
      index: true,
      element: (
        <LazyWrapper>
          <EvaluationManagementPage />
        </LazyWrapper>
      ),
    },
    {
      path: 'create',
      element: (
        <LazyWrapper>
          <CreateEvaluationPage />
        </LazyWrapper>
      ),
    },
    {
      path: ':id',
      element: (
        <LazyWrapper>
          <EvaluationDetailsPage />
        </LazyWrapper>
      ),
    },
    {
      path: 'compare',
      element: (
        <LazyWrapper>
          <CompareEvaluationsPage />
        </LazyWrapper>
      ),
    },
  ],
};

// A/B Testing routes
const abTestingRoutes = {
  path: 'ab-testing',
  children: [
    {
      index: true,
      element: (
        <LazyWrapper>
          <ABTestingDashboardPage />
        </LazyWrapper>
      ),
    },
    {
      path: 'create',
      element: (
        <LazyWrapper>
          <CreateExperimentPage />
        </LazyWrapper>
      ),
    },
    {
      path: ':id',
      element: (
        <LazyWrapper>
          <ExperimentDetailsPage />
        </LazyWrapper>
      ),
    },
  ],
};

// Monitoring routes
const monitoringRoutes = {
  path: 'monitoring',
  children: [
    {
      index: true,
      element: (
        <LazyWrapper>
          <SystemMonitoringPage />
        </LazyWrapper>
      ),
    },
    {
      path: 'alerts',
      element: (
        <LazyWrapper>
          <AlertManagementPage />
        </LazyWrapper>
      ),
    },
  ],
};

// Settings routes
const settingsRoutes = {
  path: 'settings',
  children: [
    {
      index: true,
      element: (
        <LazyWrapper>
          <UserSettingsPage />
        </LazyWrapper>
      ),
    },
    {
      path: 'organization',
      element: (
        <LazyWrapper>
          <OrganizationSettingsPage />
        </LazyWrapper>
      ),
    },
    {
      path: 'api-keys',
      element: (
        <LazyWrapper>
          <APIKeyManagementPage />
        </LazyWrapper>
      ),
    },
  ],
};

// Create router configuration
const router = createBrowserRouter([
  // Public routes
  {
    path: '/login',
    element: (
      <LazyWrapper>
        <LoginPage />
      </LazyWrapper>
    ),
  },
  // Root redirect based on auth status
  {
    path: '/',
    element: <RootRedirect />,
  },
  // Layout wrapper for all protected routes
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: (
          <LazyWrapper>
            <DashboardPage />
          </LazyWrapper>
        ),
      },
      documentRoutes,
      searchRoutes,
      graphRoutes,
      analyticsRoutes,
      evaluationRoutes,
      abTestingRoutes,
      {
        path: 'search-analytics',
        element: (
          <LazyWrapper>
            <SearchAnalyticsPage />
          </LazyWrapper>
        ),
      },
      monitoringRoutes,
      settingsRoutes,
    ],
    errorElement: (
      <LazyWrapper>
        <NotFoundPage />
      </LazyWrapper>
    ),
  },
  // Catch-all route for 404
  {
    path: '*',
    element: (
      <LazyWrapper>
        <NotFoundPage />
      </LazyWrapper>
    ),
  },
]);

// Route definitions for navigation
export const routeDefinitions = [
  {
    path: '/',
    name: 'Dashboard',
    icon: 'home',
    description: 'Main dashboard with document upload and search interface',
  },
  {
    path: '/documents',
    name: 'Documents',
    icon: 'upload',
    description: 'Manage and view uploaded documents',
  },
  {
    path: '/search',
    name: 'Search',
    icon: 'search',
    description: 'Search through your documents with AI-powered answers',
  },
  {
    path: '/graph',
    name: 'Knowledge Graph',
    icon: 'network',
    description: 'Explore entity relationships in your documents',
  },
  {
    path: '/analytics',
    name: 'Analytics',
    icon: 'bar-chart',
    children: [
      {
        path: '/analytics/overview',
        name: 'Overview',
        description: 'General analytics and insights',
      },
      {
        path: '/analytics/performance',
        name: 'Performance',
        description: 'Performance metrics and trends',
      },
      {
        path: '/analytics/usage',
        name: 'Usage Analytics',
        description: 'User behavior and usage patterns',
      },
    ],
  },
  {
    path: '/evaluation',
    name: 'Evaluations',
    icon: 'clipboard-list',
    children: [
      {
        path: '/evaluation',
        name: 'Management',
        description: 'View and manage evaluations',
      },
      {
        path: '/evaluation/create',
        name: 'Create Evaluation',
        description: 'Create new evaluation',
      },
      {
        path: '/evaluation/compare',
        name: 'Compare',
        description: 'Compare multiple evaluations',
      },
    ],
  },
  {
    path: '/ab-testing',
    name: 'A/B Testing',
    icon: 'flask',
    children: [
      {
        path: '/ab-testing',
        name: 'Experiments',
        description: 'Manage A/B testing experiments',
      },
      {
        path: '/ab-testing/create',
        name: 'Create Experiment',
        description: 'Create new A/B test',
      },
    ],
  },
  {
    path: '/search-analytics',
    name: 'Search Analytics',
    icon: 'search',
    description: 'Search patterns and query analysis',
  },
  {
    path: '/monitoring',
    name: 'Monitoring',
    icon: 'monitor',
    children: [
      {
        path: '/monitoring',
        name: 'System Health',
        description: 'System monitoring and health checks',
      },
      {
        path: '/monitoring/alerts',
        name: 'Alerts',
        description: 'Manage system alerts and notifications',
      },
    ],
  },
  {
    path: '/settings',
    name: 'Settings',
    icon: 'cog',
    children: [
      {
        path: '/settings',
        name: 'User Settings',
        description: 'Personal preferences and profile',
      },
      {
        path: '/settings/organization',
        name: 'Organization',
        description: 'Organization settings and configuration',
      },
      {
        path: '/settings/api-keys',
        name: 'API Keys',
        description: 'Manage API keys and integrations',
      },
    ],
  },
];

export const AppRouter: React.FC = () => {
  return <RouterProvider router={router} />;
};

export default AppRouter;