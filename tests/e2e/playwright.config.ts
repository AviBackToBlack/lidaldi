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
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
});
