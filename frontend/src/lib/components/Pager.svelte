<script lang="ts">
  import {
    pageWindow,
    PAGER_SLOTS_DESKTOP,
    PAGER_SLOTS_MOBILE,
  } from "../logic/pager";
  import { MOBILE_BREAKPOINT } from "../logic/pagesize";

  let {
    page,
    totalPages,
    onGoTo,
  }: {
    page: number;
    totalPages: number;
    onGoTo: (page: number) => void;
  } = $props();

  // Fewer slots on narrow viewports: even compacted, the desktop slot
  // count cannot fit one line on a phone. Mirrors the CSS breakpoint.
  const QUERY = `(max-width: ${MOBILE_BREAKPOINT}px)`;
  let narrow = $state(window.matchMedia?.(QUERY).matches ?? false);

  $effect(() => {
    const mq = window.matchMedia?.(QUERY);
    if (!mq) return;
    narrow = mq.matches;
    const onChange = (e: MediaQueryListEvent) => (narrow = e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  });

  const items = $derived(
    pageWindow(page, totalPages, narrow ? PAGER_SLOTS_MOBILE : PAGER_SLOTS_DESKTOP)
  );
</script>

<!--
  Roving tabindex (Bug #3): the whole pager is a single tab stop — only
  the active page button is tabbable. Left/Right paging is global (App
  keydown handler) and works whether or not the pager has focus.
-->
<nav class="pagination" aria-label="Pagination">
  <button
    class="step-btn"
    tabindex="-1"
    aria-label="Previous page"
    disabled={page <= 1}
    onclick={() => onGoTo(page - 1)}
    ><span aria-hidden="true">‹</span> <span class="step-label">Prev</span></button
  >
  {#each items as item (item)}
    {#if typeof item === "number"}
      <button
        class="page-number-btn"
        class:active-page={item === page}
        tabindex={item === page ? 0 : -1}
        aria-current={item === page ? "page" : undefined}
        disabled={totalPages === 1}
        aria-label={`Page ${item}`}
        onclick={() => onGoTo(item)}>{item}</button
      >
    {:else}
      <span class="ellipsis" aria-hidden="true">…</span>
    {/if}
  {/each}
  <button
    class="step-btn"
    tabindex="-1"
    aria-label="Next page"
    disabled={page >= totalPages}
    onclick={() => onGoTo(page + 1)}
    ><span class="step-label">Next</span> <span aria-hidden="true">›</span></button
  >
</nav>

<style>
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 28px;
  }
  .pagination button {
    border-radius: var(--radius);
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--text-2);
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
    padding: 9px 15px;
    transition: background var(--transition);
  }
  /* :not(.active-page) matters: this rule outranks .active-page on
     specificity, so without it hovering the current page repainted its
     background light while keeping the light text — an invisible label. */
  .pagination button:hover:not(.active-page) {
    background: var(--surface-hover);
    border-color: var(--border-hover);
  }
  .pagination .page-number-btn {
    width: 38px;
    height: 38px;
    padding: 0;
  }
  /* Explicit height, not line-box height: the webfont (Plus Jakarta Sans,
     loaded with display=swap) has different metrics from the system-ui
     fallback, so an auto-height Prev/Next measured 41px before the swap and
     36px after — the row jumped 3px mid-load and never matched the 38px
     number buttons either way. */
  .pagination .step-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 38px;
  }
  .pagination .active-page {
    background: var(--ink);
    border-color: var(--ink);
    color: var(--bg);
    font-weight: var(--weight-bold);
  }
  /* Same footprint as a page button: with a constant slot count (see
     logic/pager.ts) the pager is then pixel-stable across pages. */
  .pagination .ellipsis {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    padding: 0;
    color: var(--text-2);
  }
  .pagination [disabled] {
    color: var(--text-faint);
    cursor: default;
  }

  @media (max-width: 720px) {
    .pagination {
      gap: 5px;
      margin-top: 22px;
    }
    .pagination button {
      font-size: var(--text-sm);
      padding: 8px 11px;
    }
    .pagination .page-number-btn,
    .pagination .ellipsis {
      width: 34px;
      height: 34px;
    }
    .pagination .step-btn {
      height: 34px;
    }
  }

  /* Smallest phones: drop the Prev/Next words (the accessible names stay
     on the buttons) so the row still fits on one line. */
  @media (max-width: 400px) {
    .pagination .step-label {
      display: none;
    }
    .pagination .step-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 34px;
      height: 34px;
      padding: 0;
    }
  }
</style>
