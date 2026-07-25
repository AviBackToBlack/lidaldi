# LIDALDI — Claude Design Brief (T0)

**For the operator:** paste this brief into Claude Design (claude.ai), iterate until you like the look, then export/commit the results to `frontend/design/` on the `refactor` branch (any of: HTML+CSS mockups, a design-tokens CSS file, component screenshots). The front-end worker will translate them into Svelte components. Until exports land, the app is built on a neutral `tokens.css` — your design becomes a token/markup swap.

---

## What the product is

**LIDALDI** — a single-page site showing this week's special (non-food) offers from ALDI.IE and LIDL.IE, merged into one browsable grid. Public, no login. Daily data refresh. Audience: Irish bargain hunters on desktop and mobile.

## Page structure (fixed — design the look, not the layout logic)

1. **Header**: logo (existing mascot `website/img/lidaldi.png`), title "ALDI.IE & LIDL.IE Special Offers", two small metadata lines: "Last updated: <date>" and "Your last visit: <date>".
2. **Single-row filter bar** (wraps on mobile):
   - Store segmented control: **Both / ALDI / LIDL** (new feature — give ALDI and LIDL each a recognizable accent; ALDI ≈ blue/orange, LIDL ≈ blue/yellow/red, without infringing logos)
   - Availability buttons: All · Available now · New from last visit · date chips for upcoming availability dates
   - Category dropdown · Price from/to inputs · Sort dropdown · Search box · Reset button · **Alerts** button (bell icon)
3. **Product grid**: responsive cards (image, title, price, store badge, availability date). Hover/long-press shows a description popover.
4. **Pagination row** at the bottom (numbered pages, prev/next). Arrow keys flip pages.
5. **Footer**: disclaimer + GitHub link.
6. **Alerts & Sync modal**: sync-code section, push-notification enable, keyword-alert list + add form.
7. **Alerts view** (new): a filtered state showing products that matched a user's alert (entered from a push notification).

## Design goals

- Modern, clean, friendly "deal-hunting" energy; not corporate. Light theme primary; dark theme welcome if cheap.
- Cards are the hero: strong price typography, clear store identity per card, subtle "NEW" badge for new-since-last-visit items, "price unknown" badge style for N/A prices.
- Filter bar must stay compact and scannable; it currently looks like unstyled 2010 form controls — this is the biggest visual lift.
- Obvious keyboard focus states (`:focus-visible`) — accessibility is in scope.
- Mobile: filter bar collapses gracefully; grid 1–2 columns; touch-friendly hit areas.
- PWA: pick an accent/theme color usable in `manifest.json`.

## Constraints

- Static site, vanilla CSS output preferred (CSS custom properties as design tokens: colors, spacing, radii, type scale). No CSS frameworks required.
- Keep the five existing ideas intact (filter row, last-updated/last-visit info, auto-fit grid + pager, description popover, alerts/push) — restyle, don't remove.
- System font stack or one free Google font max.
- Images come from retailers at ~306px width — cards should look good with mediocre imagery.

## Deliverables to commit

- `frontend/design/tokens.css` — the design tokens
- `frontend/design/mockup.html` (+ CSS) — desktop + mobile mockup of the main page, and the alerts modal
- optional: screenshots of any additional states (popover, alerts view, empty states)
