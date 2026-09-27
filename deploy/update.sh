#!/bin/bash
#
# LIDALDI idempotent installer/updater (T10, arch doc §6.5).
#
# Create-or-update: service user, cron, logrotate, systemd unit, nginx
# snippet, frontend build, web root (+ permissions), pyenv virtualenv/deps,
# sample->real config merge. Every step
# checks current state and only registers an action on drift; a second run
# on an already-installed system is a no-op (no backup, no mutation).
#
# Usage: update.sh [--dry-run] [--no-restart] [--plain] [--config /path/to/install.local.conf]
#
#   --plain  plain "TOKEN message" output even on a terminal (output is
#            already plain whenever stdout is not a terminal or NO_COLOR is set)
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
PLAIN=0
CONF_FILE="$SCRIPT_DIR/install.local.conf"

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --no-restart) NO_RESTART=1 ;;
        --plain) PLAIN=1 ;;
        --config) shift; CONF_FILE="${1:?--config needs a path}" ;;
        -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "ERROR unknown argument: $1" >&2; exit 2 ;;
    esac
    shift
done

# shellcheck source=deploy/ui.sh
. "$SCRIPT_DIR/ui.sh"
ui_init "$PLAIN" "$(grep -c '^ui_section "' "${BASH_SOURCE[0]}")"
die() { say ERROR "$*" >&2; exit 1; }
trap ui_interrupt INT TERM

# --- Local config --------------------------------------------------------
[ -f "$CONF_FILE" ] || die "missing $CONF_FILE — copy \
$SCRIPT_DIR/install.local.conf.sample to install.local.conf and edit it."
# pyenv uses these names for shell selection/activation. Drop inherited values
# before sourcing local config so operator shells and sudo -E cannot steer deploys.
unset PYENV_VERSION PYENV_VIRTUALENV
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
PYENV_ROOT="${PYENV_ROOT:-/opt/pyenv}"
PYENV_PYTHON_VERSION="${PYENV_PYTHON_VERSION:-3.12.13}"
PYENV_VIRTUALENV_NAME="${PYENV_VIRTUALENV_NAME:-lidaldi}"
WEB_GROUP="${WEB_GROUP:-www-data}"
# No trailing slashes: the web root permission step matches paths exactly.
# ("/" stays "/" so the breadth guard below can reject it by name.)
[ "$WEB_ROOT" = "/" ] || WEB_ROOT="${WEB_ROOT%/}"
IMAGES_DIR="${IMAGES_DIR:-$WEB_ROOT/img/full}"
IMAGES_DIR="${IMAGES_DIR%/}"
NPM_BIN="${NPM_BIN:-npm}"

# --- Preflight: pyenv + Python runtime (decision D3) -------------------------
if [ -x "$PYENV_ROOT/bin/pyenv" ]; then
    PYENV_BIN="$PYENV_ROOT/bin/pyenv"
elif command -v pyenv >/dev/null 2>&1; then
    PYENV_BIN="$(command -v pyenv)"
    PYENV_ROOT="$("$PYENV_BIN" root 2>/dev/null || true)"
    [ -n "$PYENV_ROOT" ] || die "pyenv found on PATH but 'pyenv root' failed; set PYENV_ROOT in install.local.conf."
else
    die "pyenv not found. Install pyenv at $PYENV_ROOT or put pyenv on PATH; lidaldi expects Python $PYENV_PYTHON_VERSION from pyenv."
fi
export PYENV_ROOT
export PATH="$PYENV_ROOT/bin:$PATH"

pyenv_versions() {
    PYENV_VERSION= "$PYENV_BIN" versions --bare 2>/dev/null || true
}

pyenv_has_version() {
    pyenv_versions | grep -Fx "$1" >/dev/null 2>&1
}

python_matches_version() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info[:3] == tuple(map(int, sys.argv[1].split("."))) else 1)' "$2"
}

python_base() {
    PYENV_VERSION="$PYENV_PYTHON_VERSION" "$PYENV_BIN" exec python "$@"
}

if ! pyenv_has_version "$PYENV_PYTHON_VERSION"; then
    die "pyenv Python $PYENV_PYTHON_VERSION is not installed. Install it with: PYENV_ROOT=$PYENV_ROOT pyenv install $PYENV_PYTHON_VERSION"
fi
if ! PYENV_VERSION= "$PYENV_BIN" virtualenv --help >/dev/null 2>&1; then
    die "pyenv-virtualenv plugin not found. Install it under $PYENV_ROOT/plugins/pyenv-virtualenv."
fi
if ! python_base -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    die "Python >= 3.12 required (D3); pyenv $PYENV_PYTHON_VERSION reports $(python_base --version 2>&1)."
fi

VENV_DIR="$PYENV_ROOT/versions/$PYENV_VIRTUALENV_NAME"
LIVE_TOML="$APP_ROOT/config.toml"
LIVE_ENV="$APP_ROOT/.env"

[ -d "$REPO_DIR/deploy" ] || die "REPO_DIR=$REPO_DIR does not look like a lidaldi checkout"

IS_ROOT=0
if [ "$(id -u)" = "0" ]; then IS_ROOT=1; fi

# Root chowns/chmods under these paths, so they must be plain absolute
# paths: a textual prefix check alone would let "img/../../etc" escape.
for p in "$WEB_ROOT" "$IMAGES_DIR"; do
    case "$p" in /*) ;; *) die "path must be absolute: $p" ;; esac
    case "/$p/" in
        */../*|*/./*) die "path must not contain . or .. components: $p" ;;
    esac
done
# Canonical form (symlinks resolved, // collapsed): find(1) never descends a
# symlinked start point, so a symlinked WEB_ROOT would otherwise make the
# permission step check nothing and report OK.
WEB_ROOT="$(realpath -m -- "$WEB_ROOT")"
IMAGES_DIR="$(realpath -m -- "$IMAGES_DIR")"
# WEB_ROOT must be a directory dedicated to this site: everything under it
# is re-owned root:$WEB_GROUP 0750/0640 on every run. "/" or a shared parent
# (/var/www on a multi-site host, /opt holding APP_ROOT) would wreck the box.
WEB_ROOT_BREADTH="must be a directory dedicated to this site — everything under it is re-owned root:$WEB_GROUP 0750/0640 on every run"
case "$WEB_ROOT" in
    /|/bin|/boot|/dev|/etc|/home|/lib|/lib32|/lib64|/media|/mnt|/opt|/proc|/root|/run|/sbin|/srv|/sys|/tmp|/usr|/usr/local|/usr/share|/var|/var/lib|/var/log|/var/www)
        die "WEB_ROOT ($WEB_ROOT) is a system or shared directory; it $WEB_ROOT_BREADTH" ;;
esac
for p in "$APP_ROOT" "$SYNC_DIR" "$LOG_DIR" "$BACKUP_DIR" "$PYENV_ROOT" "$REPO_DIR"; do
    case "$(realpath -m -- "$p")/" in
        "$WEB_ROOT"/*) die "WEB_ROOT ($WEB_ROOT) contains $p; it $WEB_ROOT_BREADTH" ;;
    esac
done
case "$IMAGES_DIR" in
    "$WEB_ROOT"/?*) ;;
    *) die "IMAGES_DIR ($IMAGES_DIR) must be inside WEB_ROOT ($WEB_ROOT) — nginx serves the images from there" ;;
esac
if [ "$IS_ROOT" = "1" ] && ! getent group "$WEB_GROUP" >/dev/null 2>&1; then
    die "WEB_GROUP '$WEB_GROUP' does not exist — set WEB_GROUP in install.local.conf to the group nginx runs as (usually www-data)"
fi

if [ "$FANCY" = "1" ]; then
    UI_COMMIT="$(git -C "$REPO_DIR" log -1 --format='%h %s' 2>/dev/null)" || UI_COMMIT="(not a git checkout)"
    UI_MODE="apply"
    [ "$DRY_RUN" = "1" ] && UI_MODE="dry run — nothing will be changed"
    ui_banner "◆ LidAldi · deploy/update.sh" \
        "host     $(uname -n)" \
        "commit   $UI_COMMIT" \
        "mode     $UI_MODE" \
        "config   $CONF_FILE"
    ui_phase "PLAN"
fi

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
    say PLAN "$desc"
}

ok() { say OK "$*"; }

apply_action() {
    local rec="$1"
    local -a f
    IFS="$US" read -r -a f <<< "$rec"
    case "${f[0]}" in
        useradd)
            useradd --system --home-dir "${f[1]}" --shell /usr/sbin/nologin "${f[2]}"
            ;;
        usermod) # usermod <user> <group>
            usermod -aG "${f[2]}" "${f[1]}"
            ;;
        mkdir)
            mkdir -p "${f[1]}"
            if [ "${f[2]:-}" = "own" ]; then maybe_chown "${f[1]}"; fi
            ;;
        copyfile) # copyfile <src> <dst> <mode> [own]
            install -D -m "${f[3]}" "${f[1]}" "${f[2]}"
            if [ "${f[4]:-}" = "own" ]; then maybe_chown "${f[2]}"; fi
            ;;
        synctree) # synctree <src> <dst> — live-config/key/data/rendered patterns
            # (config.py, settings.py, *.pem, *.json) are never copied over
            # nor pruned, mirroring the drift check. run_scrapers.sh is
            # rendered separately with deployment paths. Files deleted from
            # the repo are pruned so the sync converges to a no-op.
            mkdir -p "${f[2]}"
            (cd "${f[1]}" && find . -type f ! -path '*/__pycache__/*' \
                ! -name '*.pyc' ! -name 'config.py' ! -name 'settings.py' \
                ! -name '*.pem' ! -name '*.json' ! -name 'run_scrapers.sh' \
                -exec cp -a --parents {} "${f[2]}/" \;)
            (cd "${f[2]}" && find . -type f ! -path '*/__pycache__/*' \
                ! -name '*.pyc' ! -name 'config.py' ! -name 'settings.py' \
                ! -name '*.pem' ! -name '*.json' ! -name 'run_scrapers.sh' -print0 |
                while IFS= read -r -d '' p; do
                    [ -f "${f[1]}/$p" ] || rm -f -- "$p"
                done)
            (cd "${f[2]}" && find . -depth -mindepth 1 -type d -empty -print0 |
                while IFS= read -r -d '' p; do
                    [ -d "${f[1]}/$p" ] || rmdir -- "$p"
                done)
            maybe_chown "${f[2]}"
            ;;
        webroot) # webroot <dist> <webroot>
            # Installed straight as root:$WEB_GROUP 0640 so nginx never sees
            # an unreadable file; webperms (planned right after) fixes the rest.
            # Non-root runs skip the permissions step, so keep those files
            # world-readable (0644, as before) or nginx could not read them.
            local -a owner=(-m 0644)
            if [ "$IS_ROOT" = "1" ]; then owner=(-o root -g "$WEB_GROUP" -m 0640); fi
            (cd "${f[1]}" && find . -type f \
                ! -path ./offers.json ! -path ./meta.json ! -path "./$BUILD_STAMP" -print0 |
                while IFS= read -r -d '' p; do
                    install -D "${owner[@]}" "$p" "${f[2]}/${p#./}"
                done)
            ;;
        webperms)
            webroot_fix_perms
            ;;
        build_frontend)
            # --ignore-scripts: this runs as root, so no third-party package
            # lifecycle scripts (the lockfile has none needed on Linux).
            # `npm run build` still runs the repo's own build script — the
            # same trust as this installer, which runs from the checkout.
            (cd "$FRONTEND_SRC" && "$NPM_BIN" ci --ignore-scripts --no-audit --no-fund && "$NPM_BIN" run build)
            # Stamp only after a successful build: a failed one is retried.
            printf '%s\n' "$FRONTEND_FP" > "$FRONTEND_DIST/$BUILD_STAMP"
            ;;
        venv)
            if ! pyenv_has_version "$PYENV_VIRTUALENV_NAME"; then
                PYENV_VERSION="$PYENV_PYTHON_VERSION" "$PYENV_BIN" virtualenv "$PYENV_PYTHON_VERSION" "$PYENV_VIRTUALENV_NAME"
            fi
            "$VENV_DIR/bin/pip" install --quiet --upgrade pip
            "$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"
            printf '%s' "$REQ_SUM" > "$REQ_STAMP"
            ;;
        merge) # merge <mode> <sample> <live>
            local rc=0
            python_base "$SCRIPT_DIR/merge_config.py" \
                --mode "${f[1]}" --sample "${f[2]}" --live "${f[3]}" || rc=$?
            [ "$rc" = "0" ] || [ "$rc" = "3" ] || die "merge_config.py failed (exit $rc)"
            ;;
        *) die "unknown action type: ${f[0]}" ;;
    esac
}

# --- Steps ---------------------------------------------------------------

# 1. Service user (create-or-reuse).
ui_section "Service user"
in_group() { # in_group <user> <group>
    local groups
    groups=" $(id -nG "$1" 2>/dev/null) " || return 1
    [[ "$groups" == *" $2 "* ]]
}
# The cron job reaches IMAGES_DIR through root:$WEB_GROUP 0750 directories
# (step 5), so $SERVICE_USER must be a member of $WEB_GROUP.
GROUP_HINT="the cron job reaches $IMAGES_DIR through $WEB_GROUP-only directories"
if [ "$MANAGE_USER" = "1" ]; then
    if getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
        ok "user $SERVICE_USER exists"
    elif [ "$IS_ROOT" = "1" ]; then
        plan "create system user $SERVICE_USER" useradd "$APP_ROOT" "$SERVICE_USER"
    else
        die "user $SERVICE_USER does not exist and not running as root (set MANAGE_USER=0 to skip)"
    fi
    if [ "$IS_ROOT" = "1" ]; then
        if getent passwd "$SERVICE_USER" >/dev/null 2>&1 && in_group "$SERVICE_USER" "$WEB_GROUP"; then
            ok "user $SERVICE_USER is in group $WEB_GROUP"
        else
            plan "add user $SERVICE_USER to group $WEB_GROUP ($GROUP_HINT)" \
                usermod "$SERVICE_USER" "$WEB_GROUP"
        fi
    fi
else
    ok "user management disabled (MANAGE_USER=0)"
    # Nothing will create it, and every ownership check needs it to exist.
    if [ "$IS_ROOT" = "1" ] && ! getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
        die "user $SERVICE_USER does not exist and MANAGE_USER=0 — create it (in group $WEB_GROUP) or set MANAGE_USER=1"
    fi
    if [ "$IS_ROOT" = "1" ] && getent passwd "$SERVICE_USER" >/dev/null 2>&1 && \
            ! in_group "$SERVICE_USER" "$WEB_GROUP"; then
        say WARN "user $SERVICE_USER is not in group $WEB_GROUP — $GROUP_HINT; run: usermod -aG $WEB_GROUP $SERVICE_USER"
    fi
fi

# 2. Directories. The web root and IMAGES_DIR get their owners from the
#    web root permissions step (5), not from here.
ui_section "Directories"
step_dir() { # step_dir <dir> [own]
    if [ -d "$1" ]; then
        ok "directory exists ($1)"
    else
        plan "create directory $1" mkdir "$1" "${2:-}"
    fi
}
step_dir "$APP_ROOT" own
step_dir "$WEB_ROOT"
step_dir "$IMAGES_DIR"
step_dir "$SYNC_DIR" own
step_dir "$LOG_DIR" own
step_dir "$BACKUP_DIR"

# 3. Application code (offers_processing/, scraper/) into APP_ROOT.
ui_section "Application code"
step_tree() { # step_tree <label> <src> <dst>
    local label="$1" src="$2" dst="$3"
    if [ -d "$dst" ] && diff -rq -x '__pycache__' -x '*.pyc' \
            -x 'config.py' -x 'settings.py' -x '*.pem' -x '*.json' \
            -x 'run_scrapers.sh' "$src" "$dst" >/dev/null 2>&1; then
        ok "$label up to date ($dst)"
    else
        if [ -d "$dst" ]; then
            say DIFF "$label:"
            { diff -rq -x '__pycache__' -x '*.pyc' -x 'config.py' \
                -x 'settings.py' -x '*.pem' -x '*.json' \
                -x 'run_scrapers.sh' "$src" "$dst" 2>&1 || true; } | ui_diff
        fi
        plan "sync $label -> $dst" synctree "$src" "$dst"
    fi
}
step_tree offers_processing "$REPO_DIR/offers_processing" "$APP_ROOT/offers_processing"
step_tree scraper "$REPO_DIR/scraper" "$APP_ROOT/scraper"

# 4. Frontend build. frontend/dist is a git-ignored build artifact, so a
#    `git pull` alone never updates it. Rebuild whenever the sources differ
#    from the fingerprint the last successful build stamped into dist/.
ui_section "Frontend build"
FRONTEND_SRC="$REPO_DIR/frontend"
FRONTEND_DIST="$FRONTEND_SRC/dist"
BUILD_STAMP=".build-fingerprint"
FRONTEND_FP=""
FRONTEND_BUILD_PLANNED=0

frontend_fingerprint() { # sha256 over every source file (not node_modules/dist)
    (cd "$FRONTEND_SRC" && find . \( -path ./node_modules -o -path ./dist \) -prune \
        -o -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum) |
        sha256sum | cut -d' ' -f1
}

if [ -f "$FRONTEND_SRC/package.json" ]; then
    FRONTEND_FP="$(frontend_fingerprint)"
    if [ -f "$FRONTEND_DIST/$BUILD_STAMP" ] && \
            [ "$(cat "$FRONTEND_DIST/$BUILD_STAMP")" = "$FRONTEND_FP" ]; then
        ok "frontend build up to date (frontend/dist)"
    else
        if [ -f "$FRONTEND_DIST/$BUILD_STAMP" ]; then
            why="sources changed since the last build"
        elif [ -d "$FRONTEND_DIST" ]; then
            why="frontend/dist has no build fingerprint (built by hand?)"
        else
            why="frontend/dist missing"
        fi
        if ! command -v "$NPM_BIN" >/dev/null 2>&1; then
            NPM_MISSING="frontend needs a build ($why) but '$NPM_BIN' was not found — install Node.js/npm or set NPM_BIN in install.local.conf; refusing to deploy a stale frontend"
            # A dry run still previews the whole plan; a real run stops here.
            [ "$DRY_RUN" = "1" ] || die "$NPM_MISSING"
            say WARN "$NPM_MISSING (a real run would abort here)"
        fi
        say DIFF "frontend: $why"
        plan "build frontend (npm ci && npm run build)" build_frontend
        FRONTEND_BUILD_PLANNED=1
    fi
else
    ok "no frontend sources in checkout — deploying frontend/dist as is"
fi

# 5. Web root: frontend/dist -> WEB_ROOT, then permissions.
#    offers.json/meta.json in WEB_ROOT are data written by process_offers.py
#    — their content is never deleted or overwritten.
ui_section "Web root"
WEBROOT_SYNC_PLANNED=0
if [ "$FRONTEND_BUILD_PLANNED" = "1" ]; then
    plan "sync frontend/dist -> $WEB_ROOT after the build (offers.json/meta.json preserved)" \
        webroot "$FRONTEND_DIST" "$WEB_ROOT"
    WEBROOT_SYNC_PLANNED=1
elif [ -d "$FRONTEND_DIST" ]; then
    WEB_DRIFT=0
    while IFS= read -r -d '' f; do
        rel="${f#"$FRONTEND_DIST"/}"
        case "$rel" in offers.json|meta.json|"$BUILD_STAMP") continue ;; esac
        if [ ! -f "$WEB_ROOT/$rel" ] || ! cmp -s "$f" "$WEB_ROOT/$rel"; then
            WEB_DRIFT=1
            say DIFF "web root: $rel"
        fi
    done < <(find "$FRONTEND_DIST" -type f -print0)
    if [ "$WEB_DRIFT" = "1" ]; then
        plan "sync frontend/dist -> $WEB_ROOT (offers.json/meta.json preserved)" \
            webroot "$FRONTEND_DIST" "$WEB_ROOT"
        WEBROOT_SYNC_PLANNED=1
    else
        ok "web root up to date ($WEB_ROOT)"
    fi
else
    say WARN "$FRONTEND_DIST missing — build the frontend (cd frontend && npm ci && npm run build) before deploying; skipping web root sync"
fi

# Web root permissions. Baseline: everything root:$WEB_GROUP, dirs 0750,
# files 0640 — nginx (in $WEB_GROUP) can read, only root can modify the
# app files. The cron job ($SERVICE_USER) owns exactly what it writes: the web root
# directory itself (process_offers.py creates offers.json/meta.json there
# via a .tmp file + rename), those data files, and the whole IMAGES_DIR
# tree (the scraper adds images and overwrites them once they expire).
# Symlinks are never followed or changed: $SERVICE_USER can create them in
# the directories it owns.
# Caveat: owning the web root directory also lets $SERVICE_USER rename or
# replace its *top-level* entries (index.html, sw.js, assets/) — it cannot
# edit them or anything inside root-owned subdirectories. Closing that would
# need a root-owned sticky web root plus an ACL for $SERVICE_USER.
WEB_DATA_FILES=(offers.json meta.json offers.json.tmp meta.json.tmp)

webroot_root_zone() { # webroot_root_zone <find-action...>: entries root owns
    local -a skip=()
    local n
    for n in "${WEB_DATA_FILES[@]}"; do skip+=(! -path "$WEB_ROOT/$n"); done
    find "$WEB_ROOT" -mindepth 1 \( -path "$IMAGES_DIR" -prune \) -o \
        \( -type f -o -type d \) "${skip[@]}" "$@"
}

webroot_service_paths() { # NUL-separated: the web root dir + its data files
    local n p
    printf '%s\0' "$WEB_ROOT"
    for n in "${WEB_DATA_FILES[@]}"; do
        p="$WEB_ROOT/$n"
        if [ -f "$p" ] && [ ! -L "$p" ]; then printf '%s\0' "$p"; fi
    done
}

webroot_images_tree() { # webroot_images_tree <find-action...>
    if [ -d "$IMAGES_DIR" ] && [ ! -L "$IMAGES_DIR" ]; then
        find "$IMAGES_DIR" \( -type f -o -type d \) "$@"
    fi
}

webroot_perm_drift() { # one line per entry that breaks the policy (may repeat)
    local -a svc
    mapfile -d '' -t svc < <(webroot_service_paths)
    find "$WEB_ROOT" \( -type d \( ! -perm 0750 -o ! -group "$WEB_GROUP" \) -print \) \
        -o \( -type f \( ! -perm 0640 -o ! -group "$WEB_GROUP" \) -print \)
    webroot_root_zone ! -user root -print
    find "${svc[@]}" -maxdepth 0 ! -user "$SERVICE_USER" -print
    webroot_images_tree ! -user "$SERVICE_USER" -print
}

webroot_fix_perms() {
    local -a svc left
    local rc=0
    mapfile -d '' -t svc < <(webroot_service_paths)
    # Owners first, then modes. The cron job may replace or reap files while
    # this runs (offers.json.tmp, expired images), so a vanished path is not
    # fatal: on any error, re-check and fail only if real drift remains.
    webroot_root_zone -exec chown -h "root:$WEB_GROUP" {} + 2>/dev/null || rc=1
    chown -h "$SERVICE_USER:$WEB_GROUP" "${svc[@]}" 2>/dev/null || rc=1
    webroot_images_tree -exec chown -h "$SERVICE_USER:$WEB_GROUP" {} + 2>/dev/null || rc=1
    find "$WEB_ROOT" -type d -exec chmod 0750 {} + 2>/dev/null || rc=1
    find "$WEB_ROOT" -type f -exec chmod 0640 {} + 2>/dev/null || rc=1
    [ "$rc" = "0" ] && return 0
    mapfile -t left < <(webroot_perm_drift 2>/dev/null | LC_ALL=C sort -u)
    [ "${#left[@]}" = "0" ] || die "web root permissions could not be applied to ${#left[@]} path(s), e.g. ${left[0]}"
}

# Symlinks are never followed or changed, so the drift check can't see
# them — but nginx follows them and serves their targets. Report them.
if [ -d "$WEB_ROOT" ]; then
    WEB_LINKS=()
    mapfile -t WEB_LINKS < <(find "$WEB_ROOT" -mindepth 1 -type l 2>/dev/null | LC_ALL=C sort)
    if [ "${#WEB_LINKS[@]}" -gt 0 ]; then
        say WARN "${#WEB_LINKS[@]} symlink(s) in the web root (never followed or changed here, but nginx serves their targets), e.g.:"
        for p in "${WEB_LINKS[@]:0:5}"; do
            say_item "${p#"$WEB_ROOT"/} -> $(readlink -- "$p")"
        done
    fi
fi

if [ "$IS_ROOT" != "1" ]; then
    say SKIP "web root permissions (not running as root)"
else
    # Files the build/sync/mkdir will create don't exist yet at plan time,
    # so those always get the permissions pass after them.
    PERMS_REASON=""
    if [ "$WEBROOT_SYNC_PLANNED" = "1" ]; then
        PERMS_REASON="after the web root sync"
    elif [ ! -d "$WEB_ROOT" ] || [ ! -d "$IMAGES_DIR" ]; then
        PERMS_REASON="for the new directories"
    elif ! getent passwd "$SERVICE_USER" >/dev/null 2>&1; then
        PERMS_REASON="for the new user $SERVICE_USER"
    fi
    PERM_DRIFT=()
    if [ -z "$PERMS_REASON" ]; then
        mapfile -t PERM_DRIFT < <(webroot_perm_drift | LC_ALL=C sort -u)
    fi
    if [ "${#PERM_DRIFT[@]}" -gt 0 ]; then
        say DIFF "web root permissions: ${#PERM_DRIFT[@]} path(s) differ from the policy, e.g.:"
        for p in "${PERM_DRIFT[@]:0:5}"; do
            say_item "$(stat -c '%U:%G %a' -- "$p" 2>/dev/null)  ${p#"$WEB_ROOT"/}"
        done
        PERMS_REASON="to fix ${#PERM_DRIFT[@]} path(s)"
    fi
    if [ -n "$PERMS_REASON" ]; then
        plan "set web root permissions $PERMS_REASON (root:$WEB_GROUP 0750/0640; $SERVICE_USER owns the web root dir, offers.json/meta.json and ${IMAGES_DIR#"$WEB_ROOT"/}/)" webperms
    else
        ok "web root permissions correct"
    fi
fi

# 6. cron / logrotate / systemd / nginx (rendered, compare-and-install).
ui_section "System files"
render() { # render <src> <dst>: substitute deployment paths into templates
    sed \
        -e "s|/path/to/run_scrapers.sh|$APP_ROOT/scraper/run_scrapers.sh|g" \
        -e "s|/path/to/venv|$VENV_DIR|g" \
        -e "s|/path/to/scrapy|$APP_ROOT/scraper|g" \
        -e "s|/path/to/processing|$APP_ROOT/offers_processing|g" \
        -e "s|/path/to/images/folder|$IMAGES_DIR|g" \
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
    local mode="${4:-0644}"
    if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
        ok "$label up to date ($dst)"
        return 0
    fi
    say DIFF "$label ($dst):"
    { diff -u "$dst" "$src" 2>/dev/null || true; } | ui_diff
    plan "install $label -> $dst" copyfile "$src" "$dst" "$mode"
    return 1
}

render "$REPO_DIR/cron.d/lidaldi" "$TMP_DIR/cron"
step_file cron "$TMP_DIR/cron" "$CRON_DIR/lidaldi" || true

render "$REPO_DIR/scraper/run_scrapers.sh" "$TMP_DIR/run_scrapers"
step_file run_scrapers "$TMP_DIR/run_scrapers" "$APP_ROOT/scraper/run_scrapers.sh" 0755 || true

render "$REPO_DIR/logrotate.d/lidaldi" "$TMP_DIR/logrotate"
step_file logrotate "$TMP_DIR/logrotate" "$LOGROTATE_DIR/lidaldi" || true

render "$REPO_DIR/systemd/lidaldi-sync.service" "$TMP_DIR/unit"
step_file systemd_unit "$TMP_DIR/unit" "$SYSTEMD_DIR/lidaldi-sync.service" || SERVICE_CHANGED=1

render "$REPO_DIR/nginx/lidaldi-sync-proxy.conf" "$TMP_DIR/nginx"
step_file nginx_snippet "$TMP_DIR/nginx" "$NGINX_SNIPPET_DIR/lidaldi-sync-proxy.conf" || true

# 7. pyenv virtualenv + deps (re-pip only when requirements.txt changes).
ui_section "Python environment"
REQ_STAMP="$VENV_DIR/.requirements.sha256"
REQ_SUM="$(sha256sum "$REPO_DIR/requirements.txt" | cut -d' ' -f1)"
if pyenv_has_version "$PYENV_VIRTUALENV_NAME" && [ -x "$VENV_DIR/bin/python" ] && \
        ! python_matches_version "$VENV_DIR/bin/python" "$PYENV_PYTHON_VERSION"; then
    die "pyenv virtualenv $PYENV_VIRTUALENV_NAME exists at $VENV_DIR but is not based on Python $PYENV_PYTHON_VERSION; recreate it with: PYENV_ROOT=$PYENV_ROOT pyenv virtualenv-delete $PYENV_VIRTUALENV_NAME && PYENV_ROOT=$PYENV_ROOT pyenv virtualenv $PYENV_PYTHON_VERSION $PYENV_VIRTUALENV_NAME"
fi
if pyenv_has_version "$PYENV_VIRTUALENV_NAME" && [ -x "$VENV_DIR/bin/python" ] && \
        [ -f "$REQ_STAMP" ] && \
        [ "$(cat "$REQ_STAMP")" = "$REQ_SUM" ]; then
    ok "pyenv virtualenv up to date ($PYENV_VIRTUALENV_NAME -> $VENV_DIR)"
else
    plan "create/refresh pyenv virtualenv $PYENV_VIRTUALENV_NAME from $PYENV_PYTHON_VERSION + pip install -r requirements.txt" venv
fi

# 8. Config: create-from-sample when missing, else sample->real merge
#    (adds-never-clobbers, via merge_config.py).
ui_section "Configuration"
step_config() { # step_config <mode> <sample> <live> <mode-bits>
    local mode="$1" sample="$2" live="$3" bits="$4"
    if [ ! -f "$live" ]; then
        plan "create $live from $(basename "$sample") (edit real values afterwards!)" \
            copyfile "$sample" "$live" "$bits" own
        return
    fi
    local rc=0
    python_base "$SCRIPT_DIR/merge_config.py" \
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

# The pipeline writes where the live config.toml says, not where this file
# says. If WEB_ROOT/IMAGES_DIR don't cover those paths, the permission step
# and the image cleanup act on a tree nothing writes to. WARN, not die: a
# legacy live scraper settings.py can override images_store.
if [ -f "$LIVE_TOML" ]; then
    CFG_PATHS=()
    mapfile -t CFG_PATHS < <(python_base -c '
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    d = tomllib.load(f)
print(str(d.get("paths", {}).get("website_root_dir", "")).rstrip("/"))
print(str(d.get("scraper", {}).get("images_store", "")).rstrip("/"))
' "$LIVE_TOML" 2>/dev/null) || true
    CFG_WEB="${CFG_PATHS[0]:-}"
    CFG_IMAGES="${CFG_PATHS[1]:-}"
    case "$CFG_WEB" in ""|/path/to/*) CFG_WEB="" ;; esac
    case "$CFG_IMAGES" in ""|/path/to/*) CFG_IMAGES="" ;; esac
    if [ -n "$CFG_WEB" ] && [ "$CFG_WEB" != "$WEB_ROOT" ]; then
        say WARN "config.toml [paths] website_root_dir ($CFG_WEB) != WEB_ROOT ($WEB_ROOT): process_offers.py writes offers.json/meta.json there, outside the web root this installer manages"
    fi
    if [ -n "$CFG_IMAGES" ]; then
        case "$CFG_IMAGES/full" in
            "$IMAGES_DIR"|"$IMAGES_DIR"/*) ;;
            *) say WARN "config.toml [scraper] images_store ($CFG_IMAGES) puts images in $CFG_IMAGES/full, outside IMAGES_DIR ($IMAGES_DIR): the permission step and the 90-day cleanup would miss them — set IMAGES_DIR in install.local.conf" ;;
        esac
    fi
fi

# 9. VAPID keypair: reused verbatim — never generated, moved or rewritten.
ui_section "VAPID key"
env_file_value() { # env_file_value <file> <key>
    local file="$1" key="$2" line value
    [ -f "$file" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
        if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?${key}[[:space:]]*= ]]; then
            value="${line#*=}"
            value="$(printf '%s' "$value" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
            if [[ "$value" =~ ^\".*\"$ ]] || [[ "$value" =~ ^\'.*\'$ ]]; then
                value="${value:1:${#value}-2}"
            fi
            printf '%s\n' "$value"
            return 0
        fi
    done < "$file"
    return 1
}

VAPID_PRIVATE="${VAPID_PRIVATE_KEY_PATH:-}"
if [ -z "$VAPID_PRIVATE" ]; then
    VAPID_PRIVATE="$(env_file_value "$LIVE_ENV" VAPID_PRIVATE_KEY_PATH || true)"
fi
VAPID_PRIVATE="${VAPID_PRIVATE:-$APP_ROOT/offers_processing/vapid_private.pem}"
if [ -f "$VAPID_PRIVATE" ]; then
    ok "VAPID private key present ($VAPID_PRIVATE) — reused verbatim, never touched"
else
    say WARN "no VAPID private key at $VAPID_PRIVATE — for a fresh install generate one with generate_vapid_keys.py; this script never generates or moves keys"
fi

# --- Backup + apply ------------------------------------------------------
if [ "${#PLAN_DESCS[@]}" = "0" ]; then
    ui_phase "RESULT"
    say NOOP "everything up to date — nothing to do (no backup taken)"
    ui_summary "✔ Everything up to date — nothing to do" "checked in $(ui_elapsed)"
    exit 0
fi

if [ "$DRY_RUN" = "1" ]; then
    ui_phase "RESULT"
    say DRY-RUN "would apply ${#PLAN_DESCS[@]} action(s); no changes made:"
    for d in "${PLAN_DESCS[@]}"; do say_item "$d"; done
    ui_summary "◌ Dry run: ${#PLAN_DESCS[@]} action(s) planned, nothing changed" \
        "run again without --dry-run to apply"
    exit 0
fi

ui_phase "APPLY"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_DIR/lidaldi-backup-$STAMP"
say BACKUP "-> $BACKUP (live configs + SYNC_DIR) before any mutation"
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
    ui_apply "$i" "${#PLAN_ACTIONS[@]}" "${PLAN_DESCS[$i]}"
    case "${PLAN_ACTIONS[$i]%%"$US"*}" in
        venv) ui_run "pip install -r requirements.txt" apply_action "${PLAN_ACTIONS[$i]}" ;;
        build_frontend) ui_run "npm ci && npm run build" apply_action "${PLAN_ACTIONS[$i]}" ;;
        *) apply_action "${PLAN_ACTIONS[$i]}" ;;
    esac
done

# systemd reload/restart only when the unit changed and systemd is running.
if [ "$SERVICE_CHANGED" = "1" ]; then
    if [ "$NO_RESTART" = "1" ]; then
        say SKIP "service restart (--no-restart); run: systemctl daemon-reload && systemctl restart lidaldi-sync"
    elif [ "$IS_ROOT" = "1" ] && [ -d /run/systemd/system ] && \
            command -v systemctl >/dev/null 2>&1 && \
            [ "$SYSTEMD_DIR" = "/etc/systemd/system" ]; then
        say APPLY "systemctl daemon-reload + enable/restart lidaldi-sync"
        systemctl daemon-reload
        systemctl enable lidaldi-sync >/dev/null 2>&1 || true
        systemctl restart lidaldi-sync
    else
        say SKIP "systemd restart (not root, systemd not running, or non-standard SYSTEMD_DIR); unit installed but not (re)started"
    fi
fi

say DONE "applied ${#PLAN_DESCS[@]} action(s); backup at $BACKUP"
ui_summary "✔ Applied ${#PLAN_DESCS[@]} action(s) in $(ui_elapsed)" \
    "backup   $BACKUP"
