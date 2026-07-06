# LIDALDI test harness (T1)

One containerized workflow, identical locally and in CI. All suites are
deterministic: no live calls to aldi.ie / lidl.ie or push services.

## Running everything

```sh
docker compose run --rm test make test     # containerized (same as CI)
# or, on a host with pyenv Python 3.12.13 + Node LTS + Playwright browsers:
make test
```

`make test` = `test-unit` + `test-installer` + `test-e2e` + `test-load` + `test-security`.

## Targets

| Target | What it runs |
|---|---|
| `make test-unit` | pytest (`tests/unit/`); Vitest in `frontend/` once it exists (T5) — skipped gracefully until then |
| `make test-e2e` | Playwright (`tests/e2e/`) on **chromium, firefox and webkit**, with visual snapshots (`tests/e2e/__snapshots__/`) |
| `make test-load` | k6 (`tests/load/sync_api.js`) vs a real `sync_server` booted with a temp SYNC_DIR by `tests/load/run.sh`; **fails (never skips)** if k6 or the server is unavailable. k6 is pinned + checksum-verified (`tests/load/install-k6.sh`, baked into the test image and installed by CI) |
| `make test-security` | `pip-audit` (requirements.txt), `bandit` (`offers_processing/`, `scraper/`), `npm audit` in `frontend/` once it exists |
| `make test-zap` | **Opt-in only** (D4), not part of `make test` or CI: boots `zap-target` (built frontend + sync API on one origin, port 8100) in the `zap` compose profile and runs a ZAP baseline scan against it; set `ZAP_TARGET` to scan a running instance instead. Run from a host with docker compose |

## Environment

- `.devcontainer/devcontainer.json` + `docker-compose.yml` use the pinned
  official Playwright image `mcr.microsoft.com/playwright:v1.61.1-noble`
  plus pyenv Python `3.12.13` and a `lidaldi` pyenv virtualenv.
- First run: `make setup` installs `tests/requirements.txt` into the pyenv
  `lidaldi` environment and installs `tests/e2e/` npm deps. `make test` does
  this automatically.
- Visual snapshots are per-engine. To (re)generate after intentional UI changes:
  `cd tests/e2e && npx playwright test --update-snapshots` (inside the container,
  so snapshots match CI rendering).

## Load tier notes (T13)

- `tests/load/run.sh` boots `offers_processing/sync_server.py` with a
  throwaway config.toml/SYNC_DIR, waits for readiness, then runs k6.
- Rate limiting: the server allows 30 req/min per client IP (a module
  constant — no TOML knob) and trusts `X-Forwarded-For` from loopback. The
  scenario simulates a distinct client IP per iteration (~6 requests each),
  so no simulated client ever approaches the limit and the load test cannot
  429 spuriously, while the limiter stays on every request's hot path. 429
  behaviour itself is unit-tested by
  `test_rate_limit_429_once_per_ip_limit_exceeded` in
  `tests/unit/test_sync_server.py` (the shared server fixture raises
  `RATE_MAX` for the other tests; that test scopes it back down and
  asserts 429 fires exactly once the per-IP limit is exceeded).
- Thresholds (`p(95)<500ms` plus a tighter `med<50ms`, `http_req_failed<1%`,
  `checks>99%`) are sized for the single-process 127.0.0.1 server with
  large headroom over observed latencies (~1–5 ms), so they are
  deterministic in CI — see the comment block in `tests/load/sync_api.js`.

## CI

`.github/workflows/ci.yml` runs `make test` inside the same Playwright image,
so local container results == CI results.
