#!/bin/bash
set -e

echo "=== PPT Studio Worker Starting ==="
echo "Time: $(date)"
echo "Python version: $(python --version)"
echo "Current directory: $(pwd)"
echo "User: $(whoami)"

# Debug environment variables (don't print sensitive values)
echo "=== Environment Check ==="
echo "REDIS_URL: ${REDIS_URL:0:20}... (truncated)"
echo "GCS_BUCKET_NAME: $GCS_BUCKET_NAME"
echo "GOOGLE_API_KEY: ${GOOGLE_API_KEY:0:10}... (truncated)"
echo "PORT: $PORT"

# Test Python imports
echo "=== Testing Python Imports ==="
python -c "
import sys
import os

# Test critical imports
try:
    import celery
    print('✓ Celery import successful:', celery.__version__)
except ImportError as e:
    print('✗ Celery import failed:', e)
    sys.exit(1)

try:
    import redis
    print('✓ Redis import successful:', redis.__version__)
except ImportError as e:
    print('✗ Redis import failed:', e)
    sys.exit(1)

try:
    from google.cloud import storage
    print('✓ Google Cloud Storage import successful')
except ImportError as e:
    print('✗ GCS import failed:', e)
    sys.exit(1)

try:
    import google.generativeai as genai
    print('✓ Google AI import successful')
except ImportError as e:
    print('✗ Google AI import failed:', e)
    sys.exit(1)

try:
    from pptx import Presentation
    print('✓ python-pptx import successful')
except ImportError as e:
    print('✗ python-pptx import failed:', e)
    sys.exit(1)
"

# Test Redis connection
echo "=== Testing Redis Connection ==="
python -c "
import os
import redis
import sys

try:
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    print(f'Connecting to Redis: {redis_url[:30]}...')
    r = redis.from_url(redis_url, socket_connect_timeout=10, socket_timeout=10)
    r.ping()
    print('✓ Redis connection successful')
    
    # Test basic operations
    r.set('test_key', 'test_value', ex=30)
    result = r.get('test_key')
    print(f'✓ Redis read/write test successful: {result}')
    r.delete('test_key')
    
except Exception as e:
    print(f'✗ Redis connection failed: {e}')
    print('Redis URL format should be: redis://host:port/db')
    sys.exit(1)
"

# Test GCS connection
echo "=== Testing GCS Connection ==="
python -c "
import os
import sys
from google.cloud import storage

try:
    client = storage.Client()
    bucket_name = os.getenv('GCS_BUCKET_NAME')
    
    if not bucket_name:
        print('✗ GCS_BUCKET_NAME environment variable not set')
        sys.exit(1)
        
    print(f'Testing GCS bucket: {bucket_name}')
    bucket = client.bucket(bucket_name)
    
    # Test if bucket exists and is accessible
    if bucket.exists():
        print('✓ GCS bucket exists and is accessible')
        
        # Test write permissions by creating a test blob
        test_blob = bucket.blob('health-check/test.txt')
        test_blob.upload_from_string('test', content_type='text/plain')
        print('✓ GCS write permissions confirmed')
        
        # Clean up test blob
        test_blob.delete()
        print('✓ GCS delete permissions confirmed')
    else:
        print(f'✗ GCS bucket {bucket_name} does not exist or is not accessible')
        sys.exit(1)
        
except Exception as e:
    print(f'✗ GCS connection failed: {e}')
    print('Make sure GOOGLE_APPLICATION_CREDENTIALS is set or you are using default service account')
    sys.exit(1)
"

# Test Celery configuration
echo "=== Testing Celery Configuration ==="
python -c "
import os
import sys
from worker.celery_app import celery

try:
    print('✓ Celery app imported successfully')
    print(f'Broker URL: {celery.conf.broker_url[:30]}...')
    print(f'Result backend: {celery.conf.result_backend[:30]}...')
    
    # Test broker connection
    with celery.connection() as connection:
        connection.ensure_connection(max_retries=3)
    print('✓ Celery broker connection successful')
    
except Exception as e:
    print(f'✗ Celery configuration failed: {e}')
    sys.exit(1)
"

echo "=== All Tests Passed - Starting Services ==="

# Function to handle shutdown gracefully
shutdown_handler() {
    echo "=== Shutdown signal received ==="
    if [ ! -z \"$CELERY_PID\" ]; then
        echo "Stopping Celery worker (PID: $CELERY_PID)..."
        kill -TERM $CELERY_PID
        wait $CELERY_PID 2>/dev/null
        echo "Celery worker stopped"
    fi
    echo "=== Shutdown complete ==="
    exit 0
}

# Set up signal handlers
trap shutdown_handler SIGTERM SIGINT

# Start the Celery worker in the background
echo "Starting Celery worker..."
celery -A worker.celery_app.celery worker \
    --loglevel=info \
    --concurrency=1 \
    --max-tasks-per-child=10 \
    --max-memory-per-child=500000 &

# Store the PID of the Celery worker
CELERY_PID=$!
echo "Celery worker started with PID: $CELERY_PID"

# Give Celery a moment to start
sleep 5

# Check if Celery worker is still running
if ! kill -0 $CELERY_PID 2>/dev/null; then
    echo "✗ Celery worker failed to start"
    exit 1
fi

echo "Starting health check server on port $PORT..."

# Start the health check server in the foreground
exec python health.py