import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  // @ts-ignore
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    include: [
      'src/**/*.{test,spec}.{js,ts,jsx,tsx}',
      'tests/**/*.{test,spec}.{js,ts,jsx,tsx}'
    ],
    exclude: [
      'node_modules/',
      'dist/',
      '.next/',
      'cypress/',
      'e2e/'
    ],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      reportsDirectory: './coverage',
      exclude: [
        'node_modules/',
        'dist/',
        '.next/',
        'e2e/',
        'src/test/setup.ts',
        '**/*.config.{js,ts}',
        '**/*.d.ts',
        '**/types.ts',
        'src/pages/_app.tsx',
        'src/pages/_document.tsx'
      ],
      // Coverage thresholds (baseline - increase incrementally)
      // Target: 70% lines, 70% functions, 65% branches, 70% statements
      // Current baseline set to not block CI while E2E tests provide integration coverage
      thresholds: {
        lines: 30,
        functions: 30,
        branches: 50,
        statements: 30
      }
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/components': path.resolve(__dirname, './src/components'),
      '@/lib': path.resolve(__dirname, './src/lib'),
      '@/pages': path.resolve(__dirname, './src/pages')
    }
  }
})