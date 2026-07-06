import { test, expect } from '@playwright/test';

// T7 PWA checks against the built frontend (vite preview — see webServer in
// playwright.config.ts). Installability requirements are asserted
// programmatically: valid manifest with maskable+any icons, and a
// root-scoped service worker that controls the page.

const BASE = 'http://127.0.0.1:4173';

test.describe('installability', () => {
  test('manifest is valid and its icons resolve', async ({ request, page }) => {
    await page.goto(BASE + '/');
    const link = page.locator('link[rel="manifest"]');
    await expect(link).toHaveAttribute('href', '/manifest.json');

    const res = await request.get(BASE + '/manifest.json');
    expect(res.ok()).toBe(true);
    const manifest = await res.json();
    expect(manifest.name).toBeTruthy();
    expect(manifest.short_name).toBeTruthy();
    expect(manifest.start_url).toBe('/');
    expect(manifest.display).toBe('standalone');
    expect(manifest.theme_color).toBeTruthy();
    expect(manifest.background_color).toBeTruthy();

    const purposes = new Set(manifest.icons.map((i: { purpose: string }) => i.purpose));
    expect(purposes.has('any')).toBe(true);
    expect(purposes.has('maskable')).toBe(true);
    const sizes = new Set(manifest.icons.map((i: { sizes: string }) => i.sizes));
    expect(sizes.has('192x192')).toBe(true);
    expect(sizes.has('512x512')).toBe(true);
    for (const icon of manifest.icons) {
      const r = await request.get(BASE + icon.src);
      expect(r.ok(), `icon ${icon.src}`).toBe(true);
      expect(r.headers()['content-type']).toContain('image/png');
    }
  });

  test('service worker registers, is root-scoped and controls the page', async ({ page }) => {
    await page.goto(BASE + '/');
    const scope = await page.evaluate(async () => {
      const reg = await navigator.serviceWorker.ready;
      return reg.scope;
    });
    expect(new URL(scope).pathname).toBe('/');
    // Reload so the activated worker controls the page.
    await page.reload();
    const controlled = await page.evaluate(
      () => navigator.serviceWorker.controller !== null
    );
    expect(controlled).toBe(true);
  });
});
