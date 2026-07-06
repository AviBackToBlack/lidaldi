# LIDALDI Refactor — PROGRESS

**Durable state for the orchestrated refactor run. Recovery: read this file; resume from the first incomplete task.**

- Repo: github.com/AviBackToBlack/lidaldi · branch `refactor`
- Spec of record: `LOOP1_DELIVERABLES.md` (signed off, see Hard Stop #1) · brief: `REFACTOR_MASTER_GOAL.md`
- Orchestrator session: https://app.devin.ai/sessions/acdaf608a52947a0ba010e610b3f3153

## Phase status

| Phase | Status |
|---|---|
| Loop 1 — Requirements & Design | **COMPLETE** (2026-07-05) |
| Hard Stop #1 | **SIGNED OFF** (2026-07-05, operator "GO for Loop 2") |
| Loop 2 — Implementation (T0–T15) | **IN PROGRESS** |
| Hard Stop #2 — pre-deploy sign-off | not started |
| Deploy + post-deploy verification | not started |

## Hard Stop #1 sign-off (authoritative decisions)

- **D1–D5: ALL APPROVED.** D3 caveat: VPS currently runs Python 3.8; **operator will manually install Python 3.11 via `ppa:deadsnakes/ppa` and make it the system default**. Loop-2 code targets ≥3.11; installer must verify `python3 --version` ≥3.11 and abort with a clear message otherwise.
- **Q1–Q3: defaults accepted** (last-visit advances once per session; N/A-priced items kept + badged; `frontend/` top-level dir).
- **DAG T0–T15, team (W1–W4 + Verifier + SWE-1.6 docs), ACU estimate: APPROVED.**
- Spec of record for Loop 2 = `LOOP1_DELIVERABLES.md` as amended by the decisions above.

## Loop 1 — task ledger (all verified against tool output this session)

| Task | Status | Evidence/output |
|---|---|---|
| Read companion docs + Knowledge | done | all 3 docs + README read in full |
| Deep codebase analysis (every file, ~4.5k LOC) | done | LOOP1_DELIVERABLES.md §1 (file:line citations) |
| Confirm/correct arch §2 findings | done | §1 table — all confirmed; 1 correction (per-scrape index.html rewrite → D2) |
| Bug-discovery pass | done | §2 — known 4 confirmed + root-caused; 14 new findings N1–N14 triaged (1 High, 3 Medium) |
| Toolchain validation + currency | done | §3 — endorsements + deviations D1–D5; Multi-Devin primitives verified live |
| Target design (architecture, modules, UX) | done | §4; decision: no design-role agent — Claude Design + tokens.css seam |
| Task DAG + ACU estimate + risks | done | §5 — T0–T15, ≈50–80 ACUs, 6 risks, 3 open questions |
| Team design + role prompts | done | §6 — W1–W4 + Verifier V + SWE-1.6 docs task |

## Decisions awaiting operator (Hard Stop #1)

1. Deviations **D1–D5** (LOOP1_DELIVERABLES.md §3) — approve/reject each
2. Open questions **Q1–Q3** (§5) — defaults stated
3. Task DAG + team + ACU estimate — approve
4. T0: operator runs Claude Design from orchestrator-authored brief at Loop-2 kickoff

## Out-of-scope findings log

- N13 (image GC vs IMAGES_EXPIRES window) — Info; tighten opportunistically in T10
- N14 (sync-code-only auth, ~46 bits + rate limit) — Info; accepted risk, documented

## Loop 2 — task ledger

| Task | Worker | Session | Status | PR | Verifier |
|---|---|---|---|---|---|
| T0 design brief → operator runs Claude Design | orchestrator + operator | — | **done** — exports committed to `frontend/design/` (tokens.css, mockup.html, 404.html, img) | — | — |
| T1 test harness & CI skeleton | W4 QA/DevX | devin-3c17963f6b0c42009df40dbc007b5b3f | **merged + verified** | [#1](https://github.com/AviBackToBlack/lidaldi/pull/1), [#2](https://github.com/AviBackToBlack/lidaldi/pull/2) (CI fix) | **PASS** (devin-63366bad21f44f0d96103ab408899cae) |
| T2 stable ids + first_seen + offers.json | W1 Backend | devin-46236a21665148f09c73fedd3e2d2d56 | **merged + verified** | [#3](https://github.com/AviBackToBlack/lidaldi/pull/3), [#4](https://github.com/AviBackToBlack/lidaldi/pull/4) (corrupt-store quarantine follow-up) | **PASS** (devin-c769b51ac7984751bc983bc60f579059); low finding fixed in #4 |
| T3 aggregate push + ledger | W1 Backend | devin-524c3844e7f24dc096563200a47eb501 | **merged + verified** (operator merged ahead of verdict) | [#6](https://github.com/AviBackToBlack/lidaldi/pull/6) | **PASS** (devin-8d027ed90ac849cb96470858770d50a4) |
| T4 sync lastVisit semantics | W1 Backend | devin-524c3844e7f24dc096563200a47eb501 | **merged + verified** (initial FAIL on doc contract, fixed in cbcac9e…126c823, re-verified) | [#10](https://github.com/AviBackToBlack/lidaldi/pull/10) | **PASS on re-verify** (devin-d5a341c3441147afa4f2dee976b2fb60) |
| T5 frontend scaffold | W2 Frontend | devin-2aef11583e8c4af59aaa124b8c538853 | **merged + verified** | [#5](https://github.com/AviBackToBlack/lidaldi/pull/5) | **PASS** (devin-163562d42b0a48fdb7200ca6c2819743) |
| T7 PWA manifest/icons/sw.js | W2 Frontend | devin-7bbc3b7f20034045b4c1ae78e944dae7 | **merged + verified** | [#9](https://github.com/AviBackToBlack/lidaldi/pull/9) | **PASS** (devin-7e31995bf07a45d69b058cabf42702f0) |
| T9 TOML/.env config migration | W3 DevOps | devin-a64006dcea1e424382abeef855582343 | **merged + verified** | [#7](https://github.com/AviBackToBlack/lidaldi/pull/7) | **PASS** (devin-beedc124b5f745de908083119d2f7dbe); low: secret-in-TOML guard narrow (Telegram keys only, one level deep; vapid_private_key_path not covered) — T10 follow-up |
| T10 installer/updater | W3 DevOps | devin-4e04a904db114eac9d1555e0cd749999 | dispatched | — | — |
| T11 .prom metrics parity | W1 Backend | devin-0a059fbea9b74929bca3a4b4b9f6ec22 | dispatched | — | — |
| T13 k6 load + security tiers | W4 QA/DevX | devin-1306aaa475a7474aa4ec6d4d258e6e0f | dispatched | — | — |
| T6 full frontend UI | W2 Frontend | devin-331be1bc188348fea9367b2906fc7e0e | dispatched (T0 exports landed) | — | — |
| T8 (after T6), T14 (after T10), T15 (after T10) | per DAG | — | pending | — | — |

T7 verifier follow-ups (for T6/T10): push payload icon `/img/lidaldi.png` is not shipped by the frontend build — add it to `frontend/public/img/` (T6); static cache `lidaldi-static-v1` needs a cache-name bump discipline when icons/manifest change on deploy (T10/T14 note).

Frozen contracts so far: sync contract doc `docs/sync-contract.md` (T4 PR #10) · alertMatches schema {alertId: [{id, at}]} 30d TTL/cap 100 (T3) · offers.json schema (T2 PR #3) · push payload + alertMatches (T3 PR #6) · config key map legacy→TOML/.env (T9 PR #7) · push.ts API for T6 UI wiring (T7 PR #9).

T3 verifier notes: N6 (sw.js try/catch) deferred to T7 as planned; per-endpoint ledger shares MAX_NOTIFIED=2000 cap across endpoints (low — heavy multi-device profiles could evict live entries); endpoint hash = sha256[:16] (fine).

T2 verifier notes (info): store shape id → {first_seen, last_seen} (GC needs last_seen; loader accepts legacy flat); sanity-ratio suppression still marks offers seen (pre-existing semantics); write_atomic has no fsync (benign — reseed path guarded).
