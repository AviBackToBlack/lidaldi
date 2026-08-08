/**
 * Last-visit semantics (Q1 default + Bug #2/N1 client half), pure logic:
 *
 * - lastVisit advances at most once per browser session (sessionStorage
 *   guard). Within a session (reloads included) the effective lastVisit
 *   stays frozen at the value read at the session's first load, so "New"
 *   badges don't vanish on reload.
 * - The client NEVER adopts a server lastVisit newer than the value it
 *   read at boot — this kills the same-load POST(now)->GET->adopt
 *   self-race (N1) while keeping cross-device sync for older values.
 */

export interface LastVisitStorage {
  /** persistent lastVisit (unix seconds), 0/absent if never visited */
  getPersistent(): number;
  setPersistent(ts: number): void;
  /** session-scoped snapshot of lastVisit at session start; null if unset */
  getSessionBoot(): number | null;
  setSessionBoot(ts: number): void;
}

export interface LastVisitBoot {
  /** effective lastVisit for newness comparisons this session */
  lastVisit: number;
  /** true if this call advanced the persistent value */
  advanced: boolean;
}

/**
 * Boot-time initialization. First load of a session snapshots the stored
 * value into session scope and advances the persistent value to `now`;
 * subsequent loads in the same session reuse the snapshot and do not
 * advance again.
 */
export function initLastVisit(storage: LastVisitStorage, now: number): LastVisitBoot {
  const sessionBoot = storage.getSessionBoot();
  if (sessionBoot !== null) {
    return { lastVisit: sessionBoot, advanced: false };
  }
  const persisted = storage.getPersistent();
  storage.setSessionBoot(persisted);
  storage.setPersistent(now);
  return { lastVisit: persisted, advanced: true };
}

/**
 * Decide whether to adopt a lastVisit value from the sync server.
 * Returns the new effective lastVisit.
 *
 * - invalid/non-positive server values are ignored;
 * - a first-visit client (boot value 0) adopts the server value so items
 *   already seen on another device are not re-shown as new;
 * - otherwise only server values NOT newer than the boot value are
 *   adopted (N1 guard).
 */
export function adoptServerLastVisit(bootLastVisit: number, serverLastVisit: unknown): number {
  const server =
    typeof serverLastVisit === "number" && Number.isFinite(serverLastVisit)
      ? Math.floor(serverLastVisit)
      : 0;
  if (server <= 0) return bootLastVisit;
  if (bootLastVisit <= 0) return server;
  return server <= bootLastVisit ? server : bootLastVisit;
}

const PERSISTENT_KEY = "lastVisit";
// snyk:ignore:Hardcoded Non-Cryptographic Secret  // false positive: sessionStorage key name, not a secret
const SESSION_KEY = "lidaldi_session_last_visit";

/** Browser-backed storage: localStorage + sessionStorage, cookie fallback read. */
export function browserLastVisitStorage(): LastVisitStorage {
  return {
    getPersistent() {
      const v = localStorage.getItem(PERSISTENT_KEY);
      if (v !== null) {
        const n = Number.parseInt(v, 10);
        if (Number.isFinite(n) && n > 0) return n;
      }
      // Migration: the legacy UI stored lastVisit in a cookie.
      const m = (document.cookie || "").match(/(?:^|;\s*)lastVisit=(\d+)/);
      if (m && m[1]) {
        const n = Number.parseInt(m[1], 10);
        if (Number.isFinite(n) && n > 0) return n;
      }
      return 0;
    },
    setPersistent(ts: number) {
      localStorage.setItem(PERSISTENT_KEY, String(ts));
    },
    getSessionBoot() {
      const v = sessionStorage.getItem(SESSION_KEY);
      if (v === null) return null;
      const n = Number.parseInt(v, 10);
      return Number.isFinite(n) && n >= 0 ? n : null;
    },
    setSessionBoot(ts: number) {
      sessionStorage.setItem(SESSION_KEY, String(ts));
    },
  };
}
