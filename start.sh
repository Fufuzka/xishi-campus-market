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
    for market_candidate in python3.12 python3 python; do
        if command -v "$market_candidate" >/dev/null 2>&1 && "$market_candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' 2>/dev/null; then
            market_python=$market_candidate
            break
        fi
    done
fi
if [ -z "$market_python" ] || ! "$market_python" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'; then
    printf '%s\n' 'Python 3.12 is required. Select a Python 3.12 CloudStudio environment or set MARKET_PYTHON.' >&2
    exit 2
fi
market_venv=${MARKET_VENV:-.venv}
if [ ! -f "$market_venv/bin/python" ] && [ ! -f "$market_venv/Scripts/python.exe" ]; then
    "$market_python" -m venv "$market_venv"
fi
market_env_python="$market_venv/bin/python"
if [ ! -f "$market_env_python" ]; then market_env_python="$market_venv/Scripts/python.exe"; fi
if ! "$market_env_python" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'; then
    printf '%s\n' 'Existing virtual environment is not Python 3.12. Set MARKET_VENV to a new directory.' >&2
    exit 2
fi
if [ "${MARKET_SKIP_INSTALL:-0}" != 1 ]; then
    "$market_env_python" -m pip install --disable-pip-version-check -r requirements.lock.txt
fi
if [ "$market_demo" = 1 ]; then "$market_env_python" -m backend.seed; fi
printf 'Xishi beta: listening on %s:%s (frontend and API share this port).\n' "$market_host" "$market_port"
if [ -n "${MARKET_PUBLIC_ORIGIN:-}" ]; then printf 'Preview URL: %s\n' "$MARKET_PUBLIC_ORIGIN"; fi
exec "$market_env_python" -m uvicorn backend.main:app --host "$market_host" --port "$market_port" --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
