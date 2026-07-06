import { describe, expect, it } from "vitest";
import { readThemeCookie } from "../src/lib/logic/theme";

describe("readThemeCookie", () => {
  it("reads the theme value out of a cookie header", () => {
    expect(readThemeCookie("lidaldi_theme=dark")).toBe("dark");
    expect(readThemeCookie("a=b; lidaldi_theme=light; c=d")).toBe("light");
  });

  it("ignores unknown values and missing cookies", () => {
    expect(readThemeCookie("lidaldi_theme=blue")).toBeNull();
    expect(readThemeCookie("other=dark")).toBeNull();
    expect(readThemeCookie("")).toBeNull();
  });
});
