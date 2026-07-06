# LIDALDI test harness entry points (T1).
# Run inside the containerized environment (docker compose run --rm test make test)
# or any host with python3 >= 3.11, Node LTS and Playwright browsers.
#
# `make test` = unit + e2e + load + security. `make test-zap` is opt-in only (D4).

PYTHON ?= python3
VENV := .venv
VENV_BIN := $(VENV)/bin

.PHONY: setup test test-unit test-e2e test-load test-security test-zap

setup: $(VENV)/.ok tests/e2e/node_modules/.ok

$(VENV)/.ok: tests/requirements.txt
	$(PYTHON) -c 'import sys; assert sys.version_info >= (3, 11), "python3 >= 3.11 required (D3): got %s" % sys.version'
	$(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/pip install --quiet --upgrade pip
	$(VENV_BIN)/pip install --quiet -r tests/requirements.txt
	touch $@

tests/e2e/node_modules/.ok: tests/e2e/package.json tests/e2e/package-lock.json
	cd tests/e2e && npm ci
	touch $@

test: test-unit test-e2e test-load test-security

test-unit: $(VENV)/.ok
	$(VENV_BIN)/pytest tests/unit
	# Frontend unit tests (Vitest) are gated on frontend/ existing (created by T5).
	@if [ -d frontend ]; then \
		cd frontend && npm ci && npx vitest run; \
	else \
		echo "test-unit: frontend/ not present yet — skipping Vitest"; \
	fi

test-e2e: tests/e2e/node_modules/.ok
	cd tests/e2e && npx playwright test

test-load:
	# k6 load tier (T13) vs a real sync_server booted with a temp SYNC_DIR.
	# FAILS (never skips) when k6 or the server is unavailable; k6 is pinned
	# and installed by tests/load/install-k6.sh (baked into the test image).
	bash tests/load/run.sh

test-security: $(VENV)/.ok
	$(VENV_BIN)/pip-audit -r requirements.txt
	# Gate at medium+ severity: the two pre-existing Low findings (B110 in
	# common.py, B105 placeholder token in config.sample.py) are accepted;
	# T1 must not modify existing code.
	$(VENV_BIN)/bandit -q -r --severity-level medium offers_processing scraper
	# npm audit is gated on frontend/ existing (created by T5).
	@if [ -d frontend ]; then \
		cd frontend && npm audit --audit-level=high; \
	else \
		echo "test-security: frontend/ not present yet — skipping npm audit"; \
	fi

test-zap:
	# Opt-in ZAP baseline scan (D4). NOT part of `make test` or default CI.
	# Builds the frontend + boots the sync API in compose (zap-target on
	# :8100), then runs zap-baseline against that origin. Run from a host
	# with docker compose (not inside the test container). Override the
	# target with ZAP_TARGET to scan a running instance instead.
	docker compose --profile zap run --rm zap; \
	status=$$?; docker compose --profile zap down; exit $$status
