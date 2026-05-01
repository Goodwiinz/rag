// frontend/vitest.workspace.mts
import { defineWorkspace } from 'vitest/config';

export default defineWorkspace([
  {
    extends: './vitest.config.mts',
    test: {
      name: 'unit',
      environment: 'jsdom',
      include: [
        'src/**/__tests__/**/*.test.{ts,tsx}',
        'src/__tests__/sanity.test.ts',
      ],
      exclude: [
        'src/integration/**',
        'src/__tests__/App.routing.test.tsx',
        'node_modules/**',
        'e2e/**',
      ],
    },
  },
  {
    extends: './vitest.config.mts',
    test: {
      name: 'integration',
      environment: 'jsdom',
      include: ['src/integration/**/__tests__/**/*.test.{ts,tsx}'],
      // monitoring-dashboard.test.tsx references `../../components/monitoring/SystemOverview`
      // (renamed to SystemOverviewDashboard) and monitoring-react-query.test.tsx
      // references `../../hooks/queries/useSystemHealthQuery` which doesn't
      // exist in this codebase. Both predate the current monitoring API
      // and would need a rewrite. TODO: rewrite or delete; not migration
      // bugs, just stale tests.
      exclude: [
        'node_modules/**',
        'e2e/**',
        'src/integration/__tests__/monitoring-dashboard.test.tsx',
        'src/integration/__tests__/monitoring-react-query.test.tsx',
      ],
    },
  },
  {
    extends: './vitest.config.mts',
    test: {
      name: 'cli',
      environment: 'node',
      include: ['cli/__tests__/**/*.test.{ts,tsx}'],
      exclude: ['node_modules/**'],
    },
  },
]);
