// Offer item schema frozen by T2 (PR #3): process_offers.py writes
// offers.json with exactly these fields per item.

export type Store = "ALDI" | "LIDL";

export interface OfferImage {
  path: string;
  [key: string]: unknown;
}

export interface Offer {
  store: Store;
  id: string;
  url: string;
  category: string;
  title: string;
  scraped_at: number;
  description: string;
  /** "dd-mm-yyyy"; sentinels: "01-01-0000" = While Stocks Last, "01-01-9999" = unknown */
  store_availability_date: string;
  /** decimal string or "N/A" */
  price: string;
  image_urls: string[];
  images: OfferImage[];
  /** unix seconds the product id was first seen server-side */
  first_seen: number;
}

export interface Meta {
  /** unix seconds of the last successful data run */
  lastUpdated: number;
  vapidPublicKey: string;
}

export function isSafeHttpUrl(u: unknown): u is string {
  return typeof u === "string" && /^https?:\/\//i.test(u);
}

function asString(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function asNumber(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

/**
 * Validate and normalize a raw offers.json payload. Items without a safe
 * http(s) URL are dropped (defence in depth, same policy as the legacy UI).
 * Throws if the payload is not an array.
 */
export function parseOffers(raw: unknown): Offer[] {
  if (!Array.isArray(raw)) {
    throw new Error("offers.json: expected an array");
  }
  const offers: Offer[] = [];
  for (const item of raw) {
    if (typeof item !== "object" || item === null) continue;
    const it = item as Record<string, unknown>;
    if (!isSafeHttpUrl(it.url)) continue;
    const store = it.store === "ALDI" || it.store === "LIDL" ? it.store : null;
    if (store === null) continue;
    offers.push({
      store,
      id: asString(it.id),
      url: it.url,
      category: asString(it.category),
      title: asString(it.title),
      scraped_at: asNumber(it.scraped_at),
      description: asString(it.description),
      store_availability_date: asString(it.store_availability_date),
      price: asString(it.price, "N/A"),
      image_urls: Array.isArray(it.image_urls)
        ? it.image_urls.filter((u): u is string => typeof u === "string")
        : [],
      images: Array.isArray(it.images)
        ? it.images.filter(
            (im): im is OfferImage =>
              typeof im === "object" &&
              im !== null &&
              typeof (im as Record<string, unknown>).path === "string"
          )
        : [],
      first_seen: asNumber(it.first_seen),
    });
  }
  return offers;
}

export function parseMeta(raw: unknown): Meta {
  if (typeof raw !== "object" || raw === null) {
    throw new Error("meta.json: expected an object");
  }
  const m = raw as Record<string, unknown>;
  return {
    lastUpdated: asNumber(m.lastUpdated),
    vapidPublicKey: asString(m.vapidPublicKey),
  };
}
