#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Start the Celery worker in the background. The '&' is crucial.
echo "Starting Celery worker process in the background..."
celery -A worker.celery_app.celery worker --loglevel=info &

# Start the health check server in the foreground.
# 'exec' replaces the shell process with the python process.
# This becomes the main process that Cloud Run monitors.
echo "Starting health check server on port $PORT..."
exec python health.py