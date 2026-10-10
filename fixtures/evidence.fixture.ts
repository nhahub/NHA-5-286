import { test as base, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

export const test = base.extend<{ page: import('@playwright/test').Page }>({
  page: async ({ page }, use, testInfo) => {
    const consoleLogs: string[] = [];
    const networkErrors: string[] = [];

    // Capture console errors and warnings
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.type() === 'warning') {
        consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
      }
    });

    // Capture page errors
    page.on('pageerror', (err: Error) => {
      consoleLogs.push(`[pageerror] ${err.message}`);
    });

    // Capture failed network responses (e.g., 4xx and 5xx)
    page.on('response', response => {
      if (response.status() >= 400) {
        networkErrors.push(`${response.status()} ${response.request().method()} ${response.url()}`);
      }
    });

    await use(page);

    // Attach evidence only when test fails
    if (testInfo.status !== testInfo.expectedStatus) {
      // Attach console logs
      const consolePath = testInfo.outputPath('console.json');
      fs.writeFileSync(consolePath, JSON.stringify(consoleLogs, null, 2));
      testInfo.attachments.push({ name: 'console.json', path: consolePath, contentType: 'application/json' });

      // Attach network errors
      const networkPath = testInfo.outputPath('network.json');
      fs.writeFileSync(networkPath, JSON.stringify(networkErrors, null, 2));
      testInfo.attachments.push({ name: 'network.json', path: networkPath, contentType: 'application/json' });

      // Attach final URL
      const finalUrlPath = testInfo.outputPath('final-url.txt');
      fs.writeFileSync(finalUrlPath, page.url());
      testInfo.attachments.push({ name: 'final-url.txt', path: finalUrlPath, contentType: 'text/plain' });
    }
  }
});

export { expect };