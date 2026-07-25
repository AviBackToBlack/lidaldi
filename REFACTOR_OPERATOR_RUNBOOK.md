# LIDALDI Refactor — Operator Runbook

**Companion to:** `REFACTOR_RESEARCH_AND_ARCHITECTURE.md`
**Audience:** the project maintainer / human operator
**Date:** 2026-07-05
**Covers:** Phase 0 prep/config → start Loop 1 → handle the hard stop → run Loop 2 → what to do when Loop 2 finishes.

> TL;DR of the whole flow: **Configure Devin + GitHub + Knowledge once (Phase 0). Launch a Devin Ultra (Fable 5) session with the Loop-1 goal (Phase 1). It analyzes the codebase and hard-stops with a spec + proposed deviations — you review and say GO (Phase 2). Loop 2 spawns 2–4 worker Devins, opens PRs, self-verifies, and hard-stops before anything touching production (Phase 3). When it reports done, you do local UAT, then run the automated installer on the VPS yourself (Phase 4).** Quota running out is a *pause, not a loss* — you wait for the daily refresh or buy overage, then resume with a one-line recovery prompt.

---

## Legend / conventions

- **Orchestrator** = the Devin Ultra session running Fable 5 (top of the hierarchy).
- **Worker** = a managed child Devin spawned by the orchestrator.
- **Hard stop** = the orchestrator pauses and waits for your explicit approval before continuing.
- **`PROGRESS.md`** = the durable checkpoint file in the repo the orchestrator updates after every task; your recovery anchor.
- Anything marked **[you]** is a manual action; **[agent]** is done by Devin.

---

## Phase 0 — One-time preparation & configuration

Do these once, before the first run. ~30–45 min.

### 0.1 Confirm Devin + Fable 5 access  [you]
1. Log in at **https://app.devin.ai**. Confirm your plan shows **Pro**.
2. Open the agent/model picker and confirm **Ultra** is available and **Claude Fable 5** is selectable.
3. **Model fallback is automatic — there is no toggle.** If Fable 5 is ever unavailable (it had an export-control wobble in June — architecture §1.1), Devin Ultra automatically uses the most capable available model (e.g. Opus 4.8). Nothing to configure.

### 0.2 GitHub connection  [you] — likely already done
GitHub lives under **Settings → Connectors** (not "Integrations"). You should see **GitHub — Connected**, and your repos (including **lidaldi**) under **Settings → Repositories**. If lidaldi appears there, you're set. Optional sanity check: start a throwaway session and ask it to list the repo's top-level files, then archive it.

### 0.3 Prepare the repo for agent work  [you]
1. Make sure `main` is clean and pushed.
2. **Branch strategy:** workers open PRs into an integration branch, e.g. **`refactor`**, not directly into `main`.
   - `git checkout -b refactor && git push -u origin refactor`
   - Add **branch protection on `main`** (require PR + green CI) so nothing lands unreviewed.
3. Commit both planning docs (`REFACTOR_RESEARCH_AND_ARCHITECTURE.md`, `REFACTOR_OPERATOR_RUNBOOK.md`) — sanitized versions — so the agent (and DeepWiki) can read them from the repo.

### 0.4 DeepWiki indexing  [you] — likely already done
Enable DeepWiki indexing for lidaldi under **Settings → DeepWiki** (a low effort level + weekly auto-refresh is a fine, cheap default). **This IS the "Wiki / Central-Context" step — no need to also generate a wiki during Loop 2.** DeepWiki indexes whatever is in the repo, so it will pick up the planning docs once you push them (0.3.3). Bump effort to medium only if workers report the wiki is too shallow.

### 0.5 Seed Devin Knowledge  [you]
The Knowledge UI has **no "add note from a file"** — you create entries via **Create Knowledge** (modal: Name, Contents, Macro, Folder, Pin to repository). Keep entries short — Knowledge is for high-signal *rules*, not whole documents (the docs live in the repo + DeepWiki).
1. In the **"LIDALDI Refactor"** folder → **Create Knowledge**.
2. **Name:** e.g. `Refactor — decisions are provisional`.
   **Contents:** *"Decisions in REFACTOR_RESEARCH_AND_ARCHITECTURE.md are PROVISIONAL defaults. With deeper codebase context, propose better tools/frameworks/approaches at the Loop 1 → Loop 2 hard stop; never silently follow or silently override."*
   **Macro:** leave blank (Macro = an optional trigger keyword that injects the note when typed — not needed here).
   **Folder:** LIDALDI Refactor.
   **Pin to repository:** the repo-specific option isn't offered (only **None / All Sessions**). Choose **All Sessions** if you use Devin mainly for lidaldi; otherwise **None** and rely on the folder + DeepWiki.
3. (Optional) a second entry with any coding conventions you care about.

### 0.6 Usage / spending guardrails  [you]
These controls live under **Settings → Usage** and **Settings → Plans** (not a per-session dialog):
- **Settings → Usage:** set a **default session spending limit** (caps ACU per session so no worker runs away) and, if you want uninterrupted runs, an **auto-reload threshold**.
- **Settings → Plans:** where you **top up / purchase extra usage** (consumed at API pricing, ~$2.25/ACU) beyond the daily/weekly quota.
- **Out-of-allowance policy** isn't a forced setting: either leave **auto-reload OFF** and simply wait for the daily/weekly quota to refresh (free — fine for a multi-day refactor), or turn **auto-reload ON** to keep going immediately at overage pricing.
- **Fan-out width is NOT a setting** — it's a line in the goal prompt (*"spawn at most 3–4 workers concurrently"*), bounded by the 10 concurrent-session cap.

### 0.7 Local review environment  [you]
Confirm **Docker Desktop** launches on your Windows box. You won't install test tools natively — you'll use it in Phase 4 to `docker compose up` and review/test the build. Nothing else to do now.

### 0.8 Confirm Claude Design access  [you]
The visual redesign is done in **Claude Design** (Anthropic Labs), which requires a **Claude Pro/Max/Team/Enterprise** subscription — **separate from your Devin Pro plan**. Confirm you can open Claude Design. You'll use it in Phase 3.0 to generate the design system + prototype and export it into the repo for the front-end workers (master goal §3.11).

### ✅ Phase 0 done-check
Plan = Pro, Ultra + Fable 5 available · GitHub connected (Connectors) & lidaldi in Repositories · DeepWiki indexing lidaldi · Knowledge folder + "decisions are provisional" rule · default session spending limit set (Settings → Usage) & out-of-allowance policy chosen · **Claude Design accessible** · sanitized docs committed · Docker Desktop launches.

---

## Phase 1 — Start Loop 1 (Requirements & Design)

Goal of Loop 1: the orchestrator **analyzes the real codebase**, validates/expands the architecture doc, produces a **signed-off-able spec + task plan**, lists any **proposed deviations**, and **hard-stops**. No implementation yet.

### 1.1 Open a new orchestrator session  [you]
1. app.devin.ai → **New session** → select **Ultra** (Fable 5) → attach the **`AviBackToBlack/lidaldi`** repo on the `refactor` branch.
2. Effort: **high**.

### 1.2 Give it the Loop-1 goal  [you]
Paste a prompt like the template below (adjust freely). This is a *starter*, not the full master-goal Markdown — the complete master-goal file can be produced separately as a follow-up (see the end of this runbook).

```
You are the top-of-hierarchy orchestrator for refactoring the LIDALDI project
(github.com/AviBackToBlack/lidaldi). Read these first from the repo and Knowledge:
- REFACTOR_RESEARCH_AND_ARCHITECTURE.md   (architecture + decisions — PROVISIONAL)
- REFACTOR_OPERATOR_RUNBOOK.md
- the repo's existing review prompts + any coding conventions

This is LOOP 1 (requirements & design only). Do NOT write production code yet.

Tasks:
1. Analyze the codebase deeply (structure, data flow, deploy plumbing, the
   config.sample vs config gap, the KNOWN-bugs list). Confirm or correct every
   finding in the architecture doc with evidence, AND run a dedicated bug-
   discovery pass for additional pre-existing bugs beyond the known list.
2. Treat every "locked/decided" choice in the architecture doc as a provisional
   default. If deeper analysis shows a better framework/tool/pattern/approach,
   propose it with rationale and tradeoffs. Do not silently follow or silently
   override — surface deviations for sign-off.
3. Produce: (a) a validated requirements + design spec, (b) a task DAG for Loop 2
   with inputs/outputs/success-criteria per task, (c) a list of proposed
   deviations, (d) any remaining open questions, (e) a rough ACU estimate.
4. Maintain PROGRESS.md in the repo as you work.

Operating rules:
- Before reporting progress, audit each claim against a tool result from this
  session; only report what you can point to evidence for.
- When you have produced the Loop-1 deliverables, STOP and wait for my explicit
  "GO for Loop 2". This is a hard stop. Do not begin implementation.
- You are operating with me supervising; for reversible analysis actions proceed
  without asking, but pause for genuine scope decisions.
```

### 1.3 Let it run and watch  [you/agent]
- Watch the **Agents tab** and the session log. Loop 1 is mostly analysis, so it should be relatively cheap.
- **Answer clarifying questions** it asks — this is the moment to close gaps.

### ✅ Phase 1 output
An updated spec, a Loop-2 task DAG, a **proposed-deviations list**, a **bug-discovery report** (known + newly-found bugs, triaged), open questions, an ACU estimate — and the session sitting at a **hard stop**.

---

## Phase 2 — The hard stop after Loop 1 (review & sign-off)

This is your first and most important gate. Spend real time here; it's cheap now and expensive later.

### 2.1 Review the deliverables  [you]
Read, in order:
1. **Proposed-deviations list** — the whole reason for the override clause. For each: **approve / reject / modify**. (e.g. it might argue Astro over Svelte, or `.env`-only over TOML, or a different test runner.)
2. **The spec** — does it match what you actually want? Are the kept-ideas preserved and the bugs correctly understood?
3. **The task DAG** — sensible decomposition? Anything missing (accessibility, PWA, observability, installer, sample→config merge)?
4. **ACU estimate + risks** — comfortable with the cost/scope?
5. **Claude Design direction(s)** — if the orchestrator produced one or two visual directions, pick/steer the look now, before implementation (cheapest point to change it).

### 2.2 Decide  [you]
- **Happy?** Reply with an explicit **"GO for Loop 2"** and your decisions on each deviation.
- **Not happy?** Send corrections. It revises and **hard-stops again**. Iterate until you're satisfied — do not GO prematurely.

### 2.3 Lock the source of truth  [you/agent]
Have the orchestrator write the **signed-off spec** into Knowledge and `PROGRESS.md` as the authoritative plan for Loop 2. Everything in Loop 2 references this, not the original provisional doc.

### ✅ Phase 2 gate
You have explicitly approved: the deviations, the spec, and the task DAG. Only then proceed.

---

## Phase 3 — Run Loop 2 (Implementation)

### 3.0 Establish the visual design in Claude Design  [you]
Before front-end work starts, produce the modern look in **Claude Design** (master goal §3.11):
1. Open **Claude Design**; give it the orchestrator's design brief (or point it at the repo) plus the kept-ideas constraints (single-row filter bar, auto-fit card grid, bottom pager + arrow paging, hover popover, ALDI/LIDL/Both filter).
2. Iterate on the canvas until the visual language + design system are right — keep the ALDI/LIDL brand cues, modernize everything else.
3. **Export** the design system + prototype (design tokens / standalone HTML) and **commit them to the `refactor` branch** as the design source of truth.
4. Tell the orchestrator where the exports live so the front-end workers implement against them.
(Claude Design is operator-driven — Devin workers can't log into it — so this export-and-commit is the hand-off seam.)

### 3.1 Kick off Loop 2  [you]
In the same (or a fresh) Ultra session, instruct: *"GO for Loop 2. Read the signed-off spec and PROGRESS.md. Execute to completion with verifier gates. Hard-stop before any production-impacting action."* Add the autonomous-run rules (architecture §5.5–5.6): ground progress claims, don't stop on context-budget worries, only pause for genuine blockers or production-impacting steps.

### 3.2 What the orchestrator does  [agent]
- Uses the already-indexed **DeepWiki** (Phase 0.4) for shared understanding; refreshes only if stale.
- Builds/loads **Playbooks** (refactor-a-module; verifier pass).
- Spawns **2–4 worker Devins** (cheaper models) in the specialized roles it designed in Loop 1 — the decomposition is its call, not a fixed roster.
- Runs **fresh-context verifier subagents** against the spec at intervals.
- Opens **PRs into `refactor`**, updates `PROGRESS.md` after each task.

### 3.3 Monitor  [you]
- **Agents tab:** worker status, todos, PRs.
- **PRs:** review as they open (or lean on Devin PR Review); merge into `refactor` when **CI is green**. CI = the single `make test` workflow (unit/integration/E2E/security) on GitHub Actions.
- **ACU spend:** keep an eye on the usage meter — this first real run is also how you **calibrate your true daily/weekly headroom** (architecture §4.3).

### 3.4 Handling the in-Loop hard stops  [you]
The orchestrator will **hard-stop before anything production-impacting** — the installer, migrations, touching the VPS, or anything destructive. When it does:
1. Review exactly what it wants to do and why.
2. Approve, modify, or decline. Reply to continue.

### 3.5 Handling quota exhaustion (the big one)  [you]
If you hit the daily/weekly allowance, the run **pauses / sleeps — state is preserved, nothing is lost.**
- **Wait-for-refresh:** come back after the allowance refreshes; reopen the session — it resumes.
- **Need it sooner:** buy overage (API pricing) and continue immediately.
- **If a session was terminated or you start fresh:** open a new Ultra session and paste the **recovery prompt**:
  ```
  Read PROGRESS.md in the lidaldi repo. Resume from the first incomplete task.
  Do not redo completed, verified work.
  ```
- This is why `PROGRESS.md` + Knowledge checkpoints matter — resumption is a one-liner.

### 3.6 Handling Fable 5 unavailability / refusals  [you]
If Fable 5 is pulled again or a safety classifier trips, Devin Ultra **falls back automatically** to the next most capable model (e.g. Opus 4.8) and continues — there is no fallback toggle to set. No action needed unless you see it stuck — then nudge with "continue".

### 3.7 If a worker goes off track  [you]
Open the child session from the Agents tab and message it directly (correct it or add missing context), or tell the orchestrator to re-scope/re-spawn that task. You don't have to restart the whole run.

### ✅ Phase 3 output
All task-DAG items implemented, workers' PRs merged into `refactor`, verifiers + CI green. The orchestrator reports a final summary and **stops**.

---

## Phase 4 — When Loop 2 is finished

### 4.1 Confirm the done-criteria  [you]
Don't take "done" on faith — check:
- Every task-DAG item complete; verifier subagents green; **CI green across all tiers** (unit, integration, E2E, security).
- The known bugs fixed, the dedicated bug-discovery findings resolved or logged, and no regressions; kept-ideas intact; **ALDI/LIDL/Both filter** added; approved improvements present (auto-updater, sample→config merge, accessibility, PWA `manifest.json`, observability, **`README.md` + docs updated**).

### 4.2 Local acceptance testing (UAT) on your machine  [you]
Nothing installed natively — use Docker Desktop:
1. `git fetch && git checkout refactor && git pull`
2. `docker compose up` (or the documented `make dev`) → open the local site.
3. Run the suite: `make test` (or `docker compose run --rm test`).
4. **Cross-browser:** run the Playwright E2E, especially the **WebKit** project — this is your direct check that the **Mac/Chrome rendering bug (#1)** is actually gone.
5. Manually exercise: arrow-key paging after clicking filters (#3), New-from-last-visit (#2), an alert → aggregate push → alerts deep-link view (#4), the popover, ALDI/LIDL/Both filter.

### 4.3 Production deploy — the automated installer (production-impacting → manual)  [you]
This is deliberately **not** auto-run by the agent. On the **Ubuntu VPS**:
1. Pull the new code into the **separate checkout folder** (per the installer design, architecture §6.5).
2. Create/populate **`install.local.conf`** with your real paths (`APP_ROOT` and `WEB_ROOT` — e.g. `/opt/lidaldi` and `/var/www/lidaldi` — plus service user and sync/log/prom dirs). These live only on the server, never in the repo.
3. **Dry run first:** `sudo ./deploy/update.sh --dry-run` → read the diff (config merge, user, cron, logrotate, systemd, web root).
4. Apply: `sudo ./deploy/update.sh`. Confirm it: merged new config keys **without clobbering** your live secrets, created/updated the system user, cron, logrotate, the **systemd sync service** (`daemon-reload` + restart), and web root perms.
5. **Smoke test live:** load the production site (your live URL), trigger (or wait for) a scrape, confirm offers render, and that a matching alert produces the **aggregate** push notification that deep-links back to the alerts view.

### 4.4 Land it & wrap up  [you/agent]
- Merge **`refactor` → `main`** (via PR, green CI), tag a version. (The orchestrator should already have updated **`README.md` and project docs** as part of the Definition of Done — verify they reflect the new stack, install/update flow, config format, and testing.)
- Ask the orchestrator to **consolidate Knowledge lessons** and finalize `PROGRESS.md`.
- Archive the Devin sessions (they sleep; 0 ACU).

### 4.5 Rollback plan (keep it ready)  [you]
- The installer backs up the live config and previous `WEB_ROOT`; keep those.
- If prod misbehaves: restore the previous web root + config, `git revert` the merge, redeploy. Because deploy is now idempotent, re-running the installer on the old commit is a clean rollback.

---

## Quick-reference troubleshooting

| Symptom | What's happening | What you do |
|---|---|---|
| Run paused, "out of usage" | Daily/weekly allowance hit | Wait for refresh (free) **or** buy overage; reopen session to resume |
| Started a fresh session after a pause | Context not carried | Paste the §3.5 recovery prompt (reads `PROGRESS.md`) |
| Fable 5 unavailable / `refusal` | Export-control wobble or safety classifier | Auto-falls back to Opus 4.8; nudge "continue" if stuck |
| Orchestrator ended with "I'll now do X" but didn't | Rare early-stop | Reply "continue / go ahead end to end" |
| A worker is looping or off-scope | Missing context / bad decomposition | Open the child session, correct it, or have the orchestrator re-spawn the task |
| It's about to touch prod without asking | Stop-rule not firing | Stop it; reinforce "hard-stop before production-impacting actions" |
| You disagree with a chosen tool/framework | Provisional decision | Raise it at the hard stop; the override clause expects this |

---

## Not yet produced (available as follow-ups)

1. **The full Loop-1 / Loop-2 master-goal Markdown** — a complete, paste-ready goal file with the loop / verifier / stop-rules and `PROGRESS.md` continuity fully wired in (the §1.2 block above is only a starter).
2. **The Product Designer worker brief** — the design-language spec that seeds the visual rewrite.
