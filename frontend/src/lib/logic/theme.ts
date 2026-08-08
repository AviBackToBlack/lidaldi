// Theme persistence per the design mockup: cookie (1 yr) so a static
// server could also read it; falls back to the OS preference. The
// pre-paint script in index.html applies it before first render.

export type Theme = "light" | "dark";

export function readThemeCookie(cookie: string): Theme | null {
  const m = cookie.match(/(?:^|;\s*)lidaldi_theme=(light|dark)/);
  return m ? (m[1] as Theme) : null;
}

export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  if (theme === "dark") {
    document.documentElement.dataset.theme = "dark";
  } else {
    delete document.documentElement.dataset.theme;
  }
  const secure = location.protocol === `https:` ? `; Secure` : ``;
  document.cookie = `lidaldi_theme=${theme}; path=/; max-age=31536000; SameSite=Lax${secure}`;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "dark" ? "#e6624a" : "#d9542f");
}
