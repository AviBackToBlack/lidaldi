import { defineConfig, devices } from '@playwright/test';

// Three-engine matrix (Chromium/Firefox/WebKit) + visual snapshots.
// Specs run against local static fixtures only — no live network.
export default defineConfig({
  testDir: '.',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? 'github' : 'list',
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.02 },
  },
  snapshotPathTemplate: '{testDir}/__snapshots__/{testFilePath}/{arg}-{projectName}{ext}',
  // Built frontend for the T7 PWA specs (service worker + manifest need a
  // real HTTP origin; other specs keep using file:// fixtures).
  webServer: {
    command:
      'cd ../../frontend && npm ci --no-audit --no-fund && npm run build && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    timeout: 180_000,
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] }, testIgnore: 'pwa-push.spec.ts' },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] }, testIgnore: 'pwa-push.spec.ts' },
    { name: 'webkit', use: { ...devices['Desktop Safari'] }, testIgnore: 'pwa-push.spec.ts' },
    {
      // Push E2E needs notification display: only Chromium's new headless
      // (channel 'chromium') supports granting the notifications permission
      // headlessly — see pwa-push.spec.ts.
      name: 'chromium-push',
      use: { ...devices['Desktop Chrome'], channel: 'chromium' },
      testMatch: 'pwa-push.spec.ts',
    },
  ],
});
