// Push-subscription state module (T7). Ports the legacy subscribe flow from
// website/js/lidaldi.js; UI wiring (buttons, prompts) lands in T6.
// VAPID public key comes from meta.json (loadMeta().vapidPublicKey — D2).

import {
  syncPost,
  type Alert,
  type SyncData,
  type Tombstone,
} from "./sync/client";

export function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

export function isPushSupported(): boolean {
  return (
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

let swReady: Promise<ServiceWorkerRegistration | null> | null = null;

/**
 * Register the root-scoped worker (stable URL /sw.js). Idempotent while a
 * registration is pending or succeeded; a failed attempt is not cached, so
 * the next call retries. Returns null where service workers are unsupported
 * or registration fails.
 */
export function registerServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (swReady) return swReady;
  if (!("serviceWorker" in navigator)) {
    return Promise.resolve(null);
  }
  const attempt = navigator.serviceWorker
    .register("/sw.js")
    .then(() => navigator.serviceWorker.ready)
    .catch((e: unknown) => {
      console.warn("SW registration failed:", e);
      if (swReady === attempt) swReady = null;
      return null;
    });
  swReady = attempt;
  return attempt;
}

export async function getExistingPushSubscription(): Promise<PushSubscriptionJSON | null> {
  if (!isPushSupported()) return null;
  try {
    const reg = await registerServiceWorker();
    if (!reg) return null;
    const sub = await reg.pushManager.getSubscription();
    return sub ? sub.toJSON() : null;
  } catch {
    return null;
  }
}

export type SubscribeResult =
  | { ok: true; subscription: PushSubscriptionJSON }
  | { ok: false; reason: "unsupported" | "denied" | "no-key" | "error" };

/**
 * Permission flow + subscribe. `vapidPublicKey` is the caller-supplied key
 * from meta.json. Returns a discriminated result so T6 can render the
 * appropriate message (no alert() side effects here).
 */
export async function subscribePush(
  vapidPublicKey: string
): Promise<SubscribeResult> {
  if (!isPushSupported()) return { ok: false, reason: "unsupported" };
  if (!vapidPublicKey) return { ok: false, reason: "no-key" };
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return { ok: false, reason: "denied" };
  try {
    const reg = await registerServiceWorker();
    if (!reg) return { ok: false, reason: "error" };
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey).buffer as ArrayBuffer,
    });
    return { ok: true, subscription: sub.toJSON() };
  } catch (e) {
    console.warn("Push subscribe failed:", e);
    return { ok: false, reason: "error" };
  }
}

/** POST the subscription to the sync server via the existing sync contract. */
export function postPushSubscription(
  code: string,
  lastVisit: number,
  alerts: Alert[],
  tombstones: Tombstone[],
  subscription: PushSubscriptionJSON
): Promise<SyncData | null> {
  return syncPost(code, lastVisit, alerts, tombstones, subscription);
}
