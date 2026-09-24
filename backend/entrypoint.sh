#!/bin/sh
# Default API launcher: gunicorn bound to 0.0.0.0:${PORT:-8000} so the
# container honours a platform-provided $PORT (Compose, container PaaS,
# VPS). Compose overrides CMD for workers/beat/runserver — those bypass
# this script entirely; `docker run <image> <cmd>` runs <cmd> directly.
#
# --graceful-timeout: on SIGTERM gunicorn finishes in-flight requests for
# up to N seconds before force-killing (paired with compose
# stop_grace_period so the signal is actually delivered and honoured).
set -eu

PORT="${PORT:-8000}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-3}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
GUNICORN_GRACEFUL_TIMEOUT="${GUNICORN_GRACEFUL_TIMEOUT:-30}"

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${GUNICORN_WORKERS}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT}"
