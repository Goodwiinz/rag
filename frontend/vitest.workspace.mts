// frontend/vitest.workspace.mts
import { defineWorkspace } from 'vitest/config';

export default defineWorkspace([
  {
    extends: './vitest.config.mts',
    test: {
      name: 'unit',
      environment: 'jsdom',
      // PR #1 ships only the Vitest infra + a single smoke test. PR #2 widens this
      // glob back to 'src/**/__tests__/**/*.test.{ts,tsx}' as files are migrated
      // off Jest globals.
      include: ['src/test/__tests__/**/*.test.{ts,tsx}'],
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
