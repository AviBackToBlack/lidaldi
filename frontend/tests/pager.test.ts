import { describe, expect, it } from "vitest";
import { pageWindow } from "../src/lib/logic/pager";

describe("pageWindow (N9 windowed pager)", () => {
  it("returns [1] for zero/one pages", () => {
    expect(pageWindow(1, 0)).toEqual([1]);
    expect(pageWindow(1, 1)).toEqual([1]);
  });

  it("shows every page when the range is small", () => {
    expect(pageWindow(2, 4)).toEqual([1, 2, 3, 4]);
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

  it("is bounded regardless of the page count (N9)", () => {
    for (const total of [50, 500, 5000]) {
      for (const current of [1, 2, Math.floor(total / 2), total]) {
        expect(pageWindow(current, total).length).toBeLessThanOrEqual(7);
      }
    }
  });

  it("bridges a one-page gap instead of an ellipsis", () => {
    expect(pageWindow(3, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(pageWindow(4, 6)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("anchors first and last pages at the edges", () => {
    expect(pageWindow(1, 9)).toEqual([1, 2, "ellipsis-right", 9]);
    expect(pageWindow(9, 9)).toEqual([1, "ellipsis-left", 8, 9]);
  });
});
