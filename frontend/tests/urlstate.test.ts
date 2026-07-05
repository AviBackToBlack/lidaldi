import { describe, expect, it } from "vitest";
import { DEFAULT_FILTERS } from "../src/lib/logic/filters";
import {
  decodeState,
  DEFAULT_URL_STATE,
  encodeState,
  readUrlState,
  writeUrlState,
  type AppUrlState,
} from "../src/lib/urlstate";

function state(patch: Partial<AppUrlState> = {}, filters = {}): AppUrlState {
  return {
    ...DEFAULT_URL_STATE,
    filters: { ...DEFAULT_FILTERS, ...filters },
    ...patch,
  };
}

describe("encodeState", () => {
  it("default state encodes to empty string (canonical /)", () => {
    expect(encodeState(state())).toBe("");
  });
  it("only non-default fields appear", () => {
    const qs = encodeState(
      state({ page: 3 }, { store: "aldi", search: "drill", sort: "price-asc" })
    );
    const p = new URLSearchParams(qs);
    expect(p.get("store")).toBe("aldi");
    expect(p.get("q")).toBe("drill");
    expect(p.get("sort")).toBe("price-asc");
    expect(p.get("page")).toBe("3");
    expect(p.has("cat")).toBe(false);
    expect(p.has("avail")).toBe(false);
  });
});

describe("decodeState", () => {
  it("round-trips", () => {
    const s = state(
      { page: 2, view: "alerts", alert: "abc123" },
      {
        store: "lidl",
        availability: "inStore",
        category: "DIY",
        priceFrom: "5",
        priceTo: "30",
        sort: "price-desc",
        search: "tent",
      }
    );
    expect(decodeState(encodeState(s))).toEqual(s);
  });
  it("empty search yields defaults", () => {
    expect(decodeState("")).toEqual(state());
  });
  it("rejects invalid enum/page values", () => {
    const s = decodeState("?store=tesco&sort=name&page=-2&view=nope");
    expect(s.filters.store).toBe("both");
    expect(s.filters.sort).toBe("");
    expect(s.page).toBe(1);
    expect(s.view).toBe("");
  });
  it("sanitizes price params", () => {
    const s = decodeState("?from=abc12.5x&to=<script>9");
    expect(s.filters.priceFrom).toBe("12.5");
    expect(s.filters.priceTo).toBe("9");
  });
  it("reserves ?view=alerts&alert=<id> for T6 deep links", () => {
    const s = decodeState("?view=alerts&alert=deadbeef");
    expect(s.view).toBe("alerts");
    expect(s.alert).toBe("deadbeef");
  });
});

describe("history integration (jsdom)", () => {
  it("writeUrlState push/replace + readUrlState restore", () => {
    history.replaceState(null, "", "/");
    const s = state({ page: 2 }, { store: "aldi", search: "saw" });
    writeUrlState(s, "push");
    expect(window.location.search).toBe(encodeState(s));
    expect(readUrlState()).toEqual(s);

    const s2 = state({ page: 2 }, { store: "aldi", search: "sawdust" });
    writeUrlState(s2, "replace");
    expect(readUrlState()).toEqual(s2);
  });
  it("writing the identical URL is a no-op", () => {
    history.replaceState(null, "", "/?store=aldi");
    const before = history.length;
    writeUrlState(state({}, { store: "aldi" }), "push");
    expect(history.length).toBe(before);
  });
});
