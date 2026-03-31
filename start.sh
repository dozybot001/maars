#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"

OS_NAME="$(uname -s)"
SERVER_PID=""
BROWSER_PID_FILE="/tmp/maars_browser_$$.pid"
BROWSER_PROFILE_DIR="$(mktemp -d /tmp/maars-browser-XXXXXX 2>/dev/null || true)"
LOG_FILE="$(mktemp /tmp/maars-start-log-XXXXXX 2>/dev/null || mktemp -t maars-start-log)"
LOG_KEEP=0
ACTIVE_LABEL=""

# Clean up old MAARS log files from previous runs
find /tmp -maxdepth 1 -name 'maars-start-log-*' -not -name "$(basename "$LOG_FILE")" -mmin +10 -delete 2>/dev/null || true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

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

pause_if_windows() {
    if is_windows && [ -t 0 ]; then
        printf '\nPress Enter to close...'
        read -r _ || true
    fi
}

append_log() {
    printf '%s\n' "$*" >>"$LOG_FILE"
}

print_logo() {
    printf '\n'
    printf '  %b\n' "${CYAN}${BOLD}███╗   ███╗  █████╗   █████╗  ██████╗  ███████╗${NC}"
    printf '  %b\n' "${CYAN}${BOLD}████╗ ████║ ██╔══██╗ ██╔══██╗ ██╔══██╗ ██╔════╝${NC}"
    printf '  %b\n' "${CYAN}${BOLD}██╔████╔██║ ███████║ ███████║ ██████╔╝ ███████╗${NC}"
    printf '  %b\n' "${CYAN}${BOLD}██║╚██╔╝██║ ██╔══██║ ██╔══██║ ██╔══██╗ ╚════██║${NC}"
    printf '  %b\n' "${CYAN}${BOLD}██║ ╚═╝ ██║ ██║  ██║ ██║  ██║ ██║  ██║ ███████║${NC}"
    printf '  %b\n' "${CYAN}${BOLD}╚═╝     ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚══════╝${NC}"
    printf '  %b\n' "${DIM}Multi-Agent Automated Research System${NC}"
    printf '\n'
    printf '  %b\n' "${BOLD}Checklist${NC}"
}

print_group() {
    printf '\n'
    printf '  %b\n' "${CYAN}${BOLD}$1${NC}"
}

print_check() {
    local status="$1" label="$2" hint="$3"
    local icon color label_style hint_style
    status="${status//$'\r'/}"

    case "$status" in
        ok)
            icon="[PASS]"
            color="$GREEN"
            hint_style="${DIM}"
            ;;
        warn)
            icon="[WARN]"
            color="$YELLOW"
            hint_style="${YELLOW}"
            ;;
        fail)
            icon="[FAIL]"
            color="$RED"
            hint_style="${RED}"
            ;;
        *)
            icon="[INFO]"
            color="$DIM"
            hint_style="${DIM}"
            ;;
    esac

    label_style="${BOLD}"
    printf '  %b %b: %b\n' "${color}${icon}${NC}" "${label_style}${label}${NC}" "${hint_style}${hint}${NC}"
}

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
    trap - EXIT
    close_managed_browser
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill -TERM "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    if [ "$LOG_KEEP" -eq 0 ]; then
        rm -f "$LOG_FILE"
    fi
}
trap cleanup EXIT

fail_startup() {
    local label="$1" hint="$2"
    LOG_KEEP=1
    print_check "fail" "$label" "$hint"
    printf '\n  %b\n' "${DIM}Detailed log: ${LOG_FILE}${NC}"
    pause_if_windows
    exit 1
}

on_error() {
    local exit_code="${1:-1}" line="${2:-unknown}" cmd="${3:-unknown}"
    trap - ERR
    append_log "Unexpected error at line ${line}"
    append_log "Command: ${cmd}"
    fail_startup "${ACTIVE_LABEL:-Startup}" "Unexpected script error"
}
trap 'on_error $? ${LINENO} "$BASH_COMMAND"' ERR

on_interrupt() {
    trap - INT TERM
    append_log "Interrupted by user"
    if [ "$SERVER_STARTED" -eq 1 ]; then
        LOG_KEEP=0
        printf '\n  %b\n' "${GREEN}[PASS]${NC} MAARS stopped"
    else
        LOG_KEEP=1
        printf '\n  %b\n' "${YELLOW}[WARN]${NC} Startup interrupted"
        printf '  %b\n' "${DIM}Detailed log: ${LOG_FILE}${NC}"
    fi
    exit 130
}
trap on_interrupt INT TERM

bootstrap_python() {
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

check_python_version() {
    bootstrap_python -c '
import sys
major, minor = sys.version_info[:2]
if (major, minor) < (3, 10):
    raise SystemExit(1)
print(f"Python {major}.{minor}.{sys.version_info[2]}")
'
}

resolve_bin() {
    type -P "$1" 2>/dev/null || true
}

read_env_value() {
    local key="$1"
    [ -f .env ] || return 1
    awk -F= -v target="$key" '
        $1 == target {
            value = substr($0, index($0, "=") + 1)
            sub(/\r$/, "", value)
            print value
            found = 1
            exit
        }
        END {
            if (!found) exit 1
        }
    ' .env
}

docker_install_url() {
    if is_windows || [ "$OS_NAME" = "Darwin" ]; then
        printf '%s' "https://www.docker.com/products/docker-desktop/"
    else
        printf '%s' "https://docs.docker.com/engine/install/"
    fi
}

check_results_dir() {
    local test_dir="results" test_file=""
    mkdir -p "$test_dir"
    test_file="$test_dir/.start-write-test-$$"
    : > "$test_file"
    rm -f "$test_file"
}

check_results_session_root() {
    local session_dir="results/.start-session-test-$$"
    mkdir -p "$session_dir/tasks" "$session_dir/artifacts"
    : > "$session_dir/meta.json"
    rm -rf "$session_dir"
}

check_disk_space() {
    local dir="$1" min_mb="${2:-512}"
    local probe="$dir/.disk_probe_$$"
    # Write a small file to verify disk is writable and not full
    if dd if=/dev/zero of="$probe" bs=1M count=1 >/dev/null 2>&1; then
        rm -f "$probe"
        printf 'ok\tDisk writable'
    else
        rm -f "$probe"
        printf 'fail\tDisk may be full or read-only'
        return 1
    fi
}

check_llm_connectivity() {
    "$PYTHON" -c '
import sys
from backend.config import settings

provider = settings.model_provider
api_key = settings.active_api_key
model = settings.active_model

if not api_key:
    print("fail\tNo API key to test")
    sys.exit(0)

try:
    if provider == "google":
        from google import genai
        client = genai.Client(api_key=api_key)
        client.models.get(model=f"models/{model}")
    elif provider == "openai":
        import urllib.request, json
        req = urllib.request.Request(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}")
    elif provider == "anthropic":
        import urllib.request, json
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            method="POST",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            data=json.dumps({"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}).encode(),
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    else:
        print(f"warn\tUnknown provider: {provider}")
        sys.exit(0)
    print(f"ok\t{provider} API reachable ({model})")
except Exception as exc:
    msg = str(exc)[:80]
    print(f"fail\t{provider}: {msg}")
'
}

check_docker_orphans() {
    local containers=""
    containers="$(docker ps -q --filter "ancestor=$DOCKER_IMAGE" 2>/dev/null || true)"
    if [ -n "$containers" ]; then
        local count
        count="$(echo "$containers" | wc -l | tr -d ' ')"
        printf '%s' "$count"
        return 1
    fi
    return 0
}

clean_docker_orphans() {
    docker ps -q --filter "ancestor=$DOCKER_IMAGE" 2>/dev/null | xargs -r docker rm -f >/dev/null 2>&1 || true
}

check_sandbox_image_age() {
    local dockerfile="Dockerfile.sandbox"
    [ -f "$dockerfile" ] || return 1

    local dockerfile_ts="" image_ts=""

    if is_windows && command -v powershell.exe >/dev/null 2>&1; then
        dockerfile_ts="$(powershell.exe -NoProfile -Command "(Get-Item '$dockerfile').LastWriteTimeUtc.ToString('yyyyMMddHHmmss')" 2>/dev/null | tr -d '\r')" || true
        image_ts="$(docker inspect --format '{{.Created}}' "$DOCKER_IMAGE" 2>/dev/null | head -c19 | tr -d 'T:-' | tr -d ' ')" || true
    elif command -v stat >/dev/null 2>&1; then
        if [ "$OS_NAME" = "Darwin" ]; then
            dockerfile_ts="$(stat -f '%Sm' -t '%Y%m%d%H%M%S' "$dockerfile" 2>/dev/null)" || true
        else
            dockerfile_ts="$(stat -c '%Y' "$dockerfile" 2>/dev/null)" || true
        fi
        image_ts="$(docker inspect --format '{{.Metadata.LastTagTime}}' "$DOCKER_IMAGE" 2>/dev/null)" || true
        if [ -z "$image_ts" ] || [ "$image_ts" = "0001-01-01 00:00:00 +0000 UTC" ]; then
            image_ts="$(docker inspect --format '{{.Created}}' "$DOCKER_IMAGE" 2>/dev/null)" || true
        fi
        image_ts="$(date -d "$image_ts" '+%s' 2>/dev/null)" || true
    fi

    if [ -z "$dockerfile_ts" ] || [ -z "$image_ts" ]; then
        return 1
    fi

    [ "$dockerfile_ts" -gt "$image_ts" ] 2>/dev/null
}

check_docker_memory_format() {
    "$PYTHON" -c '
import re, sys
from backend.config import settings
mem = settings.docker_sandbox_memory
if re.fullmatch(r"\d+[bkmg]", mem, re.IGNORECASE):
    print(f"ok\t{mem}")
else:
    print(f"fail\tMARS_DOCKER_SANDBOX_MEMORY=\"{mem}\" is invalid (expected e.g. 4g, 512m)")
'
}

check_frontend_dist_integrity() {
    local index="$1"
    if [ ! -s "$index" ]; then
        return 1
    fi
    grep -q '<div id="app"' "$index" 2>/dev/null || grep -q '<script' "$index" 2>/dev/null
}

probe_runtime_settings() {
    "$PYTHON" -c '
from backend.config import settings

allowed = {"google", "anthropic", "openai"}
invalid = []
scopes = [("global", settings.model_provider, settings.active_model, settings.active_api_key)]

if settings.model_provider not in allowed:
    invalid.append(f"MAARS_MODEL_PROVIDER={settings.model_provider!r} is invalid")

for stage in ("refine", "research", "write"):
    override = getattr(settings, f"{stage}_provider", "")
    if override and override not in allowed:
        invalid.append(f"MAARS_{stage.upper()}_PROVIDER={override!r} is invalid")
    scopes.append((stage, *settings.stage_config(stage)))

missing_key_providers = sorted({provider for _, provider, _, api_key in scopes if provider and not api_key})
missing_models = [scope for scope, _, model, _ in scopes if not model]

if invalid:
    model_status = "fail"
    model_hint = "; ".join(invalid)
elif missing_key_providers or missing_models:
    model_status = "fail"
    parts = []
    if missing_key_providers:
        parts.append("Missing API key for " + ", ".join(missing_key_providers))
    if missing_models:
        parts.append("No model resolved for " + ", ".join(missing_models))
    model_hint = "; ".join(parts)
else:
    model_status = "ok"
    parts = [f"{settings.model_provider}:{settings.active_model}"]
    overrides = [(s, p, m) for s, p, m, _ in scopes[1:] if getattr(settings, f"{s}_provider", "")]
    for s, p, m in overrides:
        parts.append(f"{s}={p}:{m}")
    model_hint = ", ".join(parts)

sanity_issues = []
if settings.research_max_iterations < 1:
    sanity_issues.append("MAARS_RESEARCH_MAX_ITERATIONS must be >= 1")
if settings.docker_sandbox_timeout < 1:
    sanity_issues.append("MAARS_DOCKER_SANDBOX_TIMEOUT must be >= 1")
if settings.docker_sandbox_cpu <= 0:
    sanity_issues.append("MAARS_DOCKER_SANDBOX_CPU must be > 0")
if settings.docker_sandbox_concurrency < 1:
    sanity_issues.append("MAARS_DOCKER_SANDBOX_CONCURRENCY must be >= 1")

if sanity_issues:
    config_sanity_status = "fail"
    config_sanity_hint = "; ".join(sanity_issues)
else:
    config_sanity_status = "ok"
    config_sanity_hint = (
        f"iterations={settings.research_max_iterations}, "
        f"timeout={settings.docker_sandbox_timeout}s, "
        f"cpu={settings.docker_sandbox_cpu}, "
        f"concurrency={settings.docker_sandbox_concurrency}"
    )

from pathlib import Path
kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
if settings.kaggle_api_token:
    kaggle_status = "ok"
    kaggle_hint = "Using MAARS_KAGGLE_API_TOKEN"
elif kaggle_json.exists():
    kaggle_status = "ok"
    kaggle_hint = f"Using {kaggle_json}"
else:
    kaggle_status = "warn"
    kaggle_hint = "Kaggle not configured; set MAARS_KAGGLE_API_TOKEN or ~/.kaggle/kaggle.json if needed"

print(f"MODEL_STATUS\t{model_status}")
print(f"MODEL_HINT\t{model_hint}")
print(f"CONFIG_SANITY_STATUS\t{config_sanity_status}")
print(f"CONFIG_SANITY_HINT\t{config_sanity_hint}")
print(f"KAGGLE_STATUS\t{kaggle_status}")
print(f"KAGGLE_HINT\t{kaggle_hint}")
docker_image = settings.docker_sandbox_image or "maars-sandbox:latest"
print(f"DOCKER_IMAGE\t{docker_image}")

import re
mem = settings.docker_sandbox_memory
if re.fullmatch(r"\d+[bkmg]", mem, re.IGNORECASE):
    mem_status = "ok"
    mem_hint = f"memory={mem}"
else:
    mem_status = "fail"
    mem_hint = f"MAARS_DOCKER_SANDBOX_MEMORY=\"{mem}\" is invalid (expected e.g. 4g, 512m)"
print(f"DOCKER_MEM_STATUS\t{mem_status}")
print(f"DOCKER_MEM_HINT\t{mem_hint}")
'
}

port_in_use() {
    local port="${1:-8000}"

    if is_windows && command -v powershell.exe >/dev/null 2>&1; then
        powershell.exe -NoProfile -Command "\$ErrorActionPreference='SilentlyContinue'; \$connections = Get-NetTCPConnection -LocalPort $port -State Listen; if (\$connections) { exit 0 } else { exit 1 }" >/dev/null 2>&1
    elif command -v lsof >/dev/null 2>&1; then
        lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
    elif command -v fuser >/dev/null 2>&1; then
        fuser "$port"/tcp >/dev/null 2>&1
    else
        return 1
    fi
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
        if ! port_in_use "$port"; then
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

wait_for_server_ready() {
    local port="${1:-8000}"
    local attempts=0

    while [ "$attempts" -lt 120 ]; do
        if [ -n "$SERVER_PID" ] && ! kill -0 "$SERVER_PID" 2>/dev/null; then
            return 1
        fi

        if (echo > "/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
            return 0
        fi

        sleep 0.25
        attempts=$((attempts + 1))
    done

    return 1
}

run_logged_task() {
    "$@" >>"$LOG_FILE" 2>&1
}

create_venv() {
    bootstrap_python -m venv .venv
}

install_deps() {
    "$PYTHON" -m pip install -r requirements.txt -q
}

build_frontend() {
    (
        cd frontend
        "$NPM_BIN" install --silent
        "$NPM_BIN" run build
    )
}

build_sandbox() {
    docker build -f Dockerfile.sandbox -t "$DOCKER_IMAGE" .
}

check_backend_import() {
    "$PYTHON" -c "from backend.main import app; print(app.title)"
}

check_api_health() {
    API_KEY="${API_KEY_VALUE:-}" "$PYTHON" - "http://127.0.0.1:8000/api/pipeline/status" <<'PY'
import json
import os
import sys
import urllib.request

req = urllib.request.Request(sys.argv[1])
api_key = os.environ.get("API_KEY", "")
if api_key:
    req.add_header("Authorization", f"Bearer {api_key}")

with urllib.request.urlopen(req, timeout=5) as resp:
    data = json.load(resp)
    if resp.status != 200 or "stages" not in data:
        raise SystemExit(1)

print("GET /api/pipeline/status returned 200")
PY
}

check_sse_events() {
    API_KEY="${API_KEY_VALUE:-}" "$PYTHON" - "http://127.0.0.1:8000/api/events" <<'PY'
import os
import sys
import urllib.request

req = urllib.request.Request(sys.argv[1])
api_key = os.environ.get("API_KEY", "")
if api_key:
    req.add_header("Authorization", f"Bearer {api_key}")

with urllib.request.urlopen(req, timeout=5) as resp:
    content_type = (resp.headers.get("Content-Type") or "").lower()
    if resp.status != 200 or "text/event-stream" not in content_type:
        raise SystemExit(1)

print("GET /api/events returned text/event-stream")
PY
}

check_docker_api() {
    API_KEY="${API_KEY_VALUE:-}" "$PYTHON" - "http://127.0.0.1:8000/api/docker/status" <<'PY'
import json
import os
import sys
import urllib.request

req = urllib.request.Request(sys.argv[1])
api_key = os.environ.get("API_KEY", "")
if api_key:
    req.add_header("Authorization", f"Bearer {api_key}")

with urllib.request.urlopen(req, timeout=5) as resp:
    data = json.load(resp)
    if resp.status != 200:
        raise SystemExit(1)

if not data.get("connected"):
    raise SystemExit(1)

print("GET /api/docker/status reported connected")
PY
}

check_sessions_api() {
    API_KEY="${API_KEY_VALUE:-}" "$PYTHON" - "http://127.0.0.1:8000/api/sessions" <<'PY'
import json
import os
import sys
import urllib.request

req = urllib.request.Request(sys.argv[1])
api_key = os.environ.get("API_KEY", "")
if api_key:
    req.add_header("Authorization", f"Bearer {api_key}")

with urllib.request.urlopen(req, timeout=5) as resp:
    data = json.load(resp)
    if resp.status != 200 or not isinstance(data, list):
        raise SystemExit(1)

print("GET /api/sessions returned 200")
PY
}

check_session_state() {
    API_KEY="${API_KEY_VALUE:-}" "$PYTHON" - "http://127.0.0.1:8000/api/sessions" <<'PY'
import json
import os
import sys
import urllib.parse
import urllib.request

base_url = sys.argv[1]
api_key = os.environ.get("API_KEY", "")

def request_json(url):
    req = urllib.request.Request(url)
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.load(resp)
        if resp.status != 200:
            raise SystemExit(1)
    return data

sessions = request_json(base_url)
if not isinstance(sessions, list):
    raise SystemExit(1)

if not sessions:
    print("No saved sessions to validate")
    raise SystemExit(10)

session_id = sessions[0]["id"]
state_url = f"{base_url}/{urllib.parse.quote(session_id)}/state"
state = request_json(state_url)
if not isinstance(state, dict):
    raise SystemExit(1)

print(f"GET /api/sessions/{session_id}/state returned 200")
PY
}

check_auth_middleware() {
    API_KEY="${API_KEY_VALUE:-}" "$PYTHON" - "http://127.0.0.1:8000/api/pipeline/status" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

url = sys.argv[1]
api_key = os.environ.get("API_KEY", "")

if not api_key:
    print("MAARS_ACCESS_TOKEN is not set; auth middleware is disabled by config")
    raise SystemExit(10)

unauth_req = urllib.request.Request(url)
try:
    urllib.request.urlopen(unauth_req, timeout=5)
    raise SystemExit(1)
except urllib.error.HTTPError as exc:
    if exc.code != 401:
        raise SystemExit(1)

auth_req = urllib.request.Request(url)
auth_req.add_header("Authorization", f"Bearer {api_key}")
with urllib.request.urlopen(auth_req, timeout=5) as resp:
    data = json.load(resp)
    if resp.status != 200 or "stages" not in data:
        raise SystemExit(1)

print("Unauthenticated /api returned 401; authenticated /api returned 200")
PY
}

launch_browser() {
    sleep 1

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
            local app_path="/Applications/$app.app/Contents/MacOS/$app"
            if [ -x "$app_path" ]; then
                "$app_path" "${browser_args[@]}" >/dev/null 2>&1 &
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

print_logo
append_log "MAARS startup started on $OS_NAME"
print_group "Environment"

PYTHON_READY=0
DEPS_READY=0
CONFIG_READY=0
MODEL_CONFIG_READY=0
FRONTEND_READY=0
BACKEND_IMPORT_READY=0
SERVER_STARTED=0
CONFIG_SANITY_STATUS="fail"
CONFIG_SANITY_HINT="Skipped because backend settings are unavailable"
KAGGLE_STATUS="warn"
KAGGLE_HINT="Kaggle status unknown"
DOCKER_IMAGE="$(read_env_value MAARS_DOCKER_SANDBOX_IMAGE 2>/dev/null || true)"
DOCKER_IMAGE="${DOCKER_IMAGE:-maars-sandbox:latest}"
DOCKER_MEM_STATUS="warn"
DOCKER_MEM_HINT="Docker memory config unknown"
API_KEY_VALUE=""

ACTIVE_LABEL="Python"
append_log "Checking Python"
if command -v python >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1 || command -v py >/dev/null 2>&1; then
    if PY_VER="$(check_python_version 2>>"$LOG_FILE")"; then
        PYTHON_READY=1
        append_log "Python version: $PY_VER"
        print_check "ok" "Python" "$PY_VER"
    else
        print_check "fail" "Python" "Python 3.10+ is required"
    fi
else
    print_check "fail" "Python" "Python 3.10+ is required"
fi

ACTIVE_LABEL="Dependencies"
append_log "Preparing virtual environment"
if [ "$PYTHON_READY" -ne 1 ]; then
    print_check "fail" "Dependencies" "Skipped because Python is unavailable"
else
    if [ ! -d .venv ]; then
        if run_logged_task create_venv; then
            append_log "Created .venv"
        else
            print_check "fail" "Dependencies" "Failed to create .venv"
        fi
    else
        append_log "Using existing .venv"
    fi

    if is_windows; then
        PYTHON="$PWD/.venv/Scripts/python.exe"
    else
        PYTHON="$PWD/.venv/bin/python"
    fi

    if [ ! -f "${PYTHON:-}" ]; then
        print_check "fail" "Dependencies" "Virtual environment Python not found"
    elif run_logged_task install_deps; then
        DEPS_READY=1
        print_check "ok" "Dependencies" "Python packages installed"
    else
        print_check "fail" "Dependencies" "Dependency install failed"
    fi
fi

ACTIVE_LABEL="Config File"
append_log "Checking configuration file"
ENV_CREATED=0
if [ -f .env ]; then
    CONFIG_READY=1
    print_check "ok" "Config File" ".env found"
elif cp .env.example .env >>"$LOG_FILE" 2>&1; then
    CONFIG_READY=1
    ENV_CREATED=1
    append_log "Created .env from .env.example"
    print_check "warn" "Config File" "Created .env from template"
else
    print_check "fail" "Config File" "Could not create .env from .env.example"
fi
API_KEY_VALUE="$(read_env_value MAARS_ACCESS_TOKEN 2>/dev/null || true)"

print_group "Configuration"

ACTIVE_LABEL="Model Config"
append_log "Validating runtime model configuration"
MODEL_STATUS="fail"
MODEL_HINT="Skipped because backend dependencies are unavailable"
if [ "$DEPS_READY" -eq 1 ] && [ "$CONFIG_READY" -eq 1 ]; then
    if SETTINGS_OUTPUT="$(probe_runtime_settings 2>>"$LOG_FILE")"; then
        MODEL_STATUS=""
        MODEL_HINT=""
        while IFS=$'\t' read -r key value; do
            key="${key//$'\r'/}"
            value="${value//$'\r'/}"
            case "$key" in
                MODEL_STATUS) MODEL_STATUS="$value" ;;
                MODEL_HINT) MODEL_HINT="$value" ;;
                CONFIG_SANITY_STATUS) CONFIG_SANITY_STATUS="$value" ;;
                CONFIG_SANITY_HINT) CONFIG_SANITY_HINT="$value" ;;
                KAGGLE_STATUS) KAGGLE_STATUS="$value" ;;
                KAGGLE_HINT) KAGGLE_HINT="$value" ;;
                DOCKER_IMAGE) DOCKER_IMAGE="$value" ;;
                DOCKER_MEM_STATUS) DOCKER_MEM_STATUS="$value" ;;
                DOCKER_MEM_HINT) DOCKER_MEM_HINT="$value" ;;
            esac
        done <<<"$SETTINGS_OUTPUT"
        append_log "Resolved docker image: ${DOCKER_IMAGE}"
        append_log "Model config status: ${MODEL_STATUS} (${MODEL_HINT})"
        [ "$MODEL_STATUS" != "fail" ] && MODEL_CONFIG_READY=1
        print_check "${MODEL_STATUS:-warn}" "Model Config" "${MODEL_HINT:-Could not resolve model configuration}"
    else
        print_check "fail" "Model Config" "Failed to load backend settings"
    fi
else
    print_check "fail" "Model Config" "$MODEL_HINT"
fi

ACTIVE_LABEL="LLM Connectivity"
append_log "Checking LLM API connectivity"
if [ "$MODEL_CONFIG_READY" -eq 1 ]; then
    if LLM_RESULT="$(check_llm_connectivity 2>>"$LOG_FILE")"; then
        LLM_RESULT="${LLM_RESULT//$'\r'/}"
        IFS=$'\t' read -r LLM_CONN_STATUS LLM_CONN_HINT <<<"$LLM_RESULT"
        print_check "$LLM_CONN_STATUS" "LLM Connectivity" "$LLM_CONN_HINT"
    else
        print_check "fail" "LLM Connectivity" "API connectivity check crashed"
    fi
else
    print_check "fail" "LLM Connectivity" "Skipped because model config is invalid"
fi

ACTIVE_LABEL="Config Sanity"
append_log "Validating numeric configuration"
print_check "${CONFIG_SANITY_STATUS:-fail}" "Config Sanity" "${CONFIG_SANITY_HINT:-Could not validate numeric configuration}"

ACTIVE_LABEL="Docker Memory"
append_log "Checking Docker memory format"
print_check "${DOCKER_MEM_STATUS:-warn}" "Docker Memory" "${DOCKER_MEM_HINT:-Docker memory config unknown}"

print_group "Infrastructure"

ACTIVE_LABEL="Frontend"
append_log "Checking frontend availability"
NODE_BIN="$(resolve_bin node)"
NPM_BIN="$(resolve_bin npm)"
FRONTEND_DIST_INDEX="frontend/dist/index.html"
if [ -n "$NODE_BIN" ] && [ -n "$NPM_BIN" ]; then
    NODE_VER="$("$NODE_BIN" --version 2>&1)"
    NODE_MAJOR="${NODE_VER#v}"
    NODE_MAJOR="${NODE_MAJOR%%.*}"
    append_log "Node version: $NODE_VER"
    if [[ "$NODE_MAJOR" =~ ^[0-9]+$ ]] && [ "$NODE_MAJOR" -ge 24 ]; then
        if run_logged_task build_frontend && [ -f "$FRONTEND_DIST_INDEX" ]; then
            FRONTEND_READY=1
            print_check "ok" "Frontend" "Built with Node ${NODE_VER}"
        elif [ -f "$FRONTEND_DIST_INDEX" ]; then
            FRONTEND_READY=1
            print_check "warn" "Frontend" "Build failed; using existing frontend/dist"
        else
            print_check "fail" "Frontend" "Frontend build failed and no frontend/dist fallback exists"
        fi
    elif [ -f "$FRONTEND_DIST_INDEX" ]; then
        FRONTEND_READY=1
        print_check "warn" "Frontend" "Node ${NODE_VER} is below >=24; using existing frontend/dist"
    else
        print_check "fail" "Frontend" "Node ${NODE_VER} is below >=24 and no frontend/dist fallback exists"
    fi
elif [ -f "$FRONTEND_DIST_INDEX" ]; then
    FRONTEND_READY=1
    print_check "warn" "Frontend" "Node.js not found; using existing frontend/dist"
else
    print_check "fail" "Frontend" "Node.js is missing and frontend/dist/index.html does not exist"
fi

ACTIVE_LABEL="Frontend Dist"
append_log "Checking frontend dist integrity"
if [ "$FRONTEND_READY" -eq 1 ]; then
    if check_frontend_dist_integrity "$FRONTEND_DIST_INDEX"; then
        print_check "ok" "Frontend Dist" "index.html contains expected markup"
    else
        FRONTEND_READY=0
        print_check "fail" "Frontend Dist" "index.html is empty or missing expected markup"
    fi
else
    print_check "fail" "Frontend Dist" "Skipped because frontend is unavailable"
fi

ACTIVE_LABEL="Disk Write"
append_log "Checking disk write"
if DISK_RESULT="$(check_disk_space "$(pwd)" 512)"; then
    IFS=$'\t' read -r DISK_STATUS DISK_HINT <<<"$DISK_RESULT"
    DISK_STATUS="${DISK_STATUS//$'\r'/}"
    DISK_HINT="${DISK_HINT//$'\r'/}"
    print_check "$DISK_STATUS" "Disk Write" "$DISK_HINT"
else
    IFS=$'\t' read -r DISK_STATUS DISK_HINT <<<"$DISK_RESULT"
    DISK_STATUS="${DISK_STATUS//$'\r'/}"
    DISK_HINT="${DISK_HINT//$'\r'/}"
    print_check "${DISK_STATUS:-fail}" "Disk Write" "${DISK_HINT:-Disk may be full or read-only}"
fi

ACTIVE_LABEL="Session Root"
append_log "Checking session root creation"
if run_logged_task check_results_session_root; then
    print_check "ok" "Session Root" "results/ can create a session workspace"
else
    print_check "fail" "Session Root" "results/ cannot create a session workspace"
fi

ACTIVE_LABEL="Docker Runtime"
append_log "Checking Docker"
if ! command -v docker >/dev/null 2>&1; then
    print_check "fail" "Docker Runtime" "Required for full MAARS runs: install Docker Desktop $(docker_install_url)"
elif ! docker info >/dev/null 2>&1; then
    print_check "fail" "Docker Runtime" "Required for full MAARS runs: start Docker Desktop, then rerun"
elif docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    append_log "Sandbox image already exists: ${DOCKER_IMAGE}"
    print_check "ok" "Docker Runtime" "Sandbox image ready (${DOCKER_IMAGE})"
elif run_logged_task build_sandbox; then
    print_check "ok" "Docker Runtime" "Sandbox image built (${DOCKER_IMAGE})"
else
    print_check "fail" "Docker Runtime" "Could not build sandbox image (${DOCKER_IMAGE})"
fi

ACTIVE_LABEL="Docker Orphans"
append_log "Checking orphaned sandbox containers"
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    if ORPHAN_COUNT="$(check_docker_orphans)"; then
        print_check "ok" "Docker Orphans" "No orphaned sandbox containers"
    else
        append_log "Found $ORPHAN_COUNT orphaned container(s), cleaning up"
        clean_docker_orphans
        print_check "warn" "Docker Orphans" "Cleaned up $ORPHAN_COUNT orphaned container(s)"
    fi
else
    print_check "warn" "Docker Orphans" "Skipped because Docker is unavailable"
fi

ACTIVE_LABEL="Docker Image Age"
append_log "Checking sandbox image freshness"
if command -v docker >/dev/null 2>&1 && docker image inspect "$DOCKER_IMAGE" >/dev/null 2>&1; then
    if check_sandbox_image_age 2>/dev/null; then
        append_log "Dockerfile.sandbox is newer than image; auto-rebuilding in background"
        docker build -f Dockerfile.sandbox -t "$DOCKER_IMAGE" . >>"$LOG_FILE" 2>&1 &
        print_check "ok" "Docker Image Age" "Rebuilding in background (pid $!)"
    else
        print_check "ok" "Docker Image Age" "Sandbox image is up to date"
    fi
else
    docker build -f Dockerfile.sandbox -t "${DOCKER_IMAGE:-maars-sandbox:latest}" . >>"$LOG_FILE" 2>&1 &
    print_check "ok" "Docker Image Age" "Building in background (pid $!)"
fi

print_group "Server"

ACTIVE_LABEL="Backend Import"
append_log "Importing backend app"
if [ "$DEPS_READY" -ne 1 ]; then
    print_check "fail" "Backend Import" "Skipped because dependencies are unavailable"
elif run_logged_task check_backend_import; then
    BACKEND_IMPORT_READY=1
    print_check "ok" "Backend Import" "backend.main imports cleanly"
else
    print_check "fail" "Backend Import" "backend.main failed to import"
fi

ACTIVE_LABEL="Server"
append_log "Starting server"
SERVER_BLOCKERS=()
if [ "$DEPS_READY" -ne 1 ]; then
    SERVER_BLOCKERS+=("Dependencies failed")
fi
if [ "$FRONTEND_READY" -ne 1 ]; then
    SERVER_BLOCKERS+=("Frontend is unavailable")
fi
if [ "$BACKEND_IMPORT_READY" -ne 1 ]; then
    SERVER_BLOCKERS+=("backend.main import failed")
fi
if [ "${#SERVER_BLOCKERS[@]}" -eq 0 ]; then
    if port_in_use 8000; then
        append_log "Port 8000 in use, freeing"
        free_server_port 8000
    fi
    append_log "Starting uvicorn on http://localhost:8000"
    set -m
    "$PYTHON" -m uvicorn backend.main:app --reload --reload-include "*.py" --reload-dir backend --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 8 --log-level warning >>"$LOG_FILE" 2>&1 &
    SERVER_PID=$!
    set +m

    if wait_for_server_ready 8000; then
        SERVER_STARTED=1
        launch_browser &
        print_check "ok" "Server" "Serving on http://localhost:8000"
    else
        if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
            kill -TERM "$SERVER_PID" 2>/dev/null || true
            wait "$SERVER_PID" 2>/dev/null || true
        fi
        SERVER_PID=""
        print_check "fail" "Server" "localhost:8000 did not become ready"
    fi
else
    SERVER_HINT=""
    for reason in "${SERVER_BLOCKERS[@]}"; do
        if [ -n "$SERVER_HINT" ]; then
            SERVER_HINT="${SERVER_HINT}; "
        fi
        SERVER_HINT="${SERVER_HINT}${reason}"
    done
    print_check "fail" "Server" "$SERVER_HINT"
fi

ACTIVE_LABEL="API Health"
append_log "Checking API health"
if [ "$SERVER_STARTED" -ne 1 ]; then
    print_check "fail" "API Health" "Skipped because the UI server did not start"
elif API_HEALTH_HINT="$(check_api_health 2>>"$LOG_FILE")"; then
    print_check "ok" "API Health" "$API_HEALTH_HINT"
else
    print_check "fail" "API Health" "GET /api/pipeline/status failed"
fi

ACTIVE_LABEL="SSE Events"
append_log "Checking SSE events"
if [ "$SERVER_STARTED" -ne 1 ]; then
    print_check "fail" "SSE Events" "Skipped because the UI server did not start"
elif SSE_HINT="$(check_sse_events 2>>"$LOG_FILE")"; then
    print_check "ok" "SSE Events" "$SSE_HINT"
else
    print_check "fail" "SSE Events" "GET /api/events did not return text/event-stream"
fi

ACTIVE_LABEL="Sessions API"
append_log "Checking sessions API"
if [ "$SERVER_STARTED" -ne 1 ]; then
    print_check "warn" "Sessions API" "Skipped because the UI server did not start"
elif SESSIONS_HINT="$(check_sessions_api 2>>"$LOG_FILE")"; then
    print_check "ok" "Sessions API" "$SESSIONS_HINT"
else
    print_check "warn" "Sessions API" "GET /api/sessions failed"
fi

ACTIVE_LABEL="Session State"
append_log "Checking session restore state"
if [ "$SERVER_STARTED" -ne 1 ]; then
    print_check "warn" "Session State" "Skipped because the UI server did not start"
elif SESSION_STATE_HINT="$(check_session_state 2>>"$LOG_FILE")"; then
    print_check "ok" "Session State" "$SESSION_STATE_HINT"
else
    SESSION_STATE_STATUS=$?
    if [ "$SESSION_STATE_STATUS" -eq 10 ]; then
        print_check "ok" "Session State" "No saved sessions to validate"
    else
        print_check "warn" "Session State" "A saved session could not be restored"
    fi
fi

ACTIVE_LABEL="Docker Backend"
append_log "Checking Docker API route"
if [ "$SERVER_STARTED" -ne 1 ]; then
    print_check "warn" "Docker Backend" "Skipped because the UI server did not start"
elif DOCKER_API_HINT="$(check_docker_api 2>>"$LOG_FILE")"; then
    print_check "ok" "Docker Backend" "$DOCKER_API_HINT"
else
    print_check "warn" "Docker Backend" "Backend Docker status check failed"
fi

print_group "Security"

ACTIVE_LABEL="Access Token"
append_log "Checking access token"
if [ -n "$API_KEY_VALUE" ]; then
    print_check "ok" "Access Token" "Set; enter it in the sidebar to authenticate"
else
    print_check "ok" "Access Token" "Not set; /api is open on localhost"
fi


print_group "Integrations"

ACTIVE_LABEL="Kaggle"
append_log "Checking Kaggle integration"
print_check "${KAGGLE_STATUS:-warn}" "Kaggle" "${KAGGLE_HINT:-Kaggle status unknown}"

printf '\n'
printf '  %b\n' "${DIM}Detailed log: ${LOG_FILE}${NC}"
LOG_KEEP=1

if [ "$SERVER_STARTED" -eq 1 ]; then
    printf '  %b\n' "${GREEN}${BOLD}MAARS UI is running on http://localhost:8000${NC}"
    LOG_KEEP=0
    if ! wait "$SERVER_PID"; then
        SERVER_STATUS=$?
        if [ "$SERVER_STATUS" -ne 130 ] && [ "$SERVER_STATUS" -ne 143 ]; then
            LOG_KEEP=1
            exit "$SERVER_STATUS"
        fi
    fi
else
    printf '  %b\n' "${YELLOW}${BOLD}MAARS UI was not started${NC}"
    pause_if_windows
    exit 1
fi
