<script lang="ts">
  import { loadMeta, loadOffers } from "./lib/data";
  import type { Meta, Offer } from "./lib/types";
  import {
    applyFilters,
    availableCategories,
    formatAvailability,
    futureAvailabilityDates,
    hasNewOffers,
    isNew,
    sortNewestFirst,
  } from "./lib/logic/filters";
  import { paginate } from "./lib/logic/paging";
  import { filters } from "./lib/stores/filters.svelte";
  import { paging } from "./lib/stores/paging.svelte";
  import { sync } from "./lib/stores/sync.svelte";
  import { alerts } from "./lib/stores/alerts.svelte";
  import { syncFetch, syncPost } from "./lib/sync/client";
  import {
    onUrlChange,
    readUrlState,
    writeUrlState,
    type AppUrlState,
    type View,
  } from "./lib/urlstate";

  let offers = $state<Offer[]>([]);
  let meta = $state<Meta | null>(null);
  let loadError = $state("");
  let loading = $state(true);
  let view = $state<View>("");
  let alertId = $state("");

  // Deep-link restore before first render.
  applyUrlState(readUrlState());
  sync.init();
  alerts.init();

  function applyUrlState(s: AppUrlState): void {
    filters.set(s.filters);
    paging.goTo(s.page);
    view = s.view;
    alertId = s.alert;
  }

  function currentUrlState(): AppUrlState {
    return {
      filters: { ...filters.state },
      page: paging.page,
      view,
      alert: alertId,
    };
  }

  function syncUrl(mode: "push" | "replace"): void {
    writeUrlState(currentUrlState(), mode);
  }

  $effect(() => onUrlChange(applyUrlState));

  $effect(() => {
    void (async () => {
      try {
        const [o, m] = await Promise.all([loadOffers(), loadMeta()]);
        offers = sortNewestFirst(o);
        meta = m;
      } catch (e) {
        loadError = e instanceof Error ? e.message : String(e);
      } finally {
        loading = false;
      }
    })();

    // Sync boot: POST this visit, then GET — server lastVisit adoption is
    // guarded (never newer than the boot value; N1 fix).
    void (async () => {
      if (!sync.code) return;
      await syncPost(sync.code, sync.nowTimestamp, alerts.alerts, alerts.tombstones);
      const data = await syncFetch(sync.code);
      if (data) sync.adoptServer(data.lastVisit);
    })();
  });

  const newAvailable = $derived(hasNewOffers(offers, sync.lastVisit));
  const categories = $derived(
    availableCategories(offers, filters.state, { lastVisit: sync.lastVisit })
  );
  const futureDates = $derived(futureAvailabilityDates(offers));
  const filtered = $derived(
    applyFilters(offers, filters.state, { lastVisit: sync.lastVisit })
  );
  const pageResult = $derived(paginate(filtered, paging.page, paging.pageSize));

  function setFilter(patch: Partial<typeof filters.state>): void {
    filters.set(patch);
    paging.resetToFirst();
    syncUrl("push");
  }

  function setSearch(value: string): void {
    filters.set({ search: value });
    paging.resetToFirst();
    syncUrl("replace");
  }

  function goToPage(p: number): void {
    paging.goTo(p);
    syncUrl("push");
  }

  function fmtDate(ts: number): string {
    const d = new Date(ts * 1000);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    return `${dd}/${mm}/${d.getFullYear()}`;
  }
</script>

<header class="app-header">
  <h1>LIDALDI</h1>
  <p class="meta-line">
    {#if meta}Last updated: {fmtDate(meta.lastUpdated)}{/if}
    {#if sync.lastVisit}
      · Your last visit: {fmtDate(sync.lastVisit)}
    {/if}
  </p>
</header>

<div class="filter-bar">
  {#each [["both", "Both"], ["aldi", "ALDI"], ["lidl", "LIDL"]] as const as [key, label] (key)}
    <button
      class:active={filters.state.store === key}
      onclick={() => setFilter({ store: key })}>{label}</button
    >
  {/each}

  <button
    class:active={filters.state.availability === "new"}
    disabled={!newAvailable}
    onclick={() => setFilter({ availability: "new" })}>New from last visit</button
  >
  <button
    class:active={filters.state.availability === "all"}
    onclick={() => setFilter({ availability: "all" })}>All products</button
  >
  <button
    class:active={filters.state.availability === "inStore"}
    onclick={() => setFilter({ availability: "inStore" })}>Currently in store</button
  >
  {#each futureDates as ds (ds)}
    <button
      class:active={filters.state.availability === ds}
      onclick={() => setFilter({ availability: ds })}>{formatAvailability(ds)}</button
    >
  {/each}

  <select
    value={filters.state.category}
    onchange={(e) => setFilter({ category: e.currentTarget.value })}
  >
    <option value="">All categories</option>
    {#each categories as c (c)}
      <option value={c}>{c}</option>
    {/each}
  </select>

  <input
    type="text"
    inputmode="decimal"
    placeholder="€ from"
    size="6"
    value={filters.state.priceFrom}
    oninput={(e) =>
      setFilter({ priceFrom: e.currentTarget.value.replace(/[^\d.]/g, "") })}
  />
  <input
    type="text"
    inputmode="decimal"
    placeholder="€ to"
    size="6"
    value={filters.state.priceTo}
    oninput={(e) =>
      setFilter({ priceTo: e.currentTarget.value.replace(/[^\d.]/g, "") })}
  />

  <select
    value={filters.state.sort}
    onchange={(e) =>
      setFilter({ sort: e.currentTarget.value as typeof filters.state.sort })}
  >
    <option value="">Sort: newest</option>
    <option value="price-asc">Price ↑</option>
    <option value="price-desc">Price ↓</option>
  </select>

  <input
    type="search"
    placeholder="Search…"
    value={filters.state.search}
    oninput={(e) => setSearch(e.currentTarget.value)}
  />

  <button
    onclick={() => {
      filters.reset();
      paging.resetToFirst();
      syncUrl("push");
    }}>Reset</button
  >
</div>

{#if loading}
  <p class="status">Loading offers…</p>
{:else if loadError}
  <p class="status">Failed to load offers: {loadError}</p>
{:else if view === "alerts"}
  <!-- AlertsView deep-link target: rendered by T6. -->
  <p class="status">Alerts view (T6){alertId ? ` — alert ${alertId}` : ""}</p>
{:else}
  <main class="grid">
    {#each pageResult.items as item (item.id)}
      <div class="card">
        <a href={item.url} target="_blank" rel="noopener noreferrer">
          <div class="title">
            [{item.store}] {item.title}
            {#if isNew(item, sync.lastVisit)}<span class="badge-new">New</span>{/if}
          </div>
          <div class="info">
            <span>{formatAvailability(item.store_availability_date)}</span>
            <span>€{item.price}</span>
          </div>
        </a>
      </div>
    {:else}
      <p class="status">No offers match the current filters.</p>
    {/each}
  </main>

  <nav class="pager">
    <button
      disabled={pageResult.page <= 1}
      onclick={() => goToPage(pageResult.page - 1)}>Prev</button
    >
    <span>Page {pageResult.page} / {pageResult.totalPages}</span>
    <button
      disabled={pageResult.page >= pageResult.totalPages}
      onclick={() => goToPage(pageResult.page + 1)}>Next</button
    >
  </nav>
{/if}
