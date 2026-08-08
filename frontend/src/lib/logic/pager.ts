/**
 * Windowed pager model (N9): first/last always visible, a window around
 * the current page, ellipses for the gaps. Pure — the Pager component
 * renders exactly this sequence.
 *
 * The sequence is **constant length** (`slots`) for every page of a range
 * longer than `slots`. A variable length made the pager's width jump as
 * you paged, and at its widest it wrapped onto a second line. Ellipsis
 * slots are rendered at the same width as page buttons, so a constant
 * length means a pixel-stable pager.
 */

export type PagerItem = number | "ellipsis-left" | "ellipsis-right";

/**
 * Slot counts per breakpoint; must be odd and >= 5.
 *
 * The count decides how many neighbours the current page gets, via
 * `radius = (slots - 5) / 2` in the middle case. So 5 slots means radius 0
 * — mid-range mobile renders `1 … cur … last` with no ±1 neighbours, a
 * deliberate trade-off because 7 slots cannot fit one line at 320px even
 * with the compacted mobile sizing. 7 is the minimum for ±1 neighbours.
 */
export const PAGER_SLOTS_DESKTOP = 7;
export const PAGER_SLOTS_MOBILE = 5;

function range(from: number, to: number): number[] {
  const out: number[] = [];
  for (let p = from; p <= to; p++) out.push(p);
  return out;
}

/**
 * A gap spanning a single page is rendered as that page rather than an
 * ellipsis — same slot either way, so it costs nothing and hides less.
 */
function gap(from: number, to: number, side: "left" | "right"): PagerItem {
  return from === to ? from : (`ellipsis-${side}` as PagerItem);
}

export function pageWindow(
  current: number,
  total: number,
  slots: number = PAGER_SLOTS_DESKTOP
): PagerItem[] {
  if (total <= 1) return [1];
  // Odd slot counts keep the current page centred in the middle case.
  const s = Math.max(5, slots % 2 === 0 ? slots - 1 : slots);
  const cur = Math.min(Math.max(current, 1), total);
  if (total <= s) return range(1, total);

  // Head: the first (s - 2) pages, then a gap, then the last page.
  if (cur <= s - 3) {
    return [...range(1, s - 2), gap(s - 1, total - 1, "right"), total];
  }
  // Tail: the first page, a gap, then the last (s - 2) pages.
  if (cur >= total - (s - 4)) {
    return [1, gap(2, total - (s - 2), "left"), ...range(total - (s - 3), total)];
  }
  // Middle: first, gap, window around current, gap, last.
  const radius = (s - 5) / 2;
  return [
    1,
    gap(2, cur - radius - 1, "left"),
    ...range(cur - radius, cur + radius),
    gap(cur + radius + 1, total - 1, "right"),
    total,
  ];
}
