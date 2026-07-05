// Alerts state shape (T5): local persistence + tombstoned deletes.
// The alerts UI (modal, AlertsView) is T6.

import type { Alert, Tombstone } from "../sync/client";

const ALERTS_STORAGE_KEY = "lidaldi_alerts";
const TOMBSTONES_STORAGE_KEY = "lidaldi_alert_tombstones";

function loadArray<T>(key: string): T[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(key) ?? "[]");
    return Array.isArray(parsed) ? (parsed as T[]) : [];
  } catch {
    return [];
  }
}

export class AlertsStore {
  alerts = $state<Alert[]>([]);
  tombstones = $state<Tombstone[]>([]);

  init(): void {
    this.alerts = loadArray<Alert>(ALERTS_STORAGE_KEY);
    this.tombstones = loadArray<Tombstone>(TOMBSTONES_STORAGE_KEY);
  }

  setAlerts(alerts: Alert[]): void {
    this.alerts = alerts;
    localStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(alerts));
  }

  setTombstones(tombstones: Tombstone[]): void {
    this.tombstones = tombstones;
    localStorage.setItem(TOMBSTONES_STORAGE_KEY, JSON.stringify(tombstones));
  }

  add(keyword: string, matchType: Alert["matchType"], now = Math.floor(Date.now() / 1000)): Alert | null {
    const kw = keyword.trim();
    if (!kw) return null;
    const idArr = new Uint8Array(8);
    crypto.getRandomValues(idArr);
    const id = Array.from(idArr, (b) => b.toString(16).padStart(2, "0")).join("");
    const alert: Alert = { id, keyword: kw, matchType, createdAt: now };
    this.setAlerts([...this.alerts, alert]);
    return alert;
  }

  delete(id: string, now = Math.floor(Date.now() / 1000)): void {
    const removed = this.alerts.find((a) => a.id === id);
    this.setAlerts(this.alerts.filter((a) => a.id !== id));
    if (removed) {
      this.setTombstones([...this.tombstones, { id: removed.id, at: now }]);
    }
  }
}

export const alerts = new AlertsStore();
