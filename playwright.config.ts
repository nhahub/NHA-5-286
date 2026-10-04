import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './runs',
  testMatch: '**/*.spec.ts',
  timeout: 30_000,
  retries: 1,
  workers: 1,
  reporter: [
    ['json', { outputFile: 'results/results.json' }],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  use: {
    browserName: 'chromium',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
