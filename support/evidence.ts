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

// Bounded list that remembers how many items it had to drop
class Capped<T> {
  items: T[] = [];
  dropped = 0;
  push(item: T): void {
    if (this.items.length < MAX_ENTRIES) this.items.push(item);
    else this.dropped++;
  }
}

// Query parameters whose values must never reach a report
const SENSITIVE_PARAM = /token|secret|passw|auth|session|credential|jwt|signature|api[_-]?key|\bkey\b/i;

// Keep the URL useful for diagnosis, but drop user info and the #fragment, and
// redact sensitive query values. Non-http(s) URLs (about:blank, chrome-error://...)
// are returned as they are: they carry the "page never loaded" signal.
function safeUrl(raw: string): string {
  let u: URL;
  try {
    u = new URL(raw);
  } catch {
    return raw.slice(0, MAX_TEXT);
  }
  if (u.protocol === 'data:') return 'data:[omitted]';
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return raw.slice(0, MAX_TEXT);
  u.username = '';
  u.password = '';
  u.hash = '';
  for (const name of [...u.searchParams.keys()]) {
    if (SENSITIVE_PARAM.test(name)) u.searchParams.set(name, 'REDACTED');
  }
  return u.toString().slice(0, MAX_TEXT);
}

export const test = base.extend<{ evidence: void }>({
  evidence: [
    async ({ page }, use, testInfo) => {
      const consoleLogs = new Capped<ConsoleEntry>();
      const network = new Capped<NetworkEntry>();

      page.on('console', (msg) => {
        const type = msg.type();
        if (type === 'error' || type === 'warning') {
          consoleLogs.push({ type, text: msg.text().slice(0, MAX_TEXT) });
        }
      });
      page.on('pageerror', (err) =>
        consoleLogs.push({ type: 'pageerror', text: err.message.slice(0, MAX_TEXT) }),
      );
      page.on('response', (res) => {
        if (res.status() >= 400) {
          network.push({
            kind: 'http_error', status: res.status(),
            method: res.request().method(), url: safeUrl(res.url()), failure: null,
          });
        }
      });
      page.on('requestfailed', (req) =>
        network.push({
          kind: 'request_failed', status: null, method: req.method(),
          url: safeUrl(req.url()), failure: req.failure()?.errorText ?? 'unknown',
        }),
      );

      await use();

      // Attach evidence on failure only
      if (testInfo.status === testInfo.expectedStatus) return;

      // Never let evidence collection hide the original test failure
      try {
        // Attachment shape stays a plain array on purpose: it is the contract with P3
        await testInfo.attach('console.json', {
          body: JSON.stringify(consoleLogs.items, null, 2),
          contentType: 'application/json',
        });
        await testInfo.attach('network.json', {
          body: JSON.stringify(network.items, null, 2),
          contentType: 'application/json',
        });
        await testInfo.attach('final-url.txt', {
          body: safeUrl(page.url()), contentType: 'text/plain',
        });
        if (consoleLogs.dropped || network.dropped) {
          console.warn(`evidence truncated: console=${consoleLogs.dropped}, network=${network.dropped} dropped`);
        }
      } catch (err) {
        console.error('evidence attach failed:', err);
      }
    },
    { auto: true },
  ],
});

export { expect };