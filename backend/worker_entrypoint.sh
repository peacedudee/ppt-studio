# #!/bin/bash
# set -e

# echo "Starting Celery worker..."
# celery -A worker.celery_app.celery worker --loglevel=info &

# echo "Starting health server on port $PORT..."
# exec python health.py

!/bin/bash
# Start Celery worker in the background
celery -A worker.celery_app.celery worker --loglevel=info &

# Start a dummy healthcheck server for Cloud Run
# IMPORTANT: use $PORT instead of hardcoding 8000
python -m http.server $PORT --bind 0.0.0.0
