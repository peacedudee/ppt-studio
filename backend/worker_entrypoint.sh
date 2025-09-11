#!/bin/bash
set -e

echo "DEBUG: Skipping Celery worker to test health server deployment..."
# celery -A worker.celery_app.celery worker --loglevel=info &

echo "Starting ONLY the health server on port $PORT..."
exec python health.py