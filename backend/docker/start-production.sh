#!/bin/sh
set -eu

GUNICORN_WORKERS="${GUNICORN_WORKERS:-1}"
GUNICORN_THREADS="${GUNICORN_THREADS:-2}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-300}"
GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-1000}"
GUNICORN_MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-100}"
GUNICORN_GRACEFUL_TIMEOUT="${GUNICORN_GRACEFUL_TIMEOUT:-30}"

require_positive_integer() {
    name="$1"
    value="$2"
    case "$value" in
        ""|*[!0-9]*)
            echo "$name must be a positive integer" >&2
            exit 64
            ;;
    esac
    if [ "$value" -lt 1 ]; then
        echo "$name must be a positive integer" >&2
        exit 64
    fi
}

require_nonnegative_integer() {
    name="$1"
    value="$2"
    case "$value" in
        ""|*[!0-9]*)
            echo "$name must be a non-negative integer" >&2
            exit 64
            ;;
    esac
}

require_positive_integer GUNICORN_WORKERS "$GUNICORN_WORKERS"
require_positive_integer GUNICORN_THREADS "$GUNICORN_THREADS"
require_positive_integer GUNICORN_TIMEOUT "$GUNICORN_TIMEOUT"
require_nonnegative_integer GUNICORN_MAX_REQUESTS "$GUNICORN_MAX_REQUESTS"
require_nonnegative_integer \
    GUNICORN_MAX_REQUESTS_JITTER \
    "$GUNICORN_MAX_REQUESTS_JITTER"
require_positive_integer GUNICORN_GRACEFUL_TIMEOUT "$GUNICORN_GRACEFUL_TIMEOUT"

exec gunicorn \
    --bind 0.0.0.0:8000 \
    -k uvicorn.workers.UvicornWorker \
    --workers "$GUNICORN_WORKERS" \
    --threads "$GUNICORN_THREADS" \
    --timeout "$GUNICORN_TIMEOUT" \
    --max-requests "$GUNICORN_MAX_REQUESTS" \
    --max-requests-jitter "$GUNICORN_MAX_REQUESTS_JITTER" \
    --graceful-timeout "$GUNICORN_GRACEFUL_TIMEOUT" \
    --access-logfile - \
    --error-logfile - \
    src.main:app
