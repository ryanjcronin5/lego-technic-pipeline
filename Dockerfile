# ---- api: the app on its own (used by docker compose and CI) ----
FROM python:3.12-slim AS api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install . && useradd --create-home app && mkdir -p /app/data && chown app /app/data

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os, urllib.request as u; u.urlopen('http://localhost:%s/api/health' % os.getenv('PORT', '8000'))"

# Hosting platforms like Render choose the port and pass it in $PORT.
CMD ["sh", "-c", "exec uvicorn technic.api:app --host 0.0.0.0 --port ${PORT:-8000}"]

# ---- demo: the app with a fresh copy of the data built in (used by Render) ----
FROM api AS demo
# Cache key: Docker re-checks this remote file on every build, so the data
# step below re-runs whenever Rebrickable publishes new data.
ADD https://cdn.rebrickable.com/media/downloads/sets.csv.gz /tmp/rebrickable-sets.csv.gz
RUN technic-etl && rm -rf data/raw