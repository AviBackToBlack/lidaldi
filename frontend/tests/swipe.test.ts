import { describe, expect, it } from "vitest";
import {
  swipeStep,
  SWIPE_AXIS_RATIO,
  SWIPE_EDGE_GUARD,
  SWIPE_MAX_DURATION_MS,
  SWIPE_MIN_DISTANCE,
  type TouchPoint,
} from "../src/lib/logic/swipe";

const W = 390; // phone viewport width
const start: TouchPoint = { x: 200, y: 400, t: 1000 };
const to = (dx: number, dy = 0, dt = 200): TouchPoint => ({
  x: start.x + dx,
  y: start.y + dy,
  t: start.t + dt,
});

describe("swipeStep (touch paging)", () => {
  it("finger moving left pages forward, right pages back", () => {
    expect(swipeStep(start, to(-120), W)).toBe(1);
    expect(swipeStep(start, to(120), W)).toBe(-1);
  });

  it("ignores short drags and taps", () => {
    expect(swipeStep(start, to(0), W)).toBe(0);
    expect(swipeStep(start, to(-(SWIPE_MIN_DISTANCE - 1)), W)).toBe(0);
    expect(swipeStep(start, to(-SWIPE_MIN_DISTANCE), W)).toBe(1);
  });

  it("ignores vertical and diagonal scrolls", () => {
    expect(swipeStep(start, to(-60, -300), W)).toBe(0);
    // exactly on the ratio boundary is still treated as a scroll
    expect(swipeStep(start, to(-90, 90 / SWIPE_AXIS_RATIO), W)).toBe(0);
    expect(swipeStep(start, to(-90, 20), W)).toBe(1);
  });

  it("ignores slow drags", () => {
    expect(swipeStep(start, to(-150, 0, SWIPE_MAX_DURATION_MS + 1), W)).toBe(0);
    expect(swipeStep(start, to(-150, 0, SWIPE_MAX_DURATION_MS), W)).toBe(1);
  });

  it("leaves edge swipes to the OS back/forward gesture", () => {
    const left: TouchPoint = { ...start, x: SWIPE_EDGE_GUARD - 1 };
    const right: TouchPoint = { ...start, x: W - SWIPE_EDGE_GUARD + 1 };
    expect(swipeStep(left, { ...left, x: left.x + 150, t: left.t + 100 }, W)).toBe(0);
    expect(swipeStep(right, { ...right, x: right.x - 150, t: right.t + 100 }, W)).toBe(0);
    const inside: TouchPoint = { ...start, x: SWIPE_EDGE_GUARD };
    expect(swipeStep(inside, { ...inside, x: inside.x + 150, t: inside.t + 100 }, W)).toBe(-1);
  });
});
