#!/bin/bash
set -e

echo "Starting Celery worker..."
celery -A worker.celery_app.celery worker --loglevel=info &

echo "Starting health server on port $PORT..."
exec python health.py
