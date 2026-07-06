// AlertsView data shaping: join the read-only alertMatches map from
// GET /api/sync/{code} (T3/T4 contract) with the loaded offers.json
// items by stable product id.

import type { Offer } from "../types";
import type { Alert, AlertMatches } from "../sync/client";

export interface AlertMatchGroup {
  alert: Alert;
  /** matched offers still present in offers.json, newest match first */
  offers: Offer[];
  /** matches whose product id is no longer in offers.json */
  expiredCount: number;
}

export function groupAlertMatches(
  alerts: readonly Alert[],
  matches: AlertMatches,
  offers: readonly Offer[]
): AlertMatchGroup[] {
  const byId = new Map(offers.map((o) => [o.id, o]));
  return alerts.map((alert) => {
    const entries = [...(matches[alert.id] ?? [])].sort((a, b) => b.at - a.at);
    const found: Offer[] = [];
    let expiredCount = 0;
    for (const m of entries) {
      const offer = byId.get(m.id);
      if (offer) found.push(offer);
      else expiredCount++;
    }
    return { alert, offers: found, expiredCount };
  });
}
