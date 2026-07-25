# LIDALDI Refactor — Research & Architecture Proposal

**Status:** v3 — decisions locked; Claude Design, mandatory bug-discovery, and data/push-continuity added; requirements phase complete, ready for sign-off
**Author:** Requirements & architecture pass
**Date:** 2026-07-05
**Currency window:** All external claims verified against sources dated up to early July 2026. Anything model/tool-related in this space has a shelf life of *days* — see §1.

---

## ⚠️ Note to the top-of-hierarchy orchestrator — these decisions are PROVISIONAL, not final

**Read this before treating anything below as a mandate.** This document was produced during a human-led requirements pass *before* deep, first-hand codebase analysis. Every choice marked "locked", "decided", or "recommended" in this file — the **front-end framework (Svelte/SvelteKit), the config format (TOML/.env), the testing tools (Playwright, k6, ZAP), the installer design, the two-tier topology, the model-routing, the fan-out width, the connectors/MCPs** — is a **human preference and a sensible starting default, not a fixed requirement.**

You (the orchestrator running as Devin Ultra / Fable 5) will have **deeper context** than this doc after you analyze the actual codebase. If your analysis shows that a different framework, library, tool, pattern, or overall approach better serves the goal, **you are expected to say so and propose it — with rationale and tradeoffs — rather than silently follow this document.** Equally, do not silently override it either: surface every recommended deviation at the **Loop 1 → Loop 2 hard stop** for the maintainer's explicit sign-off. **That hard stop exists precisely for this.**

What is actually fixed is only **the goal itself**: a modern, de-complexified LIDALDI that keeps the ideas the maintainer likes (single-row filter controls, auto-fitting card grid with bottom pager + arrow-key paging, Last-Updated/Your-Last-Visit, hover description popover, Web Push), fixes the four known bugs, adds the ALDI/LIDL/Both filter, and delivers the approved improvements (auto-updater, sample→real config merge, full test strategy, accessibility, PWA, observability). **The ends are fixed; the means are open for you to improve.**

---

## Decisions locked (2026-07-05)

The maintainer's answers to the v1 open questions, now binding for the implementation loop — **but provisional per the orchestrator override note above; the orchestrator may propose better alternatives at the hard stop:**

1. **Devin plan = Pro ($20/mo).** Corrected quota model in §4.3: **not** a fixed monthly ACU bucket — a **daily + weekly refreshing usage allowance**, overages at API pricing ($2.25/ACU). Up to **10 concurrent sessions**, full model availability incl. Fable 5, Devin Cloud + Ultra. (The v1 "Core/$500 Team" numbers were stale third-party data; the current lineup is Free/Pro/Max/Team/Enterprise.)
2. **Front-end:** migrate to a **component framework + build step** (static output). Framework = **Svelte/SvelteKit** (`adapter-static`) — see §6.7.1.
3. **Design latitude:** keep the *ideas* (single-row filters, auto-fitting card grid, arrow paging, hover popover) but **modernize the visuals fully**, produced with **Claude Design** (Anthropic Labs — see §6.7). The orchestrator decides whether a dedicated design-role agent is warranted around it.
4. **Config:** migrate `config.py` / `settings.py` (not limited to these two but any after-install customizable configs) from executable Python to **TOML / `.env`**. Approved.
5. **Deploy target:** single **Ubuntu** VPS; fully automated installer/updater required - separate checkout `lidaldi` git repo folder and installer ising it to update/create all the nessecary files/folders, update files/folders, etc.
6. **Orchestration seat:** **in-Devin, Ultra session (Fable 5), via the dashboard at app.devin.ai**.
7. **Sign-off gates:** orchestrator **hard-stops** (a) between Loop 1 (requirements) and Loop 2 (implementation), and (b) before anything production-impacting (installer, migrations). Confirmed.
8. **Scraper/ToS:** no special constraints in production — plain cron run.
9. **Deep-linkable filter state:** kept, but reconciled with the single-page design via the **History API** (no reload) — see corrected §7.1.
10. Approved additions: server-side `first_seen`, analytics-free observability (carry Prometheus textfiles forward), accessibility pass, `manifest.json` + PWA installability.

---

## 0. TL;DR

- **Fable 5 as top orchestrator is viable today**, but it just came off a two-week export-control ban (pulled 2026-06-12, restored globally 2026-07-01). It runs behind safety classifiers that can emit `refusal` and auto-fallback to Opus 4.8. For an unattended "run until done" loop, that's a real availability/continuity risk you must design around, not ignore.
- **Recommended entry point:** a **Devin Cloud *Ultra* session (which runs Fable 5) as the orchestrator**, delegating to **managed child Devins** (Multi-Devin) as workers. This keeps the whole hierarchy inside one system with native context sharing, instead of gluing Fable-in-Claude to Devin-via-API. Kick it off from the **dashboard (app.devin.ai)** for supervised runs; use **CLI/API + a Playbook** for repeatable/automated runs.
- **"Loop Engineering" is current, not superseded** — it's the accepted 2026 successor to prompt/context/harness engineering and is exactly the right frame for your single-Markdown-goal loop with explicit stop rules.
- **The 4 *known* bugs are all confirmed and root-caused** (see §2) — but treat them as a **seed list, not the whole picture**: a dedicated bug-discovery + regression pass is mandated (master goal §3.10), not just these four. Bug #1 (Mac Chrome) and bug #3 (focus) share a theme: the front-end does too much imperative JS layout/focus work that a modern CSS-first rewrite removes entirely.
- **Quota reality (Pro):** a **daily + weekly refreshing usage allowance**, *not* a fixed monthly ACU bucket; overages purchasable at API pricing (~$2.25/ACU, 1 ACU ≈ 15 min active work). Out of allowance → sessions **pause** (state preserved) and the allowance **refreshes next day/week**; sessions can also **sleep** (0 ACU) and resume. So a quota stop is a pause you can wait out for free or pay through — design the loop with per-session ACU caps, checkpoints, and a modest fan-out so a multi-day run rides successive daily allowances.
- **Testing:** don't install anything on the Windows host. Standardize on **Docker Compose + DevContainer**, one `make test` target, run identically locally (Docker Desktop) and in CI. **Playwright** directly de-risks the Mac/Safari bug via its bundled WebKit engine.
- **Open questions for you** are in §8. A few genuinely block a clean implementation loop.

---

## 1. Currency check (what is actually true as of July 2026)

You explicitly asked me to verify freshness rather than trust priors. Findings:

### 1.1 Claude Fable 5 availability — volatile, currently ON
- **2026-06-09:** Fable 5 goes live in Devin across Cloud, Desktop, CLI; tops Cognition's FrontierCode benchmark.
- **2026-06-12:** Cognition **removes** Fable 5 from its products following Anthropic's announcement + a **US government export-control directive** (restricting foreign-national access). Opus 4.8 and GPT-5.5 stayed available; Devin Ultra fell back to the next most capable model.
- **2026-06-30 → 07-01:** Export controls **lifted**; Fable 5 restored globally on the Claude Platform, Claude.ai, Claude Code, Claude Cowork, and Devin. Anthropic shipped an improved safety classifier (claims >99% block rate on the jailbreak technique that triggered the ban).
- **Net:** matches what you see ("Fable 5 in my model list"). But treat availability as **not guaranteed for the duration of a multi-day run**. Build in an Opus 4.8 fallback path.

### 1.2 Fable 5 safety classifiers (matters for an autonomous coder)
Fable 5 runs classifiers targeting offensive-cyber, bio/life-sciences, and reasoning-extraction. **Benign** work can trip them. Two concrete implications for this project:
- Do **not** instruct the orchestrator to "echo/transcribe your reasoning" — that can trigger the `reasoning_extraction` refusal and silently elevate fallbacks to Opus 4.8. Use structured `thinking` blocks + a `send_to_user` tool instead.
- Configure **server-/client-side fallback to Opus 4.8** so a refusal doesn't kill the loop.

### 1.3 "Loop Engineering" is the current paradigm (your example — checked)
You flagged Loop Engineering as a possible "already replaced" case. It's the opposite: it emerged **second week of June 2026** and is the current default framing — the four-step progression is *prompt → context (2025) → harness → loop (2026)*. Loop engineering = designing the trigger, topology, verifier, and stop rules the agent runs inside, instead of hand-writing prompts. Claude Code's `/goal` (the "single goal, runs until done" primitive) shipped in v2.1.139 on 2026-05-12. So your instinct ("one Markdown goal, stop only when all tasks done") is aligned with current best practice, not behind it.

### 1.4 Devin HMAS primitives are GA
"Devin can orchestrate Devins" (formerly Advanced Devin) is shipped: a coordinator session delegates to **managed child Devins**, each a full Devin with its own isolated VM; the coordinator scopes, monitors, resolves conflicts, compiles results. Child sessions support **structured JSON output schemas** and **Playbooks**; the UI has a **Sub-Devin filter** and an **Agents tab**. This is your HMAS substrate — you don't have to build orchestration plumbing yourself.

---

## 2. Codebase findings (light structural pass) + the known bugs

### 2.1 What the project is
A daily ALDI.ie/LIDL.ie non-food offers aggregator, POSIX-only in production:
- `scraper/` — Scrapy project, `aldi_spider.py` + `lidl_spider.py`, pipelines, `settings.sample.py`.
- `offers_processing/` — the pipeline: `process_offers.py` (merges offers, writes `new_offers.json` + renders `index.html` from `index.html.tpl`), `send_notifications.py` (Web Push against matched alerts), `sync_server.py` (zero-dep HTTP API for cross-device sync), `sync_store.py` (fcntl-locked JSON profile store — **POSIX only**), `common.py`, `config.sample.py`, `generate_vapid_keys.py`.
- `website/` — static front-end: `index.html.tpl`, one **1,311-line** `js/lidaldi.js`, `css/lidaldi.css`, `sw.js` (push service worker).
- Deploy plumbing: `cron.d/`, `logrotate.d/`, `nginx/lidaldi-sync-proxy.conf`, `systemd/lidaldi-sync.service`.

Data flow: cron → spiders → `process_offers.py` → `send_notifications.py`. Front-end reads offers from two inline `<script type="application/json">` blocks the template renders. Cross-device state (last-visit, alerts, push subs) lives server-side keyed by a short **sync code**; the client merges with the server on load.

### 2.2 The KNOWN bugs list — confirmed root causes

> **These four are the *known-bugs list*, not an exhaustive inventory.** They were reported up-front and are confirmed below. A **separate, dedicated bug-discovery pass** must run at the most efficient stage — during Loop 1 codebase analysis (hunt for additional pre-existing bugs) and during Loop 2 QA/verification (catch regressions / new bugs). See master goal §3.10. Fix in-scope findings; log the rest with severity.

**Bug #1 — Renders fine in Chrome/Windows, broken in Chrome/Mac.**
Root cause is `getDynamicPageSize()` in `lidaldi.js` (≈ lines 612–644). It computes page size by *measuring the live DOM*: `header`/`.filters-row`/pagination/footer `offsetHeight`, a sample card's `offsetHeight`, and by **string-parsing `getComputedStyle(grid).grid-template-columns`** (`split(/\s+/).length`) to count columns. Every one of those inputs varies across platforms:
- **Scrollbars:** macOS overlay scrollbars are 0px; Windows classic scrollbars consume ~15px. That changes `window.innerWidth`/`innerHeight`, which changes both the column count and the row count.
- **Font metrics:** Arial substitution + sub-pixel rounding differ Mac vs Windows, so card `offsetHeight` differs → different rows-per-page.
- **Timing:** if measured before web fonts/images settle, `.product-card` may not exist yet → silent fallback to `320`.
- No global `box-sizing: border-box` reset; `body` has `padding: 1rem` and `overflow-x: hidden`, which *masks* horizontal overflow rather than preventing it.
The whole approach is inherently non-deterministic across engines. **Fix direction:** delete the JS measurement; drive the grid purely with CSS (`grid-template-columns: repeat(auto-fill, minmax(250px, 1fr))` already exists) and paginate with a fixed/responsive page size or CSS scroll-snap. If JS pagination must stay, base it on `ResizeObserver` + `getBoundingClientRect()` math with normalized scrollbar handling — but CSS-first is the real cure and also fixes the "fit to window" requirement you want to keep.

**Bug #2 — "New from last visit" wrongly disabled / "All products" highlighted despite clearly-new products.**
Two compounding causes:
1. **Newness is derived from `scraped_at > lastVisitTimestamp`** (`updateNewButtonState`, `applyFilters`). `scraped_at` is a *scrape-batch* timestamp, not a stable "first time this product appeared" date. If a daily run re-timestamps items, or a product the user considers "new" carries an older/!batch `scraped_at`, the set diverges from what the user actually perceives as new.
2. **The last-visit cookie is overwritten to `now` on every page load** (`setCookie("lastVisit", nowTimestamp)` right after it's read). Combined with **sync adopting the server's `lastVisit`** in `initAsync()` (which can be *newer* — e.g. a visit from another device seconds ago), the "new" window collapses to empty → `activeAvailability` flips to `"all"` and the New button disables. So you can be looking at genuinely-new stock while the button says otherwise.
**Fix direction:** compute newness from a **stable server-side `first_seen` per product** (persisted across scrapes), and advance "last visit" **deliberately** (e.g. on explicit session boundaries), not on every reload. Ideally compute the "new" set server-side at render time so the client isn't reconstructing it from ambiguous timestamps.

**Bug #3 — Arrow-key page navigation dies after clicking a filter/dropdown.**
Confirmed in the `keydown` handler (≈ lines 1175–1217). It **bails out** (`return`) if `document.activeElement` is an `input/textarea/select/button`. After you click a filter button or a dropdown, that element **retains focus**, so Left/Right are ignored until you click empty space (which blurs focus back to `<body>`). Exactly your symptom.
**Fix direction:** blur the control after it acts (or move focus to a dedicated, `tabindex`-managed pagination region), and only suppress arrow hijacking for elements where arrows have *native* meaning while actually engaged (open `<select>`, text caret in a non-empty input). A roving-tabindex pagination component is the clean modern pattern.

**Bug #4 — Push notification links to a single ALDI/LIDL product page.**
Confirmed in `send_notifications.py` (Phase 2): the payload is built from `first = matches[0]` and `"url": first.get("url")`, and `sw.js` `notificationclick` does `clients.openWindow(data.url)`. So even when N products match, the user lands on one third-party product page and never sees the rest.
**Fix direction (matches your idea):** send a **generic aggregate** notification ("N new products match your alert '<keyword>'") whose `url` deep-links back to **the LIDALDI site in an "Alerts" view** that lists exactly the matched products with the Alerts control highlighted. This needs (a) the notification payload to carry an alert id / match token instead of a product URL, and (b) a front-end **alerts deep-link view** (e.g. `?alert=<id>` or `?view=alerts`). Note this interacts with the front-end rewrite — design the alerts view as a first-class filter state.

### 2.3 The config/sample update gap (your auto-update concern)
Repo ships `config.sample.py` and `scraper/lidaldi/settings.sample.py` (The list is not limited to these two, other configs could be found during deep analysis while executing Loop 1 having the same issue); production uses untracked `config.py`/`settings.py` created by copying the samples. A `git pull` updates the *samples*, never the live files. Any new required key added to a sample silently fails to reach production. **This is the central problem your auto-updater must solve** (see §6.5): treat samples as a schema, diff against the live file, and merge/prompt for new keys rather than overwrite.

### 2.4 Other things worth carrying into the rewrite
- **POSIX-only** (`fcntl.flock`) — fine for the server; means the Windows dev box can't run the full sync/push pipeline natively. Reinforces the "test in containers" recommendation.
- Security posture is already decent (URL allow-listing, `safe_json_for_script` escaping, rejection-sampled sync codes, hardened systemd unit). Preserve these in the rewrite; don't regress them.
- The tooltip (`.desc-tooltip` + `startTooltipTimer`) is the "badly implemented mouseover" you called out: a 1s `setTimeout`, absolute-positioned box, `blur()` side-effects on inputs. Rebuild as a proper delayed popover (CSS + a small controller, or the native Popover API) with sane show/hide and positioning.
- **Data & push continuity (migration risk — easy to get wrong):** existing user state lives in the sync profile store (alerts, last-visit, push subscriptions), and Web Push depends on the current **VAPID keypair**. The rewrite/migration must **reuse the existing VAPID keys** — generating new ones silently invalidates every existing push subscription — and migrate the profile store **without loss** (back it up first, especially when introducing the server-side `first_seen` field). The §6.5 installer should back up `SYNC_DIR`, not just config/web-root. Surface this at Hard Stop #2.

---

## 3. HMAS methods (current) mapped to your Devin vocabulary

The 2026 consensus: **two layers by default** (orchestrator + workers); add a third tier only when distinct domains genuinely demand a sub-supervisor. ~70% of production multi-agent systems use orchestrator-worker; the #1 failure mode is *adding hierarchy too early* (Deloitte: 60% of enterprise multi-agent pilots never reached production, orchestration complexity the top blocker). The top orchestrator should **never touch individual tools** — it reads summarized worker outputs and decides what to ask next. Each subtask needs explicit inputs, outputs, and success criteria; state, handoff contracts, and circuit-breaker error handling must be explicit.

Your Devin-flavored terms map cleanly onto real, current mechanisms:

| Your term | What it actually is (current) | Devin / Fable 5 primitive |
|---|---|---|
| Generator-Verifier Loops | Fresh-context verifier subagents beat self-critique | Fable 5 scaffolding: "verify your work with subagents against the spec every N"; Devin PR Review / Ask Devin |
| Central Context Bridge | Shared knowledge + auto-generated repo docs + cross-session search | Devin **Knowledge** (notes/folders), **Wiki/DeepWiki**, session **Search**, MCP scratchpad |
| Parallel Orchestration (Multi-Devin) | Coordinator delegates to isolated parallel workers | **Managed/child Devins**, Sub-Devin filter, Agents tab, structured-output child sessions |
| Autonomous Knowledge Management | Agent records & reuses lessons across runs | Devin **Knowledge** (suggested-knowledge worklog events) + a Markdown memory system (Fable 5 pattern) |
| Dynamic Re-planning & Playbooks | Reusable task templates + mid-run replanning | Devin **Playbooks** (structured output schema, per-mode); Fable 5 ambiguity-navigation |

**Design consequence:** keep it to **two tiers** — Fable-5 orchestrator + Devin workers. Only introduce a designer sub-supervisor (your "Web/UI Designer", "Product Designer", "QA Engineer" idea) if the design workstream is big enough to warrant its own coordinator; otherwise it's just one more worker with a design Playbook.

---

## 4. Devin features usable for HMAS (and the quota reality)

### 4.1 Entry points (pick per use-case)
- **Dashboard — app.devin.ai (Devin Cloud):** best for **supervised** kickoff and watching the Agents tab / child sessions. Recommended for this project's first runs given the maintainer's active-supervision stance.
- **Devin CLI (Devin for Terminal):** scriptable, good for repeatable launches and CI.
- **Devin Desktop (formerly Windsurf) — the Cascade conversation:** local-hybrid IDE + agent chat (Cascade). Good for hands-on, editor-adjacent work; weaker for supervising a fleet of parallel child Devins than the dashboard.

Mapping to the three entry points you named: **Devin Desktop Cascade conversation**, **Devin CLI**, and **Devin dashboard (`app.devin.ai`)**. For this project the **dashboard wins** (parallel child-session visibility + supervised hard-stops); CLI is the automation path; Cascade is best if you end up pairing on a specific file.
- **API (V3):** create sessions with `devin_mode`, playbooks, knowledge notes, structured output; filter by repo/tags/time. Use this if you later automate the loop.

### 4.2 Orchestration & knowledge primitives
- **Multi-Devin / child sessions** — parallel isolated workers, structured JSON returns, Playbooks per child.
- **Playbooks** — standardize recurring tasks (migrations, refactors); structured output schema; can pin a Devin mode.
- **Knowledge** — persistent notes, folders, suggested-knowledge worklog events (enterprise cap raised to 300).
- **Wiki / DeepWiki** — auto-generated, subagent-written repo docs; shows ACU cost per generation.
- **Session Search** — full search across shell/file/browser/git/MCP activity of past sessions.
- **MCP marketplace** — 48+ engineering connectors (Figma official MCP, Datadog, PostHog, Amplitude, Sentry-class observability, Postman, etc.), read-only mode, per-secret personal/org scoping, OAuth handling.

### 4.3 Quota model and out-of-usage behavior — Pro plan (critical for "run till done")
Verified against Devin's current pricing page (2026-07). The individual lineup is now **Free / Pro ($20) / Max ($200)**; team lineup **Teams ($80 + $40/seat) / Enterprise**.

- **Pro includes:** full model availability (OpenAI, Claude incl. **Fable 5**, Gemini frontier), free SWE 1.6 + open-source models, **Devin Cloud** (and Ultra), DeepWiki, Devin API, Ask Devin, **up to 10 concurrent sessions**.
- **The allowance is daily + weekly, refreshing automatically — not a monthly ACU pool.** Devin's own FAQ: *"Each paid plan comes with a usage allowance that refreshes automatically on a daily and weekly basis… If you go beyond your included usage you can purchase extra usage consumed at API pricing."* Exact included-ACU numbers are **not published** ("most users never hit their limits"), and cost-per-message varies by model/effort. **Calibrate empirically:** watch the in-app usage meter on the first supervised run to learn your real daily/weekly headroom. (Your "~9 ACU from $20/$2.25" reasoning doesn't apply — the $20 isn't converted to ACUs; it buys a refreshing allowance, and $2.25/ACU is only the *overage* rate.)
- **Out of allowance:** active work **pauses** — state is **not lost**. Two recovery paths now exist, and you can mix them:
  - **Wait for refresh** (free): the daily/weekly allowance tops itself back up; the loop resumes. Ideal for a non-urgent multi-day refactor.
  - **Buy overage** at API pricing to keep going immediately.
  - **Per-session ACU hard caps** (in settings) bound spend per worker during parallel fan-out — set these to prevent a runaway worker eating the day's allowance.
  - **Sleep vs terminate** — a session **sleeps** (0 ACU) after inactivity and **resumes** on demand; terminate ends it. A quota stop = sleep = resumable.
- **Fan-out sizing:** the binding limit is the **daily/weekly allowance**, not the 10-session concurrency cap. Ten parallel *Fable-5* workers would drain the allowance quickly. Recommended: **2–4 concurrent workers**, with **cheaper models on workers** (Sonnet/Haiku/SWE 1.6 - the last one **is free**) and **Fable 5 reserved for the orchestrator + verifier passes**. This is the model-routing strategy from §5 (item 2) applied to the quota.
- **Continuity design (most important resilience decision):** the orchestrator must checkpoint plan + per-task status to **durable storage** (Devin Knowledge note *and* a repo `PROGRESS.md`) after every task, so if it sleeps/pauses, the daily allowance runs out, or Fable 5 is briefly unavailable (§1.1), a **fresh orchestrator session reads state and continues** rather than restarting. Recovery prompt: *"Read `PROGRESS.md`; resume from the first incomplete task."*

### 4.4 MCPs / connectors / tools to install & configure (concrete, for this project)
You asked specifically what to install and wire up. For a small single-repo project, keep it lean — most of the HMAS "knowledge" plumbing is native to Devin, not extra MCPs:

**Required**
- **Git provider connector — GitHub.** Devin needs read/write to the `AviBackToBlack/lidaldi` repo and permission to open PRs. Configure the GitHub integration/OAuth and scope it to that repo. (This is the single must-have.)
- **Devin Knowledge** — create a project folder; seed it with a concise provisional-decisions rule + the project's coding conventions (the architecture doc itself lives in the repo and is indexed by DeepWiki). This is the shared "Central Context Bridge" and the home for the `PROGRESS.md`-style continuity notes. Turn on suggested-knowledge capture.
- **Devin Wiki / DeepWiki** — index the repo so every worker shares one understanding of the codebase. Enable it **once** under **Settings → DeepWiki** (low effort + weekly auto-refresh is fine); no separate mid-run generation needed. (Costs ACUs per generation — refresh sparingly.)

**Recommended (cheap wins)**
- **Playbooks** — not an install, but *configure* two: one for the standard refactor-a-module task (structured JSON output: status, files, PR, follow-ups) and one for the verifier pass. This is how re-planning + worker contracts get standardized.

**Design tooling (external, not a Devin MCP)**
- **Claude Design (Anthropic Labs) — the mandated design tool.** Design is produced in Claude Design under the operator's Claude subscription, and its exports (design system / tokens / HTML) are committed to the repo for the front-end workers to consume (see §6.7, master goal §3.11). It is operator-driven — a Devin worker does not log into it — so the committed exports are the seam.

**Optional (only if the workstream justifies it)**
- **Figma MCP (official, GA in Devin)** — optional; only if a Claude Design export needs a Figma round-trip. For a project this size the committed design-system/tokens are usually enough.
- **Observability MCP (Sentry / Datadog / PostHog)** — you already emit Prometheus textfiles, so runtime monitoring is covered; add one of these only if you want the agent to *read* production telemetry during debugging.

**Not needed**
- Filesystem/other generic MCPs — each Devin worker has its own VM + the git checkout; no extra file bridge required.
- **UI-testing tooling is *not* an MCP** — Playwright runs inside the worker VM / CI compose stack (§6.6), not as a connector. Devin's built-in computer-use can drive a live browser for ad-hoc UAT if you want it.

**Hardening while configuring:** use **MCP read-only mode** where a server only needs reads, scope secrets **personal vs org** deliberately, and keep the GitHub token least-privilege. App secrets (VAPID keys, sync config) are **not** Devin MCPs — the §6.5 installer manages those on the VPS.

---

## 5. Fable 5 as the top orchestrator — best practices

Straight from Anthropic's official "Prompting Claude Fable 5" guidance (current), tuned to this project:

1. **Aim it at the hard, whole thing.** Fable 5 is built for multi-hour/-day, ambiguous, end-to-end runs. Give it the entire refactor goal and let it scope — don't pre-chop it into trivial steps (that undersells it and wastes Fable tokens).
2. **Model routing, not one model everywhere.** Fable 5 for orchestration/architecture/final review; Sonnet/Opus for implementation workers; Haiku for scan/extract. In Devin terms: Ultra(Fable 5) coordinator, child Devins on cheaper modes for mechanical work.
3. **Effort control.** Default `high`, `xhigh` for the gnarliest design/debug work, `medium/low` for routine. Lower effort on Fable 5 still beats prior models' `xhigh`.
4. **Parallel subagents, async.** Fable 5 dispatches subagents readily; prefer **async** delegation over blocking on each worker. Long-lived workers keep context (cache-read savings). This is the core of your Multi-Devin fan-out.
5. **Ground progress claims.** Instruct: *"audit each claim against a tool result this session; only report what you can point to."* Nearly eliminates fabricated "done" reports on long runs — essential for an unattended loop.
6. **State boundaries + stop rules.** It can take unrequested actions and, deep in long runs, occasionally *say* it'll do something without the tool call. Counter both: define what it must **not** do, and add the autonomous-pipeline reminder (*"you're operating autonomously; for reversible actions that follow from the goal, proceed without asking; before ending a turn, if your last paragraph is a plan/promise, do it now"*). This is precisely how you get "stop only when all tasks are done."
7. **Verifier subagents > self-critique.** Fresh-context verifier subagents against the spec at a fixed interval. Wire this as your Generator-Verifier loop.
8. **Memory system.** Give it a Markdown notes dir (or Devin Knowledge): one lesson per file, one-line summary on top, update-don't-duplicate. This is your Autonomous Knowledge Management.
9. **Don't make it echo its reasoning.** Prompts that say "show your thinking as text" can trigger `reasoning_extraction` refusals → Opus fallbacks. Read structured `thinking` blocks; surface progress via a `send_to_user` tool.
10. **Refactor old scaffolding.** Instructions written for older models are often too prescriptive and *hurt* Fable 5. If you port any existing prompts/skills, strip the workarounds.
11. **Give the "why."** Tell it who the site is for and what the refactor enables — Fable 5 uses intent to connect tasks to context.
12. **Async harness.** Individual turns can run many minutes; runs span hours. Check on it via scheduled polls, not a blocking wait; adjust timeouts.

**Where Fable 5 physically sits as "the top":** run it as the **Devin Cloud Ultra orchestrator session** (Ultra = Fable 5) whose prompt is your single goal Markdown (or a Playbook wrapping it). It then spawns child Devins. Alternative: run Fable 5 inside Claude (Cowork/Code `/goal`) and drive Devin workers via the Devin API/MCP — more flexible, more moving parts, more places for the loop to break. Recommend the in-Devin option first.

---

## 6. Proposed architecture

### 6.1 Topology (two tiers)

```
                ┌─────────────────────────────────────────────┐
                │  ORCHESTRATOR  (Devin Cloud Ultra = Fable 5) │
                │  Input: single Markdown goal / Playbook      │
                │  Owns: plan, task DAG, stop rules, final QA  │
                │  Never touches tools directly — reads worker │
                │  summaries, re-plans, compiles results       │
                └───────────────┬─────────────────────────────┘
        durable state ▲         │ delegates (async, parallel)
        (Knowledge /   │         ▼
         PROGRESS.md)  │  ┌──────────┬──────────┬──────────┬──────────┐
                       │  │ Worker A │ Worker B │ Worker C │ Worker D │
                       │  │ Backend  │ Front-end│ UI/Design│ DevOps / │
                       │  │ refactor │ rewrite  │ system   │ installer│
                       │  └────┬─────┴────┬─────┴────┬─────┴────┬─────┘
                       │       ▼          ▼          ▼          ▼
                       │  ┌─────────────────────────────────────────┐
                       └──│ VERIFIER subagents (fresh context)       │
                          │ tests, cross-browser E2E, security scan  │
                          └─────────────────────────────────────────┘
```

- **Orchestrator (Fable 5 / Ultra):** ingests the goal, builds the task DAG, dispatches workers async, runs periodic verifier passes, re-plans on failure, and only stops when every task's success criteria are met + verifiers are green.
- **Workers (child Devins) — roles are illustrative, not a fixed roster:** the A/B/C/D split in the diagram is only an example. The orchestrator decides the real decomposition, which subtasks merit a specialized-role agent, and authors each agent's prompt (see §3 and master goal §1/§3.3). Each worker is a full Devin with its own VM and a scoped Playbook; returns **structured JSON** (status, artifacts, PR link, follow-ups).
- **Verifiers:** fresh-context subagents that check work against the spec — never the same context that produced it.
- **Central Context Bridge:** Devin **Knowledge** + repo **`PROGRESS.md`** + Wiki as the shared memory all tiers read/write.

### 6.2 Recommended entry point
**app.devin.ai dashboard for the first supervised runs** (you watch the Agents tab), with the goal captured as a **Playbook** so re-runs are one click and CLI/API-automatable later. Rationale: the maintainer is actively supervising and wants sign-off gates; the dashboard gives visibility into child sessions, ACU spend, and lets you intervene. Move to CLI/API once the loop is trusted.

### 6.3 The two-loop structure you described
- **Loop 1 — Requirements/Design (this doc + your answers):** orchestrator produces the spec, architecture, and design direction; **hard stop for your sign-off.** ← we are here.
- **Loop 2 — Implementation:** only starts after sign-off; runs to completion with verifier gates. Encode "stop only when all tasks done" via the Fable 5 autonomous-pipeline + progress-grounding instructions (§5, items 5–6).

### 6.4 Quota / continuity plan (concrete, Pro-tuned)
- **Fan-out 2–4 workers**, not 10. Concurrency cap is 10 (Pro), but the daily/weekly allowance is the real limiter — keep it narrow.
- **Model routing to stretch the allowance:** Fable 5 (Ultra) only for the orchestrator + verifier passes; workers on Sonnet/Haiku/SWE 1.6 for mechanical implementation.
- Set **per-session ACU hard caps** in settings for each worker; the orchestrator reports spend per task via `send_to_user`.
- Decide the **out-of-allowance policy up front:** *wait for the daily refresh* (free, fine for a multi-day run) vs *buy API-priced overage* (faster). For an unattended overnight loop, waiting is usually the right default.
- After **every** completed task, orchestrator writes plan+status to `PROGRESS.md` **and** a Devin Knowledge note. Recovery prompt: *"read `PROGRESS.md`, resume from first incomplete task."*
- **Fable 5 unavailability fallback:** configure Opus 4.8 fallback; if Fable 5 is pulled again mid-run (see §1.1) or trips a safety classifier, the loop degrades to Opus rather than dying.

### 6.5 Auto-update-from-git installer (your explicit requirement)
Design a single idempotent updater (a `deploy/update.sh` + a small Python step) triggered after `git pull` in a separate checkout, driven by a **local, git-ignored `install.local.conf`** so paths differ per environment (the deployment's real `APP_ROOT` and `WEB_ROOT` — e.g. the README defaults `/opt/lidaldi` and `/var/www/lidaldi` — with the live values kept out of the repo):

- **Local config:** `install.local.conf` holds `APP_ROOT`, `WEB_ROOT`, `SERVICE_USER`, `SYNC_DIR`, `LOG_DIR`, `PROM_DIR`. Everything else derives from it. Ship `install.local.conf.sample`.
- **Sample→real config merge (the core gap):** treat `*.sample.py` as the **schema**. On update, for each `config.py`/`settings.py`: load both, **add keys present in the sample but missing in the live file** (with sample defaults), **never overwrite** existing live values, and **report removed/renamed keys** for manual review. Back up the live file first. (A tiny AST/`ast.literal_eval` or a move to a non-executable format like TOML/`.env` makes this safe and diffable — worth considering in the rewrite.)
- **Idempotent resource management** (create-or-update): system user, `cron.d/lidaldi`, `logrotate.d/lidaldi`, `systemd/lidaldi-sync.service` (with `daemon-reload` + restart on change), web root perms. Each step checks current state and only acts on drift.
- **Safety:** dry-run mode, diff output before applying, and a `--no-restart` flag. This is production-impacting, so per the project's operating rules it's a "confirm before running" class of change.
- **Target env:** **Ubuntu**, single VPS.

### 6.6 Testing strategy (overview — no host installs)
Single workflow, reproducible locally (Docker Desktop) and in CI (GitHub Actions), nothing installed on the Windows box:

- **Harness:** **DevContainer** for the dev env; **Docker Compose** to stand up the full POSIX pipeline (scraper, processor, sync server, nginx, a headless browser) for integration/system tests. One entry point: `make test` (or a compose profile) that CI and your laptop both call.
- **Unit:** `pytest` for Python (scraper pipelines, matching, sync store, notification payloads); a JS unit runner (Vitest) for front-end logic once it's modularized out of the 1,311-line file.
- **Integration:** spin up `sync_server` + a temp profile store; assert sync/merge/tombstone logic and the new aggregate-notification payload.
- **System / E2E + UI:** **Playwright** (the modern Selenium replacement) — bundled **Chromium, Firefox, and WebKit** engines. **WebKit ≈ Safari and catches the Mac rendering class of bug (#1) that Chrome-on-Windows hides.** Cover: page-size/grid across viewports, arrow-key pagination after interacting with filters (bug #3), new-from-last-visit state (bug #2), and the alerts deep-link view (bug #4).
- **Regression:** Playwright **visual snapshots** (per engine) to lock layout so the "constant redesign drift" can't silently return.
- **Performance/Load:** **k6** or **Locust** against the sync API in the same compose network.
- **Security:** `pip-audit` + `bandit` (Python), `npm audit`/Retire.js (front-end), OWASP **ZAP baseline** scan against the composed site; verify the existing XSS/URL protections still hold.
- **UAT:** the compose stack *is* the local UAT environment — browse a realistic build before sign-off.

### 6.7 Design direction (keep-and-modernize)
Preserve what you like, fix what's broken:
- **Keep:** single-row button/dropdown/textarea filter bar; Last-Updated / Your-Last-Visit; auto-fitting responsive card grid with bottom pager + arrow-key paging; hover description popover; Web Push (fixed).
- **Add:** an **ALDI / LIDL / Both** store filter (currently only inferable via search).
- **Rebuild properly:** the popover (native Popover API or a small controller), the focus model (roving tabindex), the newness model (server `first_seen`), and the notification→alerts-view deep link.
- **Stack (decided): component framework + build, static output.** The build must emit **plain static assets** deployable to the existing nginx/`/var/www` setup — **no SSR server** to run on the VPS, keeping deploy as simple as today. Framework shortlist and recommendation in §6.7.1.
- **Design tool (mandated): Claude Design.** All new visual/UI work uses **Claude Design** (Anthropic Labs) — it reads the codebase, builds a consistent design system, produces interactive prototypes, and exports to HTML / tokens / PPTX. Use it to define the modern visual language (type scale, spacing, color beyond the ALDI/LIDL brand cues, card + filter-bar restyle, motion); **export the design system + prototype and commit it as the design source of truth** the front-end workers implement against. Keep the *ideas* (single-row filters, auto-fit grid, arrow paging, popover); restyle everything else freely. Prereq: a Claude **Pro/Max/Team/Enterprise** subscription (separate from Devin Pro); Claude Design is operator-driven (a Devin worker VM can't log into it), so its committed exports are the hand-off.
- **Design as a *role* is orchestrator-decided, not a fixed worker:** whether a dedicated design-role sub-agent is spun up around the Claude Design output is the orchestrator's call (master goal §1/§3.11) — the earlier "Product Designer worker" was only a suggestion.

#### 6.7.1 Framework — **DECIDED: Svelte / SvelteKit (static/SPA adapter)** ✅
Chosen 2026-07-05. Compiles away to tiny vanilla JS (closest to the current lightweight ethos), first-class transitions/stores, excellent DX, and a trivial static build (`adapter-static`) that drops straight into the existing nginx/`/var/www` deploy with no SSR server. Implementation notes for Loop 2: SPA mode (`adapter-static` with a fallback), Vite build, keep the service worker (`sw.js`) and offers-data injection working with the static output, and structure state (filters, sync, alerts) as Svelte stores. (Alternatives considered and rejected for this app: SolidJS, Vue 3, React.)

---

## 7. Added scope (all approved)

### 7.1 Deep-linkable filter state — reconciled with the single-page design ✅
**Clarification (my v1 wording was misleading):** deep-linkable URL state does **not** conflict with the single-page approach and does **not** cause a reload. The mechanism is the browser **History API**:
- As filters change, call `history.replaceState`/`pushState` to update the URL's query/hash **in place** — the page never navigates or reloads; it's the same SPA, just with a URL that reflects state. `pushState` for meaningful state changes (so Back/Forward work), `replaceState` for keystroke-level noise.
- The app reads the URL **once on init** to restore state, and listens to `popstate` for Back/Forward.
- The **only** real page load is when someone arrives **fresh** — which is exactly the push-notification case (bug #4): the notification opens `/?view=alerts&alert=<id>` on the site, the SPA boots, reads the query, and renders the alert view with the Alerts control highlighted. No reload penalty during normal browsing; correct behavior on cold entry.
- Bonus: this makes every filter state shareable/bookmarkable and makes E2E tests deterministic (navigate straight to a state).

### 7.2 Other approved additions
- **Stable product identity / `first_seen` field** server-side — fixes bug #2 properly and future-proofs "new" logic. ✅
- **Analytics-free observability** — carry the existing Prometheus textfiles forward so the refactor stays measurable (scrape success, notification delivery, sync errors). ✅
- **Accessibility pass** — keyboard nav is already a feature you value; make it a first-class, tested requirement (roving tabindex, `:focus-visible`, ARIA on the pager and modal). ✅
- **`manifest.json` + PWA installability** — push is already there; this completes the PWA, especially for the iOS Home-Screen push you support. ✅
- **Documentation refresh** — update `README.md` and project docs (new stack, install/update flow, config format, testing workflow, architecture) as part of the Definition of Done; remove stale instructions. ✅

---

## 8. Status of open questions

**Resolved (v2):** Devin plan (Pro, §4.3) · config → TOML/.env · deploy = Ubuntu VPS, automated · orchestrate in-Devin Ultra via app.devin.ai · hard-stop sign-off gates · scraper = plain cron, no special constraints · design latitude = modernize freely, keep the ideas, Product Designer worker approved · deep-links via History API (§7.1) · all §7 additions approved.

**All blocking decisions resolved.** Front-end framework = **Svelte/SvelteKit** (§6.7.1). Requirements phase is complete and ready for sign-off.

**To calibrate during the first run (not blocking):**
- **Real daily/weekly allowance headroom** — not published by Devin; read it off the in-app usage meter on the first supervised Ultra run to size fan-out and decide the wait-vs-overage policy (§6.4).

---

## 9. Sources

Devin / Cognition:
- [Devin Docs — 2026 Release Notes](https://docs.devin.ai/release-notes/2026)
- [Claude Fable 5 is now available in Devin (Cognition, 2026-06-09)](https://devin.ai/blog/claude-fable-5-available-in-devin/)
- [Devin Docs — Plans and Usage](https://docs.devin.ai/desktop/accounts/usage)
- [Devin Docs — Billing](https://docs.devin.ai/admin/billing)
- [Devin — Plans and Pricing](https://devin.ai/pricing/)
- [Cognition on X — removing Fable 5 access (export-control directive)](https://x.com/cognition/status/2065609115939062197)
- [Cognition on X — Fable 5 available in Devin Ultra/Desktop/CLI](https://x.com/cognition/status/2072405137117548601)
- [AlphaSignal — Devin restores Claude Fable 5 after government ban](https://alphasignal.ai/news/cognition-s-devin-restores-claude-fable-5-after-a-messy-government-ban)
- [Devin Fusion (Cognition)](https://cognition.com/blog/devin-fusion)

Fable 5 / Anthropic:
- [Prompting Claude Fable 5 — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5)
- [Introducing Claude Fable 5 and Claude Mythos 5 — Claude Platform Docs](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5-and-claude-mythos-5)
- [VentureBeat — Anthropic bringing back Fable 5 globally after export-control lift](https://venturebeat.com/technology/anthropic-is-bringing-back-claude-fable-5-globally-after-us-lifts-export-control-order-where-can-enterprises-access-it)
- [The Fable 5 Orchestrator Playbook — Developers Digest](https://www.developersdigest.tech/blog/fable-5-orchestrator-model-playbook)

HMAS / Loop Engineering:
- [AI Agent Orchestration Patterns 2026](https://jobsbyculture.com/blog/ai-agent-orchestration-patterns-2026)
- [Multi-Agent AI Orchestration: A CTO's 2026 Guide](https://kgt.solutions/resources/blog/multi-agent-ai-orchestration-cto-guide-2026)
- [Agentic Loops: From ReAct to Loop Engineering (2026)](https://datasciencedojo.com/blog/agentic-loops-explained-from-react-to-loop-engineering-2026-guide/)
- [Loop Engineering Guide 2026 — AI Builder Club](https://www.aibuilderclub.com/blog/loop-engineering-guide-2026)
