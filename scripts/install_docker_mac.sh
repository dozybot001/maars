#!/usr/bin/env bash
set -eEuo pipefail

STATUS_FILE=""
QUIET=0

while [ $# -gt 0 ]; do
    case "$1" in
        --status-file)
            STATUS_FILE="$2"
            shift 2
            ;;
        --quiet)
            QUIET=1
            shift
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

report() {
    local percent="$1" message="$2"
    if [ -n "$STATUS_FILE" ]; then
        printf '%s|%s\n' "$percent" "$message" > "$STATUS_FILE"
    fi
    if [ "$QUIET" -ne 1 ]; then
        echo "$message"
    fi
}

run_admin() {
    local command_string="$1"
    if [ "$QUIET" -eq 1 ] && command -v osascript >/dev/null 2>&1; then
        osascript - "$command_string" <<'APPLESCRIPT' >/dev/null
on run argv
    do shell script (item 1 of argv) with administrator privileges
end run
APPLESCRIPT
    else
        sudo /bin/sh -c "$command_string" >/dev/null
    fi
}

if [ "$(uname)" != "Darwin" ]; then
    report "0" "This installer is for macOS only"
    exit 1
fi

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    report "100" "Docker is already installed and running"
    exit 0
fi

ARCH="$(uname -m)"
case "$ARCH" in
    arm64)
        DMG_URL="https://desktop.docker.com/mac/main/arm64/Docker.dmg"
        ;;
    x86_64)
        DMG_URL="https://desktop.docker.com/mac/main/amd64/Docker.dmg"
        ;;
    *)
        report "0" "Unsupported macOS architecture: $ARCH"
        exit 1
        ;;
esac

WORKDIR="$(mktemp -d /tmp/maars-docker-install-XXXXXX)"
DMG_PATH="$WORKDIR/Docker.dmg"
MOUNT_POINT="/Volumes/Docker"

cleanup() {
    hdiutil detach "$MOUNT_POINT" -quiet >/dev/null 2>&1 || true
    rm -rf "$WORKDIR"
}
trap cleanup EXIT

trap 'report "100" "Docker Desktop install failed"' ERR

report "10" "Preparing Docker Desktop installer"
if command -v curl >/dev/null 2>&1; then
    report "25" "Downloading Docker Desktop"
    curl -L --fail --progress-bar -o "$DMG_PATH" "$DMG_URL" >/dev/null 2>&1
elif command -v wget >/dev/null 2>&1; then
    report "25" "Downloading Docker Desktop"
    wget -O "$DMG_PATH" "$DMG_URL" >/dev/null 2>&1
else
    report "100" "curl or wget is required to download Docker Desktop"
    exit 1
fi

report "55" "Mounting Docker Desktop installer"
hdiutil attach "$DMG_PATH" -nobrowse >/dev/null

report "70" "Installing Docker Desktop"
run_admin "\"/Volumes/Docker/Docker.app/Contents/MacOS/install\" --accept-license --user=\"$USER\""

report "85" "Starting Docker Desktop"
open -a /Applications/Docker.app >/dev/null 2>&1

report "92" "Waiting for Docker to become ready"
for i in $(seq 1 60); do
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        report "100" "Docker Desktop is ready"
        exit 0
    fi
    progress=$((92 + i / 8))
    report "$progress" "Waiting for Docker to become ready"
    sleep 1
done

report "100" "Docker Desktop was installed, but it is not ready yet"
exit 1
