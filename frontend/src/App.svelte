<script lang="ts">
  import { loadMeta, loadOffers } from "./lib/data";
  import type { Meta, Offer } from "./lib/types";
  import {
    applyFilters,
    availableCategories,
    futureAvailabilityDates,
    hasNewOffers,
    isNew,
    sortNewestFirst,
  } from "./lib/logic/filters";
  import { paginate } from "./lib/logic/paging";
  import { computePageSize } from "./lib/logic/pagesize";
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
  import Header from "./lib/components/Header.svelte";
  import FilterBar from "./lib/components/FilterBar.svelte";
  import Card from "./lib/components/Card.svelte";
  import Pager from "./lib/components/Pager.svelte";
  import AlertsModal from "./lib/components/AlertsModal.svelte";
  import AlertsView from "./lib/components/AlertsView.svelte";

  let offers = $state<Offer[]>([]);
  let meta = $state<Meta | null>(null);
  let loadError = $state("");
  let loading = $state(true);
  let view = $state<View>("");
  let alertId = $state("");
  let alertsModalOpen = $state(false);

  // Deep-link restore before first render.
  applyUrlState(readUrlState());
  sync.init();
  alerts.init();
  paging.pageSize = computePageSize(window.innerWidth);

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

  // Responsive page size (Bug #1): pure function of the viewport width —
  // no DOM measurement, no ResizeObserver. Debounced against resize bursts.
  $effect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const onResize = () => {
      if (timer !== null) clearTimeout(timer);
      timer = setTimeout(() => {
        timer = null;
        paging.pageSize = computePageSize(window.innerWidth);
      }, 150);
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      if (timer !== null) clearTimeout(timer);
    };
  });

  // One-shot boot work (not reactive): data load + sync handshake.
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
    if (data) {
      sync.adoptServer(data.lastVisit);
      if (Array.isArray(data.alerts)) alerts.setAlerts(data.alerts);
      if (Array.isArray(data.tombstones)) alerts.setTombstones(data.tombstones);
    }
  })();

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

  function resetFilters(): void {
    filters.reset();
    paging.resetToFirst();
    syncUrl("push");
  }

  function goToPage(p: number): void {
    paging.goTo(p);
    syncUrl("push");
  }

  function showGrid(): void {
    view = "";
    alertId = "";
    syncUrl("push");
  }

  // Global Left/Right arrow paging (Bug #3). Suppressed only where the
  // arrows have native meaning: selects and text carets. Buttons don't
  // suppress — filter controls blur after activation, and paging keeps
  // working even if something re-focuses them.
  function onKeydown(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      if (alertsModalOpen) alertsModalOpen = false;
      return;
    }
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    if (alertsModalOpen || view === "alerts" || loading || loadError) return;
    const ae = document.activeElement;
    if (ae instanceof HTMLSelectElement || ae instanceof HTMLTextAreaElement) return;
    if (ae instanceof HTMLInputElement && ae.type !== "checkbox" && ae.type !== "radio") return;
    if (ae instanceof HTMLElement && ae.isContentEditable) return;
    if (e.key === "ArrowLeft" && pageResult.page > 1) {
      goToPage(pageResult.page - 1);
    } else if (e.key === "ArrowRight" && pageResult.page < pageResult.totalPages) {
      goToPage(pageResult.page + 1);
    }
  }
</script>

<svelte:window onkeydown={onKeydown} />

<Header
  lastUpdated={meta?.lastUpdated ?? 0}
  lastVisit={sync.lastVisit}
  offerCount={offers.length}
/>

{#if loading}
  <p class="status">Loading offers…</p>
{:else if loadError}
  <p class="status">Failed to load offers: {loadError}</p>
{:else if view === "alerts"}
  <AlertsView
    {offers}
    {alertId}
    onBack={showGrid}
    onOpenAlerts={() => (alertsModalOpen = true)}
  />
{:else}
  <FilterBar
    filters={filters.state}
    {categories}
    {futureDates}
    {newAvailable}
    onFilter={setFilter}
    onSearch={setSearch}
    onReset={resetFilters}
    onOpenAlerts={() => (alertsModalOpen = true)}
  />

  <div class="grid-meta">
    <span>Showing <b>{filtered.length}</b> offers</span>
    <span class="page-ind">page {pageResult.page} of {pageResult.totalPages}</span>
  </div>

  {#if pageResult.items.length}
    <main class="products-grid">
      {#each pageResult.items as item (item.id)}
        <Card offer={item} isNew={isNew(item, sync.lastVisit)} />
      {/each}
    </main>
  {:else}
    <p class="status">No offers match the current filters.</p>
  {/if}

  <Pager page={pageResult.page} totalPages={pageResult.totalPages} onGoTo={goToPage} />
{/if}

<footer class="site-footer">
  Independent price tracker — not affiliated with ALDI or LIDL. Prices and
  availability may change in store.<br />
  <a href="https://github.com/AviBackToBlack/lidaldi">View on GitHub</a>
</footer>

{#if alertsModalOpen}
  <AlertsModal
    vapidPublicKey={meta?.vapidPublicKey ?? ""}
    onClose={() => (alertsModalOpen = false)}
  />
{/if}

<style>
  .grid-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 20px 2px 14px;
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
    color: var(--text-3);
  }
  .grid-meta b {
    color: var(--text);
  }
  .grid-meta .page-ind {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-faint);
  }

  /* Bug #1 fix: pure-CSS auto-fill grid; page size mirrors this rule
     arithmetically in logic/pagesize.ts — keep the two in sync. */
  .products-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(224px, 1fr));
    gap: 18px;
  }

  @media (max-width: 720px) {
    .products-grid {
      grid-template-columns: repeat(auto-fill, minmax(158px, 1fr));
      gap: 12px;
    }
  }
</style>
