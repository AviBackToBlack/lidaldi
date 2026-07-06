import { describe, expect, it } from "vitest";
import {
  FALLBACK_PAYLOAD,
  classifyRequest,
  notificationTargetUrl,
  parsePushPayload,
} from "../src/lib/sw/logic";

describe("parsePushPayload", () => {
  it("parses the frozen T3 payload contract verbatim", () => {
    const raw = JSON.stringify({
      title: "LidAldi Alert",
      body: "3 new matches for 'drill'",
      url: "/?view=alerts&alert=ab12cd34",
      icon: "/img/lidaldi.png",
    });
    expect(parsePushPayload(raw)).toEqual({
      title: "LidAldi Alert",
      body: "3 new matches for 'drill'",
      url: "/?view=alerts&alert=ab12cd34",
      icon: "/img/lidaldi.png",
    });
  });

  it("falls back on non-JSON payloads (N6)", () => {
    expect(parsePushPayload("not json {")).toEqual(FALLBACK_PAYLOAD);
  });

  it("falls back on empty/absent payloads (N6)", () => {
    expect(parsePushPayload(null)).toEqual(FALLBACK_PAYLOAD);
    expect(parsePushPayload("")).toEqual(FALLBACK_PAYLOAD);
  });

  it("falls back on non-object JSON", () => {
    expect(parsePushPayload("42")).toEqual(FALLBACK_PAYLOAD);
    expect(parsePushPayload('"hi"')).toEqual(FALLBACK_PAYLOAD);
    expect(parsePushPayload("null")).toEqual(FALLBACK_PAYLOAD);
  });

  it("fills missing fields from the fallback", () => {
    const p = parsePushPayload(JSON.stringify({ title: "T" }));
    expect(p.title).toBe("T");
    expect(p.body).toBe(FALLBACK_PAYLOAD.body);
    expect(p.url).toBe(FALLBACK_PAYLOAD.url);
    expect(p.icon).toBe(FALLBACK_PAYLOAD.icon);
  });

  it("rejects cross-origin url/icon values", () => {
    const p = parsePushPayload(
      JSON.stringify({
        url: "https://evil.example/x",
        icon: "//evil.example/i.png",
      })
    );
    expect(p.url).toBe(FALLBACK_PAYLOAD.url);
    expect(p.icon).toBe(FALLBACK_PAYLOAD.icon);
  });
});

describe("notificationTargetUrl", () => {
  it("returns the same-origin url from notification data", () => {
    expect(notificationTargetUrl({ url: "/?view=alerts&alert=x" })).toBe(
      "/?view=alerts&alert=x"
    );
  });

  it("falls back for missing or unsafe data", () => {
    expect(notificationTargetUrl(undefined)).toBe(FALLBACK_PAYLOAD.url);
    expect(notificationTargetUrl(null)).toBe(FALLBACK_PAYLOAD.url);
    expect(notificationTargetUrl({})).toBe(FALLBACK_PAYLOAD.url);
    expect(notificationTargetUrl({ url: "https://evil.example" })).toBe(
      FALLBACK_PAYLOAD.url
    );
  });
});

describe("classifyRequest", () => {
  it("treats navigations as network-first navigation", () => {
    expect(classifyRequest("/", "navigate")).toBe("navigation");
    expect(classifyRequest("/anything", "navigate")).toBe("navigation");
  });

  it("treats offers/meta data as network-first (no stale offers)", () => {
    expect(classifyRequest("/offers.json", "cors")).toBe("data");
    expect(classifyRequest("/meta.json", "no-cors")).toBe("data");
  });

  it("treats hashed assets, icons, images and manifest as cache-first", () => {
    expect(classifyRequest("/assets/index-Ab3dEf.js", "no-cors")).toBe("static");
    expect(classifyRequest("/icons/icon-192.png", "no-cors")).toBe("static");
    expect(classifyRequest("/img/product.jpg", "no-cors")).toBe("static");
    expect(classifyRequest("/manifest.json", "no-cors")).toBe("static");
  });

  it("passes everything else through (incl. sw.js and the sync API)", () => {
    expect(classifyRequest("/sw.js", "no-cors")).toBe("passthrough");
    expect(classifyRequest("/api/sync/abc123", "cors")).toBe("passthrough");
  });
});
