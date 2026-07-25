import type { Offer } from "../types";

export type StoreFilter = "both" | "aldi" | "lidl";
export type SortOrder = "" | "price-asc" | "price-desc";

/** "new" | "all" | "inStore" | a concrete "dd-mm-yyyy" future date */
export type Availability = string;

export interface FilterState {
  store: StoreFilter;
  availability: Availability;
  category: string;
  priceFrom: string;
  priceTo: string;
  sort: SortOrder;
  search: string;
}

export const DEFAULT_FILTERS: FilterState = {
  store: "both",
  availability: "all",
  category: "",
  priceFrom: "",
  priceTo: "",
  sort: "",
  search: "",
};

export const WHILE_STOCKS_LAST = "01-01-0000";
export const UNKNOWN_DATE = "01-01-9999";

export function parseAvailabilityDate(ds: string): Date | null {
  const parts = ds.split("-");
  if (parts.length !== 3) return null;
  const [dd, mm, yyyy] = parts;
  const d = new Date(Number(yyyy), Number(mm) - 1, Number(dd));
  return Number.isNaN(d.getTime()) ? null : d;
}

function startOfDay(d: Date): Date {
  const out = new Date(d);
  out.setHours(0, 0, 0, 0);
  return out;
}

/** Newness per the target design: first_seen (server-side) vs lastVisit. */
export function isNew(offer: Offer, lastVisit: number): boolean {
  return lastVisit > 0 && offer.first_seen > lastVisit;
}

export function priceOf(offer: Offer): number {
  if (offer.price === "N/A") return Number.POSITIVE_INFINITY;
  const p = Number.parseFloat(offer.price);
  return Number.isNaN(p) ? Number.POSITIVE_INFINITY : p;
}

function matchesAvailability(
  offer: Offer,
  availability: Availability,
  today: Date
): boolean {
  if (availability === "all") return true;
  const ds = offer.store_availability_date;
  if (availability === "inStore") {
    if (ds === WHILE_STOCKS_LAST) return true;
    if (!ds || ds === UNKNOWN_DATE) return false;
    const d = parseAvailabilityDate(ds);
    return d !== null && startOfDay(d) <= startOfDay(today);
  }
  // Concrete "From dd.mm" date filter.
  if (!ds || ds === WHILE_STOCKS_LAST || ds === UNKNOWN_DATE) return false;
  const filterDate = parseAvailabilityDate(availability);
  const itemDate = parseAvailabilityDate(ds);
  return filterDate !== null && itemDate !== null && itemDate >= filterDate;
}

/**
 * N/A / unparsable prices always pass the price filter (Q2 default: keep
 * them in, badge as "price unknown" later).
 */
function matchesPrice(offer: Offer, from: string, to: string): boolean {
  const p = priceOf(offer);
  if (p === Number.POSITIVE_INFINITY) return true;
  if (from) {
    const pf = Number.parseFloat(from);
    if (!Number.isNaN(pf) && p < pf) return false;
  }
  if (to) {
    const pt = Number.parseFloat(to);
    if (!Number.isNaN(pt) && p > pt) return false;
  }
  return true;
}

export interface ApplyFiltersOptions {
  lastVisit: number;
  today?: Date;
  ignoreCategory?: boolean;
}

/**
 * Pure port of the legacy applyFilters (website/js/lidaldi.js), with the
 * signed-off semantic changes: newness = first_seen > lastVisit; store
 * (ALDI/LIDL/Both) is a first-class filter.
 */
export function applyFilters(
  data: readonly Offer[],
  filters: FilterState,
  opts: ApplyFiltersOptions
): Offer[] {
  const today = opts.today ?? new Date();
  const search = filters.search.trim().toLowerCase();

  let filtered = data.filter((it) => {
    if (filters.store === "aldi" && it.store !== "ALDI") return false;
    if (filters.store === "lidl" && it.store !== "LIDL") return false;
    if (filters.availability === "new") {
      if (!isNew(it, opts.lastVisit)) return false;
    } else if (!matchesAvailability(it, filters.availability, today)) {
      return false;
    }
    if (!matchesPrice(it, filters.priceFrom, filters.priceTo)) return false;
    if (search) {
      const t = `${it.store} ${it.title} ${it.description}`.toLowerCase();
      if (!t.includes(search)) return false;
    }
    if (!opts.ignoreCategory && filters.category) {
      if (it.category !== filters.category) return false;
    }
    return true;
  });

  filtered = sortOffers(filtered, filters.sort);
  return filtered;
}

/**
 * Sort a filtered list. Unpriced items go last in both price directions.
 * "" keeps the incoming order (newest-first is applied once at load time).
 */
export function sortOffers(data: Offer[], sort: SortOrder): Offer[] {
  if (sort !== "price-asc" && sort !== "price-desc") return data;
  const out = [...data];
  out.sort((a, b) => {
    const pa = priceOf(a);
    const pb = priceOf(b);
    if (pa === Number.POSITIVE_INFINITY && pb === Number.POSITIVE_INFINITY) {
      return 0;
    }
    if (pa === Number.POSITIVE_INFINITY) return 1;
    if (pb === Number.POSITIVE_INFINITY) return -1;
    return sort === "price-asc" ? pa - pb : pb - pa;
  });
  return out;
}

/** Default dataset order: newest first by first_seen, then scraped_at. */
export function sortNewestFirst(data: readonly Offer[]): Offer[] {
  return [...data].sort(
    (a, b) => b.first_seen - a.first_seen || b.scraped_at - a.scraped_at
  );
}

/** Categories available under the current non-category filters, sorted. */
export function availableCategories(
  data: readonly Offer[],
  filters: FilterState,
  opts: ApplyFiltersOptions
): string[] {
  const filtered = applyFilters(data, filters, { ...opts, ignoreCategory: true });
  const set = new Set<string>();
  for (const it of filtered) {
    if (it.category) set.add(it.category);
  }
  return [...set].sort();
}

/**
 * Whether the "New from last visit" filter should be offered at all
 * (legacy updateNewButtonState, ported to first_seen semantics).
 */
export function hasNewOffers(data: readonly Offer[], lastVisit: number): boolean {
  return data.some((it) => isNew(it, lastVisit));
}

/** Distinct future "From dd.mm" availability dates, soonest first. */
export function futureAvailabilityDates(
  data: readonly Offer[],
  today: Date = new Date()
): string[] {
  const t = startOfDay(today);
  const set = new Set<string>();
  for (const it of data) {
    const ds = it.store_availability_date;
    if (!ds || ds === WHILE_STOCKS_LAST || ds === UNKNOWN_DATE) continue;
    const d = parseAvailabilityDate(ds);
    if (d !== null && d > t) set.add(ds);
  }
  return [...set].sort((a, b) => {
    const da = parseAvailabilityDate(a);
    const db = parseAvailabilityDate(b);
    return (da?.getTime() ?? 0) - (db?.getTime() ?? 0);
  });
}

export function formatAvailability(ds: string): string {
  if (!ds || ds === UNKNOWN_DATE) return "Unknown date";
  if (ds === WHILE_STOCKS_LAST) return "While Stock Lasts";
  const [dd, mm] = ds.split("-");
  return `From ${dd}.${mm}`;
}
