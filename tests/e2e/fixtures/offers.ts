import type { Page } from '@playwright/test';

// Deterministic offer fixtures for the T6 UI specs, matching the frozen
// offers.json schema (T2). Routed over the built app's /offers.json so
// specs control paging/filtering exactly.

export interface FixtureOffer {
  store: 'ALDI' | 'LIDL';
  id: string;
  url: string;
  category: string;
  title: string;
  scraped_at: number;
  description: string;
  store_availability_date: string;
  price: string;
  image_urls: string[];
  images: { path: string }[];
  first_seen: number;
}

export function makeOffers(count: number): FixtureOffer[] {
  const offers: FixtureOffer[] = [];
  for (let i = 0; i < count; i++) {
    const aldi = i % 2 === 0;
    offers.push({
      store: aldi ? 'ALDI' : 'LIDL',
      id: aldi ? String(100000000000 + i) : `/p/fixture-${i}/p${100000000 + i}`,
      url: aldi
        ? `https://www.aldi.ie/product/fixture-${i}`
        : `https://www.lidl.ie/p/fixture-${i}/p${100000000 + i}`,
      category: i % 3 === 0 ? 'DIY' : 'Kitchen',
      title: `Fixture Offer ${String(i).padStart(3, '0')}`,
      scraped_at: 1751500000,
      description: `Description for fixture offer ${i}.`,
      store_availability_date: '01-01-0000',
      price: i % 7 === 6 ? 'N/A' : `${(5 + i).toFixed(2)}`,
      image_urls: [],
      images: [],
      first_seen: 1751000000 + i,
    });
  }
  return offers;
}

export async function routeOffers(
  page: Page,
  offers: FixtureOffer[]
): Promise<void> {
  // WebKit 26 (Playwright 1.62) wedges the page — every subsequent protocol
  // call times out — when a service worker registers while page.route()
  // interception is active. The AlertsModal registers /sw.js on open, which
  // hung all four modal specs on webkit only. These SPA specs don't exercise
  // the worker; pwa.spec.ts / pwa-push.spec.ts do, and they never mock routes.
  // Blast radius: this applies to *every* routeOffers() caller (a11y,
  // alerts-deeplink, keyboard-paging, visual), and registerServiceWorker()
  // swallows the rejection with a console warning — so an offline/caching
  // assertion added to one of those specs would silently test a no-SW app.
  await page.route('**/sw.js', (route) => route.abort());
  await page.route('**/offers.json', (route) =>
    route.fulfill({ json: offers })
  );
}
