// frontend/vitest.workspace.mts
import { defineWorkspace } from 'vitest/config';

export default defineWorkspace([
  {
    extends: './vitest.config.mts',
    test: {
      name: 'unit',
      environment: 'jsdom',
      // Widened from 'src/test/__tests__/**' to cover all __tests__ directories
      // under src/ as component test files are added (e.g. ui/__tests__/).
      include: ['src/**/__tests__/**/*.test.{ts,tsx}'],
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
      name: 'cli',
      environment: 'node',
      // PR #1: no CLI tests are migrated yet. PR #2 widens this back.
      include: ['cli/__tests__/__vitest_only__/**/*.test.{ts,tsx}'],
      exclude: ['node_modules/**'],
    },
  },
]);
