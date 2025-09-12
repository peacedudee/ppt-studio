#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Start the Celery worker in the background
celery -A worker.celery_app.celery worker --loglevel=info &

# Start the health check server in the foreground
# The 'exec' command replaces the shell process with the Python process.
exec python health.py