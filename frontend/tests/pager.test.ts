import { describe, expect, it } from "vitest";
import {
  pageWindow,
  PAGER_SLOTS_DESKTOP,
  PAGER_SLOTS_MOBILE,
} from "../src/lib/logic/pager";

describe("pageWindow (N9 windowed pager)", () => {
  it("returns [1] for zero/one pages", () => {
    expect(pageWindow(1, 0)).toEqual([1]);
    expect(pageWindow(1, 1)).toEqual([1]);
  });

  it("shows every page when the range fits the slot count", () => {
    expect(pageWindow(2, 4)).toEqual([1, 2, 3, 4]);
    expect(pageWindow(4, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(pageWindow(3, 5, PAGER_SLOTS_MOBILE)).toEqual([1, 2, 3, 4, 5]);
  });

  it("windows the middle of a long range with both ellipses", () => {
    expect(pageWindow(10, 20)).toEqual([
      1,
      "ellipsis-left",
      9,
      10,
      11,
      "ellipsis-right",
      20,
    ]);
  });

  it("anchors first and last pages at the edges", () => {
    expect(pageWindow(1, 9)).toEqual([1, 2, 3, 4, 5, "ellipsis-right", 9]);
    expect(pageWindow(9, 9)).toEqual([1, "ellipsis-left", 5, 6, 7, 8, 9]);
  });

  // The layout fix: a variable-length sequence made the pager's width jump
  // between pages and wrap onto a second line at its widest.
  it("emits exactly `slots` items on every page of a long range", () => {
    for (const slots of [PAGER_SLOTS_MOBILE, PAGER_SLOTS_DESKTOP]) {
      for (const total of [slots + 1, 43, 500, 5000]) {
        for (let current = 1; current <= total; current++) {
          expect(pageWindow(current, total, slots)).toHaveLength(slots);
        }
      }
    }
  });

  it("always includes the current page, first and last, in order", () => {
    for (const slots of [PAGER_SLOTS_MOBILE, PAGER_SLOTS_DESKTOP]) {
      for (const total of [slots + 1, 43, 500]) {
        for (let current = 1; current <= total; current++) {
          const items = pageWindow(current, total, slots);
          const nums = items.filter((i): i is number => typeof i === "number");
          expect(items[0]).toBe(1);
          expect(items[items.length - 1]).toBe(total);
          expect(nums).toContain(current);
          expect(new Set(nums).size).toBe(nums.length);
          expect([...nums].sort((a, b) => a - b)).toEqual(nums);
        }
      }
    }
  });

  it("bridges a one-page gap instead of an ellipsis", () => {
    // Slot count is constant, so showing the page costs no extra width.
    expect(pageWindow(3, 9, PAGER_SLOTS_MOBILE)).toEqual([
      1,
      2,
      3,
      "ellipsis-right",
      9,
    ]);
    expect(pageWindow(7, 9, PAGER_SLOTS_MOBILE)).toEqual([
      1,
      "ellipsis-left",
      7,
      8,
      9,
    ]);
  });

  it("clamps an out-of-range current page", () => {
    expect(pageWindow(0, 43)).toEqual(pageWindow(1, 43));
    expect(pageWindow(99, 43)).toEqual(pageWindow(43, 43));
  });

  it("normalises even or too-small slot counts to an odd count >= 5", () => {
    expect(pageWindow(10, 20, 6)).toEqual(pageWindow(10, 20, 5));
    expect(pageWindow(10, 20, 2)).toEqual(pageWindow(10, 20, 5));
  });
});
