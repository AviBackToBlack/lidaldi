import { describe, expect, it } from "vitest";
import { groupAlertMatches } from "../src/lib/logic/alertmatches";
import type { Alert, AlertMatches } from "../src/lib/sync/client";
import { makeOffer } from "./helpers";

const alertA: Alert = { id: "a1", keyword: "drill", matchType: "anyWord", createdAt: 1 };
const alertB: Alert = { id: "b2", keyword: "tent", matchType: "exact", createdAt: 2 };

describe("groupAlertMatches (AlertsView data)", () => {
  it("joins matches to offers by id, newest match first", () => {
    const offers = [makeOffer({ id: "x" }), makeOffer({ id: "y" })];
    const matches: AlertMatches = {
      a1: [
        { id: "x", at: 10 },
        { id: "y", at: 20 },
      ],
    };
    const groups = groupAlertMatches([alertA], matches, offers);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.offers.map((o) => o.id)).toEqual(["y", "x"]);
    expect(groups[0]!.expiredCount).toBe(0);
  });

  it("counts matches whose offers are no longer listed", () => {
    const matches: AlertMatches = {
      a1: [
        { id: "gone", at: 5 },
        { id: "x", at: 6 },
      ],
    };
    const groups = groupAlertMatches([alertA], matches, [makeOffer({ id: "x" })]);
    expect(groups[0]!.offers.map((o) => o.id)).toEqual(["x"]);
    expect(groups[0]!.expiredCount).toBe(1);
  });

  it("returns a group for every alert, even without matches", () => {
    const groups = groupAlertMatches([alertA, alertB], {}, []);
    expect(groups.map((g) => g.alert.id)).toEqual(["a1", "b2"]);
    expect(groups.every((g) => g.offers.length === 0)).toBe(true);
  });
});
