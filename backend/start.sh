#!/bin/bash
set -e

echo "=== MSM_Pro Backend Boot ==="

echo "[1/2] Running Alembic migrations..."
alembic upgrade head

echo "[2/2] Starting supervisord (uvicorn + celery worker + celery beat)..."
# PORT é injetado pelo Railway; default 8000 para dev local
export PORT="${PORT:-8000}"
exec supervisord -c /etc/supervisor/conf.d/msm_pro.conf
