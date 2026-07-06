import { test, expect } from '@playwright/test';
import { makeOffers, routeOffers } from './fixtures/offers';

// Bug #4 spec: ?view=alerts&alert=<id> (the push deep-link target)
// restores the AlertsView, lists matched offers from GET alertMatches and
// highlights the targeted alert.

const BASE = 'http://127.0.0.1:4173';
const CODE = 'TESTCDAB';

const ALERTS = [
  { id: 'alrt0001', keyword: 'fixture', matchType: 'anyWord', createdAt: 1 },
  { id: 'alrt0002', keyword: 'nothing', matchType: 'exact', createdAt: 2 },
];

test.beforeEach(async ({ page }) => {
  const offers = makeOffers(10);
  await routeOffers(page, offers);
  await page.addInitScript(
    ([code, alerts]) => {
      localStorage.setItem('lidaldi_sync_code', code as string);
      localStorage.setItem('lidaldi_alerts', JSON.stringify(alerts));
    },
    [CODE, ALERTS] as const
  );
  await page.route(`**/api/sync/${CODE}`, (route) =>
    route.fulfill({
      json: {
        lastVisit: 1751000000,
        alerts: ALERTS,
        tombstones: [],
        alertMatches: {
          alrt0001: [
            { id: offers[1]!.id, at: 1751600001 },
            { id: offers[3]!.id, at: 1751600002 },
          ],
        },
      },
    })
  );
});

test('deep link restores AlertsView with matches and highlight', async ({ page }) => {
  await page.goto(BASE + '/?view=alerts&alert=alrt0001');

  await expect(page.getByRole('heading', { name: 'Alert matches' })).toBeVisible();

  const target = page.locator('[data-alert-id="alrt0001"]');
  await expect(target).toHaveClass(/highlight/);
  await expect(target.locator('.product-card')).toHaveCount(2);
  await expect(target).toContainText('Fixture Offer 001');
  await expect(target).toContainText('Fixture Offer 003');
  await expect(target).toContainText('2 matches');

  const other = page.locator('[data-alert-id="alrt0002"]');
  await expect(other).not.toHaveClass(/highlight/);
  await expect(other).toContainText('No current offers match this alert.');
});

test('back link returns to the grid and Back restores the view (history)', async ({ page }) => {
  await page.goto(BASE + '/?view=alerts&alert=alrt0001');
  await page.getByRole('button', { name: 'All offers' }).click();
  await expect(page.locator('.product-card').first()).toBeVisible();
  await expect(page).toHaveURL(BASE + '/');
  await page.goBack();
  await expect(page.getByRole('heading', { name: 'Alert matches' })).toBeVisible();
});

test('alerts view without a sync code explains itself', async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem('lidaldi_sync_code'));
  await page.goto(BASE + '/?view=alerts&alert=alrt0001');
  await expect(page.locator('.alerts-view')).toContainText('No sync code');
});
