import { describe, expect, it } from "vitest";
import {
  applyFilters,
  availableCategories,
  DEFAULT_FILTERS,
  formatAvailability,
  futureAvailabilityDates,
  hasNewOffers,
  isNew,
  sortNewestFirst,
  sortOffers,
} from "../src/lib/logic/filters";
import { makeOffer } from "./helpers";

const TODAY = new Date(2026, 6, 5); // 05-07-2026

function f(patch: Partial<typeof DEFAULT_FILTERS> = {}) {
  return { ...DEFAULT_FILTERS, ...patch };
}

describe("store filter", () => {
  const data = [
    makeOffer({ id: "a", store: "ALDI" }),
    makeOffer({ id: "l", store: "LIDL", url: "https://www.lidl.ie/p/x" }),
  ];
  it("both keeps everything", () => {
    expect(applyFilters(data, f(), { lastVisit: 0 })).toHaveLength(2);
  });
  it("aldi/lidl narrow to one store", () => {
    expect(applyFilters(data, f({ store: "aldi" }), { lastVisit: 0 }).map((o) => o.id)).toEqual(["a"]);
    expect(applyFilters(data, f({ store: "lidl" }), { lastVisit: 0 }).map((o) => o.id)).toEqual(["l"]);
  });
});

describe("newness = first_seen > lastVisit", () => {
  const data = [
    makeOffer({ id: "old", first_seen: 100, scraped_at: 999 }),
    makeOffer({ id: "new", first_seen: 200, scraped_at: 50 }),
  ];
  it("uses first_seen, not scraped_at", () => {
    const out = applyFilters(data, f({ availability: "new" }), { lastVisit: 150 });
    expect(out.map((o) => o.id)).toEqual(["new"]);
  });
  it("nothing is new without a lastVisit (first visit)", () => {
    expect(applyFilters(data, f({ availability: "new" }), { lastVisit: 0 })).toEqual([]);
    expect(isNew(data[1]!, 0)).toBe(false);
  });
  it("hasNewOffers mirrors the same rule", () => {
    expect(hasNewOffers(data, 150)).toBe(true);
    expect(hasNewOffers(data, 300)).toBe(false);
    expect(hasNewOffers(data, 0)).toBe(false);
  });
});

describe("availability", () => {
  const data = [
    makeOffer({ id: "wsl", store_availability_date: "01-01-0000" }),
    makeOffer({ id: "unknown", store_availability_date: "01-01-9999" }),
    makeOffer({ id: "past", store_availability_date: "01-07-2026" }),
    makeOffer({ id: "future", store_availability_date: "09-07-2026" }),
  ];
  it("inStore = while-stocks-last + dates <= today", () => {
    const out = applyFilters(data, f({ availability: "inStore" }), { lastVisit: 0, today: TODAY });
    expect(out.map((o) => o.id).sort()).toEqual(["past", "wsl"]);
  });
  it("concrete date filter keeps items from that date on, excluding sentinels", () => {
    const out = applyFilters(data, f({ availability: "09-07-2026" }), { lastVisit: 0, today: TODAY });
    expect(out.map((o) => o.id)).toEqual(["future"]);
  });
  it("futureAvailabilityDates returns distinct future dates sorted", () => {
    expect(futureAvailabilityDates(data, TODAY)).toEqual(["09-07-2026"]);
  });
  it("formatAvailability sentinels", () => {
    expect(formatAvailability("01-01-0000")).toBe("While Stock Lasts");
    expect(formatAvailability("01-01-9999")).toBe("Unknown date");
    expect(formatAvailability("09-07-2026")).toBe("From 09.07");
    expect(formatAvailability("")).toBe("Unknown date");
  });
});

describe("price filter", () => {
  const data = [
    makeOffer({ id: "cheap", price: "5.00" }),
    makeOffer({ id: "mid", price: "20.00" }),
    makeOffer({ id: "dear", price: "50.00" }),
    makeOffer({ id: "na", price: "N/A" }),
    makeOffer({ id: "junk", price: "call us" }),
  ];
  it("respects from/to bounds", () => {
    const out = applyFilters(data, f({ priceFrom: "10", priceTo: "30" }), { lastVisit: 0 });
    expect(out.map((o) => o.id).sort()).toEqual(["junk", "mid", "na"]);
  });
  it("N/A and unparsable prices always pass (Q2 default)", () => {
    const out = applyFilters(data, f({ priceFrom: "100" }), { lastVisit: 0 });
    expect(out.map((o) => o.id).sort()).toEqual(["junk", "na"]);
  });
});

describe("search and category", () => {
  const data = [
    makeOffer({ id: "1", title: "Cordless Drill", description: "18V", category: "DIY" }),
    makeOffer({ id: "2", title: "Air Fryer", description: "4 litre", store: "LIDL", category: "Kitchen" }),
  ];
  it("search matches store+title+description, case-insensitive", () => {
    expect(applyFilters(data, f({ search: "drill" }), { lastVisit: 0 }).map((o) => o.id)).toEqual(["1"]);
    expect(applyFilters(data, f({ search: "LIDL" }), { lastVisit: 0 }).map((o) => o.id)).toEqual(["2"]);
    expect(applyFilters(data, f({ search: "LITRE" }), { lastVisit: 0 }).map((o) => o.id)).toEqual(["2"]);
  });
  it("category filter, and ignoreCategory for the category dropdown", () => {
    expect(applyFilters(data, f({ category: "DIY" }), { lastVisit: 0 }).map((o) => o.id)).toEqual(["1"]);
    expect(availableCategories(data, f({ category: "DIY" }), { lastVisit: 0 })).toEqual(["DIY", "Kitchen"]);
  });
});

describe("sorting", () => {
  const data = [
    makeOffer({ id: "na", price: "N/A" }),
    makeOffer({ id: "b", price: "20" }),
    makeOffer({ id: "a", price: "10" }),
  ];
  it("price-asc puts unpriced last", () => {
    expect(sortOffers(data, "price-asc").map((o) => o.id)).toEqual(["a", "b", "na"]);
  });
  it("price-desc puts unpriced last too", () => {
    expect(sortOffers(data, "price-desc").map((o) => o.id)).toEqual(["b", "a", "na"]);
  });
  it("default order is newest first by first_seen", () => {
    const d = [
      makeOffer({ id: "x", first_seen: 1 }),
      makeOffer({ id: "y", first_seen: 3 }),
      makeOffer({ id: "z", first_seen: 2 }),
    ];
    expect(sortNewestFirst(d).map((o) => o.id)).toEqual(["y", "z", "x"]);
  });
});
