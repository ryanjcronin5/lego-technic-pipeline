FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so code changes don't bust the layer cache.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install . && useradd --create-home app && mkdir -p /app/data && chown app /app/data

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["uvicorn", "technic.api:app", "--host", "0.0.0.0", "--port", "8000"]
