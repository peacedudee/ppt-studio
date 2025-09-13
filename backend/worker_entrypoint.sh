#!/bin/bash
set -Eeuo pipefail

echo "=== PPT Studio Worker Starting ==="
echo "PORT=${PORT:-8080}"

# Graceful shutdown
pids=()
cleanup() { for p in "${pids[@]}"; do kill -TERM "$p" 2>/dev/null || true; done; wait || true; }
trap cleanup SIGTERM SIGINT

# 1) Start health server ASAP (so Cloud Run sees $PORT)
python health.py &
pids+=($!)
echo "Health server PID=${pids[-1]}"

# 2) Start Celery worker (background)
celery -A worker.celery_app.celery worker \
  --loglevel=info --concurrency=1 \
  --max-tasks-per-child=10 --max-memory-per-child=500000 &
pids+=($!)
echo "Celery PID=${pids[-1]}"

# 3) Run diagnostics NON-FATAL (log only)
( set +e
  echo "=== Diagnostics (non-fatal) ==="
  python - <<'PY'
import os, sys, traceback
def tryrun(fn, name):
    try:
        fn(); print(f"✓ {name}")
    except Exception as e:
        print(f"! {name} failed: {e}\n{traceback.format_exc()}")
def check_imports():
    import celery, redis
    from google.cloud import storage
    from pptx import Presentation
def check_redis():
    import redis, os
    r = redis.from_url(os.getenv('REDIS_URL','redis://localhost:6379/0'), socket_connect_timeout=5, socket_timeout=5)
    r.ping()
def check_gcs():
    import os
    from google.cloud import storage
    bucket = os.getenv('GCS_BUCKET_NAME')
    if not bucket: raise RuntimeError("GCS_BUCKET_NAME not set")
    client = storage.Client(); b = client.bucket(bucket); b.exists()
tryrun(check_imports,"Imports")
tryrun(check_redis,"Redis connectivity")
tryrun(check_gcs,"GCS access")
PY
) &

# Keep the container alive
wait
