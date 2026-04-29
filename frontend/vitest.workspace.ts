// frontend/vitest.workspace.ts
import { defineWorkspace } from 'vitest/config';

export default defineWorkspace([
  {
    extends: './vitest.config.ts',
    test: {
      name: 'unit',
      environment: 'jsdom',
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
    extends: './vitest.config.ts',
    test: {
      name: 'cli',
      environment: 'node',
      include: ['cli/__tests__/**/*.test.{ts,tsx}'],
      exclude: ['node_modules/**'],
    },
  },
]);
