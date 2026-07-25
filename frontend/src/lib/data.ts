import { parseMeta, parseOffers, type Meta, type Offer } from "./types";

async function fetchJson(path: string): Promise<unknown> {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) {
    throw new Error(`${path}: HTTP ${r.status}`);
  }
  return r.json();
}

export async function loadOffers(): Promise<Offer[]> {
  return parseOffers(await fetchJson("/offers.json"));
}

export async function loadMeta(): Promise<Meta> {
  return parseMeta(await fetchJson("/meta.json"));
}
