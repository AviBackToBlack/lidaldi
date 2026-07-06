<script lang="ts">
  import type { Offer } from "../types";
  import { alerts } from "../stores/alerts.svelte";
  import { sync } from "../stores/sync.svelte";
  import { syncFetch, syncPost, type AlertMatches } from "../sync/client";
  import { groupAlertMatches } from "../logic/alertmatches";
  import { isNew } from "../logic/filters";
  import Card from "./Card.svelte";

  let {
    offers,
    alertId,
    onBack,
    onOpenAlerts,
  }: {
    offers: Offer[];
    alertId: string;
    onBack: () => void;
    onOpenAlerts: () => void;
  } = $props();

  let matches = $state<AlertMatches>({});
  let loading = $state(Boolean(sync.code));
  let fetchFailed = $state(false);

  void (async () => {
    if (!sync.code) return;
    // POST first so local alerts are merged into the profile before the
    // GET reply (which includes alertMatches) is adopted — a plain GET
    // would overwrite local alerts the server hasn't seen yet.
    await syncPost(sync.code, 0, alerts.alerts, alerts.tombstones);
    const data = await syncFetch(sync.code);
    if (data) {
      matches = data.alertMatches ?? {};
      if (Array.isArray(data.alerts)) alerts.setAlerts(data.alerts);
      if (Array.isArray(data.tombstones)) alerts.setTombstones(data.tombstones);
      sync.adoptServer(data.lastVisit);
    } else {
      fetchFailed = true;
    }
    loading = false;
  })();

  const groups = $derived(groupAlertMatches(alerts.alerts, matches, offers));

  // Deep-link target: scroll it into view and move focus there so
  // keyboard/screen-reader users land on the highlighted group.
  function highlightTarget(el: HTMLElement, isTarget: boolean): void {
    if (!isTarget) return;
    el.scrollIntoView({ block: "start" });
    el.focus({ preventScroll: true });
  }
</script>

<section class="alerts-view">
  <div class="alerts-view-bar">
    <button class="chip" onclick={onBack}
      ><span aria-hidden="true">←</span> All offers</button
    >
    <h2>Alert matches</h2>
    <button class="btn-dark" onclick={onOpenAlerts}
      ><span aria-hidden="true">🔔</span> Manage alerts</button
    >
  </div>

  {#if !sync.code}
    <p class="status">
      No sync code is set on this device — connect one under “Manage alerts”
      to see your alert matches.
    </p>
  {:else if loading}
    <p class="status">Loading alert matches…</p>
  {:else if fetchFailed}
    <p class="status">
      Couldn’t load your alert matches — check your connection and reload the
      page to try again.
    </p>
  {:else if groups.length === 0}
    <p class="status">No keyword alerts yet — add one under “Manage alerts”.</p>
  {:else}
    {#each groups as group (group.alert.id)}
      <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
      <!-- tabindex="-1" only: programmatic focus target for the deep link,
           never in the Tab order. -->
      <article
        class="alert-group"
        class:highlight={group.alert.id === alertId}
        use:highlightTarget={group.alert.id === alertId}
        data-alert-id={group.alert.id}
        tabindex={group.alert.id === alertId ? -1 : undefined}
        aria-label={`Alert matches for ${group.alert.keyword}`}
      >
        <h3>
          <span class="kw">{group.alert.keyword}</span>
          <span class="mt">{group.alert.matchType}</span>
          <span class="count"
            >{group.offers.length}
            {group.offers.length === 1 ? "match" : "matches"}{group.expiredCount
              ? ` (+${group.expiredCount} no longer listed)`
              : ""}</span
          >
        </h3>
        {#if group.offers.length}
          <div class="products-grid">
            {#each group.offers as offer (offer.id)}
              <Card {offer} isNew={isNew(offer, sync.lastVisit)} />
            {/each}
          </div>
        {:else}
          <p class="status">No current offers match this alert.</p>
        {/if}
      </article>
    {/each}
  {/if}
</section>

<style>
  .alerts-view-bar {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 20px 0 6px;
  }
  .alerts-view-bar h2 {
    flex: 1;
    margin: 0;
    font-size: var(--text-lg);
    font-weight: var(--weight-heavy);
    color: var(--ink);
  }

  .alert-group {
    margin-top: 18px;
    padding: 14px;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background: var(--surface);
    box-shadow: var(--shadow-card);
  }
  .alert-group.highlight {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent), var(--shadow-card);
    background: var(--accent-tint);
  }
  .alert-group h3 {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin: 0 0 12px;
  }
  .alert-group .kw {
    font-size: var(--text-md);
    font-weight: var(--weight-heavy);
    color: var(--text);
  }
  .alert-group .mt {
    font-size: var(--text-xs);
    font-weight: var(--weight-bold);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-2);
    background: var(--surface-sunken);
    padding: 3px 8px;
    border-radius: var(--radius-sm);
  }
  .alert-group .count {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--text-2);
  }

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
