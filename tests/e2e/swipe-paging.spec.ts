import { test, expect, type Page } from '@playwright/test';
import { makeOffers, routeOffers } from './fixtures/offers';

// Touch-swipe paging on phones: swipe left = next page, right = previous.
// Thresholds are unit-tested in frontend/tests/swipe.test.ts; this covers
// the wiring (listeners, guards, page clamping, scroll-to-top).

const BASE = 'http://127.0.0.1:4173';
const VIEWPORT = { width: 390, height: 844 };

test.use({ hasTouch: true, viewport: VIEWPORT });

test.beforeEach(async ({ page }) => {
  await routeOffers(page, makeOffers(200));
  await page.goto(BASE + '/');
  await expect(page.locator('.product-card').first()).toBeVisible();
});

function pageIndicator(page: Page) {
  return page.locator('.grid-meta .page-ind');
}

// Dispatches touchstart + touchend on a card (so they bubble to the grid
// like a real finger) in one synchronous evaluate: the gesture's duration
// is then ~0ms regardless of CI load. Plain Events carrying touch lists
// rather than TouchEvent: WebKit (Linux) has no Touch constructor and
// desktop Firefox no TouchEvent, and the handlers only read
// touches/changedTouches/timeStamp.
async function swipe(
  page: Page,
  dx: number,
  dy = 0,
  startX = VIEWPORT.width / 2,
  card = page.locator('.product-card').first()
) {
  await card.evaluate(
    (card, { dx, dy, startX }) => {
      const y = Math.max(0, card.getBoundingClientRect().top) + 20;
      const fire = (type: string, touches: object[], changed: object[]) => {
        const ev = new Event(type, { bubbles: true, cancelable: true });
        Object.defineProperties(ev, {
          touches: { value: touches },
          changedTouches: { value: changed },
        });
        card.dispatchEvent(ev);
      };
      const s = { identifier: 1, clientX: startX, clientY: y };
      fire('touchstart', [s], [s]);
      fire('touchend', [], [{ identifier: 1, clientX: startX + dx, clientY: y + dy }]);
    },
    { dx, dy, startX }
  );
}

test('swiping left and right pages the grid', async ({ page }) => {
  await expect(pageIndicator(page)).toHaveText(/^page 1 of \d+$/);
  await swipe(page, -150);
  await expect(pageIndicator(page)).toHaveText(/^page 2 of/);
  await swipe(page, -150);
  await expect(pageIndicator(page)).toHaveText(/^page 3 of/);
  await swipe(page, 150);
  await expect(pageIndicator(page)).toHaveText(/^page 2 of/);
});

test('swiping right on the first page stays put', async ({ page }) => {
  await swipe(page, 150);
  await expect(pageIndicator(page)).toHaveText(/^page 1 of/);
});

test('vertical scroll gestures and short drags do not page', async ({ page }) => {
  await swipe(page, -60, -300);
  await swipe(page, -30);
  await expect(pageIndicator(page)).toHaveText(/^page 1 of/);
});

test('edge swipes are left to the OS back/forward gesture', async ({ page }) => {
  await swipe(page, 150, 0, 5);
  await swipe(page, -150, 0, VIEWPORT.width - 5);
  await expect(pageIndicator(page)).toHaveText(/^page 1 of/);
});

test('a swipe from mid-grid starts the new page at its top', async ({ page }) => {
  await page.locator('.pagination').scrollIntoViewIfNeeded();
  await expect(page.locator('.grid-meta')).not.toBeInViewport();
  const last = page.locator('.product-card').last();
  await last.scrollIntoViewIfNeeded();
  await swipe(page, -150, 0, VIEWPORT.width / 2, last);
  await expect(pageIndicator(page)).toHaveText(/^page 2 of/);
  await expect(page.locator('.grid-meta')).toBeInViewport();
});
