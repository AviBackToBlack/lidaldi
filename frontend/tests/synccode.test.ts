import { describe, expect, it } from "vitest";
import { normalizeSyncCode } from "../src/lib/logic/synccode";
import { generateSyncCode } from "../src/lib/sync/client";

describe("normalizeSyncCode (N11)", () => {
  it("accepts codes the generator emits, unchanged", () => {
    for (let i = 0; i < 20; i++) {
      const code = generateSyncCode();
      expect(normalizeSyncCode(code)).toEqual({
        ok: true,
        code,
        changed: false,
      });
    }
  });

  it("strips display whitespace and dashes", () => {
    expect(normalizeSyncCode(" AB CD-EF GH ")).toEqual({
      ok: true,
      code: "ABCDEFGH",
      changed: false,
    });
  });

  it("normalizes I/l/1 to the emitted L", () => {
    expect(normalizeSyncCode("ABCDEFGI")).toEqual({
      ok: true,
      code: "ABCDEFGL",
      changed: true,
    });
    expect(normalizeSyncCode("ABCDEFG1")).toEqual({
      ok: true,
      code: "ABCDEFGL",
      changed: true,
    });
    expect(normalizeSyncCode("ABCDEFGl")).toEqual({
      ok: true,
      code: "ABCDEFGL",
      changed: true,
    });
  });

  it("rejects unmappable confusables the generator never emits (0/O/o)", () => {
    expect(normalizeSyncCode("ABCDEFG0").ok).toBe(false);
    expect(normalizeSyncCode("ABCDEFGO").ok).toBe(false);
    expect(normalizeSyncCode("ABCDEFGo").ok).toBe(false);
  });

  it("rejects non-alphabet characters and bad lengths", () => {
    expect(normalizeSyncCode("ABC$EFGH").ok).toBe(false);
    expect(normalizeSyncCode("ABCDE").ok).toBe(false);
    expect(normalizeSyncCode("ABCDEFGHJ").ok).toBe(false);
    expect(normalizeSyncCode("").ok).toBe(false);
  });
});
