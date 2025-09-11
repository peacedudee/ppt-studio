#!/bin/bash
set -e

# Start Celery worker in background
celery -A worker.celery_app worker --loglevel=info &

# Start a minimal HTTP server for Cloud Run health checks
# (Cloud Run only needs a 200 OK on /)
exec uvicorn health:app --host 0.0.0.0 --port $PORT
