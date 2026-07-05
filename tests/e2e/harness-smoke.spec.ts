import { test, expect } from '@playwright/test';
import * as path from 'path';

// Trivial spec against a static fixture page — proves the 3-engine matrix
// (chromium/firefox/webkit) and visual-snapshot support. No network.
const fixture = 'file://' + path.resolve(__dirname, 'fixtures', 'index.html');

test('fixture page renders the offer grid', async ({ page }) => {
  await page.goto(fixture);
  await expect(page.locator('#title')).toHaveText('LIDALDI harness fixture');
  await expect(page.locator('.card')).toHaveCount(3);
});

test('fixture page visual snapshot', async ({ page }) => {
  await page.goto(fixture);
  await expect(page.locator('#grid')).toHaveScreenshot('grid.png');
});
