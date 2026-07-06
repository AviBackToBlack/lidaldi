// Sync-code entry normalization (N11). The generator's alphabet
// (sync/client.ts) deliberately omits typo-confusable characters:
// 0, 1, I, O, i, l, o. Entry accepts display formatting (whitespace,
// dash grouping) and case-folds confusables that have exactly one
// plausible emitted counterpart; anything else the generator can never
// emit is rejected instead of silently accepted.

const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";
const ALPHABET_SET = new Set(ALPHABET);

// Confusables → the only emitted character they can plausibly be a
// misreading of. "I", "l" and "1" all render like the emitted "L" family
// glyphs never do — but "L" IS emitted, so map them to "L".
// "0", "O" and "o" have no emitted lookalike (both O-forms are excluded
// and no emitted glyph resembles them), so they stay unmappable and any
// code containing them is rejected.
const CONFUSABLE_MAP: Record<string, string> = {
  I: "L",
  l: "L",
  "1": "L",
};

export interface NormalizedSyncCode {
  ok: boolean;
  /** normalized code when ok */
  code: string;
  /** true when normalization changed at least one character */
  changed: boolean;
}

export function normalizeSyncCode(input: string): NormalizedSyncCode {
  const stripped = input.replace(/[\s-]+/g, "");
  let out = "";
  let changed = false;
  for (const ch of stripped) {
    const mapped = CONFUSABLE_MAP[ch];
    if (mapped !== undefined) {
      out += mapped;
      changed = true;
      continue;
    }
    if (!ALPHABET_SET.has(ch)) {
      return { ok: false, code: "", changed: false };
    }
    out += ch;
  }
  if (out.length < 6 || out.length > 8) {
    return { ok: false, code: "", changed: false };
  }
  return { ok: true, code: out, changed };
}
