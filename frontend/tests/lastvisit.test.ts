import { beforeEach, describe, expect, it } from "vitest";
import {
  adoptServerLastVisit,
  browserLastVisitStorage,
  initLastVisit,
  type LastVisitStorage,
} from "../src/lib/logic/lastvisit";

function memoryStorage(persistent = 0, sessionBoot: number | null = null): LastVisitStorage & {
  persistent: number;
  sessionBoot: number | null;
} {
  return {
    persistent,
    sessionBoot,
    getPersistent() {
      return this.persistent;
    },
    setPersistent(ts: number) {
      this.persistent = ts;
    },
    getSessionBoot() {
      return this.sessionBoot;
    },
    setSessionBoot(ts: number) {
      this.sessionBoot = ts;
    },
  };
}

describe("initLastVisit — once-per-session advance (Q1)", () => {
  it("first load of a session snapshots and advances", () => {
    const s = memoryStorage(100);
    const boot = initLastVisit(s, 500);
    expect(boot).toEqual({ lastVisit: 100, advanced: true });
    expect(s.persistent).toBe(500);
    expect(s.sessionBoot).toBe(100);
  });
  it("reload within the same session does not advance again", () => {
    const s = memoryStorage(100);
    initLastVisit(s, 500);
    const boot2 = initLastVisit(s, 900);
    expect(boot2).toEqual({ lastVisit: 100, advanced: false });
    expect(s.persistent).toBe(500);
  });
  it("a new session advances from the previous session's value", () => {
    const s = memoryStorage(100);
    initLastVisit(s, 500);
    s.sessionBoot = null; // new browser session
    const boot = initLastVisit(s, 900);
    expect(boot).toEqual({ lastVisit: 500, advanced: true });
    expect(s.persistent).toBe(900);
  });
  it("first-ever visit boots with lastVisit 0", () => {
    const s = memoryStorage(0);
    expect(initLastVisit(s, 500).lastVisit).toBe(0);
    expect(s.persistent).toBe(500);
  });
});

describe("adoptServerLastVisit — N1 guard", () => {
  it("never adopts a server value newer than the boot value", () => {
    expect(adoptServerLastVisit(100, 500)).toBe(100);
  });
  it("adopts older/equal server values (cross-device sync)", () => {
    expect(adoptServerLastVisit(100, 50)).toBe(50);
    expect(adoptServerLastVisit(100, 100)).toBe(100);
  });
  it("first-visit client (boot 0) adopts the server value", () => {
    expect(adoptServerLastVisit(0, 300)).toBe(300);
  });
  it("ignores invalid/non-positive server values", () => {
    expect(adoptServerLastVisit(100, 0)).toBe(100);
    expect(adoptServerLastVisit(100, -5)).toBe(100);
    expect(adoptServerLastVisit(100, "junk")).toBe(100);
    expect(adoptServerLastVisit(100, null)).toBe(100);
    expect(adoptServerLastVisit(100, NaN)).toBe(100);
  });
  it("kills the same-load POST(now)->GET->adopt self-race", () => {
    // Boot reads 100; client POSTs now=1000; server replies lastVisit=1000.
    const boot = 100;
    expect(adoptServerLastVisit(boot, 1000)).toBe(boot);
  });
});

describe("browserLastVisitStorage (jsdom)", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    // snyk:ignore:Sensitive Cookie in HTTPS Session Without 'Secure' Attribute  // false positive: jsdom is not a secure context; Secure would break the test
    document.cookie = "lastVisit=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  });
  it("persists via localStorage and session snapshot via sessionStorage", () => {
    const s = browserLastVisitStorage();
    expect(s.getPersistent()).toBe(0);
    expect(s.getSessionBoot()).toBeNull();
    s.setPersistent(123);
    s.setSessionBoot(45);
    expect(s.getPersistent()).toBe(123);
    expect(s.getSessionBoot()).toBe(45);
  });
  it("falls back to the legacy lastVisit cookie", () => {
    // snyk:ignore:Sensitive Cookie in HTTPS Session Without 'Secure' Attribute  // false positive: jsdom is not a secure context; Secure would break the test
    document.cookie = "lastVisit=777; path=/";
    expect(browserLastVisitStorage().getPersistent()).toBe(777);
  });
});
