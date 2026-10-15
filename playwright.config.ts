import { defineConfig, devices } from '@playwright/test';
import * as path from 'node:path';

/**
 * Playwright configuration for generated specs.
 *
 * Contract with execution/runner.py (P3):
 *   - RUN_DIR   absolute or repo-relative path to runs/<run_id>/ (set per run)
 *   - TARGET_URL optional; resolved by intake, exposed as baseURL
 * Layout inside RUN_DIR: tests/, artifacts/, results.json, html-report/
 */
const RUN_DIR = path.resolve(process.env.RUN_DIR || 'runs/_local');

export default defineConfig({
  testDir: path.join(RUN_DIR, 'tests'),
  testMatch: '**/*.spec.ts',
  outputDir: path.join(RUN_DIR, 'artifacts'),

  timeout: 30_000, // per test, locked in the architecture spec
  expect: { timeout: 10_000 }, // generated code may not set custom timeouts
  globalTimeout: 10 * 60_000, // hard cap for the whole run (spec: limits on run duration)

  fullyParallel: false,
  workers: 1,
  retries: 0, // retries are owned by the LangGraph orchestrator
  forbidOnly: true, // a generated test.only must fail the run, never skip tests

  reporter: [
    ['list'],
    ['json', { outputFile: path.join(RUN_DIR, 'results.json') }],
    ['html', { outputFolder: path.join(RUN_DIR, 'html-report'), open: 'never' }],
  ],

  use: {
    baseURL: process.env.TARGET_URL,
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },

  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});