import { describe, expect, it } from "vitest";
import { isSafeHttpUrl, parseMeta, parseOffers } from "../src/lib/types";
import offersFixture from "../public/offers.json";
import metaFixture from "../public/meta.json";

describe("parseOffers", () => {
  it("parses the checked-in fixture (T2 schema)", () => {
    const offers = parseOffers(offersFixture);
    expect(offers).toHaveLength(3);
    const first = offers[0]!;
    expect(first.store).toBe("ALDI");
    expect(first.id).toBe("000000000001");
    expect(typeof first.first_seen).toBe("number");
    expect(first.images[0]?.path).toBe("full/drill.jpg");
  });
  it("throws on non-array payloads", () => {
    expect(() => parseOffers({})).toThrow();
    expect(() => parseOffers(null)).toThrow();
  });
  it("drops items with unsafe or missing URLs", () => {
    const offers = parseOffers([
      { store: "ALDI", url: "javascript:alert(1)", title: "evil" },
      { store: "ALDI", title: "no url" },
      { store: "ALDI", url: "https://www.aldi.ie/p/ok", title: "ok" },
    ]);
    expect(offers.map((o) => o.title)).toEqual(["ok"]);
  });
  it("drops items with unknown stores and normalizes missing fields", () => {
    const offers = parseOffers([
      { store: "TESCO", url: "https://x.example/p" },
      { store: "LIDL", url: "https://www.lidl.ie/p/y" },
    ]);
    expect(offers).toHaveLength(1);
    const o = offers[0]!;
    expect(o.price).toBe("N/A");
    expect(o.image_urls).toEqual([]);
    expect(o.first_seen).toBe(0);
  });
});

describe("parseMeta", () => {
  it("parses the checked-in fixture", () => {
    const meta = parseMeta(metaFixture);
    expect(meta.lastUpdated).toBeGreaterThan(0);
    expect(meta.vapidPublicKey.length).toBeGreaterThan(0);
  });
  it("throws on non-objects", () => {
    expect(() => parseMeta(null)).toThrow();
    expect(() => parseMeta([])).not.toThrow(); // arrays are objects; fields default
  });
});

describe("isSafeHttpUrl", () => {
  it("accepts only http(s)", () => {
    expect(isSafeHttpUrl("https://a.example")).toBe(true);
    expect(isSafeHttpUrl("http://a.example")).toBe(true);
    expect(isSafeHttpUrl("javascript:alert(1)")).toBe(false);
    expect(isSafeHttpUrl("data:text/html,x")).toBe(false);
    expect(isSafeHttpUrl(42)).toBe(false);
  });
});
