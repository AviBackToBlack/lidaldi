#!/bin/bash
#
# LIDALDI idempotent installer/updater (T10, arch doc §6.5).
#
# Create-or-update: service user, cron, logrotate, systemd unit, nginx
# snippet, web root, venv/deps, sample->real config merge. Every step
# checks current state and only registers an action on drift; a second run
# on an already-installed system is a no-op (no backup, no mutation).
#
# Usage: update.sh [--dry-run] [--no-restart] [--config /path/to/install.local.conf]
#
# Paths come from a git-ignored install.local.conf (see
# install.local.conf.sample next to this script). The VAPID keypair is
# reused verbatim — never generated, moved or rewritten here.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR_DEFAULT="$(cd "$SCRIPT_DIR/.." && pwd)"

DRY_RUN=0
NO_RESTART=0
CONF_FILE="$SCRIPT_DIR/install.local.conf"

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --no-restart) NO_RESTART=1 ;;
        --config) shift; CONF_FILE="${1:?--config needs a path}" ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "ERROR unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR %s\n' "$*" >&2; exit 1; }

# --- Preflight: Python >= 3.11 (decision D3) ---------------------------------
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    die "python3 not found. lidaldi requires Python >= 3.11 (D3)."
fi
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    die "Python >= 3.11 required (D3); found $("$PYTHON" --version 2>&1). \
On Ubuntu install python3.11 via the deadsnakes PPA (add-apt-repository \
ppa:deadsnakes/ppa) and re-run with PYTHON=python3.11."
fi

# --- Local config --------------------------------------------------------
[ -f "$CONF_FILE" ] || die "missing $CONF_FILE — copy \
$SCRIPT_DIR/install.local.conf.sample to install.local.conf and edit it."
# shellcheck disable=SC1090
. "$CONF_FILE"

: "${APP_ROOT:?install.local.conf must set APP_ROOT}"
: "${WEB_ROOT:?install.local.conf must set WEB_ROOT}"
: "${SERVICE_USER:?install.local.conf must set SERVICE_USER}"
: "${SYNC_DIR:?install.local.conf must set SYNC_DIR}"
: "${LOG_DIR:?install.local.conf must set LOG_DIR}"
PROM_DIR="${PROM_DIR:-}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/lidaldi}"
REPO_DIR="${REPO_DIR:-$REPO_DIR_DEFAULT}"
CRON_DIR="${CRON_DIR:-/etc/cron.d}"
LOGROTATE_DIR="${LOGROTATE_DIR:-/etc/logrotate.d}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"
NGINX_SNIPPET_DIR="${NGINX_SNIPPET_DIR:-/etc/nginx/snippets}"
MANAGE_USER="${MANAGE_USER:-1}"

VENV_DIR="$APP_ROOT/.venv"
LIVE_TOML="$APP_ROOT/config.toml"
LIVE_ENV="$APP_ROOT/.env"

[ -d "$REPO_DIR/deploy" ] || die "REPO_DIR=$REPO_DIR does not look like a lidaldi checkout"

IS_ROOT=0
if [ "$(id -u)" = "0" ]; then IS_ROOT=1; fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

maybe_chown() { # maybe_chown <path>
    if [ "$IS_ROOT" = "1" ]; then
        chown -R "$SERVICE_USER:$SERVICE_USER" "$1"
    fi
}

# --- Plan machinery --------------------------------------------------------
# Steps only *register* actions when drift is detected. Actions are typed
# records dispatched by apply_action after the backup. Second run = empty
# plan = no-op.
PLAN_DESCS=()
PLAN_ACTIONS=()   # "type<US>arg1<US>arg2..." (US = 0x1f, never in paths)
US=$'\x1f'
SERVICE_CHANGED=0

plan() { # plan <description> <type> [args...]
    local desc="$1" type="$2"
    shift 2
    local rec="$type"
    local a
    for a in "$@"; do rec="$rec$US$a"; done
    PLAN_DESCS+=("$desc")
    PLAN_ACTIONS+=("$rec")
    log "PLAN  $desc"
}

ok() { log "OK    $*"; }

apply_action() {
    local rec="$1"
    local -a f
    IFS="$US" read -r -a f <<< "$rec"
    case "${f[0]}" in
        useradd)
            useradd --system --home-dir "${f[1]}" --shell /usr/sbin/nologin "${f[2]}"
            ;;
        mkdir)
            mkdir -p "${f[1]}"
            if [ "${f[2]:-}" = "own" ]; then maybe_chown "${f[1]}"; fi
            ;;
        copyfile) # copyfile <src> <dst> <mode> [own]
            install -D -m "${f[3]}" "${f[1]}" "${f[2]}"
            if [ "${f[4]:-}" = "own" ]; then maybe_chown "${f[2]}"; fi
            ;;
        synctree) # synctree <src> <dst>
            mkdir -p "${f[2]}"
            cp -a "${f[1]}/." "${f[2]}/"
            maybe_chown "${f[2]}"
            ;;
        webroot) # webroot <dist> <webroot>
            (cd "${f[1]}" && find . -type f \
                ! -name offers.json ! -name meta.json -print0 |
                while IFS= read -r -d '' p; do
                    install -D -m 0644 "$p" "${f[2]}/${p#./}"
                done)
            maybe_chown "${f[2]}"
            ;;
        venv)
            [ -x "$VENV_DIR/bin/python" ] || "$PYTHON" -m venv "$VENV_DIR"
            "$VENV_DIR/bin/pip" install --quiet --upgrade pip
            "$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"
            printf '%s' "$REQ_SUM" > "$REQ_STAMP"
            maybe_chown "$VENV_DIR"
            ;;
        merge) # merge <mode> <sample> <live>
            local rc=0
            "$PYTHON" "$SCRIPT_DIR/merge_config.py" \
                --mode "${f[1]}" --sample "${f[2]}" --live "${f[3]}" || rc=$?
            [ "$rc" = "0" ] || [ "$rc" = "3" ] || die "merge_config.py failed (exit $rc)"
            ;;
        *) die "unknown action type: ${f[0]}" ;;
    esac
}

# --- Steps ---------------------------------------------------------------

# 1. Service user (create-or-reuse).
if [ "$MANAGE_USER" = "1" ]; then
    if getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
        ok "user $SERVICE_USER exists"
    elif [ "$IS_ROOT" = "1" ]; then
        plan "create system user $SERVICE_USER" useradd "$APP_ROOT" "$SERVICE_USER"
    else
        die "user $SERVICE_USER does not exist and not running as root (set MANAGE_USER=0 to skip)"
    fi
else
    ok "user management disabled (MANAGE_USER=0)"
fi

# 2. Directories.
step_dir() { # step_dir <dir> [own]
    if [ -d "$1" ]; then
        ok "directory exists ($1)"
    else
        plan "create directory $1" mkdir "$1" "${2:-}"
    fi
}
step_dir "$APP_ROOT" own
step_dir "$WEB_ROOT" own
step_dir "$SYNC_DIR" own
step_dir "$LOG_DIR" own
step_dir "$BACKUP_DIR"

# 3. Application code (offers_processing/, scraper/) into APP_ROOT.
step_tree() { # step_tree <label> <src> <dst>
    local label="$1" src="$2" dst="$3"
    if [ -d "$dst" ] && diff -rq -x '__pycache__' -x '*.pyc' \
            -x 'config.py' -x 'settings.py' -x '*.pem' -x '*.json' \
            "$src" "$dst" >/dev/null 2>&1; then
        ok "$label up to date ($dst)"
    else
        if [ -d "$dst" ]; then
            log "DIFF  $label:"
            diff -rq -x '__pycache__' -x '*.pyc' -x 'config.py' \
                -x 'settings.py' -x '*.pem' -x '*.json' "$src" "$dst" 2>&1 || true
        fi
        plan "sync $label -> $dst" synctree "$src" "$dst"
    fi
}
step_tree offers_processing "$REPO_DIR/offers_processing" "$APP_ROOT/offers_processing"
step_tree scraper "$REPO_DIR/scraper" "$APP_ROOT/scraper"

# 4. Web root: frontend/dist -> WEB_ROOT. offers.json/meta.json in WEB_ROOT
#    are data written by process_offers.py — never deleted or overwritten.
FRONTEND_DIST="$REPO_DIR/frontend/dist"
if [ -d "$FRONTEND_DIST" ]; then
    WEB_DRIFT=0
    while IFS= read -r -d '' f; do
        rel="${f#"$FRONTEND_DIST"/}"
        case "$rel" in offers.json|meta.json) continue ;; esac
        if [ ! -f "$WEB_ROOT/$rel" ] || ! cmp -s "$f" "$WEB_ROOT/$rel"; then
            WEB_DRIFT=1
            log "DIFF  web root: $rel"
        fi
    done < <(find "$FRONTEND_DIST" -type f -print0)
    if [ "$WEB_DRIFT" = "1" ]; then
        plan "sync frontend/dist -> $WEB_ROOT (offers.json/meta.json preserved)" \
            webroot "$FRONTEND_DIST" "$WEB_ROOT"
    else
        ok "web root up to date ($WEB_ROOT)"
    fi
else
    log "WARN  $FRONTEND_DIST missing — build the frontend (cd frontend && npm ci && npm run build) before deploying; skipping web root sync"
fi

# 5. cron / logrotate / systemd / nginx (rendered, compare-and-install).
render() { # render <src> <dst>: substitute deployment paths into templates
    sed \
        -e "s|/path/to/run_scrapers.sh|$APP_ROOT/scraper/run_scrapers.sh|g" \
        -e "s|/path/to/venv|$VENV_DIR|g" \
        -e "s|/opt/your-website-url/offers_processing|$APP_ROOT/offers_processing|g" \
        -e "s|/opt/your-website-url/data/sync|$SYNC_DIR|g" \
        -e "s|/var/log/lidaldi|$LOG_DIR|g" \
        -e "s|create 0640 lidaldi lidaldi|create 0640 $SERVICE_USER $SERVICE_USER|" \
        -e "s|^User=lidaldi$|User=$SERVICE_USER|" \
        -e "s|^Group=lidaldi$|Group=$SERVICE_USER|" \
        -e "s|\\* lidaldi |* $SERVICE_USER |" \
        "$1" > "$2"
    if [ -n "$PROM_DIR" ]; then
        sed -i "s|^# ReadWritePaths=/var/lib/prometheus/node-exporter$|ReadWritePaths=$PROM_DIR|" "$2"
    fi
}

step_file() { # step_file <label> <rendered-src> <dst>
    local label="$1" src="$2" dst="$3"
    if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
        ok "$label up to date ($dst)"
        return 0
    fi
    log "DIFF  $label ($dst):"
    diff -u "$dst" "$src" 2>/dev/null || true
    plan "install $label -> $dst" copyfile "$src" "$dst" 0644
    return 1
}

render "$REPO_DIR/cron.d/lidaldi" "$TMP_DIR/cron"
step_file cron "$TMP_DIR/cron" "$CRON_DIR/lidaldi" || true

render "$REPO_DIR/logrotate.d/lidaldi" "$TMP_DIR/logrotate"
step_file logrotate "$TMP_DIR/logrotate" "$LOGROTATE_DIR/lidaldi" || true

render "$REPO_DIR/systemd/lidaldi-sync.service" "$TMP_DIR/unit"
step_file systemd_unit "$TMP_DIR/unit" "$SYSTEMD_DIR/lidaldi-sync.service" || SERVICE_CHANGED=1

render "$REPO_DIR/nginx/lidaldi-sync-proxy.conf" "$TMP_DIR/nginx"
step_file nginx_snippet "$TMP_DIR/nginx" "$NGINX_SNIPPET_DIR/lidaldi-sync-proxy.conf" || true

# 6. venv + deps (re-pip only when requirements.txt changes).
REQ_STAMP="$VENV_DIR/.requirements.sha256"
REQ_SUM="$(sha256sum "$REPO_DIR/requirements.txt" | cut -d' ' -f1)"
if [ -x "$VENV_DIR/bin/python" ] && [ -f "$REQ_STAMP" ] && \
        [ "$(cat "$REQ_STAMP")" = "$REQ_SUM" ]; then
    ok "venv up to date ($VENV_DIR)"
else
    plan "create/refresh venv $VENV_DIR + pip install -r requirements.txt" venv
fi

# 7. Config: create-from-sample when missing, else sample->real merge
#    (adds-never-clobbers, via merge_config.py).
step_config() { # step_config <mode> <sample> <live> <mode-bits>
    local mode="$1" sample="$2" live="$3" bits="$4"
    if [ ! -f "$live" ]; then
        plan "create $live from $(basename "$sample") (edit real values afterwards!)" \
            copyfile "$sample" "$live" "$bits" own
        return
    fi
    local rc=0
    "$PYTHON" "$SCRIPT_DIR/merge_config.py" \
        --mode "$mode" --sample "$sample" --live "$live" --dry-run || rc=$?
    case "$rc" in
        0) ok "config $live in sync with sample" ;;
        3) plan "merge new sample keys into $live (never clobbers live values)" \
               merge "$mode" "$sample" "$live" ;;
        *) die "merge_config.py failed for $live (exit $rc)" ;;
    esac
}
step_config toml "$REPO_DIR/config.toml.sample" "$LIVE_TOML" 0640
step_config env  "$REPO_DIR/.env.sample"        "$LIVE_ENV"  0600

# 8. VAPID keypair: reused verbatim — never generated, moved or rewritten.
VAPID_PRIVATE="${VAPID_PRIVATE_KEY_PATH:-$APP_ROOT/offers_processing/vapid_private.pem}"
if [ -f "$VAPID_PRIVATE" ]; then
    ok "VAPID private key present ($VAPID_PRIVATE) — reused verbatim, never touched"
else
    log "WARN  no VAPID private key at $VAPID_PRIVATE — for a fresh install generate one with generate_vapid_keys.py; this script never generates or moves keys"
fi

# --- Backup + apply ------------------------------------------------------
if [ "${#PLAN_DESCS[@]}" = "0" ]; then
    log "NOOP  everything up to date — nothing to do (no backup taken)"
    exit 0
fi

if [ "$DRY_RUN" = "1" ]; then
    log "DRY-RUN would apply ${#PLAN_DESCS[@]} action(s); no changes made:"
    for d in "${PLAN_DESCS[@]}"; do log "  - $d"; done
    exit 0
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_DIR/lidaldi-backup-$STAMP"
log "BACKUP -> $BACKUP (live configs + SYNC_DIR) before any mutation"
mkdir -p "$BACKUP/configs"
for f in "$LIVE_TOML" "$LIVE_ENV" \
         "$APP_ROOT/offers_processing/config.py" \
         "$APP_ROOT/scraper/lidaldi/settings.py"; do
    if [ -f "$f" ]; then cp -a "$f" "$BACKUP/configs/"; fi
done
if [ -d "$SYNC_DIR" ]; then
    cp -a "$SYNC_DIR" "$BACKUP/sync"
fi

for i in "${!PLAN_ACTIONS[@]}"; do
    log "APPLY ${PLAN_DESCS[$i]}"
    apply_action "${PLAN_ACTIONS[$i]}"
done

# systemd reload/restart only when the unit changed and systemd is running.
if [ "$SERVICE_CHANGED" = "1" ]; then
    if [ "$NO_RESTART" = "1" ]; then
        log "SKIP  service restart (--no-restart); run: systemctl daemon-reload && systemctl restart lidaldi-sync"
    elif [ "$IS_ROOT" = "1" ] && [ -d /run/systemd/system ] && \
            command -v systemctl >/dev/null 2>&1 && \
            [ "$SYSTEMD_DIR" = "/etc/systemd/system" ]; then
        log "APPLY systemctl daemon-reload + enable/restart lidaldi-sync"
        systemctl daemon-reload
        systemctl enable lidaldi-sync >/dev/null 2>&1 || true
        systemctl restart lidaldi-sync
    else
        log "SKIP  systemd restart (not root, systemd not running, or non-standard SYSTEMD_DIR); unit installed but not (re)started"
    fi
fi

log "DONE  applied ${#PLAN_DESCS[@]} action(s); backup at $BACKUP"
