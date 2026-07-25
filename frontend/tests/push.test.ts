import { describe, expect, it } from "vitest";
import { urlBase64ToUint8Array } from "../src/lib/push";

describe("urlBase64ToUint8Array", () => {
  it("decodes url-safe base64 without padding (VAPID key format)", () => {
    // "Hello" -> SGVsbG8 (unpadded)
    expect(Array.from(urlBase64ToUint8Array("SGVsbG8"))).toEqual([
      72, 101, 108, 108, 111,
    ]);
  });

  it("maps url-safe characters (- and _) to their base64 values", () => {
    // 0xfb 0xff 0xbf encodes to "-_-_" in url-safe base64
    expect(Array.from(urlBase64ToUint8Array("-_-_"))).toEqual([251, 255, 191]);
  });

  it("round-trips a 65-byte uncompressed P-256 point (VAPID key length)", () => {
    const bytes = new Uint8Array(65).map((_, i) => (i * 7) % 256);
    let bin = "";
    for (const b of bytes) bin += String.fromCharCode(b);
    const b64 = btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
    expect(Array.from(urlBase64ToUint8Array(b64))).toEqual(Array.from(bytes));
  });
});
