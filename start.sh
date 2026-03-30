#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

BROWSER_PID_FILE="/tmp/maars_browser_$$.pid"
BROWSER_PROFILE_DIR="$(mktemp -d /tmp/maars-browser-XXXXXX 2>/dev/null || true)"
OS_NAME="$(uname -s)"

close_managed_browser() {
    if [ -f "$BROWSER_PID_FILE" ]; then
        local browser_pid
        browser_pid="$(cat "$BROWSER_PID_FILE" 2>/dev/null || true)"
        if [ -n "$browser_pid" ]; then
            kill -TERM "$browser_pid" 2>/dev/null || true
        fi
        rm -f "$BROWSER_PID_FILE"
    fi
    if [ -n "$BROWSER_PROFILE_DIR" ] && [ -d "$BROWSER_PROFILE_DIR" ]; then
        rm -rf "$BROWSER_PROFILE_DIR" 2>/dev/null || true
    fi
}

cleanup() {
    if [ -n "$ORIGINAL_STTY" ]; then
        stty "$ORIGINAL_STTY" 2>/dev/null || true
    fi
    tput cnorm 2>/dev/null || true
    close_managed_browser
    if [ -n "$INSTALLER_PID" ] && kill -0 "$INSTALLER_PID" 2>/dev/null; then
        kill -TERM "$INSTALLER_PID" 2>/dev/null || true
        wait "$INSTALLER_PID" 2>/dev/null || true
    fi
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill -TERM "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    kill $(jobs -p) 2>/dev/null || true
    wait 2>/dev/null || true
    if [ -n "$EXIT_SUMMARY_MESSAGE" ]; then
        if [ "$EXIT_SUMMARY_STATUS" = "error" ]; then
            printf '%b\n' "${RED}${EXIT_SUMMARY_MESSAGE}${NC}"
        else
            printf '%b\n' "${DIM}${EXIT_SUMMARY_MESSAGE}${NC}"
        fi
    fi
}
trap cleanup EXIT

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

ARROW="${CYAN}>${NC}"
SPIN_CHARS='|/-\'
TOTAL_STEPS=6
STEP=0
CURRENT_STAGE="Preparing startup checks"
READY_URL=""
FOOTER_STATE="hidden"
FOOTER_DETAIL=""
FOOTER_PROMPT=""
INTERACTIVE_UI=0
ORIGINAL_STTY=""
SERVER_PID=""
INSTALLER_PID=""
STOP_REQUESTED=0
SERVER_SHUTDOWN_TIMEOUT=8
EXIT_SUMMARY_MESSAGE=""
EXIT_SUMMARY_STATUS="info"

if [ -t 1 ]; then
    INTERACTIVE_UI=1
fi

SUMMARY_LABELS=(
    "Python"
    "Dependencies"
    "API Key"
    "Frontend"
    "Docker Sandbox"
    "Server"
)

SUMMARY_STATUS=(
    "pending"
    "pending"
    "pending"
    "pending"
    "pending"
    "pending"
)

SUMMARY_NOTES=(
    "Waiting"
    "Waiting"
    "Waiting"
    "Waiting"
    "Waiting"
    "Waiting"
)

SUMMARY_ROWS=()
STAGE_ROW=0
URL_ROW=0
HINT_ROW=0
BOTTOM_ROW=0
UI_READY=0

is_windows() {
    case "$OS_NAME" in
        MINGW*|MSYS*|CYGWIN*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

run_bootstrap_python() {
    if command -v python3 >/dev/null 2>&1; then
        python3 "$@"
    elif command -v python >/dev/null 2>&1; then
        python "$@"
    elif command -v py >/dev/null 2>&1; then
        py -3 "$@"
    else
        return 127
    fi
}

cursor_to() {
    [ "$INTERACTIVE_UI" -eq 1 ] || return 0
    local row="$1" col="$2" zero_based_row=0
    if [ "$row" -gt 0 ]; then
        zero_based_row=$((row - 1))
    fi
    tput cup "$zero_based_row" "$col" 2>/dev/null || printf '\033[%s;%sH' "$row" "$((col + 1))"
}

clear_line_at() {
    [ "$INTERACTIVE_UI" -eq 1 ] || return 0
    cursor_to "$1" 0
    tput el 2>/dev/null || printf '\033[2K'
}

park_cursor() {
    [ "$INTERACTIVE_UI" -eq 1 ] || return 0
    cursor_to "$BOTTOM_ROW" 0
}

print_at() {
    local row="$1" text="$2"
    if [ "$INTERACTIVE_UI" -eq 1 ]; then
        clear_line_at "$row"
        cursor_to "$row" 0
        printf '%b' "$text"
        park_cursor
    else
        printf '%b\n' "$text"
    fi
}

trim_cell() {
    local text="$1" width="$2"
    if [ "${#text}" -gt "$width" ]; then
        printf "%-${width}s" "${text:0:$((width - 3))}..."
    else
        printf "%-${width}s" "$text"
    fi
}

supports_hyperlinks() {
    [ "$INTERACTIVE_UI" -eq 1 ] || return 1
    [ -n "${FORCE_HYPERLINKS:-}" ] && return 0
    [ "${TERM_PROGRAM:-}" = "iTerm.app" ] && return 0
    [ "${TERM_PROGRAM:-}" = "WezTerm" ] && return 0
    [ "${VTE_VERSION:-0}" -ge 5000 ] 2>/dev/null && return 0
    [ "${WT_SESSION:-}" != "" ] && return 0
    return 1
}

format_link() {
    local url="$1"
    if supports_hyperlinks; then
        printf '\033]8;;%s\a%s\033]8;;\a' "$url" "$url"
    else
        printf '%s' "$url"
    fi
}

format_status() {
    local status="$1" frame="${2:- }"
    case "$status" in
        ok)
            printf "%b" "${GREEN}$(printf '%-8s' 'Ready')${NC}"
            ;;
        warn)
            printf "%b" "${YELLOW}$(printf '%-8s' 'Warning')${NC}"
            ;;
        fail)
            printf "%b" "${RED}$(printf '%-8s' 'Failed')${NC}"
            ;;
        running)
            printf "%b" "${CYAN}$(printf '%-8s' "Busy ${frame}")${NC}"
            ;;
        *)
            printf "%b" "${DIM}$(printf '%-8s' 'Pending')${NC}"
            ;;
    esac
}

render_stage_line() {
    print_at "$STAGE_ROW" "  ${DIM}Step ${STEP}/${TOTAL_STEPS}${NC} ${ARROW} ${CURRENT_STAGE}"
}

render_summary_row() {
    local index="$1" frame="${2:- }"
    local label_cell note_cell status_cell

    label_cell="$(trim_cell "${SUMMARY_LABELS[$index]}" 16)"
    note_cell="$(trim_cell "${SUMMARY_NOTES[$index]}" 28)"
    status_cell="$(format_status "${SUMMARY_STATUS[$index]}" "$frame")"
    print_at "${SUMMARY_ROWS[$index]}" "  ${DIM}│${NC} ${label_cell} ${DIM}│${NC} ${status_cell} ${DIM}│${NC} ${note_cell} ${DIM}│${NC}"
}

render_footer_block() {
    if [ "$FOOTER_STATE" = "ready" ] && [ -n "$READY_URL" ]; then
        local ready_link
        ready_link="$(format_link "$READY_URL")"
        print_at "$URL_ROW" "  ${GREEN}${BOLD}MAARS is running${NC} ${DIM}The app window should open automatically.${NC}"
        print_at "$HINT_ROW" "  ${DIM}Press Ctrl+C to stop. Open manually if needed:${NC} ${CYAN}${BOLD}${ready_link}${NC}"
    elif [ "$FOOTER_STATE" = "stopping" ]; then
        print_at "$URL_ROW" "  ${YELLOW}${BOLD}Stopping MAARS...${NC}"
        print_at "$HINT_ROW" "  ${DIM}Closing the app window and waiting for active tasks to finish${NC}"
    elif [ "$FOOTER_STATE" = "done" ]; then
        print_at "$URL_ROW" "  ${GREEN}${BOLD}MAARS stopped${NC}"
        print_at "$HINT_ROW" "  ${DIM}Safe to run start.sh again${NC}"
    elif [ "$FOOTER_STATE" = "action" ]; then
        print_at "$URL_ROW" "  ${YELLOW}${BOLD}Docker Desktop is required${NC} ${DIM}${FOOTER_DETAIL}${NC}"
        print_at "$HINT_ROW" "  ${CYAN}${BOLD}${FOOTER_PROMPT}${NC}"
    elif [ "$INTERACTIVE_UI" -eq 1 ]; then
        clear_line_at "$URL_ROW"
        clear_line_at "$HINT_ROW"
        park_cursor
    fi
}

prepare_terminal() {
    if [ "$INTERACTIVE_UI" -eq 1 ]; then
        ORIGINAL_STTY="$(stty -g 2>/dev/null || true)"
        stty -echoctl 2>/dev/null || true
    fi
}

set_summary() {
    local label="$1" status="$2" note="$3"
    local i
    for i in "${!SUMMARY_LABELS[@]}"; do
        if [ "${SUMMARY_LABELS[$i]}" = "$label" ]; then
            SUMMARY_STATUS[$i]="$status"
            SUMMARY_NOTES[$i]="$note"
            if [ "$UI_READY" -eq 1 ]; then
                render_summary_row "$i"
            fi
            return 0
        fi
    done
}

set_step() {
    STEP=$((STEP + 1))
    CURRENT_STAGE="$1"
    if [ "$UI_READY" -eq 1 ]; then
        render_stage_line
    fi
}

run_with_spinner() {
    local label="$1" running_note="$2" success_note="$3"
    shift 3

    local row_index=-1 pid frame_index=0 frame
    local i
    for i in "${!SUMMARY_LABELS[@]}"; do
        if [ "${SUMMARY_LABELS[$i]}" = "$label" ]; then
            row_index="$i"
            break
        fi
    done

    set_summary "$label" "running" "$running_note"
    tput civis 2>/dev/null || true
    "$@" &
    pid=$!

    while kill -0 "$pid" 2>/dev/null; do
        frame="${SPIN_CHARS:frame_index%${#SPIN_CHARS}:1}"
        if [ "$UI_READY" -eq 1 ] && [ "$row_index" -ge 0 ]; then
            render_summary_row "$row_index" "$frame"
        fi
        frame_index=$((frame_index + 1))
        sleep 0.08
    done

    if wait "$pid"; then
        tput cnorm 2>/dev/null || true
        set_summary "$label" "ok" "$success_note"
        return 0
    fi

    tput cnorm 2>/dev/null || true
    return 1
}

fail_and_exit() {
    local label="$1" note="$2"
    set_summary "$label" "fail" "$note"
    CURRENT_STAGE="Startup aborted"
    if [ -z "$EXIT_SUMMARY_MESSAGE" ]; then
        EXIT_SUMMARY_MESSAGE="$label: $note"
    fi
    EXIT_SUMMARY_STATUS="error"
    if [ "$UI_READY" -eq 1 ]; then
        render_stage_line
    fi
    exit 1
}

wait_for_server_shutdown() {
    local attempts=0
    local max_attempts=$((SERVER_SHUTDOWN_TIMEOUT * 10 + 20))
    while [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; do
        if [ "$attempts" -ge "$max_attempts" ]; then
            kill -KILL "$SERVER_PID" 2>/dev/null || true
            break
        fi
        sleep 0.1
        attempts=$((attempts + 1))
    done
    wait "$SERVER_PID" 2>/dev/null || true
}

handle_interrupt() {
    STOP_REQUESTED=1
    CURRENT_STAGE="Stopping server"
    READY_URL=""
    FOOTER_STATE="stopping"
    if [ "$UI_READY" -eq 1 ]; then
        set_summary "Server" "warn" "Stopping..."
        render_stage_line
        render_footer_block
    fi
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill -TERM "$SERVER_PID" 2>/dev/null || true
        wait_for_server_shutdown
    fi
    CURRENT_STAGE="Shutdown complete"
    FOOTER_STATE="done"
    if [ "$UI_READY" -eq 1 ]; then
        set_summary "Server" "ok" "Stopped"
        render_stage_line
        render_footer_block
        cursor_to "$BOTTOM_ROW" 0
        printf '\n'
    fi
    exit 0
}

trap handle_interrupt INT TERM

create_venv() {
    run_bootstrap_python -m venv .venv >/dev/null 2>&1
}

install_deps() {
    "$PYTHON" -m pip install -r requirements.txt -q >/dev/null 2>&1
}

build_frontend() {
    cd frontend
    npm install --silent >/dev/null 2>&1
    npm run build >/dev/null 2>&1
}

build_sandbox() {
    docker build -f Dockerfile.sandbox -t maars-sandbox:latest . -q >/dev/null
}

free_server_port() {
    local port="${1:-8000}"
    local pids=""

    if is_windows && command -v powershell.exe >/dev/null 2>&1; then
        pids="$(powershell.exe -NoProfile -Command "\$ErrorActionPreference='SilentlyContinue'; \$connections = Get-NetTCPConnection -LocalPort $port -State Listen; if (\$connections) { \$connections | Select-Object -ExpandProperty OwningProcess -Unique }" | tr -d '\r' | xargs 2>/dev/null || true)"
    elif command -v lsof >/dev/null 2>&1; then
        pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' | xargs 2>/dev/null || true)"
    elif command -v fuser >/dev/null 2>&1; then
        pids="$(fuser "$port"/tcp 2>/dev/null | tr '\n' ' ' | xargs 2>/dev/null || true)"
    fi

    [ -n "$pids" ] || return 0

    if is_windows && command -v taskkill.exe >/dev/null 2>&1; then
        for pid in $pids; do
            taskkill.exe //PID "$pid" >/dev/null 2>&1 || true
        done
    else
        kill -TERM $pids 2>/dev/null || true
    fi

    local attempts=0
    while [ "$attempts" -lt 30 ]; do
        if is_windows && command -v powershell.exe >/dev/null 2>&1; then
            powershell.exe -NoProfile -Command "\$ErrorActionPreference='SilentlyContinue'; exit([int](Get-NetTCPConnection -LocalPort $port -State Listen | Measure-Object).Count -gt 0)" >/dev/null 2>&1 || return 0
        elif command -v lsof >/dev/null 2>&1; then
            lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 || return 0
        elif command -v fuser >/dev/null 2>&1; then
            fuser "$port"/tcp >/dev/null 2>&1 || return 0
        else
            return 0
        fi
        sleep 0.1
        attempts=$((attempts + 1))
    done

    if is_windows && command -v taskkill.exe >/dev/null 2>&1; then
        for pid in $pids; do
            taskkill.exe //F //T //PID "$pid" >/dev/null 2>&1 || true
        done
    else
        kill -KILL $pids 2>/dev/null || true
    fi
}

start_docker_service() {
    if docker info >/dev/null 2>&1; then
        return 0
    fi

    if is_windows && command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command "\$paths = @(\$env:ProgramFiles + '\\Docker\\Docker\\Docker Desktop.exe', \$env:LocalAppData + '\\Programs\\Docker\\Docker\\Docker Desktop.exe'); foreach (\$path in \$paths) { if (Test-Path \$path) { Start-Process -FilePath \$path | Out-Null; exit 0 } }; exit 1" >/dev/null 2>&1 || true
    elif [ "$OS_NAME" = "Darwin" ]; then
        open -gj -a "Docker Desktop" >/dev/null 2>&1 || open -gj -a "Docker" >/dev/null 2>&1 || true
    elif command -v systemctl >/dev/null 2>&1; then
        systemctl --user start docker-desktop >/dev/null 2>&1 || true
        systemctl start docker >/dev/null 2>&1 || true
    elif command -v service >/dev/null 2>&1; then
        service docker start >/dev/null 2>&1 || true
    fi
}

wait_for_docker() {
    local i
    for i in $(seq 1 60); do
        if docker info >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

docker_requirement_message() {
    if is_windows; then
        printf '%s' "Docker Desktop is required on Windows"
    elif [ "$OS_NAME" = "Darwin" ]; then
        printf '%s' "Docker is required. Run: bash scripts/install_docker_mac.sh"
    else
        printf '%s' "Docker CLI and daemon are required"
    fi
}

docker_install_note() {
    local percent="$1" message="$2"
    if [ -n "$percent" ]; then
        printf '%s (%s%%)' "$message" "$percent"
    else
        printf '%s' "$message"
    fi
}

prompt_and_run_docker_installer() {
    local installer_cmd="bash scripts/install_docker_mac.sh"
    local status_file="" log_file="" progress="" message="" detail_note="" installer_status=0

    if [ "$INTERACTIVE_UI" -eq 1 ]; then
        FOOTER_STATE="action"
        FOOTER_DETAIL="Press Enter to install Docker Desktop now, or Ctrl+C to cancel"
        FOOTER_PROMPT="$installer_cmd"
        render_footer_block
        cursor_to "$BOTTOM_ROW" 0
        IFS= read -r _ </dev/tty
        FOOTER_DETAIL=""
        FOOTER_PROMPT=""
        render_footer_block
    else
        echo
        echo "Docker Desktop is required on macOS."
        echo "$installer_cmd"
    fi

    status_file="$(mktemp /tmp/maars-docker-status-XXXXXX)"
    log_file="$(mktemp /tmp/maars-docker-install-log-XXXXXX)"
    set_summary "Docker Sandbox" "running" "Preparing installer"

    bash scripts/install_docker_mac.sh --quiet --status-file "$status_file" >"$log_file" 2>&1 &
    INSTALLER_PID=$!

    while kill -0 "$INSTALLER_PID" 2>/dev/null; do
        if [ -s "$status_file" ]; then
            IFS='|' read -r progress message <"$status_file" || true
            detail_note="$(docker_install_note "$progress" "$message")"
            set_summary "Docker Sandbox" "running" "$detail_note"
            if [ "$INTERACTIVE_UI" -eq 1 ]; then
                FOOTER_STATE="action"
                FOOTER_DETAIL="$message"
                FOOTER_PROMPT="Progress: ${progress}%"
                render_footer_block
            fi
        fi
        sleep 0.2
    done

    if ! wait "$INSTALLER_PID"; then
        installer_status=$?
    fi
    INSTALLER_PID=""

    if [ -s "$status_file" ]; then
        IFS='|' read -r progress message <"$status_file" || true
    fi

    if [ "$installer_status" -eq 0 ]; then
        set_summary "Docker Sandbox" "ok" "Docker Desktop ready"
        FOOTER_STATE="hidden"
        FOOTER_DETAIL=""
        FOOTER_PROMPT=""
        render_footer_block
        rm -f "$status_file" "$log_file"
        return 0
    fi

    set_summary "Docker Sandbox" "fail" "$(docker_install_note "$progress" "${message:-Docker install failed}")"
    if [ "$INTERACTIVE_UI" -eq 1 ]; then
        FOOTER_STATE="action"
        FOOTER_DETAIL="${message:-Docker install failed}"
        FOOTER_PROMPT="Log: $log_file"
        render_footer_block
    else
        echo "Docker install failed. Log: $log_file"
    fi
    EXIT_SUMMARY_MESSAGE="Docker install failed. Log: $log_file"
    EXIT_SUMMARY_STATUS="error"
    rm -f "$status_file"
    return 1
}

launch_browser() {
    sleep 2

    local browser_args=(
        "--app=http://localhost:8000"
        "--new-window"
        "--no-first-run"
        "--no-default-browser-check"
    )

    if [ -n "$BROWSER_PROFILE_DIR" ] && [ -d "$BROWSER_PROFILE_DIR" ]; then
        browser_args+=("--user-data-dir=$BROWSER_PROFILE_DIR")
    fi

    for cmd in google-chrome google-chrome-stable chromium microsoft-edge-stable; do
        if command -v "$cmd" >/dev/null 2>&1; then
            "$cmd" "${browser_args[@]}" >/dev/null 2>&1 &
            echo $! > "$BROWSER_PID_FILE"
            return 0
        fi
    done

    if [ "$OS_NAME" = "Darwin" ]; then
        for app in "Google Chrome" "Microsoft Edge" "Chromium"; do
            APP_PATH="/Applications/$app.app/Contents/MacOS/$app"
            if [ -x "$APP_PATH" ]; then
                "$APP_PATH" "${browser_args[@]}" >/dev/null 2>&1 &
                echo $! > "$BROWSER_PID_FILE"
                return 0
            fi
        done
    fi

    if is_windows && command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command "Start-Process 'http://localhost:8000'" >/dev/null 2>&1
        return 0
    fi

    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open http://localhost:8000 >/dev/null 2>&1
    elif command -v open >/dev/null 2>&1; then
        open http://localhost:8000 >/dev/null 2>&1
    fi
}

render_static_ui() {
    local row=0 i

    if [ "$INTERACTIVE_UI" -eq 1 ]; then
        printf '\033[H\033[J'
    fi

    print_line() {
        printf '%b\n' "$1"
        row=$((row + 1))
    }

    print_line ""
    print_line "  ${CYAN}${BOLD}███╗   ███╗  █████╗   █████╗  ██████╗  ███████╗${NC}"
    print_line "  ${CYAN}${BOLD}████╗ ████║ ██╔══██╗ ██╔══██╗ ██╔══██╗ ██╔════╝${NC}"
    print_line "  ${CYAN}${BOLD}██╔████╔██║ ███████║ ███████║ ██████╔╝ ███████╗${NC}"
    print_line "  ${CYAN}${BOLD}██║╚██╔╝██║ ██╔══██║ ██╔══██║ ██╔══██╗ ╚════██║${NC}"
    print_line "  ${CYAN}${BOLD}██║ ╚═╝ ██║ ██║  ██║ ██║  ██║ ██║  ██║ ███████║${NC}"
    print_line "  ${CYAN}${BOLD}╚═╝     ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚══════╝${NC}"
    print_line "  ${DIM}Multi-Agent Automated Research System${NC}"
    STAGE_ROW=$((row + 1))
    print_line "  ${DIM}Step ${STEP}/${TOTAL_STEPS}${NC} ${ARROW} ${CURRENT_STAGE}"
    print_line ""
    print_line "  ${DIM}┌──────────────────┬──────────┬──────────────────────────────┐${NC}"
    print_line "  ${DIM}│${NC} ${BOLD}Check${NC}            ${DIM}│${NC} ${BOLD}Status${NC}   ${DIM}│${NC} ${BOLD}Notes${NC}                        ${DIM}│${NC}"
    print_line "  ${DIM}├──────────────────┼──────────┼──────────────────────────────┤${NC}"
    for i in "${!SUMMARY_LABELS[@]}"; do
        SUMMARY_ROWS[$i]=$((row + 1))
        print_line ""
    done
    print_line "  ${DIM}└──────────────────┴──────────┴──────────────────────────────┘${NC}"
    print_line ""
    URL_ROW=$((row + 1))
    print_line ""
    HINT_ROW=$((row + 1))
    print_line ""
    BOTTOM_ROW=$((row + 1))
    print_line ""
    UI_READY=1

    render_stage_line
    for i in "${!SUMMARY_LABELS[@]}"; do
        render_summary_row "$i"
    done
    render_footer_block
}

render_static_ui
prepare_terminal

set_step "Checking Python"
if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1 && ! command -v py >/dev/null 2>&1; then
    fail_and_exit "Python" "Python 3.10+ is required"
fi
PY_VER="$(run_bootstrap_python --version 2>&1)"
set_summary "Python" "ok" "$PY_VER"

set_step "Preparing environment"
if [ ! -d .venv ]; then
    if ! run_with_spinner "Dependencies" "Creating virtual environment" "Virtual environment ready" create_venv; then
        fail_and_exit "Dependencies" "Failed to create .venv"
    fi
else
    set_summary "Dependencies" "running" "Using existing .venv"
fi

if is_windows; then
    PYTHON="$PWD/.venv/Scripts/python.exe"
else
    PYTHON="$PWD/.venv/bin/python"
fi

if [ ! -x "$PYTHON" ] && [ ! -f "$PYTHON" ]; then
    fail_and_exit "Dependencies" "Virtual environment Python not found"
fi

if ! run_with_spinner "Dependencies" "Installing Python packages" "Packages installed" install_deps; then
    fail_and_exit "Dependencies" "Dependency install failed"
fi

set_step "Checking configuration"
if [ ! -f .env ]; then
    cp .env.example .env
    set_summary "API Key" "warn" "Created .env from template"
else
    HAS_KEY=false
    grep -qE '^MAARS_GOOGLE_API_KEY=.+' .env 2>/dev/null && HAS_KEY=true
    grep -qE '^MAARS_OPENAI_API_KEY=.+' .env 2>/dev/null && HAS_KEY=true
    grep -qE '^MAARS_ANTHROPIC_API_KEY=.+' .env 2>/dev/null && HAS_KEY=true
    if [ "$HAS_KEY" = false ]; then
        set_summary "API Key" "warn" "No API key configured"
    else
        set_summary "API Key" "ok" "API key configured"
    fi
fi

set_step "Building frontend"
if command -v node >/dev/null 2>&1; then
    NODE_VER=$(node --version 2>&1)
    set_summary "Frontend" "running" "Node ${NODE_VER}"
    if ! run_with_spinner "Frontend" "Installing and building assets" "Frontend built" build_frontend; then
        fail_and_exit "Frontend" "Frontend build failed"
    fi
else
    set_summary "Frontend" "warn" "Node.js missing; using built assets"
fi

set_step "Checking Docker sandbox"
if ! command -v docker >/dev/null 2>&1; then
    if [ "$(uname)" = "Darwin" ] && [ -x "scripts/install_docker_mac.sh" ]; then
        set_summary "Docker Sandbox" "fail" "Installer ready below"
        prompt_and_run_docker_installer || fail_and_exit "Docker Sandbox" "Docker install failed"
    fi
fi

if ! command -v docker >/dev/null 2>&1; then
    fail_and_exit "Docker Sandbox" "$(docker_requirement_message)"
fi

if ! docker info >/dev/null 2>&1; then
    start_docker_service
    if ! run_with_spinner "Docker Sandbox" "Starting Docker daemon" "Docker daemon ready" wait_for_docker; then
        fail_and_exit "Docker Sandbox" "Docker did not become ready"
    fi
fi

if docker image inspect maars-sandbox:latest >/dev/null 2>&1; then
    set_summary "Docker Sandbox" "ok" "Sandbox image ready"
else
    if ! run_with_spinner "Docker Sandbox" "Building sandbox image" "Sandbox image built" build_sandbox; then
        fail_and_exit "Docker Sandbox" "Sandbox image build failed"
    fi
fi

set_step "Starting server"
set_summary "Server" "running" "Freeing port 8000"
free_server_port 8000
set_summary "Server" "ok" "Reloading on localhost:8000"
READY_URL="http://localhost:8000"
FOOTER_STATE="ready"
render_footer_block

launch_browser &

set -m
"$PYTHON" -m uvicorn backend.main:app --reload --reload-include "*.py" --reload-dir backend --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown "$SERVER_SHUTDOWN_TIMEOUT" --log-level warning &
SERVER_PID=$!
set +m

if ! wait "$SERVER_PID"; then
    SERVER_STATUS=$?
    if [ "$STOP_REQUESTED" -eq 0 ] && [ "$SERVER_STATUS" -ne 130 ] && [ "$SERVER_STATUS" -ne 143 ]; then
        EXIT_SUMMARY_MESSAGE="MAARS exited with status $SERVER_STATUS"
        EXIT_SUMMARY_STATUS="error"
        exit "$SERVER_STATUS"
    fi
fi
