/**
 * Responsive page size (Bug #1 fix): a pure function of the viewport
 * width — no DOM measurement, no ResizeObserver. It mirrors the CSS grid
 * rule (auto-fill / minmax) arithmetically and fixes the number of rows
 * per breakpoint, so layout and paging can never disagree.
 *
 * Must stay in sync with the .products-grid CSS (App.svelte) and the
 * mobile breakpoint (720px).
 */

export const MOBILE_BREAKPOINT = 720;

interface GridSpec {
  /** horizontal page padding, both sides combined (px) */
  pagePadding: number;
  /** minmax() column minimum (px) */
  minColumn: number;
  /** grid gap (px) */
  gap: number;
  /** fixed rows per page at this breakpoint */
  rows: number;
}

const DESKTOP: GridSpec = { pagePadding: 60, minColumn: 224, gap: 18, rows: 3 };
const MOBILE: GridSpec = { pagePadding: 32, minColumn: 158, gap: 12, rows: 4 };

export function gridColumns(viewportWidth: number): number {
  const spec = viewportWidth <= MOBILE_BREAKPOINT ? MOBILE : DESKTOP;
  const content = Math.max(0, viewportWidth - spec.pagePadding);
  return Math.max(1, Math.floor((content + spec.gap) / (spec.minColumn + spec.gap)));
}

export function computePageSize(viewportWidth: number): number {
  const spec = viewportWidth <= MOBILE_BREAKPOINT ? MOBILE : DESKTOP;
  return gridColumns(viewportWidth) * spec.rows;
}
