#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

market_cloud=0
market_demo=0
for market_arg in "$@"; do
    case "$market_arg" in
        --cloud) market_cloud=1 ;;
        --demo) market_demo=1 ;;
        --help|-h)
            printf '%s\n' 'Usage: sh start.sh [--cloud] [--demo]' \
                'Local: 127.0.0.1:8000. --cloud: 0.0.0.0:8000 for CloudStudio preview.' \
                'Environment: PORT, MARKET_HOST, MARKET_PYTHON, MARKET_VENV, MARKET_DATA_DIR.' \
                'Demo accounts are only created with --demo. No default administrator.'
            exit 0 ;;
        *) printf 'Unknown option: %s\n' "$market_arg" >&2; exit 2 ;;
    esac
done

market_port=${PORT:-8000}
case "$market_port" in ''|*[!0-9]*) printf '%s\n' 'PORT must be a number from 1024 to 65535.' >&2; exit 2 ;; esac
if [ "${#market_port}" -gt 5 ] || [ "$market_port" -lt 1024 ] || [ "$market_port" -gt 65535 ]; then
    printf '%s\n' 'PORT must be a number from 1024 to 65535.' >&2; exit 2
fi
if [ "$market_cloud" = 1 ]; then
    market_host=${MARKET_HOST:-0.0.0.0}
    # CloudStudio publishes an HTTPS URL; no browser-side localhost address is needed.
    if [ -z "${MARKET_PUBLIC_ORIGIN:-}" ] && [ -n "${X_IDE_SPACE_KEY:-}" ] && [ -n "${X_IDE_SPACE_REGION:-}" ] && [ -n "${X_IDE_SPACE_HOST:-}" ]; then
        MARKET_PUBLIC_ORIGIN="https://${X_IDE_SPACE_KEY}--${market_port}.${X_IDE_SPACE_REGION}.${X_IDE_SPACE_HOST}"
        export MARKET_PUBLIC_ORIGIN
    fi
    COOKIE_SECURE=${COOKIE_SECURE:-1}
    export COOKIE_SECURE
else
    market_host=${MARKET_HOST:-127.0.0.1}
fi

market_python=${MARKET_PYTHON:-}
if [ -z "$market_python" ]; then
    for market_candidate in python3 python python3.12 python3.11; do
        if command -v "$market_candidate" >/dev/null 2>&1 && "$market_candidate" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 13) else 1)' 2>/dev/null; then
            market_python=$market_candidate
            break
        fi
    done
fi
if [ -z "$market_python" ] || ! "$market_python" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 13) else 1)'; then
    printf '%s\n' 'Python 3.11 or 3.12 is required. Select an installed version or set MARKET_PYTHON.' >&2
    exit 2
fi
market_version=$("$market_python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
market_env_path() {
    if [ -f "$1/bin/python" ]; then printf '%s/bin/python' "$1"; else printf '%s/Scripts/python.exe' "$1"; fi
}
market_env_usable() {
    market_check_python=$(market_env_path "$1")
    [ -f "$market_check_python" ] && \
        "$market_check_python" -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix and "%d.%d" % sys.version_info[:2] == sys.argv[1] else 1)' "$market_version" 2>/dev/null && \
        "$market_check_python" -m pip --version >/dev/null 2>&1
}
market_venv=${MARKET_VENV:-.venv}
if ! market_env_usable "$market_venv"; then
    # Preserve failed or incompatible environments; never delete a user's directory.
    if [ -e "$market_venv" ]; then
        if [ -n "${MARKET_VENV:-}" ]; then
            printf '%s\n' 'MARKET_VENV exists but is incomplete or incompatible. Choose a new MARKET_VENV directory.' >&2
            exit 2
        fi
        market_venv=".venv-$market_version"
        market_env_suffix=1
        while [ -e "$market_venv" ] && ! market_env_usable "$market_venv"; do
            market_env_suffix=$((market_env_suffix + 1))
            market_venv=".venv-$market_version-$market_env_suffix"
        done
        printf 'Existing .venv is incomplete or uses another Python; preserving it and using %s.\n' "$market_venv" >&2
    fi
    if ! market_env_usable "$market_venv"; then
        "$market_python" -m venv --without-pip "$market_venv"
        market_env_python=$(market_env_path "$market_venv")
        if ! "$market_env_python" -m ensurepip --upgrade >&2; then
            printf '%s\n' 'ensurepip is unavailable; trying the installed pip to bootstrap only the virtual environment.' >&2
            "$market_python" -m pip --python "$market_env_python" install pip >&2 || {
                printf '%s\n' 'Cannot bootstrap pip. Choose a Python with ensurepip, or install its python3-venv package.' >&2
                exit 2
            }
        fi
    fi
fi
market_env_python=$(market_env_path "$market_venv")
printf 'Using Python %s, virtual environment %s.\n' "$market_version" "$market_venv"
if [ "${MARKET_SKIP_INSTALL:-0}" != 1 ]; then
    "$market_env_python" -m pip install --disable-pip-version-check -r requirements.lock.txt
fi
if [ "$market_demo" = 1 ]; then "$market_env_python" -m backend.seed; fi
printf 'Xishi beta: listening on %s:%s (frontend and API share this port).\n' "$market_host" "$market_port"
if [ -n "${MARKET_PUBLIC_ORIGIN:-}" ]; then printf 'Preview URL: %s\n' "$MARKET_PUBLIC_ORIGIN"; fi
exec "$market_env_python" -m uvicorn backend.main:app --host "$market_host" --port "$market_port" --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
