import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright Configuration for Autonomous AI Test Execution Engine.
 */
export default defineConfig({
  testDir: './runs',
  testMatch: '**/*.spec.ts',

  /* Timeout per individual test execution (30 seconds limit as per locked specs) */
  timeout: 30_000,
  
  expect: {
    timeout: 5000,
  },

  /* Do not run test files in parallel to guarantee isolated execution state */
  fullyParallel: false,

  /* Retries managed exclusively by LangGraph orchestrator, set to 0 */
  retries: 0,

  /* Single worker execution for deterministic results */
  workers: 1,

  /* Reporters: console list + JSON for evidence parser */
  reporter: [
    ['list'],
    ['json', { outputFile: 'results.json' }]
  ],

  use: {
    browserName: 'chromium',
    headless: true,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 10_000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  outputDir: 'test-results/',
});