import { test, expect, type Page } from '@playwright/test';

// T7 push E2E (mocked push event). Runs only on the 'chromium-push' project:
// notification display needs Chromium's new headless mode (channel
// 'chromium') — the default headless shell silently denies the notifications
// permission, and headless Firefox/WebKit cannot display notifications.
//
// The SW exposes a message seam ("lidaldi:simulate-push") that runs the
// exact push-handler path; real push events cannot be injected portably.

const BASE = 'http://127.0.0.1:4173';

test.use({ permissions: ['notifications'] });

interface ShownNotification {
  title: string;
  body: string;
  data: { url?: string } | null;
}

function readNotifications(page: Page): Promise<ShownNotification[]> {
  return page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready;
    const ns = await reg.getNotifications();
    return ns.map((n) => ({
      title: n.title,
      body: n.body,
      data: n.data as { url?: string } | null,
    }));
  });
}

async function simulatePush(
  page: Page,
  payload: string | null
): Promise<ShownNotification[]> {
  await page.goto(BASE + '/');
  await page.evaluate(async (p) => {
    const reg = await navigator.serviceWorker.ready;
    for (const n of await reg.getNotifications()) n.close();
    reg.active!.postMessage({ type: 'lidaldi:simulate-push', payload: p });
  }, payload);
  await expect.poll(() => readNotifications(page)).toHaveLength(1);
  return readNotifications(page);
}

test('shows a notification with the T3 payload and alerts deep-link', async ({ page }) => {
  const [n] = await simulatePush(
    page,
    JSON.stringify({
      title: 'LidAldi Alert',
      body: "2 new matches for 'drill'",
      url: '/?view=alerts&alert=ab12cd34',
      icon: '/img/lidaldi.png',
    })
  );
  expect(n!.title).toBe('LidAldi Alert');
  expect(n!.body).toBe("2 new matches for 'drill'");
  // notificationclick opens/focuses this URL (data.url) — asserted here
  // since a real notification click cannot be synthesized in Playwright.
  expect(n!.data?.url).toBe('/?view=alerts&alert=ab12cd34');
});

test('shows a fallback notification on a corrupt payload (N6)', async ({ page }) => {
  const [n] = await simulatePush(page, 'this is not { json');
  expect(n!.title).toBe('LidAldi Alert');
  expect(n!.body).toBe('You have new alert matches.');
  expect(n!.data?.url).toBe('/?view=alerts');
});
