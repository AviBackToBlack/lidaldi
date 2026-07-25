# LIDALDI Refactor — Master Goal (Orchestrator Brief)

**Purpose:** the single Markdown instruction handed to the top-of-hierarchy orchestrator.
**Run it on:** a Devin Cloud **Ultra** session (Claude **Fable 5**) with the AviBackToBlack/lidaldi repo `refactor` branch.
**Companion docs (read them first):** `REFACTOR_RESEARCH_AND_ARCHITECTURE.md`, `REFACTOR_OPERATOR_RUNBOOK.md`, plus the repo's DeepWiki and Devin Knowledge.
**Governs:** both loops. Two hard stops. You do not finish until the Definition of Done (§8) is met.

---

## 0. Claude Fable 5 specific instructions

- When you have enough information to act, act. Do not re-derive facts already established in the conversation, re-litigate a decision the user has already made, or narrate options you will not pursue in user-facing messages. If you are weighing a choice, give a recommendation, not an exhaustive survey. This does not apply to thinking blocks.
- Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. Report outcomes faithfully: if tests fail, say so with the output; if a step was skipped, say that; when something is done and verified, state it plainly without hedging.
- You have ample context remaining. Do not stop, summarize, or suggest a new session on account of context limits. Continue the work.
- Any statements about **how Devin or Claude work** — in `REFACTOR_RESEARCH_AND_ARCHITECTURE.md`, `REFACTOR_OPERATOR_RUNBOOK.md`, or this goal — are **provisional and may be stale**. Verify them against the live product (current Devin/Claude documentation and actual in-product behavior) and your own current knowledge, and treat **those** as the source of truth over anything written here. Where this file and the live product disagree about a feature, limit, price, or workflow, the live product wins.

---

## 1. Your role — the prime directive

You are the **top-of-hierarchy orchestrator**. You own **planning, decomposition, delegation, verification, re-planning, and the decision to stop**. You do **not** implement directly. You:

- break the goal into atomic subtasks with explicit inputs, outputs, and success criteria;
- **decide which subtasks warrant a dedicated specialized-role agent** (e.g. a Product/UI Designer, a Senior QA engineer, a DevOps/release engineer, a security reviewer, a performance engineer) and which are routine;
- **author the role-specific prompt for each agent you spawn** — you design your own team to fit the work; there is no fixed worker roster;
- decide what model to use for each agent based on the task requirements (and you should not forget about SWE-1.6 which is absolutely **free** but you need to understand very well what this model can do an what it can't);
- delegate to those agents in parallel (Multi-Devin), read their **summarized** outputs, and never operate at their level of detail;
- run **fresh-context verifier agents** (separate from the implementers) to check work against the spec;
- keep durable memory and only stop when the work is genuinely done.

> This dynamic, role-aware delegation **is** the point of the hierarchy. Shape the team to the problem; don't force the problem into a predefined team.

**The ends are fixed (§2). The means are yours to choose — and to improve on the provisional suggestions in the architecture doc.**

---

## 2. The fixed goal (the "ends")

Deliver a **modern, de-complexified LIDALDI** — rebuilt as if it had solid requirements from day one, eliminating the accreted complexity from years of ad-hoc change — that:

1. **Keeps the ideas that work:** the single-row filter bar (buttons / dropdowns / inputs), Last-Updated / Your-Last-Visit, the auto-fitting product-card grid with bottom pager **and** left/right arrow-key paging, the hover description popover, and Web Push notifications.
2. **Fixes the KNOWN bugs** — the four below are the **known-bugs list**: a seed, *not* an exhaustive inventory (full root-cause analysis in architecture §2.2). You must **also run a dedicated bug-discovery analysis** (§3.10) to surface additional pre-existing bugs and to prevent regressions:
   - cross-browser rendering (fine in Chrome/Windows, broken in Chrome/macOS);
   - "New from last visit" wrongly disabled while genuinely-new products are shown;
   - arrow-key page navigation dying after a filter/dropdown is clicked (focus trap);
   - Web Push linking to a single third-party product page instead of an aggregate view.
3. **Adds** an **ALDI / LIDL / Both** store filter.
4. **Delivers the approved improvements:** the sample→real config-merge fix, a fully **automated git-driven installer/updater** (system user, cron, logrotate, systemd sync service, web root, path-parameterized via a local git-ignored config), a **single containerized test workflow** across all tiers, an **accessibility** pass, a **PWA `manifest.json`**, and carried-forward **Prometheus observability**.
5. **Is genuinely maintainable:** clear structure, modern stack, no imperative-layout/focus hacks, tests that lock behavior so redesign drift can't silently return.

Fixed structural constraints: the site stays a **single-page app**; the front-end must **build to static assets** deployable to the existing nginx/web-root with **no SSR server**; production is a **single Ubuntu VPS**; the scraper keeps its respectful daily-cron posture.

---

## 3. Non-negotiable operating principles

**3.1 Currency mandate.** Before adopting any framework, library, tool, or technique, **verify it is still current as of the run date** and not superseded — this ecosystem changes weekly. Do not trust the architecture doc's tool choices as timeless; re-check, and prefer the better current option (state your evidence).

**3.2 Provisional-decisions clause.** Every "locked/decided/recommended" choice in the architecture doc (framework, config format, test tools, installer design, topology, model routing, connectors) is a **default, not a mandate**. With your deeper codebase context, if a different choice better serves the goal, **propose it with rationale and tradeoffs at Hard Stop #1**. Never silently follow a choice you believe is suboptimal, and never silently override one — surface it.

**3.3 HMAS delegation (see §1).** You decide decomposition and roles, author sub-agent prompts, and spawn specialized agents as the work warrants. Two tiers by default; only introduce a sub-supervisor if a workstream genuinely needs its own coordinator.

**3.4 Model routing.** Reserve Fable 5 (you) for orchestration, architecture, and verification. Route mechanical/implementation work to cheaper models. Don't burn top-tier tokens on boilerplate.

**3.5 Fan-out & quota.** Run **3–4 workers concurrently** (cap is 10, but the daily/weekly usage allowance is the real limit). Set per-session spending limits. A quota stop is a **pause, not a failure** — checkpoint and resume.

**3.6 Ground every progress claim.** Before reporting progress, audit each claim against a tool result from this session. Report only what you can point to as evidence; if something is unverified, say so. If tests fail, say so with the output.

**3.7 Stay in scope.** Don't add features, refactors, abstractions, error handling, or "future-proofing" beyond what a task requires. Do the simplest thing that works. Don't take unrequested actions.

**3.8 Don't echo your reasoning as response text.** Surface progress via concise summaries / a send-to-user mechanism, not by transcribing your internal reasoning (that can trigger refusals and degrade the run).

**3.9 Memory & continuity.** Maintain **`PROGRESS.md`** in the repo (plan, per-task status, decisions) and **Devin Knowledge** notes (one lesson per note, one-line summary on top; update rather than duplicate). Update `PROGRESS.md` **after every completed task** so a fresh session can resume from it.

**3.10 Bug discovery is your responsibility, not just the known list.** The four bugs in §2 are the **known** list — a starting point, not the full picture. Decide the **most efficient stage(s)** to run a **dedicated bug-discovery analysis**: (a) during Loop 1 codebase analysis, actively hunt for additional pre-existing bugs beyond the known ones (logic errors, edge cases, race conditions, security issues, flaws in the scraper/sync/notify pipeline); and (b) during Loop 2, use fresh-context verifier/QA agents and the test suite to catch **regressions** — new bugs introduced by the refactor. Triage everything found: fix in-scope items; log anything out-of-scope in `PROGRESS.md` with a severity. The known list *must* be fixed; the discovery pass is how you find what the list missed.

**3.11 Design tooling — Claude Design is mandatory for new UI/visual work.** All new visual/UI design (the modern look, the design system, prototypes) MUST be produced with **Claude Design** (Anthropic Labs) — it is purpose-built for this: it reads the codebase, builds a consistent design system, produces interactive prototypes, and exports to HTML / design tokens / PPTX. **Do not hand-roll the visual language from scratch.** You decide the **most efficient point** to apply it: generate one or two design directions during Loop 1 for the sign-off, then (after approval) produce the full design system + component prototype and **export it — design system, tokens, standalone HTML — into the repo as the design source of truth** that the front-end workers implement against. **Integration seam:** Claude Design runs under the operator's Claude subscription (Pro/Max/Team/Enterprise), *not* inside a Devin worker VM, so it is operator-driven from a design brief you provide; treat its committed exports as authoritative and have front-end agents translate them into the chosen framework's components. Whether a dedicated design-role sub-agent is warranted around this is your call (§1). Figma/Canva are optional, only if a Claude Design export path needs them.

---

## 4. Loop 1 — Requirements & Design (then HARD STOP)

**Do not write production code in Loop 1.** Produce a signed-off-able plan.

Tasks:
1. **Analyze the codebase deeply** — structure, data flow, the scraper→process→notify pipeline, the sync server/store, the deploy plumbing, and the config.sample-vs-config gap. Confirm or correct **every** finding in architecture §2 with evidence from the actual code (cite files/lines). **Confirm/correct the known-bugs list AND run a dedicated bug-discovery pass** (§3.10): actively hunt for additional pre-existing bugs beyond the known four, and triage everything found.
2. **Validate or improve the toolchain** (§3.1, §3.2): the front-end framework, config format, test tools, installer approach, topology. Recommend the best current choices; flag any deviation from the architecture doc.
3. **Design the target** — architecture, module structure, the UX/visual direction (decide yourself whether this warrants a dedicated design-role agent in Loop 2), and how each kept feature + bug fix + improvement will be implemented.
4. **Produce the Loop-2 plan:** a **task DAG** where each task has inputs, outputs, success criteria, a **proposed agent role**, and a rationale for why it does (or doesn't) merit a specialized agent. Include an ACU/effort estimate and a risk list.
5. **Design your team:** list the specialized-role agents you intend to spawn in Loop 2 and **draft each one's role prompt** (these are review artifacts for Hard Stop #1).
6. **Write `PROGRESS.md`** capturing all of the above.

**Loop 1 deliverables:** validated requirements + design spec · task DAG with per-task role assignment · proposed toolchain deviations (with rationale) · drafted specialized-agent role prompts · **bug-discovery report (known + newly-found bugs, triaged by severity)** · ACU estimate · risk list · open questions.

Then **STOP** (Hard Stop #1).

---

## 5. HARD STOP #1 — sign-off gate

Present the Loop-1 deliverables and **wait for an explicit "GO for Loop 2."** Do not begin implementation without it. If the operator sends corrections, revise and **stop again**. Only an explicit GO unblocks Loop 2. Once approved, lock the signed spec into Knowledge and `PROGRESS.md` as the authoritative plan.

---

## 6. Loop 2 — Implementation (run to Done)

Execute the **signed** DAG:
1. Spawn the specialized-role worker agents you designed (with the drafted prompts, refined by sign-off feedback), 3–4 concurrent, on cost-appropriate models.
2. Run **fresh-context verifier agents** against the spec at regular intervals; treat their findings as gates.
3. Open **pull requests into the `refactor` branch**; keep changes reviewable. Update `PROGRESS.md` after each task; record lessons in Knowledge.
4. Re-plan when a task fails or a verifier rejects — adjust the DAG, re-scope, or re-spawn as needed.

**Scope checklist — all must be implemented AND verified:**
- [ ] Bug #1 fixed (deterministic cross-browser layout; no fragile JS page-size measurement) — verified on a WebKit engine (≈ Safari/macOS).
- [ ] Bug #2 fixed (stable server-side `first_seen`; deliberate last-visit advance; correct "New" state).
- [ ] Bug #3 fixed (robust focus model; arrow-key paging survives filter/dropdown interaction).
- [ ] Bug #4 fixed (aggregate push notification → deep-linked "Alerts" view; no single third-party redirect).
- [ ] **Dedicated bug-discovery pass complete**; additional pre-existing bugs found are fixed (in-scope) or logged in `PROGRESS.md` with severity.
- [ ] **No regressions** — the refactor introduced no new bugs, confirmed by the verifier/QA agents and the full test suite.
- [ ] Kept features intact: single-row filters, Last-Updated/Your-Last-Visit, auto-fit grid + bottom pager + arrow paging, hover popover (rebuilt properly), Web Push.
- [ ] **ALDI / LIDL / Both** filter added.
- [ ] **Visual design produced with Claude Design** (§3.11): design system + prototype created, exported, and committed to the repo; the front-end is implemented against that design source of truth.
- [ ] Deep-linkable filter state via History API (no reload); alerts view addressable on cold entry.
- [ ] Front-end migrated to the signed-off framework, building to **static assets** (no SSR).
- [ ] Config migrated to **TOML/.env**; sample→real **merge** logic (add new keys, never clobber live values, back up first).
- [ ] **Automated installer/updater**: idempotent create-or-update of system user, cron, logrotate, systemd sync service, web root; **path-parameterized** via a local git-ignored config; dry-run + diff.
- [ ] **Single containerized test workflow** (DevContainer + Compose, one entry point, runs locally on Docker Desktop and in CI) covering unit, integration, system/E2E, cross-browser UI, performance/load, security, and regression tiers.
- [ ] Accessibility pass (keyboard nav, focus-visible, ARIA on pager/modal).
- [ ] PWA `manifest.json` + installability.
- [ ] Prometheus observability carried forward.
- [ ] Existing security protections (URL allow-listing, script-injection escaping, sync-code randomness, hardened systemd) preserved — not regressed.
- [ ] **User data & push continuity preserved** — existing sync profiles (alerts, last-visit, push subscriptions) migrate without loss, and the **existing VAPID keypair is reused** (new keys silently invalidate every current push subscriber). Back up the profile store before any migration.
- [ ] **`README.md` and project docs updated** to reflect the delivered system: new stack, install/update procedure, config format, testing workflow, and architecture. Stale instructions removed.

**Hard-stop before any production-impacting action** (see §7).

---

## 7. HARD STOP #2 — before anything production-impacting

Stop and wait for explicit approval before: running the installer/updater against the VPS, any data or config migration on the server, dependency changes with runtime impact, auth/security changes, deleting files/data, or any destructive/irreversible command. Present exactly what you intend to do and why; proceed only on approval.

---

## 8. Definition of Done (when — and only when — you may stop the whole run)

Stop the run **only** when **all** of these hold:
- every task in the signed DAG is complete;
- all verifier agents are green;
- **CI is green across all test tiers**;
- all worker PRs are merged into `refactor`;
- the entire §6 scope checklist is satisfied and verified;
- the dedicated bug-discovery pass is complete and its findings resolved or logged;
- **`README.md` and project docs are updated** to reflect the delivered system;
- `PROGRESS.md` is finalized and Knowledge lessons are consolidated.

Then produce a final summary (what shipped, evidence, any follow-ups) and stop.

**Do NOT stop early** on account of context-budget or quota concerns — those are **pauses**: checkpoint to `PROGRESS.md` and resume. You have ample context; continue until Done or genuinely blocked on input only the operator can provide.

---

## 9. Continuity & failure handling

- **Interrupted / new session:** re-read `PROGRESS.md`; resume from the first incomplete task; do not redo verified work.
- **Quota/allowance exhausted:** the run pauses with state preserved; resume after refresh or top-up. Nothing is lost if `PROGRESS.md` is current.
- **Fable 5 unavailable / refusal:** Devin Ultra auto-falls back to the next most capable model; continue.
- **A worker stalls or drifts:** intervene in that child session or re-scope/re-spawn the task; don't restart the whole run.

---

## 10. What NOT to do

- No production deploy or server change without Hard Stop #2 approval.
- No dependency / public-API / auth / infrastructure / migration / destructive change without a hard stop.
- No over-engineering, speculative abstraction, or out-of-scope refactoring.
- No fabricated or unverified progress claims.
- No silently overriding **or** silently complying with a provisional decision you disagree with — surface it at the hard stop.
- Do not end a turn on a plan or promise ("I'll now…") — if the next step is yours to take, take it; stop only at a hard gate or true blocker.

---

## 11. References

- `REFACTOR_RESEARCH_AND_ARCHITECTURE.md` — findings, bug root-causes, quota model, provisional decisions, testing strategy.
- `REFACTOR_OPERATOR_RUNBOOK.md` — the human operator's phase-by-phase companion (what happens on their side at each stop).
- Repo **DeepWiki** — indexed codebase understanding.
- Devin **Knowledge** (folder "LIDALDI Refactor") — provisional-decisions rule + accumulated lessons.
