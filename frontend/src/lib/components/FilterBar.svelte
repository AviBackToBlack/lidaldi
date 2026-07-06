<script lang="ts">
  import {
    formatAvailability,
    type FilterState,
    type SortOrder,
    type StoreFilter,
  } from "../logic/filters";

  let {
    filters,
    categories,
    futureDates,
    newAvailable,
    onFilter,
    onSearch,
    onReset,
    onOpenAlerts,
  }: {
    filters: FilterState;
    categories: string[];
    futureDates: string[];
    newAvailable: boolean;
    onFilter: (patch: Partial<FilterState>) => void;
    onSearch: (value: string) => void;
    onReset: () => void;
    onOpenAlerts: () => void;
  } = $props();

  // Debounced search (N4 dies by construction: keystrokes update only this
  // local value; the store/grid update at most once per DEBOUNCE_MS).
  const DEBOUNCE_MS = 250;
  let searchValue = $state("");
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  $effect(() => {
    // External resets (Reset button, Back/Forward) update the box.
    searchValue = filters.search;
  });
  $effect(() => () => {
    // Drop a pending debounce on unmount so a stale onSearch can't fire
    // (and rewrite the URL) after the user navigated away.
    if (searchTimer !== null) clearTimeout(searchTimer);
  });

  function handleSearchInput(value: string): void {
    searchValue = value;
    if (searchTimer !== null) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchTimer = null;
      onSearch(searchValue);
    }, DEBOUNCE_MS);
  }

  // Bug #3: filter controls blur after activation so the global
  // Left/Right paging handler keeps working after any filter click.
  function act(e: Event, fn: () => void): void {
    fn();
    (e.currentTarget as HTMLElement | null)?.blur();
  }

  const STORES: [StoreFilter, string, string][] = [
    ["both", "Both", ""],
    ["aldi", "ALDI", "seg-aldi"],
    ["lidl", "LIDL", "seg-lidl"],
  ];

  function sanitizePriceInput(v: string): string {
    return v.replace(/[^\d.]/g, "");
  }
</script>

<div class="filters-row">
  <div class="segmented" role="group" aria-label="Store">
    {#each STORES as [key, label, cls] (key)}
      <button
        class={cls}
        aria-pressed={filters.store === key}
        onclick={(e) => act(e, () => onFilter({ store: key }))}>{label}</button
      >
    {/each}
  </div>
  <div class="divider"></div>
  <div class="availability-filters">
    <button
      class="chip"
      class:active={filters.availability === "all"}
      onclick={(e) => act(e, () => onFilter({ availability: "all" }))}>All</button
    >
    <button
      class="chip"
      class:active={filters.availability === "inStore"}
      onclick={(e) => act(e, () => onFilter({ availability: "inStore" }))}
      >Available now</button
    >
    <button
      class="chip"
      class:active={filters.availability === "new"}
      disabled={!newAvailable && filters.availability !== "new"}
      onclick={(e) => act(e, () => onFilter({ availability: "new" }))}
      >✦ New for you</button
    >
    {#each futureDates as ds (ds)}
      <button
        class="chip date"
        class:active={filters.availability === ds}
        onclick={(e) => act(e, () => onFilter({ availability: ds }))}
        >{formatAvailability(ds).replace(/^From /, "")}</button
      >
    {/each}
  </div>
  <div class="spacer"></div>
  <div class="select-wrapper">
    <select
      aria-label="Category"
      value={filters.category}
      onchange={(e) =>
        act(e, () => onFilter({ category: (e.currentTarget as HTMLSelectElement).value }))}
    >
      <option value="">All categories</option>
      {#each categories as c (c)}
        <option value={c}>{c}</option>
      {/each}
    </select>
  </div>
  <div class="price-range">
    <input
      class="price-input"
      type="text"
      inputmode="decimal"
      placeholder="€ min"
      aria-label="Price from"
      value={filters.priceFrom}
      oninput={(e) =>
        onFilter({ priceFrom: sanitizePriceInput(e.currentTarget.value) })}
    />–<input
      class="price-input"
      type="text"
      inputmode="decimal"
      placeholder="€ max"
      aria-label="Price to"
      value={filters.priceTo}
      oninput={(e) =>
        onFilter({ priceTo: sanitizePriceInput(e.currentTarget.value) })}
    />
  </div>
  <div class="select-wrapper">
    <select
      aria-label="Sort"
      value={filters.sort}
      onchange={(e) =>
        act(e, () =>
          onFilter({ sort: (e.currentTarget as HTMLSelectElement).value as SortOrder })
        )}
    >
      <option value="">Sort</option>
      <option value="price-asc">Price ↑</option>
      <option value="price-desc">Price ↓</option>
    </select>
  </div>
  <input
    class="search-input"
    type="search"
    placeholder="Search products…"
    aria-label="Search products"
    value={searchValue}
    oninput={(e) => handleSearchInput(e.currentTarget.value)}
  />
  <button class="chip" onclick={(e) => act(e, onReset)}>Reset</button>
  <button class="btn-dark" onclick={(e) => act(e, onOpenAlerts)}>🔔 Alerts</button>
</div>

<style>
  .filters-row {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 14px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    box-shadow: var(--shadow-card);
  }

  .segmented {
    display: inline-flex;
    gap: 3px;
    background: var(--surface-sunken);
    padding: 4px;
    border-radius: var(--radius-md);
  }
  .segmented button {
    border: none;
    background: transparent;
    color: var(--text-2);
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
    padding: 8px 17px;
    border-radius: 9px;
    transition: all var(--transition);
  }
  .segmented button[aria-pressed="true"] {
    font-weight: var(--weight-bold);
    background: var(--surface);
    color: var(--ink);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }
  .segmented button.seg-aldi[aria-pressed="true"] {
    background: var(--aldi-tint);
    color: var(--aldi);
  }
  .segmented button.seg-lidl[aria-pressed="true"] {
    background: var(--lidl-tint);
    color: var(--lidl-text);
  }

  .divider {
    width: 1px;
    height: 26px;
    background: var(--border);
  }
  .spacer {
    flex: 1;
  }
  .availability-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .price-range {
    display: flex;
    align-items: center;
    gap: 5px;
    color: var(--border-hover);
  }
  .filters-row input[type="text"],
  .filters-row input[type="search"] {
    font-family: var(--font-sans);
    font-size: var(--text-base);
    font-weight: var(--weight-medium);
    color: var(--text);
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius);
    padding: 9px 12px;
  }
  .filters-row input::placeholder {
    color: var(--text-faint);
  }
  .price-input {
    width: 78px;
  }
  .search-input {
    min-width: 180px;
  }

  @media (max-width: 720px) {
    .filters-row {
      padding: 10px;
    }
    .segmented {
      width: 100%;
    }
    .segmented button {
      flex: 1;
    }
    .search-input {
      min-width: 0;
      flex: 1;
    }
    .divider,
    .spacer {
      display: none;
    }
  }
</style>
