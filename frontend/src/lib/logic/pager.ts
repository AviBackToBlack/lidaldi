/**
 * Windowed pager model (N9): first/last always visible, a window around
 * the current page, ellipses for the gaps. Pure — the Pager component
 * renders exactly this sequence.
 */

export type PagerItem = number | "ellipsis-left" | "ellipsis-right";

export function pageWindow(
  current: number,
  total: number,
  radius = 1
): PagerItem[] {
  if (total <= 1) return [1];
  const pages = new Set<number>([1, total]);
  for (let p = current - radius; p <= current + radius; p++) {
    if (p >= 1 && p <= total) pages.add(p);
  }
  // Avoid a silly one-page gap: replace it with the page itself.
  const sorted = [...pages].sort((a, b) => a - b);
  const out: PagerItem[] = [];
  for (let i = 0; i < sorted.length; i++) {
    const p = sorted[i]!;
    if (i > 0) {
      const prev = sorted[i - 1]!;
      if (p - prev === 2) {
        out.push(prev + 1);
      } else if (p - prev > 2) {
        out.push(p < current ? "ellipsis-left" : "ellipsis-right");
      }
    }
    out.push(p);
  }
  return out;
}
