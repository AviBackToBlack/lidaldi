# shellcheck shell=bash
#
# Console output for deploy/update.sh (sourced, never executed).
#
# Plain mode prints exactly the historical "TOKEN  message" lines — the
# installer tests assert on them, and logs/pipes/cron stay greppable. Fancy
# mode (interactive UTF-8 terminal) adds colour, icons, section headers, a
# progress gauge and spinners. It changes how things are shown, never what
# is done.
#
# Selection: --plain  >  LIDALDI_FANCY=1  >  NO_COLOR  >  tty + UTF-8 + TERM

FANCY=0
UI_SECTION=0
UI_SECTIONS=0
UI_JOB=""
UI_T0=$SECONDS

ui_init() { # ui_init <plain-flag> <section-count>
    UI_SECTIONS="$2"
    if [ "$1" = "1" ]; then
        FANCY=0
    elif [ "${LIDALDI_FANCY:-}" = "1" ]; then
        FANCY=1
    elif [ -n "${NO_COLOR:-}" ]; then
        FANCY=0
    elif [ -t 1 ] && [ "${TERM:-dumb}" != "dumb" ]; then
        case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
            *UTF-8*|*utf-8*|*UTF8*|*utf8*) FANCY=1 ;;
        esac
    fi
    if [ "$FANCY" = "1" ]; then
        C_RESET=$'\e[0m' C_BOLD=$'\e[1m' C_DIM=$'\e[2m'
        C_RED=$'\e[31m' C_GREEN=$'\e[32m' C_YELLOW=$'\e[33m'
        C_BLUE=$'\e[34m' C_MAGENTA=$'\e[35m' C_CYAN=$'\e[36m'
    else
        C_RESET="" C_BOLD="" C_DIM="" C_RED="" C_GREEN="" C_YELLOW=""
        C_BLUE="" C_MAGENTA="" C_CYAN=""
    fi
}

_ui_repeat() { # _ui_repeat <count> <char>
    local s=""
    [ "$1" -gt 0 ] && printf -v s '%*s' "$1" ''
    printf '%s' "${s// /$2}"
}

# One status line. Plain: "%-5s %s" reproduces "OK    x", "PLAN  x",
# "APPLY x", "BACKUP x", "DRY-RUN x" exactly.
say() { # say <TOKEN> <message...>
    local token="$1" icon color
    shift
    if [ "$FANCY" != "1" ]; then
        printf '%-5s %s\n' "$token" "$*"
        return 0
    fi
    case "$token" in
        OK)      icon='✔' color="$C_GREEN" ;;
        PLAN)    icon='●' color="$C_YELLOW" ;;
        DIFF)    icon='±' color="$C_CYAN" ;;
        APPLY)   icon='▶' color="$C_BLUE" ;;
        WARN)    icon='⚠' color="$C_YELLOW$C_BOLD" ;;
        SKIP)    icon='↷' color="$C_DIM" ;;
        ERROR)   icon='✖' color="$C_RED$C_BOLD" ;;
        BACKUP)  icon='⛁' color="$C_MAGENTA" ;;
        DRY-RUN) icon='◌' color="$C_CYAN$C_BOLD" ;;
        NOOP|DONE) icon='✔' color="$C_GREEN$C_BOLD" ;;
        *)       icon='·' color="" ;;
    esac
    printf '  %s%s %-7s%s %s\n' "$color" "$icon" "$token" "$C_RESET" "$*"
}

# Indented detail line under a status line ("  - x" in plain mode).
say_item() { # say_item <text>
    if [ "$FANCY" = "1" ]; then
        printf '      %s•%s %s\n' "$C_DIM" "$C_RESET" "$1"
    else
        printf '  - %s\n' "$1"
    fi
}

# Filter for diff output: plain passes it through untouched.
ui_diff() {
    if [ "$FANCY" != "1" ]; then
        cat
        return 0
    fi
    local line
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            '+++'*|'---'*) printf '      %s%s%s\n' "$C_BOLD" "$line" "$C_RESET" ;;
            '+'*) printf '      %s%s%s\n' "$C_GREEN" "$line" "$C_RESET" ;;
            '-'*) printf '      %s%s%s\n' "$C_RED" "$line" "$C_RESET" ;;
            '@@'*) printf '      %s%s%s\n' "$C_CYAN" "$line" "$C_RESET" ;;
            *) printf '      %s%s%s\n' "$C_DIM" "$line" "$C_RESET" ;;
        esac
    done
}

_ui_box() { # _ui_box <colour> <bold-first-line:0|1> <line...>
    local colour="$1" bold_first="$2" width=62 line pad first=1
    shift 2
    printf '\n  %s╭%s╮%s\n' "$colour" "$(_ui_repeat "$width" '─')" "$C_RESET"
    for line in "$@"; do
        if [ "${#line}" -gt $((width - 3)) ]; then line="${line:0:$((width - 4))}…"; fi
        pad=$((width - 2 - ${#line}))
        if [ "$first" = "1" ] && [ "$bold_first" = "1" ]; then
            line="$C_BOLD$line$C_RESET"
        fi
        first=0
        printf '  %s│%s  %s%*s%s│%s\n' "$colour" "$C_RESET" "$line" "$pad" '' "$colour" "$C_RESET"
    done
    printf '  %s╰%s╯%s\n' "$colour" "$(_ui_repeat "$width" '─')" "$C_RESET"
}

ui_banner() { # ui_banner <title> <line...>
    [ "$FANCY" = "1" ] || return 0
    _ui_box "$C_CYAN" 1 "$@"
}

ui_section() { # ui_section <title>
    [ "$FANCY" = "1" ] || return 0
    UI_SECTION=$((UI_SECTION + 1))
    local head="$UI_SECTION/$UI_SECTIONS  $1"
    printf '\n  %s%s◆ %s%s %s%s%s\n' "$C_BOLD" "$C_CYAN" "$head" "$C_RESET" \
        "$C_DIM" "$(_ui_repeat $((56 - ${#head})) '─')" "$C_RESET"
}

ui_phase() { # ui_phase <title>  (big divider between plan and apply)
    [ "$FANCY" = "1" ] || return 0
    printf '\n  %s%s━━ %s %s%s\n' "$C_BOLD" "$C_MAGENTA" "$1" \
        "$(_ui_repeat $((58 - ${#1})) '━')" "$C_RESET"
}

# "APPLY desc" in plain mode; a progress gauge + description in fancy mode.
ui_apply() { # ui_apply <index-0-based> <total> <description>
    if [ "$FANCY" != "1" ]; then
        say APPLY "$3"
        return 0
    fi
    local width=20 filled
    filled=$(( ($1 + 1) * width / $2 ))
    printf '  %s▕%s%s%s%s▏%s %s%d/%d%s %s▶%s %s\n' \
        "$C_BLUE" "$(_ui_repeat "$filled" '█')" "$C_DIM" \
        "$(_ui_repeat $((width - filled)) '░')" "$C_BLUE" "$C_RESET" \
        "$C_BOLD" $(($1 + 1)) "$2" "$C_RESET" "$C_BLUE" "$C_RESET" "$3"
}

# Run a slow command. Plain: inline, output streams as before. Fancy: a
# spinner with elapsed time; output goes to a log whose tail is shown only
# on failure. Call it as a plain statement (not in && / ||) so set -e still
# applies inside the command.
ui_run() { # ui_run <label> <command...>
    if [ "$FANCY" != "1" ]; then
        shift
        "$@"
        return
    fi
    local label="$1" log="$TMP_DIR/ui-run.log" t0=$SECONDS rc=0 i=0
    local -a frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    shift
    ( "$@" ) >"$log" 2>&1 &
    UI_JOB=$!
    while kill -0 "$UI_JOB" 2>/dev/null; do
        printf '\r      %s%s%s %s %s%ds%s\e[K' "$C_CYAN" "${frames[i % 10]}" \
            "$C_RESET" "$label" "$C_DIM" $((SECONDS - t0)) "$C_RESET"
        i=$((i + 1))
        sleep 0.1
    done
    wait "$UI_JOB" || rc=$?
    UI_JOB=""
    printf '\r\e[K'
    if [ "$rc" = "0" ]; then
        printf '      %s✔ done in %ds%s\n' "$C_GREEN" $((SECONDS - t0)) "$C_RESET"
    else
        printf '      %s✖ failed (exit %d) after %ds — last output:%s\n' \
            "$C_RED$C_BOLD" "$rc" $((SECONDS - t0)) "$C_RESET"
        tail -n 25 "$log" | sed "s/^/        ${C_DIM}│${C_RESET} /"
    fi
    return "$rc"
}

ui_interrupt() {
    if [ -n "$UI_JOB" ]; then
        kill "$UI_JOB" 2>/dev/null || true
        printf '\r\e[K'
    fi
    printf '%s\n' "ERROR interrupted" >&2
    exit 130
}

ui_summary() { # ui_summary <line...>
    [ "$FANCY" = "1" ] || return 0
    _ui_box "$C_GREEN" 1 "$@"
    printf '\n'
}

ui_elapsed() { printf '%ds' $((SECONDS - UI_T0)); }
