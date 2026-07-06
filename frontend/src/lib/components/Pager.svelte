<script lang="ts">
  import { pageWindow } from "../logic/pager";

  let {
    page,
    totalPages,
    onGoTo,
  }: {
    page: number;
    totalPages: number;
    onGoTo: (page: number) => void;
  } = $props();

  const items = $derived(pageWindow(page, totalPages));
</script>

<!--
  Roving tabindex (Bug #3): the whole pager is a single tab stop — only
  the active page button is tabbable. Left/Right paging is global (App
  keydown handler) and works whether or not the pager has focus.
-->
<nav class="pagination" aria-label="Pagination">
  <button tabindex="-1" disabled={page <= 1} onclick={() => onGoTo(page - 1)}
    ><span aria-hidden="true">‹</span> Prev</button
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
    tabindex="-1"
    disabled={page >= totalPages}
    onclick={() => onGoTo(page + 1)}>Next <span aria-hidden="true">›</span></button
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
  .pagination button:hover {
    background: var(--surface-hover);
    border-color: var(--border-hover);
  }
  .pagination .page-number-btn {
    width: 38px;
    height: 38px;
    padding: 0;
  }
  .pagination .active-page {
    background: var(--ink);
    border-color: var(--ink);
    color: var(--bg);
    font-weight: var(--weight-bold);
  }
  .pagination .ellipsis {
    color: var(--text-2);
    padding: 0 4px;
  }
  .pagination [disabled] {
    color: var(--text-faint);
    cursor: default;
  }
</style>
