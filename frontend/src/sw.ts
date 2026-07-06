/// <reference lib="webworker" />
// LIDALDI service worker (root-scoped, stable URL /sw.js — built by
// vite.sw.config.ts). Push (N6-hardened) + static-SPA caching.

import {
  classifyRequest,
  notificationTargetUrl,
  parsePushPayload,
} from "./lib/sw/logic";

declare const self: ServiceWorkerGlobalScope;

const STATIC_CACHE = "lidaldi-static-v1";
const DATA_CACHE = "lidaldi-data-v1";
const KNOWN_CACHES = new Set([STATIC_CACHE, DATA_CACHE]);

self.addEventListener("install", () => {
  void self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names.filter((n) => !KNOWN_CACHES.has(n)).map((n) => caches.delete(n))
      );
      await self.clients.claim();
    })()
  );
});

async function cacheFirst(request: Request): Promise<Response> {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(STATIC_CACHE);
    await cache.put(request, response.clone());
  }
  return response;
}

async function networkFirst(
  request: Request,
  fallbackKey?: string
): Promise<Response> {
  const fromCache = async (): Promise<Response | undefined> =>
    (await caches.match(request)) ??
    (fallbackKey ? await caches.match(fallbackKey) : undefined);
  let response: Response;
  try {
    response = await fetch(request);
  } catch (err) {
    const cached = await fromCache();
    if (cached) return cached;
    throw err;
  }
  if (response.ok) {
    const cache = await caches.open(DATA_CACHE);
    await cache.put(request, response.clone());
    return response;
  }
  return (await fromCache()) ?? response;
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const kind = classifyRequest(url.pathname, request.mode);
  if (kind === "static") {
    event.respondWith(cacheFirst(request));
  } else if (kind === "data") {
    event.respondWith(networkFirst(request));
  } else if (kind === "navigation") {
    event.respondWith(networkFirst(request, "/"));
  }
});

async function showPushNotification(raw: string | null): Promise<void> {
  const payload = parsePushPayload(raw);
  await self.registration.showNotification(payload.title, {
    body: payload.body,
    icon: payload.icon,
    badge: "/icons/icon-192.png",
    data: { url: payload.url },
  });
}

function safePayloadText(data: PushMessageData | null): string | null {
  if (!data) return null;
  try {
    return data.text();
  } catch {
    return null;
  }
}

self.addEventListener("push", (event) => {
  event.waitUntil(showPushNotification(safePayloadText(event.data)));
});

// Test seam: lets E2E tests exercise the exact push-notification path
// without a push service (real push events cannot be injected portably).
self.addEventListener("message", (event) => {
  const d: unknown = event.data;
  if (
    typeof d === "object" &&
    d !== null &&
    (d as Record<string, unknown>).type === "lidaldi:simulate-push"
  ) {
    const payload = (d as Record<string, unknown>).payload;
    event.waitUntil(
      showPushNotification(typeof payload === "string" ? payload : null)
    );
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = notificationTargetUrl(event.notification.data);
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });
      for (const client of windows) {
        if (new URL(client.url).origin === self.location.origin) {
          try {
            await client.focus();
            await client.navigate(url);
            return;
          } catch {
            // e.g. navigate() may reject for uncontrolled clients —
            // fall through to openWindow.
          }
        }
      }
      await self.clients.openWindow(url);
    })()
  );
});
