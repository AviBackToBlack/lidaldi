import { describe, expect, it } from "vitest";
import { paginate } from "../src/lib/logic/paging";

const data = Array.from({ length: 25 }, (_, i) => i + 1);

describe("paginate", () => {
  it("slices the requested page", () => {
    const r = paginate(data, 2, 10);
    expect(r.items).toEqual([11, 12, 13, 14, 15, 16, 17, 18, 19, 20]);
    expect(r.totalPages).toBe(3);
  });
  it("clamps out-of-range pages", () => {
    expect(paginate(data, 99, 10).page).toBe(3);
    expect(paginate(data, 0, 10).page).toBe(1);
    expect(paginate(data, -5, 10).page).toBe(1);
  });
  it("empty data yields one empty page", () => {
    const r = paginate([], 3, 10);
    expect(r.items).toEqual([]);
    expect(r.page).toBe(1);
    expect(r.totalPages).toBe(1);
  });
  it("pageSize <= 0 puts everything on one page", () => {
    const r = paginate(data, 5, 0);
    expect(r.items).toHaveLength(25);
    expect(r.totalPages).toBe(1);
  });
});
