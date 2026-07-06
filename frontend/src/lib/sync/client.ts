// Thin HTTP client for the sync API — port of the legacy syncFetch/syncPost
// (website/js/lidaldi.js) with the same validation posture.

export interface Alert {
  id: string;
  keyword: string;
  matchType: "exact" | "allWords" | "anyWord";
  createdAt: number;
}

export interface Tombstone {
  id: string;
  at: number;
}

/** alert id → matched offers; written only by the server (T3 contract). */
export type AlertMatches = Record<string, { id: string; at: number }[]>;

export interface SyncData {
  lastVisit?: number;
  alerts?: Alert[];
  tombstones?: Tombstone[];
  alertMatches?: AlertMatches;
}

export interface SyncPostBody {
  lastVisit: number;
  alerts: Alert[];
  deletedAlertIds?: Tombstone[];
  pushSubscription?: unknown;
}

export async function syncFetch(code: string): Promise<SyncData | null> {
  try {
    const r = await fetch(`/api/sync/${encodeURIComponent(code)}`, {
      cache: "no-store",
    });
    if (!r.ok) return null;
    return (await r.json()) as SyncData;
  } catch (e) {
    console.warn("Sync fetch failed:", e);
    return null;
  }
}

export async function syncPost(
  code: string,
  lastVisit: number,
  alerts: Alert[],
  tombstones: Tombstone[],
  pushSubscription?: unknown
): Promise<SyncData | null> {
  try {
    const body: SyncPostBody = { lastVisit, alerts };
    if (tombstones.length) body.deletedAlertIds = tombstones;
    if (pushSubscription) body.pushSubscription = pushSubscription;
    const r = await fetch(`/api/sync/${encodeURIComponent(code)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    if (!r.ok) return null;
    try {
      return (await r.json()) as SyncData;
    } catch {
      return null;
    }
  } catch (e) {
    console.warn("Sync post failed:", e);
    return null;
  }
}

const SYNC_CODE_ALPHABET =
  "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";

/** 8-char sync code via rejection sampling (no modulo bias) — legacy port. */
export function generateSyncCode(): string {
  let code = "";
  const limit = 256 - (256 % SYNC_CODE_ALPHABET.length);
  const arr = new Uint8Array(8);
  crypto.getRandomValues(arr);
  for (let i = 0; i < 8; i++) {
    let r = arr[i]!;
    while (r >= limit) {
      const tmp = new Uint8Array(1);
      crypto.getRandomValues(tmp);
      r = tmp[0]!;
    }
    code += SYNC_CODE_ALPHABET[r % SYNC_CODE_ALPHABET.length];
  }
  return code;
}

export function isValidSyncCode(code: string): boolean {
  return /^[A-Za-z0-9]{6,8}$/.test(code);
}
