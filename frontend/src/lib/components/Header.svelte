<script lang="ts">
  import { applyTheme, currentTheme, type Theme } from "../logic/theme";

  let {
    lastUpdated = 0,
    lastVisit = 0,
    offerCount = 0,
  }: { lastUpdated?: number; lastVisit?: number; offerCount?: number } =
    $props();

  let theme = $state<Theme>(currentTheme());

  function toggleTheme(): void {
    theme = theme === "dark" ? "light" : "dark";
    applyTheme(theme);
  }

  function fmtDate(ts: number): string {
    const d = new Date(ts * 1000);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    return `${dd}/${mm}/${d.getFullYear()}`;
  }
</script>

<header>
  <img class="logo" src="/img/lidaldi.png" alt="LIDALDI mascot" />
  <div class="header-info">
    <h1>ALDI.IE &amp; LIDL.IE Special Offers</h1>
    <div class="meta-row">
      {#if lastUpdated}
        <span class="page-last-updated">Last updated <b>{fmtDate(lastUpdated)}</b></span>
      {/if}
      {#if lastVisit}
        <span class="last-visit-info">Your last visit <b>{fmtDate(lastVisit)}</b></span>
      {/if}
    </div>
  </div>
  {#if offerCount}
    <span class="offer-count">{offerCount} offers this week</span>
  {/if}
  <button
    class="theme-toggle"
    aria-label="Toggle dark theme"
    aria-pressed={theme === "dark"}
    onclick={toggleTheme}>◐ <span>{theme === "dark" ? "Light" : "Dark"}</span></button
  >
</header>

<style>
  header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 22px;
  }
  .logo {
    width: 56px;
    height: 56px;
    border-radius: 14px;
    flex: none;
  }
  .header-info {
    flex: 1;
  }
  h1 {
    margin: 0;
    font-size: var(--text-xl);
    font-weight: var(--weight-heavy);
    letter-spacing: -0.02em;
    color: var(--ink);
  }
  .meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 20px;
    margin-top: 7px;
    font-size: var(--text-base);
    font-weight: var(--weight-medium);
    color: var(--text-2);
  }
  .meta-row b {
    color: var(--text);
    font-weight: var(--weight-bold);
  }
  /* WCAG contrast: --accent on --accent-tint is 3.42:1; the darker
     --accent-active passes in light, --accent-text in dark. */
  .offer-count {
    font-size: var(--text-base);
    font-weight: var(--weight-bold);
    color: var(--accent-active);
    background: var(--accent-tint);
    padding: 9px 15px;
    border-radius: var(--radius);
    white-space: nowrap;
  }
  :global([data-theme="dark"]) .offer-count {
    color: var(--accent-text);
  }
  .theme-toggle {
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--text-2);
    border-radius: var(--radius);
    padding: 9px 13px;
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
  }

  @media (max-width: 720px) {
    .logo {
      width: 44px;
      height: 44px;
    }
    h1 {
      font-size: 17px;
    }
    .offer-count {
      display: none;
    }
  }
</style>
