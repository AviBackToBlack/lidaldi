import { test, expect } from '@playwright/test';
import { makeOffers, routeOffers } from './fixtures/offers';

// Bug #3 spec: global Left/Right arrow paging must survive filter clicks
// (legacy bug: focus stuck on a clicked filter button swallowed arrows).

const BASE = 'http://127.0.0.1:4173';

test.beforeEach(async ({ page }) => {
  await routeOffers(page, makeOffers(60));
  await page.goto(BASE + '/');
  await expect(page.locator('.product-card').first()).toBeVisible();
});

function pageIndicator(page: import('@playwright/test').Page) {
  return page.locator('.grid-meta .page-ind');
}

test('arrow keys page the grid', async ({ page }) => {
  await expect(pageIndicator(page)).toHaveText(/^page 1 of \d+$/);
  await page.keyboard.press('ArrowRight');
  await expect(pageIndicator(page)).toHaveText(/^page 2 of/);
  await page.keyboard.press('ArrowRight');
  await expect(pageIndicator(page)).toHaveText(/^page 3 of/);
  await page.keyboard.press('ArrowLeft');
  await expect(pageIndicator(page)).toHaveText(/^page 2 of/);
});

test('arrow paging survives filter clicks (Bug #3)', async ({ page }) => {
  // Click several filter controls, then page with arrows — no re-focus
  // dance needed because controls blur after activation.
  await page.getByRole('button', { name: 'Available now' }).click();
  await page.getByRole('button', { name: 'ALDI', exact: true }).click();
  await page.keyboard.press('ArrowRight');
  await expect(pageIndicator(page)).toHaveText(/^page 2 of/);

  // Also after using the pager itself.
  await page.getByRole('button', { name: 'Next ›' }).click();
  await expect(pageIndicator(page)).toHaveText(/^page 3 of/);
  await page.keyboard.press('ArrowLeft');
  await expect(pageIndicator(page)).toHaveText(/^page 2 of/);
});

test('arrows are suppressed while a text caret is active', async ({ page }) => {
  await page.getByRole('searchbox', { name: 'Search products' }).click();
  await page.keyboard.type('fixture');
  await page.keyboard.press('ArrowLeft');
  await expect(pageIndicator(page)).toHaveText(/^page 1 of/);
});

test('pager is a single tab stop (roving tabindex)', async ({ page }) => {
  const tabbable = await page
    .locator('.pagination [tabindex="0"], .pagination button:not([tabindex])')
    .count();
  expect(tabbable).toBe(1);
  await expect(
    page.locator('.pagination [tabindex="0"]')
  ).toHaveAttribute('aria-current', 'page');
});

test('windowed pager stays bounded (N9)', async ({ page }) => {
  const buttons = page.locator('.pagination .page-number-btn');
  expect(await buttons.count()).toBeLessThanOrEqual(5);
  await expect(page.locator('.pagination .ellipsis')).toHaveCount(1);
});
