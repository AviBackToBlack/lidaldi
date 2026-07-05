import type { Offer } from "../src/lib/types";

export function makeOffer(overrides: Partial<Offer> = {}): Offer {
  return {
    store: "ALDI",
    id: "id-1",
    url: "https://www.aldi.ie/product/x",
    category: "DIY",
    title: "Widget",
    scraped_at: 1000,
    description: "A widget.",
    store_availability_date: "01-01-0000",
    price: "9.99",
    image_urls: [],
    images: [],
    first_seen: 1000,
    ...overrides,
  };
}
