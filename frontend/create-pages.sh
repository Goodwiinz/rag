#!/bin/bash

# Dashboard
cat > src/app/\(dashboard\)/dashboard/page.tsx << 'EOPAGE'
'use client';

import DashboardPage from '@/pages/DashboardPage';

export default function Dashboard() {
  return <DashboardPage />;
}
EOPAGE

# Documents list
cat > src/app/\(dashboard\)/documents/page.tsx << 'EOPAGE'
'use client';

import DocumentsPage from '@/pages/documents/DocumentsPage';

export default function Documents() {
  return <DocumentsPage />;
}
EOPAGE

# Document detail
cat > src/app/\(dashboard\)/documents/\[id\]/page.tsx << 'EOPAGE'
'use client';

import DocumentDetailPage from '@/pages/documents/DocumentDetailPage';

export default function DocumentDetail() {
  return <DocumentDetailPage />;
}
EOPAGE

# Search
cat > src/app/\(dashboard\)/search/page.tsx << 'EOPAGE'
'use client';

import SearchPage from '@/pages/search/SearchPage';

export default function Search() {
  return <SearchPage />;
}
EOPAGE

# Knowledge Graph
cat > src/app/\(dashboard\)/graph/page.tsx << 'EOPAGE'
'use client';

import KnowledgeGraphPage from '@/pages/graph/KnowledgeGraphPage';

export default function Graph() {
  return <KnowledgeGraphPage />;
}
EOPAGE

# Analytics Overview
cat > src/app/\(dashboard\)/analytics/overview/page.tsx << 'EOPAGE'
'use client';

import AnalyticsOverviewPage from '@/pages/analytics/AnalyticsOverviewPage';

export default function AnalyticsOverview() {
  return <AnalyticsOverviewPage />;
}
EOPAGE

# Analytics Performance
cat > src/app/\(dashboard\)/analytics/performance/page.tsx << 'EOPAGE'
'use client';

import PerformanceAnalyticsPage from '@/pages/analytics/PerformanceAnalyticsPage';

export default function PerformanceAnalytics() {
  return <PerformanceAnalyticsPage />;
}
EOPAGE

# Analytics Usage
cat > src/app/\(dashboard\)/analytics/usage/page.tsx << 'EOPAGE'
'use client';

import UsageAnalyticsPage from '@/pages/analytics/UsageAnalyticsPage';

export default function UsageAnalytics() {
  return <UsageAnalyticsPage />;
}
EOPAGE

# Evaluation Management
cat > src/app/\(dashboard\)/evaluation/page.tsx << 'EOPAGE'
'use client';

import EvaluationManagementPage from '@/pages/evaluation/EvaluationManagementPage';

export default function EvaluationManagement() {
  return <EvaluationManagementPage />;
}
EOPAGE

# Create Evaluation
cat > src/app/\(dashboard\)/evaluation/create/page.tsx << 'EOPAGE'
'use client';

import CreateEvaluationPage from '@/pages/evaluation/CreateEvaluationPage';

export default function CreateEvaluation() {
  return <CreateEvaluationPage />;
}
EOPAGE

# Evaluation Details
cat > src/app/\(dashboard\)/evaluation/\[id\]/page.tsx << 'EOPAGE'
'use client';

import EvaluationDetailsPage from '@/pages/evaluation/EvaluationDetailsPage';

export default function EvaluationDetails() {
  return <EvaluationDetailsPage />;
}
EOPAGE

# Compare Evaluations
cat > src/app/\(dashboard\)/evaluation/compare/page.tsx << 'EOPAGE'
'use client';

import CompareEvaluationsPage from '@/pages/evaluation/CompareEvaluationsPage';

export default function CompareEvaluations() {
  return <CompareEvaluationsPage />;
}
EOPAGE

# A/B Testing Dashboard
cat > src/app/\(dashboard\)/ab-testing/page.tsx << 'EOPAGE'
'use client';

import ABTestingDashboardPage from '@/pages/ab-testing/ABTestingDashboardPage';

export default function ABTestingDashboard() {
  return <ABTestingDashboardPage />;
}
EOPAGE

# Create Experiment
cat > src/app/\(dashboard\)/ab-testing/create/page.tsx << 'EOPAGE'
'use client';

import CreateExperimentPage from '@/pages/ab-testing/CreateExperimentPage';

export default function CreateExperiment() {
  return <CreateExperimentPage />;
}
EOPAGE

# Experiment Details
cat > src/app/\(dashboard\)/ab-testing/\[id\]/page.tsx << 'EOPAGE'
'use client';

import ExperimentDetailsPage from '@/pages/ab-testing/ExperimentDetailsPage';

export default function ExperimentDetails() {
  return <ExperimentDetailsPage />;
}
EOPAGE

# Search Analytics
cat > src/app/\(dashboard\)/search-analytics/page.tsx << 'EOPAGE'
'use client';

import SearchAnalyticsPage from '@/pages/search-analytics/SearchAnalyticsPage';

export default function SearchAnalytics() {
  return <SearchAnalyticsPage />;
}
EOPAGE

# System Monitoring
cat > src/app/\(dashboard\)/monitoring/page.tsx << 'EOPAGE'
'use client';

import SystemMonitoringPage from '@/pages/monitoring/SystemMonitoringPage';

export default function SystemMonitoring() {
  return <SystemMonitoringPage />;
}
EOPAGE

# Alert Management
cat > src/app/\(dashboard\)/monitoring/alerts/page.tsx << 'EOPAGE'
'use client';

import AlertManagementPage from '@/pages/monitoring/AlertManagementPage';

export default function AlertManagement() {
  return <AlertManagementPage />;
}
EOPAGE

# User Settings
cat > src/app/\(dashboard\)/settings/page.tsx << 'EOPAGE'
'use client';

import UserSettingsPage from '@/pages/settings/UserSettingsPage';

export default function UserSettings() {
  return <UserSettingsPage />;
}
EOPAGE

# Organization Settings
cat > src/app/\(dashboard\)/settings/organization/page.tsx << 'EOPAGE'
'use client';

import OrganizationSettingsPage from '@/pages/settings/OrganizationSettingsPage';

export default function OrganizationSettings() {
  return <OrganizationSettingsPage />;
}
EOPAGE

# API Key Management
cat > src/app/\(dashboard\)/settings/api-keys/page.tsx << 'EOPAGE'
'use client';

import APIKeyManagementPage from '@/pages/settings/APIKeyManagementPage';

export default function APIKeyManagement() {
  return <APIKeyManagementPage />;
}
EOPAGE

echo "All pages created successfully!"
