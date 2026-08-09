# Testing Guide

The authoritative testing documentation lives in
[../tests/README.md](../tests/README.md) (kept next to the harness so it
moves with it). Summary:

```bash
docker compose run --rm test make test    # containerized, identical to CI
# or, on a host with pyenv Python 3.12.13 + Node LTS + Playwright browsers:
make test
```

`make test` = `test-unit` (pytest + Vitest) + `test-installer` (sandboxed
`deploy/update.sh` tests) + `test-e2e` (Playwright: chromium, firefox,
webkit, visual snapshots) + `test-load` (pinned k6 vs a real sync server;
fails, never skips) + `test-security` (pip-audit, bandit, npm audit).

`make test-zap` (OWASP ZAP baseline) is **opt-in only** and not part of
`make test` or default CI (decision D4). Snyk, CodeQL and Dependabot run
outside `make test` entirely — all of it is described in
[operations.md](operations.md#security-scans).

All suites are deterministic: no live calls to aldi.ie / lidl.ie or push
services. The one exception is the webfont — the e2e specs load the real
`fonts.googleapis.com` stylesheet, so specs that measure element geometry
must await `document.fonts.ready` first (see
[../tests/README.md](../tests/README.md#known-flakes-scoped-retries-not-app-bugs)).

CI (`.github/workflows/ci.yml`) runs `make test` inside the same pinned
Playwright image as the local container, so results match.
