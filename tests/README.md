# LIDALDI test harness (T1)

One containerized workflow, identical locally and in CI. All suites are
deterministic: no live calls to aldi.ie / lidl.ie or push services.

## Running everything

```sh
docker compose run --rm test make test     # containerized (same as CI)
# or, on a host with python3 >= 3.11 + Node LTS + Playwright browsers:
make test
```

`make test` = `test-unit` + `test-e2e` + `test-load` + `test-security`.

## Targets

| Target | What it runs |
|---|---|
| `make test-unit` | pytest (`tests/unit/`); Vitest in `frontend/` once it exists (T5) — skipped gracefully until then |
| `make test-e2e` | Playwright (`tests/e2e/`) on **chromium, firefox and webkit**, with visual snapshots (`tests/e2e/__snapshots__/`) |
| `make test-load` | k6 script (`tests/load/sync_api.js`) vs the sync API; skipped unless k6 is installed and the server is up (`SYNC_API_URL`, default `http://localhost:8080`) |
| `make test-security` | `pip-audit` (requirements.txt), `bandit` (`offers_processing/`, `scraper/`), `npm audit` in `frontend/` once it exists |
| `make test-zap` | **Opt-in only** (D4), not part of `make test`: OWASP ZAP baseline via the `zap` compose profile against `ZAP_TARGET` |

## Environment

- `.devcontainer/devcontainer.json` + `docker-compose.yml` use the pinned
  official Playwright image `mcr.microsoft.com/playwright:v1.61.1-noble`
  (Node LTS + all three browser engines; Ubuntu 24.04 → python3.12 ≥ 3.11 floor, D3).
- First run: `make setup` creates `.venv/` (tests/requirements.txt) and installs
  `tests/e2e/` npm deps. `make test` does this automatically.
- Visual snapshots are per-engine. To (re)generate after intentional UI changes:
  `cd tests/e2e && npx playwright test --update-snapshots` (inside the container,
  so snapshots match CI rendering).

## CI

`.github/workflows/ci.yml` runs `make test` inside the same Playwright image,
so local container results == CI results.
