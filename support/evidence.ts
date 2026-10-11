import { test as base, expect } from '@playwright/test';

type ConsoleEntry = { type: 'error' | 'warning' | 'pageerror'; text: string };
type NetworkEntry = {
  kind: 'http_error' | 'request_failed';
  status: number | null;
  method: string;
  url: string;
  failure: string | null;
};

const MAX_ENTRIES = 200;
const MAX_TEXT = 500;

function capped<T>(list: T[], item: T): void {
  if (list.length < MAX_ENTRIES) list.push(item);
}

export const test = base.extend<{ evidence: void }>({
  evidence: [
    async ({ page }, use, testInfo) => {
      const consoleLogs: ConsoleEntry[] = [];
      const network: NetworkEntry[] = [];

      page.on('console', (msg) => {
        const type = msg.type();
        if (type === 'error' || type === 'warning') {
          capped(consoleLogs, { type, text: msg.text().slice(0, MAX_TEXT) });
        }
      });
      page.on('pageerror', (err) =>
        capped(consoleLogs, { type: 'pageerror', text: err.message.slice(0, MAX_TEXT) }),
      );
      page.on('response', (res) => {
        if (res.status() >= 400) {
          capped(network, {
            kind: 'http_error', status: res.status(),
            method: res.request().method(), url: res.url(), failure: null,
          });
        }
      });
      page.on('requestfailed', (req) =>
        capped(network, {
          kind: 'request_failed', status: null, method: req.method(),
          url: req.url(), failure: req.failure()?.errorText ?? 'unknown',
        }),
      );

      await use();

      if (testInfo.status === testInfo.expectedStatus) return; // evidence on failure only

      await testInfo.attach('console.json', {
        body: JSON.stringify(consoleLogs, null, 2), contentType: 'application/json',
      });
      await testInfo.attach('network.json', {
        body: JSON.stringify(network, null, 2), contentType: 'application/json',
      });
      await testInfo.attach('final-url.txt', {
        body: page.url(), contentType: 'text/plain',
      });
    },
    { auto: true },
  ],
});

export { expect };