#!/usr/bin/env bash
# Universal MAARS launcher: Linux, macOS, and Windows (Git Bash / MSYS2 / Cygwin).
# Windows: use Git Bash Here (not "Open with" → System32 bash.exe — that is WSL).
if [ -z "${BASH_VERSION:-}" ]; then
    printf '%s\n' "MAARS requires Bash. In the project folder use Git Bash Here, then: ./start.sh" >&2
    exit 1
fi
set -Eeuo pipefail
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_ROOT" || { printf '%s\n' "Cannot cd to script directory: $SCRIPT_ROOT" >&2; exit 1; }

OS_NAME="$(uname -s)"
case "$OS_NAME" in
    Darwin*) OS_KIND=darwin ;;
    MINGW*|MSYS*|CYGWIN*) OS_KIND=windowsish ;;
    *) OS_KIND=unix ;;
esac

# When Explorer opens this script in a throwaway Git Bash window, pause so errors are visible.
_pause_if_windows_explorer() {
    [ "$OS_KIND" = windowsish ] || return 0
    [ -t 0 ] && [ -t 1 ] || return 0
    case "${MAARS_PAUSE_ON_ERROR:-1}" in 0|false|FALSE|no|NO) return 0 ;; esac
    printf '\nPress Enter to close this window...\n' >&2
    read -r _ || true
}

SERVER_PID=""
SERVER_PORT="${MAARS_SERVER_PORT:-8000}"
# Set MAARS_AUTO_RELEASE_PORT=false to fail fast if :PORT is busy (no taskkill).
AUTO_RELEASE_PORT="${MAARS_AUTO_RELEASE_PORT:-true}"
LOG_FILE="$PWD/maars-start.log"
ACTIVE_LABEL=""
SERVER_STARTED=0

: >"$LOG_FILE"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

append_log() { printf '%s\n' "$*" >>"$LOG_FILE"; }

print_logo() {
    printf '\n'
    printf '  %b\n' "${CYAN}${BOLD}███╗   ███╗  █████╗   █████╗  ██████╗  ███████╗${NC}"
    printf '  %b\n' "${CYAN}${BOLD}████╗ ████║ ██╔══██╗ ██╔══██╗ ██╔══██╗ ██╔════╝${NC}"
    printf '  %b\n' "${CYAN}${BOLD}██╔████╔██║ ███████║ ███████║ ██████╔╝ ███████╗${NC}"
    printf '  %b\n' "${CYAN}${BOLD}██║╚██╔╝██║ ██╔══██║ ██╔══██║ ██╔══██╗ ╚════██║${NC}"
    printf '  %b\n' "${CYAN}${BOLD}██║ ╚═╝ ██║ ██║  ██║ ██║  ██║ ██║  ██║ ███████║${NC}"
    printf '  %b\n' "${CYAN}${BOLD}╚═╝     ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚══════╝${NC}"
    printf '  %b\n\n' "${DIM}Multi-Agent Automated Research System${NC}"
}

print_check() {
    local status="$1" label="$2" hint="$3"
    local icon color hint_style
    case "$status" in
        ok)   icon="[PASS]"; color="$GREEN";  hint_style="$DIM"    ;;
        warn) icon="[WARN]"; color="$YELLOW"; hint_style="$YELLOW" ;;
        fail) icon="[FAIL]"; color="$RED";    hint_style="$RED"    ;;
        *)    icon="[INFO]"; color="$DIM";    hint_style="$DIM"    ;;
    esac
    printf '  %b %b  %b\n' "${color}${icon}${NC}" "${BOLD}${label}${NC}" "${hint_style}${hint}${NC}"
}

cleanup() {
    trap - EXIT
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill -TERM "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

fail_startup() {
    print_check "fail" "$1" "$2"
    printf '\n  %b\n' "${DIM}Log: ${LOG_FILE}${NC}"
    printf '\n  %b\n' "${DIM}Tip: On Windows use Git Bash Here (avoid Open with → bash.exe from System32 — that is WSL).${NC}"
    _pause_if_windows_explorer
    exit 1
}

on_error() {
    trap - ERR
    append_log "Unexpected error at line ${2:-?}: ${3:-?}"
    fail_startup "${ACTIVE_LABEL:-Startup}" "Unexpected script error (see log)"
}
trap 'on_error $? ${LINENO} "$BASH_COMMAND"' ERR

on_interrupt() {
    trap - INT TERM
    if [ "$SERVER_STARTED" -eq 1 ]; then
        printf '\n  %b\n' "${GREEN}[PASS]${NC} MAARS stopped"
    else
        printf '\n  %b\n' "${YELLOW}[WARN]${NC} Startup interrupted"
        printf '  %b\n' "${DIM}Log: ${LOG_FILE}${NC}"
        _pause_if_windows_explorer
    fi
    exit 130
}
trap on_interrupt INT TERM

bootstrap_python() {
    if [ "$OS_KIND" = windowsish ] && command -v py >/dev/null 2>&1; then
        py -3 "$@"
        return $?
    fi
    if command -v python3 >/dev/null 2>&1; then python3 "$@"; return $?; fi
    if command -v python >/dev/null 2>&1; then python "$@"; return $?; fi
    return 127
}

check_python_version() {
    bootstrap_python -c '
import sys
v = sys.version_info
if (v.major, v.minor) < (3, 10): raise SystemExit(1)
print(f"Python {v.major}.{v.minor}.{v.micro}")
'
}

read_env_value() {
    [ -f .env ] || return 1
    awk -F= -v k="$1" \
        '$1==k {v=substr($0,index($0,"=")+1); sub(/\r$/,"",v); print v; found=1; exit}
         END   {if(!found) exit 1}' .env
}

run_logged() { "$@" >>"$LOG_FILE" 2>&1; }

port_in_use() {
    local port="${1:-$SERVER_PORT}"
    if command -v lsof >/dev/null 2>&1; then
        lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1 && return 0
        return 1
    fi
    if (echo >/dev/tcp/127.0.0.1/"$port") 2>/dev/null; then
        return 0
    fi
    if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 "$port" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

listen_pids_on_port() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' '
        return 0
    fi
    if [ "$OS_KIND" = windowsish ]; then
        local ps_out ns_out
        ps_out=""
        if command -v powershell.exe >/dev/null 2>&1; then
            ps_out="$(MSYS2_ARG_CONV_EXCL='*' powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
                "Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Where-Object { \$_.OwningProcess -gt 0 } | Select-Object -ExpandProperty OwningProcess -Unique" 2>/dev/null \
                | tr ' \r' '\n' | grep -E '^[0-9]+$' | grep -v '^0$' || true)"
        fi
        ns_out="$(MSYS2_ARG_CONV_EXCL='*' cmd.exe //c "netstat -ano" 2>/dev/null | tr -d '\r' | awk -v p="$port" \
            '$0 ~ /LISTENING/ && NF >= 5 && $2 ~ (":" p "$") {
                pid = $NF
                if (pid ~ /^[0-9]+$/ && (pid + 0) > 0) print pid
            }' || true)"
        printf '%s\n%s\n' "$ps_out" "$ns_out" | grep -E '^[0-9]+$' | sort -nu | tr '\n' ' '
        return 0
    fi
    if command -v fuser >/dev/null 2>&1; then
        fuser -n tcp "$port" 2>/dev/null | tr -cs '0-9\n' '\n' | grep -E '^[0-9]+$' | tr '\n' ' '
        return 0
    fi
    if command -v ss >/dev/null 2>&1; then
        ss -tlnp 2>/dev/null | sed -n "s/.*:${port} .*pid=\\([0-9]*\\).*/\\1/p" | tr '\n' ' '
        return 0
    fi
    printf ''
}

collect_descendants() {
    local pid="$1" child
    command -v pgrep >/dev/null 2>&1 || return 0
    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        collect_descendants "$child"
        printf '%s\n' "$child"
    done
}

kill_pid_tree() {
    local signal="$1"; shift
    local pid child targets=()
    for pid in "$@"; do
        [ -z "$pid" ] && continue
        while IFS= read -r child; do
            [ -n "$child" ] && targets+=("$child")
        done < <(collect_descendants "$pid")
        targets+=("$pid")
    done
    [ "${#targets[@]}" -eq 0 ] && return 0
    printf '%s\n' "${targets[@]}" | awk '!seen[$0]++' | xargs kill "-$signal" 2>/dev/null || true
}

auto_release_port() {
    local port="${1:-$SERVER_PORT}"
    local pids i new_pids round
    port_in_use "$port" || return 0

    case "$AUTO_RELEASE_PORT" in
        0|false|FALSE|no|NO)
            append_log "Port $port in use; auto-release disabled (MAARS_AUTO_RELEASE_PORT=$AUTO_RELEASE_PORT)"
            return 1
            ;;
    esac

    if command -v lsof >/dev/null 2>&1; then
        pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
        [ -z "$pids" ] && return 1
        kill_pid_tree TERM $pids
        append_log "Auto-releasing port $port: TERM sent to pid tree rooted at $pids"
        i=0
        while [ "$i" -lt 20 ] && port_in_use "$port"; do sleep 0.25; i=$((i + 1)); done
        if port_in_use "$port"; then
            pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
            [ -n "$pids" ] && kill_pid_tree KILL $pids
            append_log "Auto-releasing port $port: KILL sent to pid tree rooted at $pids"
            sleep 0.5
        fi
        ! port_in_use "$port"
        return
    fi

    if [ "$OS_KIND" = windowsish ]; then
        local tk_out sp_out ps_csv
        round=1
        while [ "$round" -le 2 ]; do
            port_in_use "$port" || return 0
            pids="$(listen_pids_on_port "$port" | xargs)"
            [ -z "$pids" ] && return 1
            append_log "Auto-releasing port $port (attempt $round/2): PIDs $pids"
            for i in $pids; do
                [ "${i:-0}" -eq 0 ] 2>/dev/null && continue
                tk_out="$(MSYS2_ARG_CONV_EXCL='*' taskkill.exe //PID "$i" //F //T 2>&1)" || true
                [ -n "$tk_out" ] && append_log "taskkill //PID $i: $tk_out"
            done
            ps_csv="$(printf '%s' "$pids" | tr ' ' ',')"
            sp_out="$(MSYS2_ARG_CONV_EXCL='*' powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
                "foreach (\$id in @($ps_csv)) { if (\$id -gt 0) { Stop-Process -Id \$id -Force -ErrorAction SilentlyContinue } }" 2>&1)" || true
            [ -n "$sp_out" ] && append_log "Stop-Process: $sp_out"
            i=0
            while [ "$i" -lt 12 ] && port_in_use "$port"; do sleep 0.25; i=$((i + 1)); done
            port_in_use "$port" || return 0
            new_pids="$(listen_pids_on_port "$port" | xargs)"
            if [ -n "$new_pids" ] && [ "$new_pids" = "$pids" ]; then
                append_log "Port $port: same PID(s) after kill ($pids) — not released (permissions, system process, or admin required). Use another port: MAARS_SERVER_PORT=8001"
                return 1
            fi
            round=$((round + 1))
        done
        ! port_in_use "$port"
        return
    fi

    if command -v fuser >/dev/null 2>&1; then
        append_log "Auto-releasing port $port via fuser"
        fuser -TERM -k -n tcp "$port" >/dev/null 2>&1 || true
        sleep 1
        fuser -KILL -k -n tcp "$port" >/dev/null 2>&1 || true
        sleep 0.5
        ! port_in_use "$port"
        return
    fi

    pids="$(listen_pids_on_port "$port" | xargs)"
    [ -z "$pids" ] && return 1
    kill_pid_tree TERM $pids
    append_log "Auto-releasing port $port: TERM sent to PIDs $pids"
    i=0
    while [ "$i" -lt 20 ] && port_in_use "$port"; do sleep 0.25; i=$((i + 1)); done
    if port_in_use "$port"; then
        pids="$(listen_pids_on_port "$port" | xargs)"
        if [ -n "$pids" ]; then
            kill_pid_tree KILL $pids
            sleep 0.5
        fi
    fi
    ! port_in_use "$port"
}

open_browser_url() {
    local url="$1"
    case "$OS_KIND" in
        darwin)
            ( sleep 1 && open "$url" >/dev/null 2>&1 ) &
            ;;
        windowsish)
            ( sleep 1 && start "" "$url" >/dev/null 2>&1 ) &
            ;;
        *)
            ( sleep 1 && { xdg-open "$url" 2>/dev/null || sensible-browser "$url" 2>/dev/null || true; } ) &
            ;;
    esac
}

wait_for_server() {
    local i=0
    while [ "$i" -lt 120 ]; do
        [ -n "$SERVER_PID" ] && ! kill -0 "$SERVER_PID" 2>/dev/null && return 1
        (echo > "/dev/tcp/127.0.0.1/$SERVER_PORT") 2>/dev/null && return 0
        sleep 0.25; i=$((i + 1))
    done
    return 1
}

sync_env_keys() {
    local missing=0
    while IFS='=' read -r key _; do
        [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
        key="$(echo "$key" | xargs)"
        [ -z "$key" ] && continue
        if ! grep -q "^${key}=" .env 2>/dev/null; then
            grep "^${key}=" .env.example >> .env 2>/dev/null || true
            missing=$((missing + 1))
        fi
    done < .env.example
    return "$missing"
}

# ===================================================================
command -v clear >/dev/null 2>&1 && clear || printf '\033[2J\033[H'
print_logo
append_log "MAARS startup on $OS_NAME ($(date))"

# Free SERVER_PORT first: fail fast before venv/pip/Docker/import if the port cannot be released.
ACTIVE_LABEL="Port"
PORT_BUSY_BEFORE=0
if port_in_use "$SERVER_PORT"; then
    PORT_BUSY_BEFORE=1
fi
if ! auto_release_port "$SERVER_PORT"; then
    fail_startup "Port" ":$SERVER_PORT in use (could not release — close the other process or set MAARS_SERVER_PORT)"
fi
if [ "$PORT_BUSY_BEFORE" -eq 1 ]; then
    print_check "warn" "Port" "Released previous listener on :$SERVER_PORT"
fi

PYTHON_READY=0
DEPS_READY=0
CONFIG_READY=0
DOCKER_AVAILABLE=0

printf '  %b\n' "${CYAN}${BOLD}Environment${NC}"

ACTIVE_LABEL="Python"
if PY_VER="$(check_python_version 2>>"$LOG_FILE")"; then
    PYTHON_READY=1
    print_check "ok" "Python" "$PY_VER"
else
    fail_startup "Python" "Python 3.10+ required"
fi

ACTIVE_LABEL="Dependencies"
if [ ! -d .venv ]; then
    run_logged bootstrap_python -m venv .venv
fi
if [ -f "$PWD/.venv/Scripts/python.exe" ]; then
    PYTHON="$PWD/.venv/Scripts/python"
elif [ -f "$PWD/.venv/bin/python" ]; then
    PYTHON="$PWD/.venv/bin/python"
else
    fail_startup "Dependencies" "venv Python not found"
fi
# Python 3.14+ venvs may omit pip; bootstrap it if missing.
if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
    run_logged "$PYTHON" -m ensurepip --upgrade || true
fi
STAMP="$PWD/.venv/.maars_deps_installed"
if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ]; then
    if run_logged "$PYTHON" -m pip install -r requirements.txt -q; then
        : >"$STAMP"
        DEPS_READY=1
        print_check "ok" "Dependencies" "Installed"
    else
        fail_startup "Dependencies" "pip install failed (see log)"
    fi
else
    DEPS_READY=1
    print_check "ok" "Dependencies" "Up to date"
fi

ACTIVE_LABEL="Config File"
if [ -f .env ]; then
    CONFIG_READY=1
    SYNCED="$(sync_env_keys 2>/dev/null; echo $?)"
    if [ "$SYNCED" -gt 0 ] 2>/dev/null; then
        print_check "warn" "Config File" ".env found — added $SYNCED missing key(s)"
    else
        print_check "ok" "Config File" ".env found"
    fi
elif cp .env.example .env 2>>"$LOG_FILE"; then
    CONFIG_READY=1
    print_check "warn" "Config File" "Created from .env.example — add your API key"
else
    fail_startup "Config File" "Cannot create .env"
fi

printf '\n  %b\n' "${CYAN}${BOLD}Configuration${NC}"

ACTIVE_LABEL="Google API Key"
GOOGLE_KEY="$(read_env_value MAARS_GOOGLE_API_KEY 2>/dev/null || true)"
GOOGLE_MODEL="$(read_env_value MAARS_GOOGLE_MODEL 2>/dev/null || echo 'gemini-3-flash-preview')"
if [ -z "$GOOGLE_KEY" ]; then
    print_check "fail" "Google API Key" "MAARS_GOOGLE_API_KEY is empty in .env"
elif API_OUT="$("$PYTHON" -c "
import urllib.request, urllib.error, json, sys
url = 'https://generativelanguage.googleapis.com/v1beta/models/${GOOGLE_MODEL}:generateContent?key=${GOOGLE_KEY}'
req = urllib.request.Request(url, data=json.dumps({'contents':[{'parts':[{'text':'hi'}]}]}).encode(), headers={'Content-Type':'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=10) as r: print('ok')
except urllib.error.HTTPError as e: print(f'fail\t{e.code} {e.reason}')
except Exception as e: print(f'warn\t{e}')
" 2>>"$LOG_FILE")"; then
    IFS=$'\t' read -r KEY_STATUS KEY_HINT <<< "$API_OUT"
    case "$KEY_STATUS" in
        ok)   print_check "ok"   "Google API Key" "Verified ($GOOGLE_MODEL)" ;;
        fail) print_check "fail" "Google API Key" "$KEY_HINT — check key or model name" ;;
        *)    print_check "warn" "Google API Key" "Set but unreachable — $KEY_HINT" ;;
    esac
else
    print_check "warn" "Google API Key" "Set but could not verify"
fi

ACTIVE_LABEL="Config Sanity"
if SANITY_OUT="$("$PYTHON" -c '
import re
from backend.config import settings as s
bad = []
if s.research_max_iterations < 1: bad.append("research_max_iterations < 1")
if s.docker_sandbox_timeout < 1:  bad.append("docker_sandbox_timeout < 1")
if s.agent_session_timeout_seconds() < s.docker_sandbox_timeout:
    bad.append("agent_session_timeout < docker_sandbox_timeout")
if s.docker_sandbox_cpu <= 0:     bad.append("docker_sandbox_cpu <= 0")
if not re.fullmatch(r"\d+[bkmg]", s.docker_sandbox_memory, re.I):
    bad.append(f"docker_sandbox_memory={s.docker_sandbox_memory!r} invalid")
if bad:
    print("fail\t" + "; ".join(bad))
else:
    print(f"ok\titerations={s.research_max_iterations}, sandbox={s.docker_sandbox_timeout}s, agent={s.agent_session_timeout_seconds()}s, memory={s.docker_sandbox_memory}")
' 2>>"$LOG_FILE")"; then
    IFS=$'\t' read -r S_STATUS S_HINT <<< "$SANITY_OUT"
    print_check "${S_STATUS:-warn}" "Config Sanity" "${S_HINT:-Could not validate}"
else
    print_check "warn" "Config Sanity" "Could not load settings"
fi

printf '\n  %b\n' "${CYAN}${BOLD}Infrastructure${NC}"

ACTIVE_LABEL="Frontend"
if [ -f frontend/dist/index.html ] && [ -s frontend/dist/index.html ]; then
    print_check "ok" "Frontend" "frontend/dist ready"
elif [ -f frontend/index.html ]; then
    print_check "ok" "Frontend" "frontend/index.html ready"
else
    print_check "fail" "Frontend" "No frontend files found"
fi

ACTIVE_LABEL="Docker"
DOCKER_IMAGE="$(read_env_value MAARS_DOCKER_SANDBOX_IMAGE 2>/dev/null || echo 'maars-sandbox:latest')"
if ! command -v docker >/dev/null 2>&1; then
    print_check "warn" "Docker" "Not installed — sandbox unavailable"
elif ! docker info >/dev/null 2>&1; then
    print_check "warn" "Docker" "Not running — start Docker Desktop"
else
    DOCKER_AVAILABLE=1
    if docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
        print_check "ok" "Docker" "Image ready ($DOCKER_IMAGE)"
    elif [ -f Dockerfile.sandbox ] && run_logged docker build -f Dockerfile.sandbox -t "$DOCKER_IMAGE" .; then
        print_check "ok" "Docker" "Image built ($DOCKER_IMAGE)"
    else
        print_check "warn" "Docker" "Image build failed (see log)"
    fi

    GPU_ENABLED="$(read_env_value MAARS_DOCKER_SANDBOX_GPU 2>/dev/null || echo 'false')"
    if [ "$GPU_ENABLED" = "true" ]; then
        if docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu24.04 nvidia-smi >/dev/null 2>&1; then
            print_check "ok" "GPU" "NVIDIA GPU available"
        else
            print_check "warn" "GPU" "GPU=true but nvidia-docker not working — will fall back to CPU"
        fi
    else
        print_check "info" "GPU" "Disabled (set MAARS_DOCKER_SANDBOX_GPU=true to enable)"
    fi
fi

printf '\n  %b\n' "${CYAN}${BOLD}Server${NC}"

ACTIVE_LABEL="Backend Import"
if run_logged "$PYTHON" -c "from backend.main import app; print(app.title)"; then
    print_check "ok" "Backend Import" "backend.main OK"
else
    fail_startup "Backend Import" "Import failed (see log)"
fi

ACTIVE_LABEL="Server"
append_log "Starting uvicorn on port $SERVER_PORT"
"$PYTHON" -m uvicorn backend.main:app \
    --reload --reload-include "*.py" --reload-dir backend \
    --host 0.0.0.0 --port "$SERVER_PORT" \
    --timeout-graceful-shutdown 3 \
    --log-level warning >>"$LOG_FILE" 2>&1 &
SERVER_PID=$!

if wait_for_server; then
    SERVER_STARTED=1
    open_browser_url "http://localhost:$SERVER_PORT"
    print_check "ok" "Server" "http://localhost:$SERVER_PORT"
else
    kill -TERM "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    SERVER_PID=""
    fail_startup "Server" "Did not become ready (see log)"
fi

printf '\n  %b\n' "${GREEN}${BOLD}MAARS is running — press Ctrl+C to stop${NC}"
printf '  %b\n\n' "${DIM}Log: ${LOG_FILE}${NC}"

# Git Bash / MSYS: `wait "$SERVER_PID"` often fails with "pid is not a child of this
# shell" (exit 127), which made this script exit immediately and the terminal vanish
# while uvicorn kept running. Block until the PID is gone, then best-effort reap.
while kill -0 "$SERVER_PID" 2>/dev/null; do
    sleep 1
done
STATUS=0
wait "$SERVER_PID" 2>/dev/null || STATUS=$?
# MSYS/Git Bash: wait on $! may return 127 even after the process has exited.
if [ "$STATUS" -eq 127 ] && [ "$OS_KIND" = windowsish ]; then
    STATUS=0
fi
if [ "$STATUS" -ne 0 ] && [ "$STATUS" -ne 130 ] && [ "$STATUS" -ne 143 ]; then
    _pause_if_windows_explorer
    exit "$STATUS"
fi
