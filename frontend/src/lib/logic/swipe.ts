/**
 * Touch-swipe paging: decides whether a completed single-finger gesture
 * was a deliberate horizontal swipe. Pure so it can be unit-tested; the
 * touch listeners live in App.svelte.
 */

export interface TouchPoint {
  x: number;
  y: number;
  /** event timeStamp (ms) */
  t: number;
}

/** Minimum horizontal travel (px) to count as a swipe. */
export const SWIPE_MIN_DISTANCE = 50;
/** Horizontal travel must exceed vertical travel by this factor, so
 *  slightly diagonal vertical scrolls never page. */
export const SWIPE_AXIS_RATIO = 1.5;
/** Gestures lasting this long or longer are treated as reading/panning,
 *  not a flick (exclusive bound: a swipe must take < this). */
export const SWIPE_MAX_DURATION_MS = 700;
/** Gestures starting this close to a screen edge belong to the OS
 *  (iOS Safari / Android gesture-nav back & forward). */
export const SWIPE_EDGE_GUARD = 24;

/**
 * Page step for a gesture: +1 = next page (finger moved left),
 * -1 = previous page (finger moved right), 0 = not a paging swipe.
 */
export function swipeStep(
  start: TouchPoint,
  end: TouchPoint,
  viewportWidth: number
): -1 | 0 | 1 {
  if (start.x < SWIPE_EDGE_GUARD || start.x > viewportWidth - SWIPE_EDGE_GUARD) {
    return 0;
  }
  if (end.t - start.t >= SWIPE_MAX_DURATION_MS) return 0;
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  if (Math.abs(dx) < SWIPE_MIN_DISTANCE) return 0;
  if (Math.abs(dx) <= SWIPE_AXIS_RATIO * Math.abs(dy)) return 0;
  return dx < 0 ? 1 : -1;
}
