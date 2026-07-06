import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { makeOffers, routeOffers } from './fixtures/offers';

// T8 automated accessibility tier: axe-core (WCAG 2.1 A/AA rulesets) must
// report zero serious/critical violations on every main view, in both the
// light and dark themes. Runs on all three engines as part of `make test`.

const BASE = 'http://127.0.0.1:4173';
const THEMES = ['light', 'dark'] as const;
type Theme = (typeof THEMES)[number];

const CODE = 'TESTCDAB';
const ALERTS = [
  { id: 'alrt0001', keyword: 'fixture', matchType: 'anyWord', createdAt: 1 },
];

async function checkA11y(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const blocking = results.violations.filter(
    (v) => v.impact === 'serious' || v.impact === 'critical'
  );
  expect(
    blocking.map((v) => ({
      id: v.id,
      impact: v.impact,
      help: v.help,
      nodes: v.nodes.map((n) => n.target),
    }))
  ).toEqual([]);
}

// Axe samples computed colors, so CSS transitions/animations still in flight
// after a theme toggle, click, or popover open (e.g. the popover's `pop`
// keyframe starts at opacity 0) make color-contrast checks nondeterministic.
// Freeze all motion before any axe run to keep the tier deterministic.
async function freezeTransitions(page: Page): Promise<void> {
  await page.addStyleTag({
    content:
      '*, *::before, *::after { transition: none !important; animation: none !important; }',
  });
}

async function applyTheme(page: Page, theme: Theme): Promise<void> {
  await freezeTransitions(page);
  if (theme === 'dark') {
    await page.getByRole('button', { name: 'Toggle dark theme' }).click();
  }
}

for (const theme of THEMES) {
  test.describe(`${theme} theme`, () => {
    test.beforeEach(async ({ page }) => {
      await routeOffers(page, makeOffers(60));
    });

    test('grid view', async ({ page }) => {
      await page.goto(BASE + '/');
      await expect(page.locator('.product-card').first()).toBeVisible({ timeout: 15_000 });
      await applyTheme(page, theme);
      await checkA11y(page);
    });

    test('grid with active filters', async ({ page }) => {
      await page.goto(BASE + '/');
      await expect(page.locator('.product-card').first()).toBeVisible({ timeout: 15_000 });
      await applyTheme(page, theme);
      await page.getByRole('button', { name: 'ALDI', exact: true }).click();
      await page.getByRole('button', { name: 'Available now' }).click();
      await expect(page.locator('.product-card').first()).toBeVisible({ timeout: 15_000 });
      await checkA11y(page);
    });

    test('card popover open', async ({ page }) => {
      await page.goto(BASE + '/');
      await expect(page.locator('.product-card').first()).toBeVisible({ timeout: 15_000 });
      await applyTheme(page, theme);
      await page.locator('.card-link').first().focus();
      await expect(page.locator('.desc-popover:popover-open')).toHaveCount(1, {
        timeout: 5_000,
      });
      await checkA11y(page);
    });

    test('alerts modal', async ({ page }) => {
      await page.goto(BASE + '/');
      await expect(page.locator('.product-card').first()).toBeVisible({ timeout: 15_000 });
      await applyTheme(page, theme);
      await page.getByRole('button', { name: 'Alerts', exact: true }).click();
      await expect(page.getByRole('dialog')).toBeVisible();
      await checkA11y(page);
    });

    test('alerts view (deep link)', async ({ page }) => {
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
              alrt0001: [{ id: offers[1]!.id, at: 1751600001 }],
            },
          },
        })
      );
      await page.goto(BASE + '/?view=alerts&alert=alrt0001');
      await expect(
        page.getByRole('heading', { name: 'Alert matches' })
      ).toBeVisible();
      await applyTheme(page, theme);
      await checkA11y(page);
    });
  });
}
