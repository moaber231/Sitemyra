FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .


# Install the Chromium browser required by advanced DOM/screenshot/price monitors.
RUN playwright install --with-deps chromium

EXPOSE 8000

# Production serving: Gunicorn (3 sync workers, generous timeout for
# on-demand monitor checks triggered via the API). Overridden by
# docker-compose.yml for local development (runserver + live reload).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
