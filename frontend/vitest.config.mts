// frontend/vitest.config.mts
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';

// `import.meta.url`-based __dirname replacement (ESM has no __dirname).
const __dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  // `loose: true` makes vite-tsconfig-paths resolve aliases for ALL files,
  // not just those matched by tsconfig.json's `include`. The base tsconfig.json
  // excludes test files (e.g. `**/*.test.ts`), so without `loose` the `@/*`
  // aliases would not resolve inside Vitest tests.
  plugins: [react(), tsconfigPaths({ loose: true })],
  // Backstop alias: tsconfig has `@/*` mapping to multiple targets
  // (`./src/*` and `./app/*`), which vite-tsconfig-paths does not always
  // handle reliably. Pin `@` → `./src` here so test imports like
  // `@/types/schemas` resolve deterministically. The narrow alias for
  // `@/nous` must come *first* — Vite matches longest prefix wins, but
  // listing it first is defensive and matches what tsconfig's specific
  // entry says (`./app/components/nous`).
  resolve: {
    alias: [
      { find: '@/nous', replacement: resolve(__dirname, './app/components/nous') },
      { find: /^@\//, replacement: resolve(__dirname, './src') + '/' },
    ],
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: false,
    css: { modules: { classNameStrategy: 'non-scoped' } },
    testTimeout: 15_000,
    clearMocks: true,
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov', 'json-summary'],
      reportsDirectory: './coverage',
      include: [
        'src/components/**/*.{ts,tsx}',
        'src/hooks/**/*.{ts,tsx}',
        'src/services/**/*.{ts,tsx}',
        'src/store/**/*.{ts,tsx}',
        'src/utils/**/*.{ts,tsx}',
      ],
      exclude: [
        'src/**/*.d.ts',
        'src/**/*.stories.{ts,tsx}',
        'src/**/index.{ts,tsx}',
        'src/components/ui/**',
      ],
      // PR #1 ships smoke-test-only coverage; PR #5 raises this to 50/40/45/50
      // after the codemod sweep and MSW standardization land.
      thresholds: { lines: 0, branches: 0, functions: 0, statements: 0 },
    },
    reporters: process.env.CI
      ? ['default', ['junit', { outputFile: 'coverage/junit-vitest.xml' }]]
      : ['default'],
    typecheck: {
      tsconfig: './tsconfig.vitest.json',
    },
  },
});
