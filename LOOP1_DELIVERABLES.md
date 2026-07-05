# LIDALDI Refactor — Loop 1 Deliverables (Requirements & Design)

**Status:** awaiting Hard Stop #1 sign-off ("GO for Loop 2")
**Produced by:** orchestrator session, 2026-07-05
**Basis:** full read of every source file in the repo (`refactor` branch, all ~4,550 LOC), `REFACTOR_RESEARCH_AND_ARCHITECTURE.md` (v3), `REFACTOR_OPERATOR_RUNBOOK.md`, Devin Knowledge.

---

## 1. Codebase analysis — architecture-doc §2 findings, confirmed/corrected with evidence

Every §2 claim was checked against the actual code. Verdicts:

| Arch-doc claim | Verdict | Evidence |
|---|---|---|
| Structure & data flow (cron → spiders → process_offers → send_notifications; inline JSON blocks; sync-code profiles) | **Confirmed** | `scraper/run_scrapers.sh` (sequential chain, per-step `timeout`, `set -euo pipefail`); `website/index.html.tpl:132-137` (two `<script type="application/json">` blocks); `offers_processing/sync_store.py:83-117` (fcntl-locked RMW) |
| `lidaldi.js` is 1,311 lines | **Confirmed** | `wc -l` = 1311 |
| Bug #1 root cause: `getDynamicPageSize()` measures live DOM + string-parses `grid-template-columns` | **Confirmed** | `website/js/lidaldi.js:612-644`: `offsetHeight` of header/filters/pagination/footer, sample-card fallback `320` (l.632), `templateColumns.split(/\s+/).length` (l.641). Also un-debounced full re-render on every `resize` event (l.646-648) |
| Bug #2 root cause: `scraped_at`-based newness + cookie overwritten on load + sync adopts server lastVisit | **Confirmed, and worse than described** | Cookie overwritten at l.340-341; newness = `scraped_at > lastVisitTimestamp` (l.306-307, l.677). **Self-race found:** `initAsync()` POSTs `nowTimestamp` first (l.1240), then GETs (l.1242) and adopts the server's `lastVisit` (l.1245-1246) — which the server just set to `max(existing, now) = now` (`sync_server.py:318`). So on any synced device the "new" window collapses to empty **within the same page load**. This alone fully explains the symptom. |
| Bug #3 root cause: keydown handler bails when a filter button/select retains focus | **Confirmed** | `lidaldi.js:1175-1217`, early `return` for `input/textarea/select/button` (l.1195-1203). Filter buttons keep focus after click (no `blur()`), so Left/Right die until user clicks empty space |
| Bug #4 root cause: payload URL = first match's third-party URL | **Confirmed** | `send_notifications.py:201-215` (`first = matches[0]`, `"url": first.get("url")`); `sw.js:18-23` (`clients.openWindow(data.url)`) |
| Config/sample gap (§2.3) | **Confirmed, with a live specimen** | `.gitignore` excludes `settings.py`/`config.py`; `config.sample.py:35-36` still ships `INDEX_NEW_HTML`/`INDEX_OLD_HTML` keys that no code references anymore (legacy of the removed two-step rename, cf. `process_offers.py:407-413`) — exactly the schema-drift class the merge tool must handle |
| Security posture decent; preserve it | **Confirmed** | `safe_json_for_script` (`process_offers.py:48-57`), URL allow-listing client-side (`lidaldi.js:35-37, 816-819`) and spider-side (`lidl_spider.py:107-114`), rejection-sampled sync codes (`lidaldi.js:131-148`), input validation + rate limiting (`sync_server.py:96-148, 55-74`), hardened systemd unit, VAPID key file perms |
| POSIX-only sync stack | **Confirmed** | `sync_store.py:16-22` hard-fails without `fcntl` |
| Tooltip is a 1s `setTimeout` + `blur()` side effect | **Confirmed** | `lidaldi.js:42-57` — `startTooltipTimer` blurs any focused `INPUT` (l.44-46), a focus-model hack that interacts with Bug #3 |
| Data/push continuity risk (VAPID reuse, profile-store backup) | **Confirmed** | Subscriptions live per-profile (`sync_server.py:327-332`); push signing uses the on-disk PEM (`send_notifications.py:46-66`). New keys would 410 every subscriber. |

**Correction of note:** the arch doc says the front-end "reads offers from two inline JSON blocks the template renders" — true, but it also means **every scrape rewrites the whole `index.html`** (`process_offers.py:374-413`), coupling content deploys to data runs. The redesign should decouple (see deviation D2).

---

## 2. Bug-discovery report (dedicated pass — known 4 + newly found, triaged)

### Known bugs (all confirmed, root-caused above)
| # | Severity | Fix direction (per spec §2.2, validated) |
|---|---|---|
| 1 | High | Delete JS measurement; CSS-first grid (`auto-fill/minmax` already exists in CSS) + fixed/responsive page size |
| 2 | High | Server-side `first_seen` per product; deliberate last-visit advance; kill the POST-then-adopt self-race |
| 3 | Medium | Roving-tabindex pager; blur-after-act on filter buttons; suppress arrows only where they have native meaning |
| 4 | Medium | Aggregate payload with alert id; `/?view=alerts&alert=<id>` deep link; alerts view as first-class filter state |

### Newly discovered (pre-existing) bugs — triaged
| ID | Severity | Finding | Evidence | Disposition |
|---|---|---|---|---|
| N1 | **High** | Bug #2 self-race: same-load POST(now) → GET → adopt collapses "new" window (detailed above). A distinct mechanism from the cookie overwrite; must be fixed explicitly or `first_seen` alone won't cure symptom on synced devices | `lidaldi.js:1240-1246`, `sync_server.py:318` | Fix in-scope (part of Bug #2 task) |
| N2 | Medium | Two inconsistent "new" definitions: notifications use URL-set diff (`process_offers.py:325-337`) while the UI uses `scraped_at > lastVisit` (`lidaldi.js:677`). A product can be push-notified yet not marked "New", and vice-versa | cited | Fix in-scope (unified by `first_seen`) |
| N3 | Medium | `scraped_at` continuity is keyed by exact URL (`aldi_spider.py:149`, `lidl_spider.py:192`); ALDI URLs embed slug+SKU — any slug change resurrects the item as "new" and re-notifies (URL-diff too) | cited | Fix in-scope: key identity by SKU/canonical id where possible; `first_seen` store server-side |
| N4 | Medium | `render()` rebuilds `categorySelect.innerHTML` on every render (`lidaldi.js:767-794`) — resets an open dropdown mid-interaction and contributes to the focus mess; every keystroke in search triggers full grid rebuild (no debounce/vDOM) | cited | Fixed by framework rewrite |
| N5 | Medium | Per-alert delivery ledger marks an alert "notified" if **any** subscription got it (`send_notifications.py:256-270`); a user's other device that transiently 5xx'd never gets that alert again | cited | Fix in-scope (ledger per endpoint or per sub) |
| N6 | Low | `sw.js:7` — `event.data.json()` throws on non-JSON payload, killing the push event (no notification shown; browsers may penalize the subscription) | cited | Fix in rewrite (try/catch) |
| N7 | Low | Year-rollover heuristic in `parse_store_availability` (`process_offers.py:93-97, 109-116`) only handles Nov→Feb; a "From 05.03" seen in December is misclassified as past ("While Stock Lasts") | cited | Fix in-scope (small) |
| N8 | Low | Price filter passes all unparsable prices (`applyFilters`, `lidaldi.js:694-707`) — "N/A" items ignore the user's price range | cited | Keep-or-fix: decide at design (proposed: keep, but badge as "price unknown") |
| N9 | Low | Pager renders one button per page with no windowing (`lidaldi.js:904-921`) — degrades with many pages | cited | Fixed by new pager design |
| N10 | Low | `render()` appends `bottom` to `card` then moves it into `link` (`lidaldi.js:871-876`) — works by accident of `appendChild` move semantics | cited | Dies in rewrite |
| N11 | Low | Sync-code entry accepts chars the generator never emits (regex `[A-Za-z0-9]{6,8}` vs 55-char alphabet, `lidaldi.js:132` vs `1009`) — typo-confusable codes (0/O, 1/l) accepted silently | cited | Low; normalize on entry in rewrite |
| N12 | Low | Dead code: `middlewares.py` (boilerplate, unused), `items.py` (empty), unused `remove_query()` in both spiders, unused config keys (§1 above) | cited | Remove in rewrite |
| N13 | Info | Image GC (`run_scrapers.sh` `find -mtime +90 -delete`) vs `IMAGES_EXPIRES = 90` — an offer live >90 days has a window where its image is deleted before re-download | cited | Log only (rare); tighten in installer task if cheap |
| N14 | Info | Sync GET is auth'd only by the code (~46 bits entropy) with 30 req/min/IP rate limit — acceptable for this data class; document as accepted risk | `sync_server.py:32-36` | Log only |

**Regression discovery (Loop 2 side):** fresh-context QA/verifier agents + full test suite (Playwright incl. WebKit, visual snapshots per engine) gate every merge — see DAG T12.

---

## 3. Toolchain validation & proposed deviations (§3.1/§3.2)

Verified against the primitives actually available in this run (Multi-Devin `devin_session_create/gather/interact`, Playbooks, Knowledge — all live) and current ecosystem state.

**Endorsed as-is:** Svelte-family front-end with static build (no SSR) · TOML/.env config (stdlib `tomllib`) · Playwright (Chromium/Firefox/**WebKit**) + visual snapshots · pytest + Vitest · Docker Compose + DevContainer, one `make test` · k6 for sync-API load · installer design per §6.5 · two-tier topology, 3–4 workers, cheap models on workers.

**Proposed deviations (approve/reject each at this hard stop):**

- **D1 — Vite + Svelte 5, no SvelteKit.** The app is a single page with query-string state; SvelteKit's router/adapter machinery adds concepts (routes, `+page` conventions, adapter config) without benefit here. Plain Vite + Svelte 5 emits the same static assets with less framework surface, and History-API state (§7.1) is ~30 lines. Tradeoff: forgoes Kit conveniences if the site ever grows multi-page. **Recommend D1**; SvelteKit `adapter-static` remains a fine fallback.
- **D2 — Serve offers as `offers.json`, stop rendering `index.html` per scrape.** Today every cron run rewrites the whole HTML (`process_offers.py:374-413`), coupling app deploys to data runs and making the template a merge hazard. Instead: `index.html` becomes a pure build artifact; `process_offers.py` writes `offers.json` (+ `meta.json`) to the web root; the SPA fetches them (cacheable, `Cache-Control` friendly). VAPID public key moves to `meta.json`. Simplifies the installer (app deploy ≠ data write) and testing. Tradeoff: one extra request on load (mitigable via preload link).
- **D3 — Python ≥ 3.11 floor** (from the current ≥3.9) so TOML parsing is stdlib `tomllib` — no new dependency. Ubuntu LTS ships ≥3.10/3.12; the VPS target satisfies this.
- **D4 — Security tier = `pip-audit` + `bandit` + `npm audit` in CI on every run; OWASP ZAP baseline as an opt-in profile** (`make test-zap`), not in the default gate. ZAP adds minutes and flake for a mostly-static site; the real protections (escaping, allow-listing) get locked by targeted unit/E2E tests instead.
- **D5 — Alert/notification identity: extend `first_seen` store with a stable product id** (ALDI SKU; LIDL canonical path) so slug churn can't re-notify (N3). Slightly larger backend task than the doc's `first_seen`-only wording.

Claude Design mandate (§3.11) acknowledged — see §5 (design brief is a Loop-2 kickoff artifact; front-end is built against committed exports). Model routing: workers on Sonnet-class; free SWE-1.6 for mechanical tasks (docs sweep, config plumbing); Fable 5 reserved for orchestration/verification.

---

## 4. Target design (architecture & module structure)

```
lidaldi/
├── frontend/                  # Vite + Svelte 5 (D1) → builds to static dist/
│   ├── src/lib/stores/        # filters, paging, sync, alerts, push (runes/stores)
│   ├── src/lib/components/    # FilterBar (incl. StoreFilter ALDI/LIDL/Both), Grid,
│   │                          # Card, Popover (native Popover API), Pager (roving tabindex),
│   │                          # AlertsModal, AlertsView (deep-link target)
│   ├── src/lib/urlstate.ts    # History API <-> store bridge (§7.1)
│   ├── public/ (manifest.json, icons, sw.js)
│   └── tests/ (Vitest unit)
├── backend/  (renamed offers_processing/, same runtime posture)
│   ├── config.toml.sample + config.py loader (tomllib + .env for secrets)
│   ├── first_seen store (JSON, atomic, keyed by stable product id — D5)
│   ├── process_offers.py → offers.json + meta.json + new_offers.json (D2)
│   ├── send_notifications.py → aggregate payload {title, body, url:"/?view=alerts&alert=<id>"}
│   ├── sync_server.py / sync_store.py (kept; lastVisit semantics fixed)
├── scraper/ (kept; settings.toml.sample; stable-id emission)
├── deploy/ (update.sh + merge_config.py, install.local.conf.sample)
├── tests/ (pytest unit+integration, Playwright E2E incl. WebKit + visual, k6)
├── .devcontainer/ + docker-compose.yml + Makefile (`make test`, `make dev`)
└── .github/workflows/ci.yml
```

**Key behavior designs**
- **Newness (Bug #2/N1/N2/N3):** server keeps `first_seen[product_id]`; `offers.json` items carry `first_seen`. Client: "New" = `first_seen > lastVisit`. Last-visit advances **once per session** (on load, `sessionStorage`-guarded) and the client **never adopts a server `lastVisit` newer than the value it read at boot** — kills the self-race while keeping cross-device sync.
- **Layout/paging (Bug #1):** CSS grid `repeat(auto-fill, minmax(250px,1fr))`; page size from a pure-CSS/`ResizeObserver`-free responsive rule (fixed rows per breakpoint); no DOM measurement; `box-sizing: border-box` reset; visual snapshots per engine lock it.
- **Focus (Bug #3):** pager is a roving-tabindex widget; filter controls blur after activation; global Left/Right handler suppressed only for open selects / text carets; all covered by Playwright keyboard tests.
- **Push (Bug #4):** payload `{alertId, count}`; SW opens `/?view=alerts&alert=<id>`; AlertsView lists matched products (matched URLs persisted per alert in the profile at send time) with the Alerts control highlighted; addressable on cold entry.
- **Continuity:** installer backs up `SYNC_DIR` + live configs before touching anything; **existing VAPID keypair reused verbatim**; profile-store schema migration is additive-only.

**UX/visual direction:** keep the five ideas (single-row filter bar, Last-Updated/Your-Last-Visit, auto-fit grid + bottom pager + arrow paging, hover popover, Web Push); add ALDI/LIDL/Both as a segmented control in the filter row; modernize visuals entirely via **Claude Design** exports (operator-produced, committed to repo). Decision: **no dedicated design-role agent** — Claude Design does the design work; the front-end worker translates committed tokens/HTML into Svelte components; a verifier checks fidelity. Until exports land, the front-end builds against a neutral token layer (`tokens.css`) so design arrival is a token swap, not a rewrite (de-risks the operator-driven seam).

---

## 5. Loop-2 task DAG

Legend: role → worker (§6). Every task's success criteria are verified by tests + a fresh-context verifier before merge. PRs into `refactor`.

| ID | Task | Inputs | Outputs | Success criteria | Role | Deps |
|---|---|---|---|---|---|---|
| T0 | Design brief → **operator runs Claude Design** → exports committed | §4 UX constraints | design brief (orchestrator-authored); committed tokens/HTML | exports in repo | Orchestrator + operator | — |
| T1 | Test harness & CI skeleton | repo | devcontainer, compose, Makefile, GH Actions, pytest/Vitest/Playwright scaffolds | `make test` runs green (empty suites) locally & CI | QA/DevX | — |
| T2 | Backend: stable ids + `first_seen` store + `offers.json`/`meta.json` (D2/D5) | current pipeline | updated process_offers, spiders emit stable id; migration for profile store | pytest: first_seen stable across simulated runs; N2/N3 covered | Backend | T1 |
| T3 | Backend: aggregate push + per-endpoint ledger (Bug #4, N5, N6, N7) | T2 | new payload, matched-URL persistence, sw-compatible contract | pytest integration: payload shape, dedup per endpoint, year-rollover fix | Backend | T2 |
| T4 | Sync semantics fix (Bug #2/N1) | T2 | server lastVisit semantics + client contract doc | integration test: same-load POST/GET no longer collapses "new" | Backend | T2 |
| T5 | Frontend scaffold: Vite+Svelte 5, stores, URL state, data loading, tokens.css | T1, D1/D2 | building SPA shell (static dist/) | builds; unit tests for stores/urlstate; deep-link restore works | Frontend | T1 |
| T6 | Frontend features: filter bar (+ **ALDI/LIDL/Both**), grid+pager (Bug #1), roving focus (Bug #3), popover, alerts modal, AlertsView (Bug #4 client), N4/N8/N9/N11 | T5, T0 exports | full UI | Playwright (3 engines) + visual snapshots green; keyboard paging survives filter clicks; WebKit layout matches | Frontend | T5, T0 |
| T7 | PWA: manifest.json, icons, sw.js rewrite (push + N6), installability | T5 | PWA assets | Lighthouse installable; push E2E (mock push service) | Frontend | T5 |
| T8 | Accessibility pass: keyboard nav, `:focus-visible`, ARIA on pager/modal | T6 | a11y fixes + axe checks in E2E | axe: no serious violations; keyboard-only walkthrough scripted | Frontend | T6 |
| T9 | Config migration: TOML/.env loaders (D3), all sample configs | T2 | config.toml.sample, settings migration, loader shims | pipeline runs from TOML in compose; secrets via .env | DevOps | T2 |
| T10 | Installer/updater: `deploy/update.sh` idempotent create-or-update (user, cron, logrotate, systemd, web root), sample→real **merge**, dry-run+diff, backups (config + SYNC_DIR), `install.local.conf` | T9 | deploy/ tree | bats/pytest tests in an Ubuntu container: idempotency (2nd run = no-op), merge adds-never-clobbers, dry-run output | DevOps | T9 |
| T11 | Observability carry-forward: .prom emission parity in new pipeline | T2,T9 | metrics preserved | metric-name parity test vs current set | Backend | T9 |
| T12 | Verifier passes (fresh context, recurring): spec conformance, security-preservation checklist (escaping, allow-listing, sync-code randomness, systemd hardening), regression hunt | each merged PR | verdicts, findings | all green before DoD | Verifier | continuous |
| T13 | Load + security tiers: k6 vs sync API; pip-audit/bandit/npm-audit (D4) | T1,T4 | CI jobs | thresholds pass | QA/DevX | T4 |
| T14 | Docs refresh: README + docs reflect new stack/install/config/testing; stale removed | all | updated docs | verifier doc-accuracy check | SWE-1.6 worker | T10 |
| T15 | Migration rehearsal (staging in compose): profile backup/restore, VAPID reuse, `first_seen` backfill | T2,T10 | rehearsal report | data intact post-migration in rehearsal | DevOps | T10 → **Hard Stop #2 before touching VPS** |

**ACU/effort estimate (calibrate on first run per §4.3):** T1 4–6 · T2–T4 10–14 · T5–T8 16–24 · T9–T10 8–12 · T11,T13 4–6 · T12 6–10 · T14–T15 4–6 → **≈ 50–80 ACUs** total for Loop 2, spread over multiple daily allowances; 3–4 concurrent workers max; per-session ACU caps set in Settings → Usage (operator action).

**Risk list**
1. **Claude Design seam** (operator-driven): blocks T6 visual fidelity → mitigated by tokens.css neutral layer; T6 can land function-complete and re-skin.
2. **Push continuity**: any VAPID mistake silently kills all subscribers → T15 rehearsal + Hard Stop #2 + backups.
3. **Retailer API drift** mid-refactor (ALDI/LIDL endpoints): scraper kept as-is minus id emission; E2E uses recorded fixtures, not live scrapes.
4. **Quota**: multi-day run; pauses are checkpointed via PROGRESS.md; workers on cheap models.
5. **WebKit-only layout surprises**: caught by Playwright WebKit project + per-engine visual snapshots (the exact Bug-#1 class).
6. Scope creep in the 1,311-line JS port — verifier enforces the kept-ideas list, nothing more.

**Open questions (non-blocking, defaults stated)**
- Q1: Advance "last visit" on load-once-per-session (proposed) vs an explicit "mark all seen" button? Default: per-session.
- Q2: N8 — should the price filter exclude "N/A"-priced items? Default: keep including, badge them.
- Q3: Repo layout — `frontend/` top-level dir as in §4? Default: yes.

---

## 6. Team design — specialized agents & draft role prompts (review artifacts)

Roster (4 workers + recurring verifier; 3–4 concurrent; models routed for cost):

**W1 — Backend/Pipeline Engineer** (Sonnet-class) — T2,T3,T4,T11
> You are the backend engineer for the LIDALDI refactor. Read PROGRESS.md, LOOP1_DELIVERABLES.md §4–5, and the code in backend/ & scraper/. Your tasks: [T-ids + success criteria injected per dispatch]. Constraints: POSIX-only runtime stays; preserve security protections (safe_json_for_script, URL allow-listing, locked RMW); never touch the VAPID keypair or live profile data; all changes covered by pytest; open a PR into `refactor` with a structured JSON summary {task, status, files, pr, follow_ups}. Do the simplest thing that meets the criteria; no scope creep.

**W2 — Frontend Engineer (Svelte)** (Sonnet-class) — T5,T6,T7,T8
> You are the front-end engineer. Implement the Vite+Svelte 5 SPA per LOOP1_DELIVERABLES.md §4 against the committed Claude-Design exports (or tokens.css if not yet landed). Hard requirements: static build output only (no SSR); the five kept ideas preserved exactly; ALDI/LIDL/Both segmented filter; no DOM-measurement layout; roving-tabindex pager; native Popover API; History-API URL state; alerts deep-link view. Every behavior locked by Vitest or Playwright (incl. WebKit + visual snapshots). PR into `refactor` + structured JSON summary.

**W3 — DevOps/Release Engineer** (Sonnet-class) — T9,T10,T15
> You are the DevOps engineer. Deliver the TOML/.env config migration and the idempotent git-driven installer/updater per §6.5 of the architecture doc and T9/T10/T15 criteria. Non-negotiables: dry-run + diff mode; backups (live configs AND SYNC_DIR) before any mutation; sample→real merge adds new keys and never clobbers live values; path-parameterized via git-ignored install.local.conf; test idempotency inside an Ubuntu container — you never touch a real server. PR into `refactor` + JSON summary.

**W4 — QA/DevX Engineer** (Sonnet-class) — T1,T13
> You own the single containerized test workflow: DevContainer + Compose, one `make test` entry point running unit (pytest/Vitest), integration (sync server + temp store), E2E (Playwright: Chromium/Firefox/WebKit + visual snapshots), load (k6 vs sync API), security (pip-audit, bandit, npm audit; ZAP as opt-in profile) — identical locally and in GitHub Actions. Keep it fast and deterministic (recorded scraper fixtures, mock push service). PR into `refactor` + JSON summary.

**V — Fresh-context Verifier** (high-capability model, recurring) — T12
> You are a fresh-context verifier with no prior involvement. Inputs: the signed spec (LOOP1_DELIVERABLES.md), one merged/candidate PR, and the scope checklist (master goal §6). Verify claims against the code and test results only — run the suite yourself. Check: success criteria met; kept-ideas intact; security-preservation checklist; no regressions or scope creep. Output structured verdict {pass|fail, findings[severity, evidence, file:line]}. Be adversarial; a wrong "pass" is the worst outcome.

Docs task T14 → free **SWE-1.6** session with a tightly-scoped prompt (mechanical rewrite against a checklist).

Rationale for specialization: T2–T4 vs T5–T8 vs T9–T10 have disjoint codebases, skills, and test surfaces — parallelizable with minimal conflicts (only shared contract: `offers.json`/push-payload schema, frozen in T2's PR first). No sub-supervisor tier is warranted at this scale (arch doc §3 concurs).
