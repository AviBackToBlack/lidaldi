<script lang="ts">
  import type { Offer } from "../types";
  import { formatAvailability, priceOf } from "../logic/filters";

  let {
    offer,
    isNew,
  }: {
    offer: Offer;
    isNew: boolean;
  } = $props();

  const priceUnknown = $derived(priceOf(offer) === Number.POSITIVE_INFINITY);

  // Images are served from the web root's img/ tree (legacy layout kept).
  // Defence in depth: refuse traversal or absolute segments.
  function imageSrc(o: Offer): string {
    const path = o.images[0]?.path ?? "";
    if (!path || path.startsWith("/") || path.includes("..")) return "";
    return `/img/${path}`;
  }
  const img = $derived(imageSrc(offer));

  // Hover/focus popover via the native Popover API. The popover lives in
  // the top layer, so it is positioned from the card's rect on show
  // (visual placement copied from the design mockup: left 24 / top -10 /
  // right -12 relative to the card).
  const SHOW_DELAY_MS = 400;
  const popId = `desc-pop-${Math.random().toString(36).slice(2, 10)}`;
  let cardEl = $state<HTMLElement | null>(null);
  let popEl = $state<HTMLElement | null>(null);
  let timer: ReturnType<typeof setTimeout> | null = null;

  function showPopover(): void {
    if (!cardEl || !popEl || !popEl.showPopover) return;
    const r = cardEl.getBoundingClientRect();
    popEl.style.left = `${r.left + 24}px`;
    popEl.style.top = `${Math.max(0, r.top - 10)}px`;
    popEl.style.width = `${r.width - 12}px`;
    try {
      popEl.showPopover();
    } catch {
      /* already shown */
    }
  }

  function hidePopover(): void {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    try {
      popEl?.hidePopover?.();
    } catch {
      /* already hidden */
    }
  }

  function scheduleShow(): void {
    if (timer !== null) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      showPopover();
    }, SHOW_DELAY_MS);
  }

  // WCAG 1.4.13: hover/focus content must be dismissible without moving
  // the pointer or focus.
  function onCardKeydown(e: KeyboardEvent): void {
    if (e.key === "Escape") hidePopover();
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<!-- The keydown listener only dismisses the hover/focus popover (WCAG
     1.4.13); the card itself is not interactive — the link inside is. -->
<article
  class="product-card {offer.store === 'ALDI' ? 'aldi' : 'lidl'}"
  bind:this={cardEl}
  onmouseenter={scheduleShow}
  onmouseleave={hidePopover}
  onfocusin={scheduleShow}
  onfocusout={hidePopover}
  onkeydown={onCardKeydown}
>
  {#if isNew}<span class="new-badge">NEW<span class="sr-only"> since your last visit</span></span>{/if}
  <span class="store-badge">{offer.store}</span>
  <a
    class="card-link"
    href={offer.url}
    target="_blank"
    rel="noopener noreferrer"
    aria-describedby={popId}
  >
    <div class="product-image">
      {#if img}
        <img src={img} alt={offer.title || "Product"} loading="lazy" />
      {:else}
        <span class="ph">{offer.category || "no image"}</span>
      {/if}
    </div>
    <div class="product-title">{offer.title}</div>
  </a>
  <div class="product-info">
    <span class="availability">{formatAvailability(offer.store_availability_date)}</span>
    {#if priceUnknown}
      <span class="price unknown">Price N/A</span>
    {:else}
      <span class="price">€{offer.price}</span>
    {/if}
  </div>
  <div class="desc-popover" popover="manual" id={popId} bind:this={popEl}>
    <b>{offer.store}</b>
    {offer.description}
    <div class="pop-meta">
      <span>{formatAvailability(offer.store_availability_date)}</span>
      <span>{priceUnknown ? "Price N/A" : `€${offer.price}`}</span>
    </div>
  </div>
</article>

<style>
  .product-card {
    position: relative;
    display: flex;
    flex-direction: column;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: var(--card-border-accent) solid var(--store, var(--border));
    border-radius: var(--radius-lg);
    padding: 14px;
    box-shadow: var(--shadow-card);
    transition: transform var(--transition), box-shadow var(--transition),
      border-color var(--transition);
  }
  .product-card:hover,
  .product-card:focus-within {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lift);
    border-color: var(--border-hover);
    border-left-color: var(--store);
  }
  .product-card.aldi {
    --store: var(--aldi);
    --store-text: var(--aldi);
    --store-tint: var(--aldi-tint);
  }
  .product-card.lidl {
    --store: var(--lidl);
    --store-text: var(--lidl-text);
    --store-tint: var(--lidl-tint);
  }

  .card-link {
    display: flex;
    flex-direction: column;
    flex: 1;
    color: inherit;
    text-decoration: none;
  }

  .store-badge {
    align-self: flex-start;
    font-size: 10px;
    font-weight: var(--weight-bold);
    letter-spacing: 0.06em;
    color: var(--store-text);
    background: var(--store-tint);
    padding: 4px 9px;
    border-radius: var(--radius-sm);
    margin-bottom: 12px;
  }
  .new-badge {
    position: absolute;
    top: 12px;
    right: 12px;
    font-size: 10px;
    font-weight: var(--weight-bold);
    letter-spacing: 0.05em;
    color: #fff;
    background: var(--accent-hover);
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    box-shadow: 0 2px 6px rgba(217, 84, 47, 0.4);
  }
  :global([data-theme="dark"]) .new-badge {
    background: var(--accent);
    color: var(--bg);
  }

  .product-image {
    height: 148px;
    border-radius: var(--radius);
    background: var(--surface-sunken);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 13px;
    overflow: hidden;
  }
  .product-image img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
    mix-blend-mode: multiply;
  }
  :global([data-theme="dark"]) .product-image img {
    mix-blend-mode: normal;
    border-radius: var(--radius-sm);
  }
  .product-image .ph {
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: var(--weight-semibold);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-2);
  }

  .product-title {
    font-size: var(--text-md);
    line-height: 1.32;
    font-weight: var(--weight-bold);
    color: var(--text);
    min-height: 37px;
    margin-bottom: 12px;
  }
  .product-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-top: auto;
  }
  /* No nowrap: the price pill never shrinks, so a long label ("While
     Stock Lasts") used to push it past the card's right edge on narrow
     columns. Wrapping the label is the only shrinkable part of the row. */
  .availability {
    font-size: var(--text-sm);
    font-weight: var(--weight-semibold);
    color: var(--text-2);
    min-width: 0;
    overflow-wrap: anywhere;
  }
  /* WCAG contrast: --accent-text on --accent-tint is 4.37:1 in light;
     --accent-active passes there, --accent-text stays for dark. */
  .price {
    font-size: var(--text-price);
    line-height: 1;
    font-weight: var(--weight-heavy);
    color: var(--accent-active);
    background: var(--accent-tint);
    padding: 7px 11px;
    border-radius: var(--radius);
    white-space: nowrap;
    flex: none;
  }
  :global([data-theme="dark"]) .price {
    color: var(--accent-text);
  }
  .price.unknown {
    font-size: var(--text-xs);
    font-weight: var(--weight-bold);
    color: var(--text-2);
    background: var(--surface-sunken);
    border: 1px dashed var(--border-hover);
    padding: 6px 10px;
  }

  .desc-popover {
    position: fixed;
    inset: auto;
    margin: 0;
    border: none;
    background: var(--ink);
    color: var(--bg);
    border-radius: 13px;
    padding: 14px 15px;
    box-shadow: var(--shadow-popover);
    font-size: 12.5px;
    line-height: 1.5;
    font-weight: var(--weight-medium);
  }
  /* WCAG contrast: the popover sits on the dark --ink surface, where the
     light theme's --accent-text is illegible — use the pale --accent-tint
     there and the dark theme's own --accent-text on black. */
  .desc-popover b {
    display: block;
    color: var(--accent-tint);
    font-size: var(--text-xs);
    letter-spacing: 0.05em;
    margin-bottom: 6px;
  }
  .desc-popover:popover-open {
    animation: pop 0.18s ease backwards;
  }
  :global([data-theme="dark"]) .desc-popover {
    background: #000;
    color: var(--text-2);
  }
  :global([data-theme="dark"]) .desc-popover b {
    color: var(--accent-text);
  }
  .pop-meta {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    margin-top: 8px;
    font-size: var(--text-xs);
    color: var(--text-faint);
  }
  :global([data-theme="dark"]) .pop-meta {
    color: var(--text-3);
  }

  @keyframes pop {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
  }

  @media (max-width: 720px) {
    .product-image {
      height: 110px;
    }
    .product-title {
      font-size: 12px;
      min-height: 32px;
    }
    .price {
      font-size: 14px;
    }
    /* Mobile columns are ~160-195px wide — too narrow for label + pill on
       one line. Stack them so the pill can never be squeezed or clipped. */
    .product-info {
      flex-direction: column;
      align-items: flex-start;
      gap: 6px;
    }
    .availability {
      overflow-wrap: normal;
    }
  }
</style>
