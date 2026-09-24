# ---------------------------------------------------------------------------
# Two targets from one file (docs/OPTIMIZATION-PLAN.md D1):
#
#   api     — gunicorn / Django / beat / http-worker image.
#             NO Playwright, NO Pillow, NO pixelmatch, NO Chromium.
#   browser — extends the same base with the Playwright package and
#             Chromium for the dedicated celery-browser-worker only.
#
# Build:
#   docker build --target api     -t sitemyra-api     ./backend
#   docker build --target browser -t sitemyra-browser ./backend
# ---------------------------------------------------------------------------

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

# Non-root runtime user shared by both targets. /app/storage pre-created
# with this owner so named-volume initialization keeps write access.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin apeiro \
    && mkdir -p /app/storage \
    && chown -R apeiro:apeiro /app

# Shared Python dependencies (API, http engine, Celery, billing, storage).
# Browser-only packages live in requirements-browser.txt (never here).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Target `api` — API + HTTP worker + beat. Chromium-free by construction:
# nothing below installs playwright/Pillow/pixelmatch, and .dockerignore
# keeps venvs, storage and .env out of COPY . .
# ---------------------------------------------------------------------------
FROM base AS api

COPY . .
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

USER apeiro

# entrypoint.sh execs gunicorn on 0.0.0.0:${PORT:-8000}. Compose
# overrides CMD for workers/beat/runserver (bypassing the script).
CMD ["/app/entrypoint.sh"]

# ---------------------------------------------------------------------------
# Target `browser` — API contents + Playwright pip package + Chromium.
# The expensive layers (browser pip deps + ~660 MB browser download) sit
# BEFORE `COPY . .` so ordinary code changes reuse them via layer cache.
# ---------------------------------------------------------------------------
FROM base AS browser

# Chromium is downloaded to, and launched from, this explicit path.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY requirements-browser.txt .
RUN pip install --no-cache-dir -r requirements-browser.txt \
    && playwright install --with-deps chromium \
    # Keep the image lean: apt lists + pip cache from install-deps.
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip \
    # Owned by the runtime user: Chromium must be able to (re)write its
    # browser state even though launch itself is non-root.
    && chown -R apeiro:apeiro /ms-playwright

COPY . .
RUN chmod +x /app/entrypoint.sh

USER apeiro

CMD ["/app/entrypoint.sh"]
