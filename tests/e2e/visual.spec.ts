import { test, expect } from '@playwright/test';
import { makeOffers, routeOffers } from './fixtures/offers';

// Visual snapshots on all 3 engines (baselined in the pinned container).
// WebKit layout parity is asserted by the per-project webkit baselines.

const BASE = 'http://127.0.0.1:4173';

test.beforeEach(async ({ page }) => {
  await routeOffers(page, makeOffers(24));
  // Freeze time-dependent rendering (dates in the header/meta line).
  await page.clock.setFixedTime(new Date('2026-07-06T12:00:00Z'));
  await page.goto(BASE + '/');
  await expect(page.locator('.product-card').first()).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
});

test('grid page layout', async ({ page }) => {
  await expect(page).toHaveScreenshot('grid-page.png', {
    fullPage: true,
    animations: 'disabled',
  });
});

test('filter bar with active store + availability filters', async ({ page }) => {
  await page.getByRole('button', { name: 'LIDL', exact: true }).click();
  await page.getByRole('button', { name: 'Available now' }).click();
  await expect(page.locator('.filters-row')).toHaveScreenshot(
    'filter-bar-active.png',
    { animations: 'disabled' }
  );
});

test('alerts modal', async ({ page }) => {
  await page.getByRole('button', { name: 'Alerts', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveScreenshot('alerts-modal.png', {
    animations: 'disabled',
  });
});

test('dark theme grid', async ({ page }) => {
  await page.getByRole('button', { name: 'Toggle dark theme' }).click();
  await expect(page).toHaveScreenshot('grid-page-dark.png', {
    fullPage: true,
    animations: 'disabled',
  });
});
