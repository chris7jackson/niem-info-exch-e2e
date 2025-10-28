import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E Test Configuration
 *
 * This configuration sets up end-to-end testing for the NIEM GraphRAG UI.
 * Tests run against a local development server and cover critical user workflows
 * including schema upload, data ingestion, and graph visualization.
 *
 * Key Features:
 * - Runs tests in Chrome (with optional Firefox/Safari)
 * - Automatically starts backend (Docker Compose) and frontend (Next.js dev server)
 * - Captures screenshots/videos on failure
 * - Retries flaky tests in CI environment
 * - Generates HTML reports for test results
 *
 * Prerequisites:
 * - Docker Desktop running
 * - .env file in project root (copy from .env.example)
 * - Backend services started: docker compose up -d (from project root)
 */
export default defineConfig({
  // Test directory containing E2E tests
  testDir: './e2e/tests',

  // Global setup script (uploads test schema via API before all tests)
  globalSetup: './e2e/global-setup.ts',

  // Run tests in files in parallel
  fullyParallel: true,

  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Opt out of parallel tests on CI (to avoid resource contention)
  workers: process.env.CI ? 1 : undefined,

  // Reporter configuration
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['junit', { outputFile: 'test-results/junit.xml' }],
    ['json', { outputFile: 'test-results/results.json' }],
    ['list'], // Console output
  ],

  // Shared settings for all tests
  use: {
    // Base URL for navigation
    baseURL: process.env.BASE_URL || 'http://localhost:3000',

    // Collect trace when retrying the failed test
    trace: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video on failure
    video: 'retain-on-failure',

    // Maximum time each action can take (e.g., click, fill)
    actionTimeout: 10000,
  },

  // Global timeout for each test
  timeout: 60000,

  // Expect timeout for assertions
  expect: {
    timeout: 10000,
  },

  // Configure projects for major browsers
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    // Uncomment to test in Firefox
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },

    // Uncomment to test in Safari
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  // Run local dev server before starting tests
  // Note: Backend services (API, Neo4j, MinIO) must be running via Docker Compose
  // Run: docker compose up -d (from project root) before running E2E tests
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000, // 2 minutes to start dev server
    stdout: 'pipe',
    stderr: 'pipe',
  },
});
