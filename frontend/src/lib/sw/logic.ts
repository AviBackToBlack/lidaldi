// Pure service-worker logic, extracted for Vitest coverage. No DOM/Worker
// globals here — sw.ts wires these into the actual event handlers.

/** Push payload contract frozen by T3 (send_notifications.build_payload). */
export interface PushPayload {
  title: string;
  body: string;
  /** same-origin path, e.g. "/?view=alerts&alert=<alertId>" */
  url: string;
  /** same-origin icon path */
  icon: string;
}

export const FALLBACK_PAYLOAD: PushPayload = {
  title: "LidAldi Alert",
  body: "You have new alert matches.",
  url: "/?view=alerts",
  icon: "/icons/icon-192.png",
};

function samePath(v: unknown, fallback: string): string {
  return typeof v === "string" && v.startsWith("/") && !v.startsWith("//")
    ? v
    : fallback;
}

/**
 * Parse a raw push payload. Never throws (N6): invalid JSON, non-object
 * payloads, or missing/unsafe fields degrade to FALLBACK_PAYLOAD values so a
 * notification is always shown.
 */
export function parsePushPayload(raw: string | null): PushPayload {
  if (raw === null || raw === "") return { ...FALLBACK_PAYLOAD };
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ...FALLBACK_PAYLOAD };
  }
  if (typeof parsed !== "object" || parsed === null) {
    return { ...FALLBACK_PAYLOAD };
  }
  const p = parsed as Record<string, unknown>;
  return {
    title:
      typeof p.title === "string" && p.title !== ""
        ? p.title
        : FALLBACK_PAYLOAD.title,
    body: typeof p.body === "string" ? p.body : FALLBACK_PAYLOAD.body,
    url: samePath(p.url, FALLBACK_PAYLOAD.url),
    icon: samePath(p.icon, FALLBACK_PAYLOAD.icon),
  };
}

/** Click target from a Notification's data (set by the push handler). */
export function notificationTargetUrl(data: unknown): string {
  if (typeof data === "object" && data !== null) {
    return samePath((data as Record<string, unknown>).url, FALLBACK_PAYLOAD.url);
  }
  return FALLBACK_PAYLOAD.url;
}

export type FetchKind = "navigation" | "data" | "static" | "passthrough";

const DATA_PATHS = new Set(["/offers.json", "/meta.json"]);
const STATIC_PREFIXES = ["/assets/", "/icons/", "/img/"];

/**
 * Caching strategy per request: navigations and offers/meta data are
 * network-first (no stale offers); hashed build assets, icons and the
 * manifest are cache-first; everything else passes through untouched.
 */
export function classifyRequest(pathname: string, mode: string): FetchKind {
  if (mode === "navigate") return "navigation";
  if (DATA_PATHS.has(pathname)) return "data";
  if (pathname === "/manifest.json") return "static";
  if (STATIC_PREFIXES.some((p) => pathname.startsWith(p))) return "static";
  return "passthrough";
}
