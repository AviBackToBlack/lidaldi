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
| T10 installer/updater | W3 DevOps | devin-4e04a904db114eac9d1555e0cd749999 | **merged + verified** (operator merged ahead of verdict); verifier follow-up fixed in [#17](https://github.com/AviBackToBlack/lidaldi/pull/17) (synctree never overwrites live config/keys/data; run_scrapers.sh +x) | [#12](https://github.com/AviBackToBlack/lidaldi/pull/12), [#17](https://github.com/AviBackToBlack/lidaldi/pull/17) | **PASS** (devin-4e64c877a50745ad933f85a6c512dbd7); low: no automated restore (idempotent re-run is recovery) — T15 rehearsal notes |
| T11 .prom metrics parity | W1 Backend | devin-0a059fbea9b74929bca3a4b4b9f6ec22 | **merged + verified** (metric inventory frozen in PR desc → T14) | [#11](https://github.com/AviBackToBlack/lidaldi/pull/11) | **PASS** (devin-274e49ac82364a2fa4652b3f418c1c8a); info: host .venv mount breaks containerized run (harness quirk) |
| T13 k6 load + security tiers | W4 QA/DevX | devin-1306aaa475a7474aa4ec6d4d258e6e0f | **merged + verified** — initial FAIL (rate-limit coverage falsely claimed) fixed in follow-up [#15](https://github.com/AviBackToBlack/lidaldi/pull/15) (real 429 test, med<50ms threshold, scoped zap teardown), re-verify PASS | [#13](https://github.com/AviBackToBlack/lidaldi/pull/13), [#15](https://github.com/AviBackToBlack/lidaldi/pull/15) | **PASS on re-verify** (devin-42b7edcb4e5e4a198fe82776ee486598) |
| T6 full frontend UI | W2 Frontend | devin-331be1bc188348fea9367b2906fc7e0e | PR open, CI green (deviations stated: popover placement, grid minmax 224/158px vs 250px) | [#14](https://github.com/AviBackToBlack/lidaldi/pull/14) | verifying (devin-614bc48c27234140871c1630cd4da681) |
| T14 docs refresh | SWE-1.6 docs | devin-f495eee3efd5495791d803724ebc2e4f | **merged + verified** (T6 UI section placeholder — fill after T6/T8) | [#16](https://github.com/AviBackToBlack/lidaldi/pull/16) | **PASS** (devin-ab03da8daf8d440bb11d99a27ae72311); low: tests/README.md summary line omits test-installer tier; host .venv breaks containerized run (harness quirk) |
| T15 migration rehearsal | W3 DevOps | devin-358afab2acd945e79e10f2b82f8e3ccf | **merged + verified** | [#18](https://github.com/AviBackToBlack/lidaldi/pull/18) | **PASS** (devin-3f14c66ecc4c44dbb3037041ad6a76ee); med for HS#2: F2 must be fixed before cutover (first cron run clobbers SPA index.html); rollback is data-level only (configs+SYNC_DIR, not code/webroot) |
| D2-fix: stop index.html render in process_offers (T15 finding F2) | W1 Backend | devin-24afd19762764bee9e283d0f133506ff | PR open — rebasing on merged #18 to flip strict xfail | [#19](https://github.com/AviBackToBlack/lidaldi/pull/19) | — |
| T8 a11y (after T6) | per DAG | — | pending | — | — |

T15 findings: F1 no automated legacy config.py→TOML value migration (mandatory manual operator edit, runbook Step 4); F2 process_offers still renders index.html clobbering the Vite build (strict xfail; D2-fix task dispatched); T6 PR #14 ships /img/lidaldi.png (xfail resolves once merged).

T6 worker follow-ups: pre-existing flaky [chromium-push] pwa-push.spec.ts (5s poll timeout; also failed on refactor base) — consider longer poll in T7 spec; push unsubscribe is local-only (no removal op in frozen sync contract; sender should prune on 404/410) — candidate contract follow-up.

T7 verifier follow-ups (for T6/T10): push payload icon `/img/lidaldi.png` is not shipped by the frontend build — add it to `frontend/public/img/` (T6); static cache `lidaldi-static-v1` needs a cache-name bump discipline when icons/manifest change on deploy (T10/T14 note).

Frozen contracts so far: sync contract doc `docs/sync-contract.md` (T4 PR #10) · alertMatches schema {alertId: [{id, at}]} 30d TTL/cap 100 (T3) · offers.json schema (T2 PR #3) · push payload + alertMatches (T3 PR #6) · config key map legacy→TOML/.env (T9 PR #7) · push.ts API for T6 UI wiring (T7 PR #9).

T3 verifier notes: N6 (sw.js try/catch) deferred to T7 as planned; per-endpoint ledger shares MAX_NOTIFIED=2000 cap across endpoints (low — heavy multi-device profiles could evict live entries); endpoint hash = sha256[:16] (fine).

T2 verifier notes (info): store shape id → {first_seen, last_seen} (GC needs last_seen; loader accepts legacy flat); sanity-ratio suppression still marks offers seen (pre-existing semantics); write_atomic has no fsync (benign — reseed path guarded).
