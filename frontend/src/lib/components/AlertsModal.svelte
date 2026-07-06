<script lang="ts">
  import { alerts } from "../stores/alerts.svelte";
  import { sync } from "../stores/sync.svelte";
  import {
    generateSyncCode,
    syncPost,
    type Alert,
  } from "../sync/client";
  import { normalizeSyncCode } from "../logic/synccode";
  import {
    getExistingPushSubscription,
    isPushSupported,
    postPushSubscription,
    registerServiceWorker,
    subscribePush,
  } from "../push";

  let {
    vapidPublicKey,
    onClose,
  }: {
    vapidPublicKey: string;
    onClose: () => void;
  } = $props();

  let codeEntry = $state("");
  let syncMessage = $state("");
  let pushEnabled = $state(false);
  let pushMessage = $state("");
  let pushBusy = $state(false);
  let newKeyword = $state("");
  let newMatchType = $state<Alert["matchType"]>("anyWord");
  let copied = $state(false);

  void (async () => {
    pushEnabled = (await getExistingPushSubscription()) !== null;
  })();

  const MATCH_TYPE_LABELS: Record<Alert["matchType"], string> = {
    exact: "exact",
    allWords: "all words",
    anyWord: "any word",
  };

  /** Push local alerts state to the profile and adopt the merged reply. */
  async function pushProfile(code: string): Promise<void> {
    // lastVisit 0 = "don't advance" (sync contract rule 4).
    const reply = await syncPost(code, 0, alerts.alerts, alerts.tombstones);
    if (reply) {
      if (Array.isArray(reply.alerts)) alerts.setAlerts(reply.alerts);
      if (Array.isArray(reply.tombstones)) alerts.setTombstones(reply.tombstones);
      sync.adoptServer(reply.lastVisit);
    }
  }

  function generateCode(): void {
    const code = generateSyncCode();
    sync.setCode(code);
    syncMessage = "";
    void pushProfile(code);
  }

  function connectCode(): void {
    const norm = normalizeSyncCode(codeEntry);
    if (!norm.ok) {
      syncMessage =
        "That doesn't look like a valid code — check for confusable characters (0/O, 1/l are never used).";
      return;
    }
    if (!sync.setCode(norm.code)) {
      syncMessage = "Invalid sync code.";
      return;
    }
    syncMessage = norm.changed
      ? `Connected as ${norm.code} (typo-confusable characters corrected).`
      : "";
    codeEntry = "";
    void pushProfile(norm.code);
  }

  function disconnect(): void {
    sync.clearCode();
    syncMessage = "";
  }

  async function copyCode(): Promise<void> {
    try {
      await navigator.clipboard.writeText(sync.code);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      syncMessage = "Copy failed — select the code manually.";
    }
  }

  async function togglePush(): Promise<void> {
    if (pushBusy) return;
    pushBusy = true;
    pushMessage = "";
    try {
      if (pushEnabled) {
        const reg = await registerServiceWorker();
        const sub = await reg?.pushManager.getSubscription();
        if (sub) await sub.unsubscribe();
        pushEnabled = false;
        return;
      }
      // Ensure a code exists without pushProfile's fire-and-forget POST:
      // postPushSubscription below already sends alerts + tombstones, and a
      // concurrent subscription-less POST could race it on the server.
      if (!sync.code) {
        sync.setCode(generateSyncCode());
        syncMessage = "";
      }
      const result = await subscribePush(vapidPublicKey);
      if (!result.ok) {
        pushMessage = {
          unsupported: "Push notifications are not supported in this browser.",
          denied: "Notification permission was denied.",
          "no-key": "Push is not configured on this server.",
          error: "Could not subscribe — please try again.",
        }[result.reason];
        return;
      }
      await postPushSubscription(
        sync.code,
        0,
        alerts.alerts,
        alerts.tombstones,
        result.subscription
      );
      pushEnabled = true;
    } finally {
      pushBusy = false;
    }
  }

  function addAlert(e: SubmitEvent): void {
    e.preventDefault();
    const created = alerts.add(newKeyword, newMatchType);
    if (!created) return;
    newKeyword = "";
    if (sync.code) void pushProfile(sync.code);
  }

  function removeAlert(id: string): void {
    alerts.delete(id);
    if (sync.code) void pushProfile(sync.code);
  }

  function onOverlayClick(e: MouseEvent): void {
    if (e.target === e.currentTarget) onClose();
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={onOverlayClick}>
  <div
    class="modal-content"
    role="dialog"
    aria-modal="true"
    aria-labelledby="alerts-title"
  >
    <div class="modal-header">
      <h2 id="alerts-title">🔔 Alerts &amp; Sync</h2>
      <button class="modal-close" aria-label="Close" onclick={onClose}>✕</button>
    </div>
    <div class="modal-body">
      <h3>Sync across devices</h3>
      {#if sync.code}
        <div class="sync-row">
          <div class="sync-code-value">{sync.code}</div>
          <button class="btn-ink" onclick={copyCode}>{copied ? "Copied" : "Copy"}</button>
          <button class="btn-ink" onclick={disconnect}>Disconnect</button>
        </div>
      {:else}
        <div class="sync-row">
          <input
            class="sync-code-entry"
            type="text"
            placeholder="Enter a sync code…"
            aria-label="Sync code"
            bind:value={codeEntry}
            onkeydown={(e) => e.key === "Enter" && connectCode()}
          />
          <button class="btn-ink" onclick={connectCode}>Connect</button>
          <button class="btn-primary connect-btn" onclick={generateCode}
            >New code</button
          >
        </div>
      {/if}
      {#if syncMessage}<p class="form-message">{syncMessage}</p>{/if}

      {#if isPushSupported()}
        <div class="push-row">
          <div>
            <div class="t">Push notifications</div>
            <div class="d">Get pinged when a match drops</div>
          </div>
          <button
            class="switch"
            role="switch"
            aria-checked={pushEnabled}
            aria-label="Enable push notifications"
            disabled={pushBusy}
            onclick={togglePush}
          ></button>
        </div>
        {#if pushMessage}<p class="form-message">{pushMessage}</p>{/if}
      {/if}

      <h3>Keyword alerts</h3>
      <div class="keyword-list">
        {#each alerts.alerts as alert (alert.id)}
          <span class="keyword-chip"
            >{alert.keyword}
            <em>({MATCH_TYPE_LABELS[alert.matchType]})</em>
            <button
              aria-label={`Remove ${alert.keyword}`}
              onclick={() => removeAlert(alert.id)}>✕</button
            ></span
          >
        {:else}
          <span class="no-alerts">No keyword alerts yet.</span>
        {/each}
      </div>
      <form class="add-alert-form" onsubmit={addAlert}>
        <input
          type="text"
          placeholder="Add a keyword…"
          aria-label="Keyword"
          bind:value={newKeyword}
        />
        <div class="select-wrapper">
          <select aria-label="Match type" bind:value={newMatchType}>
            <option value="anyWord">Any word</option>
            <option value="allWords">All words</option>
            <option value="exact">Exact</option>
          </select>
        </div>
        <button class="btn-primary add-btn" type="submit">Add</button>
      </form>
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(20, 16, 12, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    z-index: 100;
  }
  .modal-content {
    background: var(--surface);
    border-radius: var(--radius-xl);
    border: 1px solid var(--border);
    box-shadow: var(--shadow-modal);
    width: 100%;
    max-width: 440px;
    max-height: 88vh;
    overflow-y: auto;
  }
  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 22px;
    border-bottom: 1px solid var(--border);
  }
  .modal-header h2 {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 11px;
    font-size: var(--text-lg);
    font-weight: var(--weight-heavy);
    color: var(--ink);
    white-space: nowrap;
  }
  .modal-close {
    width: 30px;
    height: 30px;
    border-radius: 9px;
    border: none;
    background: var(--surface-sunken);
    color: var(--text-3);
    font-size: 15px;
    line-height: 1;
  }
  .modal-close:hover {
    color: var(--text);
  }
  .modal-body {
    padding: 22px;
  }
  .modal-body h3 {
    margin: 0 0 10px;
    font-size: var(--text-sm);
    font-weight: var(--weight-bold);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--text-3);
  }
  .sync-row {
    display: flex;
    gap: 9px;
    margin-bottom: 22px;
  }
  .sync-code-value {
    flex: 1;
    padding: 12px 14px;
    border-radius: var(--radius-md);
    background: var(--bg);
    border: 1px solid var(--border);
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: var(--weight-bold);
    letter-spacing: 0.15em;
    color: var(--text);
  }
  .sync-code-entry {
    flex: 1;
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: var(--weight-bold);
    letter-spacing: 0.1em;
    color: var(--text);
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-md);
    padding: 11px 14px;
  }
  .sync-code-entry::placeholder {
    color: var(--text-faint);
    letter-spacing: normal;
    font-family: var(--font-sans);
    font-weight: var(--weight-medium);
  }
  .connect-btn {
    padding: 0 14px;
  }
  .form-message {
    margin: -14px 0 18px;
    font-size: var(--text-sm);
    font-weight: var(--weight-medium);
    color: var(--accent-text);
  }
  .push-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 15px;
    border-radius: 13px;
    background: var(--accent-tint);
    margin-bottom: 22px;
  }
  .push-row .t {
    font-size: var(--text-md);
    font-weight: var(--weight-bold);
    color: var(--text);
  }
  .push-row .d {
    font-size: var(--text-sm);
    font-weight: var(--weight-medium);
    color: var(--text-3);
    margin-top: 2px;
  }
  .switch {
    width: 46px;
    height: 27px;
    border-radius: 14px;
    background: var(--accent);
    border: none;
    position: relative;
    flex: none;
    transition: background var(--transition);
  }
  .switch::after {
    content: "";
    position: absolute;
    top: 3px;
    right: 3px;
    width: 21px;
    height: 21px;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    transition: transform var(--transition);
  }
  .switch[aria-checked="false"] {
    background: var(--border-hover);
  }
  .switch[aria-checked="false"]::after {
    transform: translateX(-19px);
  }
  .keyword-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 12px;
  }
  .keyword-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 7px 8px 7px 13px;
    border-radius: 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    font-size: var(--text-base);
    font-weight: var(--weight-semibold);
    color: var(--text);
    white-space: nowrap;
  }
  .keyword-chip em {
    font-style: normal;
    font-size: var(--text-xs);
    font-weight: var(--weight-medium);
    color: var(--text-3);
  }
  .keyword-chip button {
    border: none;
    background: none;
    color: var(--text-faint);
    font-size: 12px;
    padding: 2px;
  }
  .keyword-chip button:hover {
    color: var(--lidl-text);
  }
  .no-alerts {
    font-size: var(--text-base);
    font-weight: var(--weight-medium);
    color: var(--text-3);
  }
  .add-alert-form {
    display: flex;
    gap: 9px;
  }
  .add-alert-form input {
    flex: 1;
    min-width: 0;
    font-family: var(--font-sans);
    font-size: var(--text-base);
    font-weight: var(--weight-medium);
    color: var(--text);
    background: var(--surface);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-md);
    padding: 11px 14px;
  }
  .add-alert-form input::placeholder {
    color: var(--text-faint);
  }
  .add-btn {
    padding: 11px 18px;
  }
</style>
