# Operations Guide

Operator procedures for installing, updating and running LidAldi in
production. Companion docs: [observability.md](observability.md)
(metrics), [testing.md](testing.md) (test suites),
[sync-contract.md](sync-contract.md) (sync API).

## Installer / updater (`deploy/update.sh`)

One script handles both fresh installs and updates. It is **idempotent and
plan-then-apply**: every step (service user, directories, code sync,
frontend build, `frontend/dist` → web root, web root permissions, rendered
cron/logrotate/systemd/nginx files, pyenv virtualenv + deps, config merge)
checks the current state and only
registers an action on drift. A second run on an already-installed system is a strict
no-op (`NOOP`, no backup, no mutation).

```bash
cp deploy/install.local.conf.sample deploy/install.local.conf
$EDITOR deploy/install.local.conf     # APP_ROOT, WEB_ROOT, SERVICE_USER, SYNC_DIR, LOG_DIR, ...

sudo ./deploy/update.sh --dry-run     # ALWAYS dry-run first
sudo ./deploy/update.sh               # apply
```

- `--dry-run` prints the per-file diffs and full action list and mutates
  nothing.
- `--no-restart` skips the systemd `daemon-reload`/`restart` of
  `lidaldi-sync` (which otherwise happens only when the rendered unit
  changed, running as root, with systemd present).
- `--config /path/to/install.local.conf` uses an alternate local config.
- `--plain` forces plain output on a terminal (see *Output* below).
- Preflight: aborts unless pyenv and pyenv-virtualenv are available, pyenv
  has the pinned Python `3.12.x` base installed (`3.12.13` by default), and
  that interpreter is ≥ 3.12 (decision D3). Override with `PYENV_ROOT`,
  `PYENV_PYTHON_VERSION`, or `PYENV_VIRTUALENV_NAME` in `install.local.conf`
  only when needed.
- The real `install.local.conf` is git-ignored — paths differ per
  environment and never belong in the repo.
- The pyenv virtualenv (`lidaldi` by default) is created/reused and re-pipped
  only when the `requirements.txt` hash changes. `requirements.txt` pins
  exact (`==`) versions and the test suite installs that same file, so a
  deploy only ever installs direct dependencies CI has tested (transitive
  dependencies are not locked).
- **Frontend build.** `frontend/dist` is a git-ignored build artifact, so a
  `git pull` never updates it. The installer fingerprints the frontend
  sources and, when they differ from what the current `dist/` was built
  from, runs `npm ci && npm run build` itself before the web-root sync (the
  fingerprint is stamped into `dist/.build-fingerprint` only after a
  successful build, so a failed build is retried and the live site is left
  as it was). If a build is needed and `npm` is missing (`NPM_BIN`), the
  installer aborts before changing anything rather than deploy a stale
  frontend.
- The web-root sync deploys `frontend/dist` but **never rewrites the
  content of `offers.json` / `meta.json`** — those are data written by
  `process_offers.py` (D2: app deploy ≠ data write).
- **Web root permissions** are enforced on every run (drift is shown as
  `DIFF` and fixed; nothing to fix = no action):
  - everything `root:$WEB_GROUP` (default `www-data`), directories `0750`,
    files `0640` — nginx reads, only root changes;
  - `SERVICE_USER` owns what the cron job writes: the web root directory
    itself (offers.json/meta.json are written via `.tmp` + rename there),
    `offers.json`/`meta.json`, and the whole `IMAGES_DIR` tree (default
    `$WEB_ROOT/img/full`; the scraper adds images and overwrites expired
    ones);
  - `SERVICE_USER` must be in `WEB_GROUP` to reach `IMAGES_DIR` through the
    `root:$WEB_GROUP 0750` parents — added automatically with
    `MANAGE_USER=1`, a `WARN` otherwise;
  - symlinks are never followed or changed (the cron user can create them
    in the directories it owns).

  This replaces the old hand-run `fix_perms_lidaldi.sh`. Right after a
  scrape, expect a permissions fix in the plan: new files the cron job
  created (umask `0002`, group `$SERVICE_USER`) are normalised to the policy.
- `IMAGES_DIR` is also what the daily 90-day image cleanup in
  `run_scrapers.sh` prunes. (It used to be rendered to a non-existent
  `$APP_ROOT/data/images`, so no image was ever deleted; the first cron run
  after that fix deletes every image older than 90 days.)
- **Output.** On an interactive UTF-8 terminal the installer shows colours,
  sections, a progress gauge and spinners (build/pip output goes to a log
  shown only on failure). Anywhere else — pipes, logs, cron, CI, `NO_COLOR`
  set, or `--plain` — it prints the plain `TOKEN  message` lines.

Expected production pyenv layout:

```bash
sudo git clone https://github.com/pyenv/pyenv.git /opt/pyenv
sudo git -C /opt/pyenv checkout 933d0aaf1d1190a641c3ddce484e72b1a993473d
sudo mkdir -p /opt/pyenv/plugins
sudo git clone https://github.com/pyenv/pyenv-virtualenv.git /opt/pyenv/plugins/pyenv-virtualenv
sudo git -C /opt/pyenv/plugins/pyenv-virtualenv checkout eda64556af9b2992386deeb75dad2130899fc4c9
echo 'export PYENV_ROOT="/opt/pyenv"' | sudo tee /etc/profile.d/pyenv.sh
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' | sudo tee -a /etc/profile.d/pyenv.sh
echo 'eval "$(pyenv init --path)"' | sudo tee -a /etc/profile.d/pyenv.sh
echo 'eval "$(pyenv virtualenv-init -)"' | sudo tee -a /etc/profile.d/pyenv.sh
sudo env PYENV_ROOT=/opt/pyenv /opt/pyenv/bin/pyenv install 3.12.13
```

Use `PYENV_VERSION=3.12.13 python ...` for bare interpreter checks. Use
`PYENV_VERSION=lidaldi python ...` (or `/opt/pyenv/versions/lidaldi/bin/python`)
for application commands that need packages from `requirements.txt`.

### Config merge (`deploy/merge_config.py`)

Run by the installer; the sample files are the schema:

- **ADD** — keys present in `config.toml.sample`/`.env.sample` but missing in
  the live file are appended (into the right `[section]`); live values are
  **never overwritten**.
- **REVIEW** — live keys absent from the sample (removed/renamed upstream)
  are reported, never deleted.
- **WARN** — secret-looking keys in the TOML (`token|secret|password|api_key|private_key`)
  are flagged: secrets belong in `.env`.
- Exit codes: `0` in-sync, `3` changes made/needed, `2` error.

## Backups

Before its **first mutating action** (and only then — no-op runs take no
backup), `update.sh` writes a timestamped backup to
`$BACKUP_DIR/lidaldi-backup-<stamp>/` containing:

- live configs: `config.toml`, `.env`, and legacy `config.py` /
  `settings.py` if present;
- the entire `SYNC_DIR` (sync profiles: alerts, lastVisit, push
  subscriptions, tombstones, alertMatches).

`BACKUP_DIR` is set in `install.local.conf`. Keep independent periodic
backups of `SYNC_DIR` and the VAPID private key as well — the sync profiles
and the keypair are the only state that cannot be regenerated from the repo.

## VAPID keys

The VAPID keypair authenticates the server to browser push services. It is
**a long-lived credential: if the private key is lost or regenerated, every
existing push subscription silently dies** and all users must re-enable
notifications.

- Generate **once**, at first install only:

  ```bash
  PYENV_VERSION=lidaldi python offers_processing/generate_vapid_keys.py /path/to/processing/folder
  ```

  This writes `vapid_private.pem` and prints the public key. Put the public
  key in `config.toml` (`[push] vapid_public_key`) and the private key path
  in `.env` (`VAPID_PRIVATE_KEY_PATH`, defaults to
  `<offers_processing_dir>/vapid_private.pem`).

- Lock the private key down — anyone who reads it can forge push messages to
  every subscriber:

  ```bash
  sudo chown lidaldi:lidaldi vapid_private.pem
  sudo chmod 600 vapid_private.pem
  ```

- `deploy/update.sh` **never generates, moves or rewrites** the keypair; it
  only checks and reports its existence. Include `vapid_private.pem` in your
  off-machine backups.

## Deploy discipline: service-worker cache-name bump

The service worker (`frontend/src/sw.ts`) caches the app shell in a
versioned static cache (`STATIC_CACHE = "lidaldi-static-v1"`) with a
cache-first strategy, and prunes caches not in `KNOWN_CACHES` on activate.
Consequence for deploys:

> **Whenever statically-cached assets change** (icons, `manifest.json`,
> anything served cache-first) **bump the `STATIC_CACHE` version** (e.g.
> `lidaldi-static-v1` → `-v2`) in `frontend/src/sw.ts` as part of the same
> change, then rebuild. The new SW installs, activates
> (`skipWaiting`/`clients.claim`) and deletes the old cache; without the
> bump, returning clients keep serving stale assets from the old cache.

Hashed Vite build assets are immune (new URLs), so this mainly concerns the
fixed-URL files in `frontend/public/`. Data files (`offers.json`,
`meta.json`) use a network-first data cache and never need a bump.

## Services, cron, logs

Managed by the installer (rendered from the repo templates with your
`install.local.conf` paths):

- **systemd**: `lidaldi-sync.service` — the sync server on
  `127.0.0.1:8099`. The unit ships hardened (`NoNewPrivileges`,
  `ProtectSystem=strict`, `MemoryDenyWriteExecute`, restrictive
  `SystemCallFilter`); its `ReadWritePaths=` must cover `SYNC_DIR` and (if
  enabled) the Prometheus textfile directory — the installer renders this
  from your paths.
- **nginx**: `nginx/lidaldi-sync-proxy.conf` — reverse proxy for
  `/api/sync/` (10 KB body cap, `X-Real-IP`/`X-Forwarded-For` headers; the
  server rate-limits 30 req/min per client IP).
- **cron**: `cron.d/lidaldi` — daily chain `run_scrapers.sh` → spiders →
  `process_offers.py` → `send_notifications.py`.
- **logrotate**: `logrotate.d/lidaldi` for `LOG_DIR`.
- **Prometheus** (optional): set `[paths] prom_textfile_dir` in
  `config.toml` and `PROM_DIR` in `install.local.conf`; see
  [observability.md](observability.md).

## Security scans

Four automated layers run against `main` (plus the opt-in ZAP scan below):

| Layer | Where | Gating? |
|---|---|---|
| `pip-audit`, `bandit` (medium+), `npm audit` (high+) | `make test-security`, so every CI run | **Yes** — any finding fails the build |
| Snyk Code (SAST) + Snyk Open Source (SCA) | `.github/workflows/snyk-security.yml`, on push/PR to `main` | No — findings are uploaded to the GitHub **Security → Code scanning** tab for review |
| CodeQL | `.github/workflows/codeql.yml`, on push/PR to `main` and weekly | No — reports to the same Code scanning tab |
| Dependabot | `.github/dependabot.yml` — pip, npm (`frontend/`, `tests/e2e/`), github-actions, docker-compose, devcontainers | No — opens PRs |

Two Snyk gotchas worth knowing before you debug that workflow:

- **The trailing `403 Forbidden` is expected and cosmetic.** The CLI calls
  `GET /rest/orgs/{id}` to resolve the org, and the Snyk REST API is
  Enterprise-only — Free/Team tokens authenticate fine for CLI/CI but get a
  403 there. No scope grant or token regeneration fixes it. Consequence:
  `snyk monitor` works (legacy v1 API), and `snyk code test` still analyses
  locally and uploads SARIF to GitHub, but its results don't appear in the
  Snyk web UI.
- **False positives are suppressed inline**, with `snyk:ignore` annotations
  at the finding site (test fixtures, sample config, the legacy `website/`
  JS, design mockups) rather than in a central `.snyk` policy file — so
  grep for `snyk:ignore` if a finding disappears mysteriously.

The OWASP ZAP baseline scan is **opt-in only** (decision D4), from a host
with docker compose:

```bash
make test-zap
```

This boots a `zap-target` compose service (built frontend + real sync
server on one origin, port 8100, mirroring the production nginx layout) and
runs `zap-baseline.py` against it. Set `ZAP_TARGET` to scan a running
instance instead. Teardown is scoped to the zap-profile services, so a
running `test` container is untouched.
