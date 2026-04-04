#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")"

OS_NAME="$(uname -s)"
SERVER_PID=""
SERVER_PORT="${MAARS_SERVER_PORT:-8000}"
LOG_FILE="$(mktemp /tmp/maars-start-log-XXXXXX 2>/dev/null || mktemp -t maars-start-log)"
LOG_KEEP=0
ACTIVE_LABEL=""
SERVER_STARTED=0

find /tmp -maxdepth 1 -name 'maars-start-log-*' -not -name "$(basename "$LOG_FILE")" -mmin +10 -delete 2>/dev/null || true

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
    [ "$LOG_KEEP" -eq 0 ] && rm -f "$LOG_FILE"
}
trap cleanup EXIT

fail_startup() {
    LOG_KEEP=1
    print_check "fail" "$1" "$2"
    printf '\n  %b\n' "${DIM}Log: ${LOG_FILE}${NC}"
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
        LOG_KEEP=0
        printf '\n  %b\n' "${GREEN}[PASS]${NC} MAARS stopped"
    else
        LOG_KEEP=1
        printf '\n  %b\n' "${YELLOW}[WARN]${NC} Startup interrupted"
        printf '  %b\n' "${DIM}Log: ${LOG_FILE}${NC}"
    fi
    exit 130
}
trap on_interrupt INT TERM

bootstrap_python() {
    if command -v python3 >/dev/null 2>&1; then python3 "$@"
    elif command -v python >/dev/null 2>&1; then python "$@"
    else return 127; fi
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
        lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    else
        return 1
    fi
}

auto_release_port() {
    local port="${1:-$SERVER_PORT}"
    local pids
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    [ -z "$pids" ] && return 0
    # TERM first
    echo "$pids" | xargs kill -TERM 2>/dev/null || true
    append_log "Auto-releasing port $port: TERM sent to pids $pids"
    local i=0
    while [ "$i" -lt 20 ] && port_in_use "$port"; do sleep 0.25; i=$((i + 1)); done
    if port_in_use "$port"; then
        # KILL stragglers
        pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
        [ -n "$pids" ] && echo "$pids" | xargs kill -9 2>/dev/null || true
        append_log "Auto-releasing port $port: KILL sent"
        sleep 0.5
    fi
    ! port_in_use "$port"
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
clear
print_logo
append_log "MAARS startup on $OS_NAME ($(date))"

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
PYTHON="$PWD/.venv/bin/python"
[ ! -f "$PYTHON" ] && fail_startup "Dependencies" "venv Python not found"
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
if [ -n "$GOOGLE_KEY" ]; then
    print_check "ok" "Google API Key" "Set"
else
    print_check "fail" "Google API Key" "MAARS_GOOGLE_API_KEY is empty in .env"
fi

ACTIVE_LABEL="Config Sanity"
if SANITY_OUT="$("$PYTHON" -c '
import re
from backend.config import settings as s
bad = []
if s.research_max_iterations < 1: bad.append("research_max_iterations < 1")
if s.docker_sandbox_timeout < 1:  bad.append("docker_sandbox_timeout < 1")
if s.docker_sandbox_cpu <= 0:     bad.append("docker_sandbox_cpu <= 0")
if not re.fullmatch(r"\d+[bkmg]", s.docker_sandbox_memory, re.I):
    bad.append(f"docker_sandbox_memory={s.docker_sandbox_memory!r} invalid")
if bad:
    print("fail\t" + "; ".join(bad))
else:
    print(f"ok\titerations={s.research_max_iterations}, timeout={s.docker_sandbox_timeout}s, memory={s.docker_sandbox_memory}")
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
fi

printf '\n  %b\n' "${CYAN}${BOLD}Server${NC}"

ACTIVE_LABEL="Backend Import"
if run_logged "$PYTHON" -c "from backend.main import app; print(app.title)"; then
    print_check "ok" "Backend Import" "backend.main OK"
else
    fail_startup "Backend Import" "Import failed (see log)"
fi

ACTIVE_LABEL="Server"
if port_in_use "$SERVER_PORT"; then
    if auto_release_port "$SERVER_PORT"; then
        print_check "warn" "Port" "Released previous MAARS listener on :$SERVER_PORT"
    else
        fail_startup "Port" ":$SERVER_PORT in use"
    fi
fi

append_log "Starting uvicorn on port $SERVER_PORT"
"$PYTHON" -m uvicorn backend.main:app \
    --reload --reload-include "*.py" --reload-dir backend \
    --host 0.0.0.0 --port "$SERVER_PORT" \
    --timeout-graceful-shutdown 3 \
    --log-level warning >>"$LOG_FILE" 2>&1 &
SERVER_PID=$!

if wait_for_server; then
    SERVER_STARTED=1
    ( sleep 1 && open "http://localhost:$SERVER_PORT" 2>/dev/null ) &
    print_check "ok" "Server" "http://localhost:$SERVER_PORT"
else
    kill -TERM "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    SERVER_PID=""
    fail_startup "Server" "Did not become ready (see log)"
fi

printf '\n  %b\n' "${GREEN}${BOLD}MAARS is running — press Ctrl+C to stop${NC}"
printf '  %b\n\n' "${DIM}Log: ${LOG_FILE}${NC}"
LOG_KEEP=0

if ! wait "$SERVER_PID"; then
    STATUS=$?
    if [ "$STATUS" -ne 130 ] && [ "$STATUS" -ne 143 ]; then
        LOG_KEEP=1; exit "$STATUS"
    fi
fi
