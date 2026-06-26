FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps for psycopg2 / asyncpg builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY tools ./tools
COPY alembic.ini .

# Non-root runtime user
RUN useradd --create-home --uid 10001 polyprov && chown -R polyprov:polyprov /app
USER polyprov

EXPOSE 8000

# Default command runs the combined plane; compose/k8s override POLYPROV_PLANE
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
