// Sync state: sync code + lastVisit with the Q1/N1 semantics
// (once-per-session advance; never adopt a newer server lastVisit).

import {
  adoptServerLastVisit,
  browserLastVisitStorage,
  initLastVisit,
  type LastVisitStorage,
} from "../logic/lastvisit";
import { isValidSyncCode } from "../sync/client";

const SYNC_STORAGE_KEY = "lidaldi_sync_code";

export class SyncStore {
  code = $state("");
  /** effective lastVisit (unix seconds) for newness comparisons */
  lastVisit = $state(0);
  /** value read at boot — upper bound for server adoption (N1 guard) */
  bootLastVisit = 0;
  /** this page load's visit timestamp, POSTed to the sync server */
  nowTimestamp = 0;

  /** Boot-time init; call once on app start. */
  init(storage: LastVisitStorage = browserLastVisitStorage(), now = Math.floor(Date.now() / 1000)): void {
    this.code = localStorage.getItem(SYNC_STORAGE_KEY) ?? "";
    this.nowTimestamp = now;
    const boot = initLastVisit(storage, now);
    this.bootLastVisit = boot.lastVisit;
    this.lastVisit = boot.lastVisit;
  }

  /** Apply a lastVisit from a sync-server reply (guarded, N1). */
  adoptServer(serverLastVisit: unknown): void {
    this.lastVisit = adoptServerLastVisit(this.bootLastVisit, serverLastVisit);
  }

  setCode(code: string): boolean {
    if (!isValidSyncCode(code)) return false;
    this.code = code;
    localStorage.setItem(SYNC_STORAGE_KEY, code);
    return true;
  }

  clearCode(): void {
    this.code = "";
    localStorage.removeItem(SYNC_STORAGE_KEY);
  }
}

export const sync = new SyncStore();
