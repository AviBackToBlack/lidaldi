# CLAUDE.md — LidAldi

Context for Claude Code (or any agent) working in this repository.
`README.md` and `docs/` are the source of truth for how the system
works; this file is about *how to work on it* — conventions, gotchas,
and things that aren't obvious from reading the code once.

## What this is

LidAldi aggregates non-food special offers from ALDI.IE and LIDL.IE.
A daily cron chain (Scrapy → `process_offers.py` → `send_notifications.py`)
publishes static JSON, a small sync server keeps cross-device state
(last-visit, keyword alerts, push subscriptions), and a Vite + Svelte 5
PWA frontend serves it all as static assets behind nginx. Live at
[lidaldi.neit.me](https://lidaldi.neit.me/). Production is a single
Ubuntu VPS — no SSR server, no database (JSON files + locked RMW).

Read `README.md` first for the architecture diagram and repo layout —
it's accurate and detailed. This file adds what README doesn't cover.

## Branches

- **`main`** is the active default branch. Work off `main`, PR into `main`.
- **`refactor`** is the (now fully-merged-into-`main`) branch used for a
  large orchestrated rewrite (legacy static-HTML frontend → Svelte 5 SPA,
  plus the whole test harness, installer, PWA, config system). It's
  historical — don't branch from it, don't merge it again, everything it
  had is already in `main`.
- `website/` in `main` is the **frozen legacy frontend** (pre-rewrite).
  It's kept only for context/rollback; `frontend/` is the real, live one.
  Don't add features to `website/`.
- The repo-root `REFACTOR_*`/`PROGRESS.md`/`LOOP1_DELIVERABLES.md`/
  `DESIGN_BRIEF.md` docs are planning/process artifacts from that rewrite
  — see the documentation map right below for what each one covers. Useful
  for archaeology, not living docs; don't feel obligated to update them.

## Documentation map — every `.md` in the repo

Living docs (current state — read these for how the system works today):

| File | What's in it |
|---|---|
| [`README.md`](README.md) | Main entry point: feature list, architecture diagram, data-file table, repo layout, requirements, quickstart, full config key map (legacy `config.py` → TOML/.env), deploy summary, push/PWA notes, frontend UI feature map. |
| [`docs/operations.md`](docs/operations.md) | Operator procedures: `deploy/update.sh` usage, config-merge rules, backups, VAPID key handling, service-worker cache-bump discipline, systemd/nginx/cron/logrotate, security scans. |
| [`docs/observability.md`](docs/observability.md) | Prometheus metric inventory — **frozen contract**, enforced by `tests/unit/test_metrics_parity.py`. All 20 metric names, types, labels; Telegram alerting is mentioned here too. |
| [`docs/sync-contract.md`](docs/sync-contract.md) | The sync API contract — **frozen**, GET/POST semantics for `/api/sync/{code}`, and critically the client-side `lastVisit` self-race rules (rule 2 is the one that's easy to accidentally violate). Read before touching `sync_server.py`, `client.ts`, or `App.svelte`'s boot handshake. |
| [`docs/testing.md`](docs/testing.md) | One-page pointer/summary; the real detail is in `tests/README.md`. |
| [`docs/cutover-runbook.md`](docs/cutover-runbook.md) | Exact step-by-step VPS migration procedure (legacy → refactored stack). **Completed 2026-07-07** — kept as a historical record of the cutover that was performed. Includes the rollback procedure and the known gaps (F1: no automated config-value migration; F2: resolved). |
| [`tests/README.md`](tests/README.md) | Test harness reference: all tiers (`make test-*`), environment/container details, k6 load-tier notes (rate-limit design, thresholds), CI wiring. |
| [`website/README.md`](website/README.md) | One-paragraph freeze notice for the legacy `website/` frontend — don't build on it. |
| [`SECURITY.md`](SECURITY.md) | Vulnerability disclosure policy: `main` is the only supported version, report privately via the GitHub Security tab. Names the automated scanning (Dependabot, Snyk, CodeQL) as already-covered ground. |
| [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) | The PR checklist contributors get pre-filled. |

Historical / process docs from the Svelte rewrite (archaeology only — **do
not treat as current state**, don't feel obliged to keep them updated):

| File | What's in it |
|---|---|
| [`REFACTOR_MASTER_GOAL.md`](REFACTOR_MASTER_GOAL.md) | The orchestrator brief that kicked off the rewrite: fixed goal, known bugs to fix, operating principles, Loop 1/Loop 2 structure, scope checklist, definition of done. |
| [`REFACTOR_RESEARCH_AND_ARCHITECTURE.md`](REFACTOR_RESEARCH_AND_ARCHITECTURE.md) | Pre-implementation research/architecture proposal — framework choice rationale, quota/model notes for the Devin-based orchestration, provisional-decisions list. Explicitly marked as *provisional defaults*, not mandates. |
| [`REFACTOR_OPERATOR_RUNBOOK.md`](REFACTOR_OPERATOR_RUNBOOK.md) | The human operator's companion guide for running that orchestration (Devin/Fable 5 setup, GitHub connection, Knowledge seeding, spending guardrails, phase-by-phase what-to-expect). |
| [`LOOP1_DELIVERABLES.md`](LOOP1_DELIVERABLES.md) | The signed-off Loop 1 spec: codebase analysis findings, the confirmed known-bugs root causes plus the bug-discovery pass (N1–N14), task DAG (T0–T15), team/role design. This is the spec Loop 2 was implemented against. |
| [`DESIGN_BRIEF.md`](DESIGN_BRIEF.md) | The brief handed to Claude Design (Anthropic Labs) for the visual redesign — page structure, design goals/constraints, deliverables (`frontend/design/tokens.css`, mockups). |
| [`PROGRESS.md`](PROGRESS.md) | The durable task ledger for the whole rewrite: phase status, per-task (T0–T15) worker/PR/verifier record, out-of-scope findings log, post-deploy log. The most useful of the historical docs for "why does X work this way" questions. |

## Platform constraint: POSIX only for the backend

`sync_server.py`, `sync_store.py`, and `send_notifications.py` use
`fcntl.flock` for cross-process locking and **do not run on Windows**.
If you're on a Windows dev machine (this repo is frequently worked on
from one), you cannot run these directly — always test them inside the
Docker test image (see below). The scraper and `process_offers.py` are
portable. Node/npm are typically *not* installed on a Windows host here
either — the frontend toolchain only exists inside the container.

## Running things — always via the pinned container

Don't install Playwright/pyenv/k6 locally. Build and use the actual test
image so results match CI exactly:

```bash
docker build -f .devcontainer/Dockerfile -t lidaldi-test:local .

# full suite (unit + installer + e2e + load + security)
docker run --rm --ipc=host -v "$PWD:/work" -w /work -e CI=true lidaldi-test:local make test

# just the frontend, iterating
docker run --rm -v "$PWD/frontend:/work" -w /work mcr.microsoft.com/playwright:v1.62.1-noble bash -c "npm ci && npm run build"
```

On Windows/Git Bash, `docker run -v` with a Windows path needs
`MSYS_NO_PATHCONV=1` prefixed, or the colon in `D:/...` gets mis-parsed —
e.g. `MSYS_NO_PATHCONV=1 docker run --rm -v "D:/Work/GIT/lidaldi:/work" ...`.
`--ipc=host` is required for Chromium — without it, Docker's default 64 MB
`/dev/shm` breaks the browser.

`--project=webkit`/`chromium`/`firefox` and `--repeat-each=N` on
`npx playwright test` are your friends for isolating a flaky e2e test —
see the webkit-flake investigation below for the actual workflow.

## Test tiers (`make test` = all of these)

| Tier | What | Notes |
|---|---|---|
| `test-unit` | pytest (`tests/unit/`) + Vitest (`frontend/`) | |
| `test-installer` | pytest (`tests/installer/`) | sandboxed `deploy/update.sh` tests |
| `test-e2e` | Playwright (`tests/e2e/`), chromium+firefox+webkit + visual snapshots | |
| `test-load` | k6 vs a real `sync_server` | **fails, never skips**, if k6/server unavailable |
| `test-security` | `pip-audit`, `bandit` (medium+), `npm audit` (`--audit-level=high`) | any finding fails the build |
| `test-zap` | opt-in only, not in CI | OWASP ZAP baseline scan |

Full details: `tests/README.md`, `docs/testing.md`. CI (`.github/workflows/ci.yml`)
runs `make test` inside this exact same Docker image, so a green local
container run means a green CI run.

## Frontend (`frontend/`)

Vite + Svelte 5, builds to static assets (`frontend/dist`), no SSR.
Key structure:

```
frontend/src/
  App.svelte                 top-level: boot data-load + sync handshake, routing state
  main.ts                    entry point
  sw.ts                      service worker source (built separately, see below)
  lib/components/            FilterBar, Card, Pager, Header, AlertsModal, AlertsView
  lib/stores/                Svelte 5 runes-based stores (*.svelte.ts)
  lib/logic/                 pure, unit-tested logic (filters, paging, lastvisit, etc.)
  lib/sync/client.ts         syncFetch/syncPost — the sync API client
  lib/sw/logic.ts            pure logic extracted from sw.ts for Vitest coverage
  lib/push.ts                push subscription management
```

The service worker builds as a **second, separate Vite pass**
(`vite.sw.config.ts`, invoked by `npm run build` right after the main
build) to a single-file IIFE at the stable URL `dist/sw.js` — module
workers aren't universally supported (Firefox). **Whenever
statically-cached assets change** (icons, `manifest.json`), bump
`STATIC_CACHE` in `sw.ts` (e.g. `-v1` → `-v2`) in the same change, or
returning clients keep serving stale assets — see
`docs/operations.md#deploy-discipline-service-worker-cache-name-bump`.

### Frontend dependency compatibility — check the full chain on any bump

`vite`, `@sveltejs/vite-plugin-svelte`, and `vitest` are version-locked
to each other, and Dependabot bumping just one of them **will** break the
other two silently (peer-dep warnings, or worse — `vitest` has a
*hard* dependency on a vite major range, not just a peer, so it'll
silently nest a private vite install and test against a different vite
version than the app builds with). Before merging any dependabot PR that
touches one of these three, check all three's compatibility together:

```bash
npm view @sveltejs/vite-plugin-svelte@latest peerDependencies
npm view vitest@latest dependencies   # note: dependencies, not peerDependencies, for vite
npm ls vite vitest @sveltejs/vite-plugin-svelte svelte   # after install — must all dedupe onto one vite version
```

This actually happened: dependabot PR #40 bumped `vite` 6→8 alone and
left `vite-plugin-svelte` (peer `vite ^6`) and `vitest` (dependency
`vite ^5||^6`) behind. Fixed by bumping all three together (see commit
`893fcc6` / PR #42) — `vite-plugin-svelte` needed `^7.x` for vite 8 (not
`^6.x`, which only covers vite 6/7), `vitest` needed `^4.x`. Always verify
with a real `npm install` + `npm ls` + full `make test`, not just reading
version ranges.

**`frontend/.npmrc` sets `legacy-peer-deps=true`** (commit `71ce83d`, added
because `svelte-check` hadn't yet declared a peer range covering TypeScript
7). That flag makes npm *silently ignore every peer-dependency conflict in
`frontend/`* — which removes exactly the install-time warning the check
above relies on. So the `npm ls` dedupe step isn't belt-and-braces here,
it's the only signal left. If `svelte-check` gains a TS 7 peer range, drop
the file rather than keeping a repo-wide suppression around.

### Known flaky test: `alerts-deeplink.spec.ts` (webkit only)

`deep link restores AlertsView with matches and highlight` intermittently
fails on the `webkit` project — scoped `retries: 2` via
`test.describe.configure` (see the test file). This is a **confirmed
webkit/Playwright request-interception reliability gap** (matches
microsoft/playwright#6045, #4173), not an app bug: under instrumentation,
webkit occasionally never invokes `page.route()` for one specific mocked
GET, and the request falls through to the real dev server's SPA
`index.html` fallback instead, which then fails JSON parsing exactly like
a corrupted response would. This was root-caused via ~150 instrumented
repro runs, ruling out (in order): CPU-contention timing, concurrent
identical-GET coalescing, missing `Cache-Control` header, and glob vs.
URL-predicate route matching — all reproduced the identical failure rate,
which is the actual evidence it's an engine/tooling issue, not fixable
from test or app code. If this pattern shows up in a *new* test, don't
re-litigate it — scope a retry the same way (see commit `8bb6708`) rather
than chasing it again. The same category of flake already existed and is
documented for `pwa-push.spec.ts` (`chromium-push` project) in
`PROGRESS.md`.

## Backend (`offers_processing/`, `scraper/`)

- **Scraper** (`scraper/lidaldi/spiders/{aldi,lidl}_spider.py`): API-based,
  not HTML-scraping — ALDI uses `api.aldi.ie/v3/product-search` (listing) +
  `/v2/products/{sku}` (detail, HTML description via BeautifulSoup); LIDL
  uses `lidl.ie/q/api/search` (listing, category-filtered) + product-page
  ld+json (description only). This was a deliberate move away from
  CSS/XPath selectors because both sites' HTML layouts changed every 1–2
  weeks and broke the old scraper constantly. Keep it API-based; don't
  reintroduce brittle CSS/XPath selectors for anything the APIs already
  provide. The one remaining HTML dependency is discovering the
  SpecialBuys category key from a breadcrumb on `aldi.ie/products/specialbuys`
  (kept deliberately, see conversation history / commit `bf74716` era).
- **JSON `null` gotcha (Python)**: `dict.get(key, default)` returns `None`,
  *not* `default`, when the key exists with a JSON `null` value. Both
  spiders had real bugs from this (`AttributeError: 'NoneType' object has
  no attribute 'strip'`). Always use `(data.get(key) or default)` for
  string fields coming from these APIs, not the two-arg `.get()` form.
- **`ErrorCheckingPipeline`** (`scraper/lidaldi/pipelines.py`) fails the
  whole scrape if any of several thresholds is crossed (see
  `scraper/lidaldi/pipelines.py:88-103`): `total_items` is 0 or below a
  hardcoded minimum (currently **60** — 100 → 90 → 60, each time because
  LIDL's real non-food inventory dropped below the old floor and sank an
  otherwise-healthy scrape; verify against the live site before assuming a
  threshold failure means a bug — see
  `scraper/lidaldi/pipelines.py:90`); the ERROR-log ratio exceeds 10%
  (`error_ratio > 0.1` — a *single* `logger.error()` does **not** sink the
  run, only >10% of items producing ERROR entries does); the dropped-item
  ratio exceeds 10% (`dropped_ratio > 0.1`); a per-field missing ratio
  exceeds its threshold; or any exception was recorded during item
  processing.
- **Sync server contract is frozen**: `docs/sync-contract.md` documents
  the exact GET/POST semantics, most importantly the `lastVisit`
  self-race fix (client must never adopt a server `lastVisit` newer than
  its own session-frozen boot value, except on first visit). Don't change
  this contract without reading that doc fully — it encodes a real bug
  fix (Bug #2/N1) that's easy to accidentally reintroduce.
- **Config**: `config.toml` (non-secret) + `.env` (secrets), loaded via
  `offers_processing/config_loader.py`. A legacy `config.py` still works
  with a deprecation warning. See README's config key map if migrating
  an old install.

## Deploy

`deploy/update.sh` is the one idempotent installer/updater — plan-then-apply,
strict no-op on a second run with no drift. **Never** hand-edit production
config or services directly; go through the installer (dry-run first,
always). It never touches `offers.json`/`meta.json` (data, written by the
pipeline) and never touches the VAPID keypair (a long-lived credential —
losing/regenerating it kills push for every subscriber). Full procedure:
`docs/operations.md`.

## Things that bit us before (don't repeat)

- **PATH on the Windows dev box**: `gh`, and sometimes other CLIs, can be
  correctly installed but invisible to a long-running shell-tool process
  that started before the install (Windows only refreshes env vars for
  freshly-spawned processes). If a tool "isn't found" but you're sure
  it's installed, check `Get-Command -All` / common install dirs and
  invoke by full path rather than concluding it's missing.
- **Dependabot config had real gaps** (fixed in `b43b402`): the
  `github-actions` ecosystem entry had `directory: "/.github"`, but
  Dependabot always appends `.github/workflows` itself — so it silently
  scanned nothing for over two weeks. If you're auditing `dependabot.yml`
  again, that specific mistake (`directory` should be `"/"` for
  `github-actions`) is an easy one to reintroduce.
- **CI's `on:` triggers must match the branch you're merging into.** It's
  happened before that `ci.yml` only triggered on a feature branch, so
  every PR against `main` merged with zero CI signal. Check this whenever
  branch strategy changes.
- Before concluding a CI failure is a real regression, check whether the
  triggering commit's diff even touches the failing area — a lot of
  "regressions" here turned out to be pre-existing flakes surfaced by
  unrelated commits (see the webkit flake above).
- **`@playwright/test` and the container image are one version, two
  places.** `tests/e2e/package.json` and `.devcontainer/Dockerfile`'s
  `FROM mcr.microsoft.com/playwright:vX.Y.Z-noble` must match exactly, or
  *every* e2e test dies with "Executable doesn't exist … Please update
  docker image as well". Dependabot only ever bumps the npm side. This has
  now happened twice (`c9db2ea` bumped, `9a4136e` reverted it, `1c5f70d`
  bumped again and left `main` fully red until the image was bumped to
  1.62.0 to match). Bump both, plus the version strings in this file and
  `tests/README.md`, and re-run the visual tier.
- **Root `.gitignore` patterns aren't anchored unless you anchor them.**
  The Python-artifact block's `lib/` matched `frontend/src/lib/` at any
  depth; git only kept the app source because `frontend/.gitignore`
  re-includes it with `!src/lib/`, but tooling that reads only the root
  ignore file (some agents/editors) treats the whole app `lib/` tree as
  ignored and refuses to open it. Root-level build dirs are now written
  `/lib/`, `/lib64/`. Keep new root-only patterns anchored.
- **WebKit 26 (Playwright 1.62) wedges a page when a service worker
  registers while `page.route()` interception is active.** Not a hang in
  one API — the whole page stops answering, so every later protocol call
  (`locator.count()`, `evaluate`, screenshots) times out; `waitForTimeout`
  still resolves, which is the tell. It surfaced as all four AlertsModal
  specs failing on webkit only (the modal registers `/sw.js` on open).
  `routeOffers()` now aborts `**/sw.js`, since the SPA specs don't
  exercise the worker and `pwa*.spec.ts` (which do) never mock routes.
  Same family as the route-interception flake documented above.
- **WebKit 26 also exposes `PushManager`/`Notification` headlessly**, so
  `isPushSupported()` is now true there and the modal renders its extra
  `.push-row` (+84px). That's a genuine capability change, not a
  regression — the `alerts-modal-webkit.png` baseline was re-recorded for
  it. Expect capability-gated UI to shift on browser bumps.
- **The e2e suite is not actually network-isolated: it loads Google Fonts.**
  `playwright.config.ts` claims "local static fixtures only — no live
  network", but `frontend/index.html` pulls Plus Jakarta Sans from
  `fonts.googleapis.com` with `display=swap` on every spec. Because the
  webfont's metrics differ from the system-ui fallback, any auto-height
  element changes size when the swap lands, and CI's variable fetch latency
  decides whether that happens before or during a test. It sank
  `keyboard-paging.spec.ts`'s pager assertion intermittently (measured 41px
  on the fallback, 38px after the swap → `Expected: 41 / Received: 38`,
  reproducible by delaying `fonts.gstatic.com`). Two rules follow: **never
  size a component off its line box when the layout has to be stable** (the
  pager's Prev/Next buttons now carry an explicit `height`, commit
  `6e4c3b6`), and **`await page.evaluate(() => document.fonts.ready)`
  before any geometry assertion**. Self-hosting the woff2 would remove the
  whole category — metrics are identical, so baselines would survive.
