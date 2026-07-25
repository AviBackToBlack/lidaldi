# website/ — LEGACY frontend (frozen for cutover)

This directory is the pre-refactor frontend: `index.html.tpl` (rendered by
`process_offers.py` each run), `js/lidaldi.js`, `css/`, `sw.js`, `404.html`.

**Status: frozen.** It receives no new features or fixes. It remains in the
repo — and `process_offers.py` still renders `index.html` from the template —
only so production keeps working until the cutover to the new
Vite + Svelte 5 frontend in `frontend/` (migration rehearsal T15 and
Hard Stop #2 sign-off gate the switch). After cutover this directory and the
legacy rendering path will be removed.

Do not base new work on this code; the replacement lives in `frontend/`.
