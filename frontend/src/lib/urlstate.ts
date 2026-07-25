// Bidirectional History-API <-> app-state bridge (architecture doc §7.1).
//
// Encoding: query params, defaults omitted so the canonical default URL
// stays "/". `?view=alerts&alert=<id>` is reserved for the alerts view
// (T6 / push deep links, Bug #4).

import {
  DEFAULT_FILTERS,
  type FilterState,
  type SortOrder,
  type StoreFilter,
} from "./logic/filters";

export type View = "" | "alerts";

export interface AppUrlState {
  filters: FilterState;
  page: number;
  view: View;
  /** alert id for ?view=alerts&alert=<id> deep links (rendered by T6) */
  alert: string;
}

export const DEFAULT_URL_STATE: AppUrlState = {
  filters: { ...DEFAULT_FILTERS },
  page: 1,
  view: "",
  alert: "",
};

const STORES: readonly StoreFilter[] = ["both", "aldi", "lidl"];
const SORTS: readonly SortOrder[] = ["", "price-asc", "price-desc"];

export function encodeState(state: AppUrlState): string {
  const p = new URLSearchParams();
  const f = state.filters;
  if (f.store !== DEFAULT_FILTERS.store) p.set("store", f.store);
  if (f.availability !== DEFAULT_FILTERS.availability) {
    p.set("avail", f.availability);
  }
  if (f.category) p.set("cat", f.category);
  if (f.priceFrom) p.set("from", f.priceFrom);
  if (f.priceTo) p.set("to", f.priceTo);
  if (f.sort) p.set("sort", f.sort);
  if (f.search) p.set("q", f.search);
  if (state.page > 1) p.set("page", String(state.page));
  if (state.view) p.set("view", state.view);
  if (state.alert) p.set("alert", state.alert);
  const qs = p.toString();
  return qs ? `?${qs}` : "";
}

export function decodeState(search: string): AppUrlState {
  const p = new URLSearchParams(search);
  const store = p.get("store") ?? "";
  const sort = p.get("sort") ?? "";
  const pageRaw = Number.parseInt(p.get("page") ?? "1", 10);
  return {
    filters: {
      store: (STORES as readonly string[]).includes(store)
        ? (store as StoreFilter)
        : DEFAULT_FILTERS.store,
      availability: p.get("avail") ?? DEFAULT_FILTERS.availability,
      category: p.get("cat") ?? "",
      priceFrom: sanitizePrice(p.get("from") ?? ""),
      priceTo: sanitizePrice(p.get("to") ?? ""),
      sort: (SORTS as readonly string[]).includes(sort)
        ? (sort as SortOrder)
        : DEFAULT_FILTERS.sort,
      search: p.get("q") ?? "",
    },
    page: Number.isFinite(pageRaw) && pageRaw > 0 ? pageRaw : 1,
    view: p.get("view") === "alerts" ? "alerts" : "",
    alert: p.get("alert") ?? "",
  };
}

function sanitizePrice(v: string): string {
  return v.replace(/[^\d.]/g, "");
}

/** Read the current URL state (deep-link restore on load / popstate). */
export function readUrlState(): AppUrlState {
  return decodeState(window.location.search);
}

/**
 * Write state to the URL. `push` for meaningful state changes (Back/Forward
 * navigates them), `replace` for keystroke-level noise.
 */
export function writeUrlState(state: AppUrlState, mode: "push" | "replace"): void {
  const url = `${window.location.pathname}${encodeState(state)}`;
  const current = `${window.location.pathname}${window.location.search}`;
  if (url === current) return;
  if (mode === "push") {
    history.pushState(null, "", url);
  } else {
    history.replaceState(null, "", url);
  }
}

/** Subscribe to Back/Forward; returns an unsubscribe function. */
export function onUrlChange(handler: (state: AppUrlState) => void): () => void {
  const listener = () => handler(readUrlState());
  window.addEventListener("popstate", listener);
  return () => window.removeEventListener("popstate", listener);
}
