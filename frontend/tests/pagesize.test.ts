import { describe, expect, it } from "vitest";
import {
  computePageSize,
  gridColumns,
  MOBILE_BREAKPOINT,
} from "../src/lib/logic/pagesize";

describe("computePageSize (Bug #1: pure viewport arithmetic)", () => {
  it("matches the CSS auto-fill column count at common widths", () => {
    // desktop: content = width - 60; col >= 224; gap 18
    expect(gridColumns(1440)).toBe(5); // (1380+18)/(224+18) = 5.77
    expect(gridColumns(1024)).toBe(4); // (964+18)/(224+18) = 4.05
    expect(gridColumns(800)).toBe(3);
  });

  it("uses the mobile spec at/below the breakpoint", () => {
    expect(gridColumns(MOBILE_BREAKPOINT)).toBe(4); // (688+12)/(158+12)
    expect(gridColumns(390)).toBe(2); // iPhone-ish
  });

  it("multiplies columns by fixed rows per breakpoint", () => {
    expect(computePageSize(1440)).toBe(15); // 5 cols x 3 rows
    expect(computePageSize(390)).toBe(8); // 2 cols x 4 rows
  });

  it("never returns less than one column", () => {
    expect(gridColumns(0)).toBe(1);
    expect(computePageSize(100)).toBe(4);
  });
});
