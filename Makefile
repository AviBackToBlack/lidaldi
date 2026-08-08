# LIDALDI test harness entry points (T1).
# Run inside the containerized environment (docker compose run --rm test make test)
# or any host with pyenv Python 3.12.13, Node LTS and Playwright browsers.
#
# `make test` = unit + e2e + load + security. `make test-zap` is opt-in only (D4).

PYENV_ROOT ?= /opt/pyenv
PYENV_PYTHON_VERSION ?= 3.12.13
PYENV_VIRTUALENV_NAME ?= lidaldi
PYENV_BIN ?= $(PYENV_ROOT)/bin/pyenv
PYTHON := PYENV_ROOT=$(PYENV_ROOT) PYENV_VERSION=$(PYENV_VIRTUALENV_NAME) $(PYENV_BIN) exec python
PIP := PYENV_ROOT=$(PYENV_ROOT) PYENV_VERSION=$(PYENV_VIRTUALENV_NAME) $(PYENV_BIN) exec pip
PYENV_STAMP := $(PYENV_ROOT)/versions/$(PYENV_VIRTUALENV_NAME)/.tests-requirements.ok

.PHONY: setup test test-unit test-installer test-e2e test-load test-security test-zap

setup: $(PYENV_STAMP) tests/e2e/node_modules/.ok

$(PYENV_STAMP): tests/requirements.txt
	$(PYENV_BIN) versions --bare | grep -Fx $(PYENV_PYTHON_VERSION)
	$(PYENV_BIN) versions --bare | grep -Fx $(PYENV_VIRTUALENV_NAME)
	$(PYTHON) -c 'import sys; assert sys.version_info[:3] == tuple(map(int, "$(PYENV_PYTHON_VERSION)".split("."))), "pyenv virtualenv must use Python $(PYENV_PYTHON_VERSION): got %s" % sys.version'
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r tests/requirements.txt
	touch $@

tests/e2e/node_modules/.ok: tests/e2e/package.json tests/e2e/package-lock.json
	cd tests/e2e && npm ci
	touch $@

test: test-unit test-installer test-e2e test-load test-security

test-unit: $(PYENV_STAMP)
	$(PYTHON) -m pytest tests/unit
	# Frontend unit tests (Vitest) are gated on frontend/ existing (created by T5).
	@if [ -d frontend ]; then \
		cd frontend && npm ci && npx vitest run; \
	else \
		echo "test-unit: frontend/ not present yet — skipping Vitest"; \
	fi

test-installer: $(PYENV_STAMP)
	# Installer/updater tests (T10) — fully sandboxed, safe in any container.
	$(PYTHON) -m pytest tests/installer

test-e2e: tests/e2e/node_modules/.ok
	cd tests/e2e && npx playwright test

test-load:
	# k6 load tier (T13) vs a real sync_server booted with a temp SYNC_DIR.
	# FAILS (never skips) when k6 or the server is unavailable; k6 is pinned
	# and installed by tests/load/install-k6.sh (baked into the test image).
	bash tests/load/run.sh

test-security: $(PYENV_STAMP)
	$(PYTHON) -m pip_audit -r requirements.txt
	# Gate at medium+ severity: the two pre-existing Low findings (B110 in
	# common.py, B105 placeholder token in config.sample.py) are accepted;
	# T1 must not modify existing code.
	$(PYTHON) -m bandit -q -r --severity-level medium offers_processing scraper deploy
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
	# Teardown is scoped to the zap-profile services so a running `test`
	# container (and the compose network) is left untouched.
	docker compose --profile zap run --rm zap; \
	status=$$?; docker compose --profile zap rm -sf zap-target; exit $$status
