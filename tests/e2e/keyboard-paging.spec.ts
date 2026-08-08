import { test, expect } from '@playwright/test';
import { makeOffers, routeOffers } from './fixtures/offers';

// Bug #3 spec: global Left/Right arrow paging must survive filter clicks
// (legacy bug: focus stuck on a clicked filter button swallowed arrows).

const BASE = 'http://127.0.0.1:4173';

test.beforeEach(async ({ page }) => {
  await routeOffers(page, makeOffers(200));
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
  await page.getByRole('button', { name: 'Next page' }).click();
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

test('windowed pager stays bounded and constant-width (N9)', async ({ page }) => {
  const slots = page.locator('.pagination .page-number-btn, .pagination .ellipsis');
  const pager = page.locator('.pagination');
  const count = await slots.count();
  expect(count).toBeLessThanOrEqual(7);
  await expect(page.locator('.pagination .ellipsis')).toHaveCount(1);

  // The slot count must not change as you page — a varying count made the
  // pager's width jump and wrap onto a second line at its widest.
  const firstBox = await pager.boundingBox();
  for (const target of [2, 3, 4, 5]) {
    await page.getByRole('button', { name: `Page ${target}` }).click();
    await expect(page.locator('.grid-meta .page-ind')).toHaveText(
      new RegExp(`^page ${target} of`)
    );
    expect(await slots.count()).toBe(count);
    const box = await pager.boundingBox();
    expect(box!.height).toBeCloseTo(firstBox!.height, 0);
  }
});

test('modified arrows never page (screen-reader shortcuts)', async ({ page }) => {
  await page.keyboard.press('Control+ArrowRight');
  await page.keyboard.press('Alt+ArrowRight');
  await page.keyboard.press('Shift+ArrowRight');
  await expect(pageIndicator(page)).toHaveText(/^page 1 of/);
});

test('card popover opens on focus and Escape dismisses it (WCAG 1.4.13)', async ({ page }) => {
  await page.locator('.card-link').first().focus();
  await expect(page.locator('.desc-popover:popover-open')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(page.locator('.desc-popover:popover-open')).toHaveCount(0);
});

test('alerts modal traps focus and restores it to the opener', async ({ page }) => {
  const opener = page.getByRole('button', { name: 'Alerts', exact: true });
  await opener.click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toBeFocused();

  // Tab through every focusable control: focus must stay inside the dialog.
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press('Tab');
    const inside = await page.evaluate(() => {
      const d = document.querySelector('[role="dialog"]');
      return d ? d.contains(document.activeElement) : false;
    });
    expect(inside).toBe(true);
  }

  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(opener).toBeFocused();
});
