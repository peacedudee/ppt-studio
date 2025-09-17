from fastapi import FastAPI, HTTPException
import uvicorn
import os
import sys
import redis
import psutil
from google.cloud import storage
from datetime import datetime
import traceback

from config import settings

app = FastAPI(title="PPT Studio Worker Health Check")

@app.get("/")
def health():
    return {
        "status": "ok", 
        "service": "ppt-studio-worker",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0"
    }

@app.get("/health")
def detailed_health():
    health_status = {
        "status": "ok", 
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
        "system": {
            "python_version": sys.version,
            "memory_usage": f"{psutil.virtual_memory().percent}%",
            "cpu_count": psutil.cpu_count(),
            "disk_usage": f"{psutil.disk_usage('/').percent}%"
        }
    }
    
    # Redis check
    try:
        redis_url = settings.celery_broker_url
        r = redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
        r.ping()
        
        # Test basic operations
        test_key = "health_check_test"
        r.set(test_key, "test_value", ex=30)
        result = r.get(test_key)
        r.delete(test_key)
        
        health_status["checks"]["redis"] = {
            "status": "ok",
            "url": redis_url[:30] + "...",
            "test_operation": "success"
        }
    except Exception as e:
        health_status["checks"]["redis"] = {
            "status": "failed",
            "error": str(e),
            "url": redis_url[:30] + "..." if redis_url else "not_set"
        }
        health_status["status"] = "degraded"
    
    # GCS check
    try:
        client = storage.Client()
        bucket_name = settings.gcs_bucket_name
        
        if not bucket_name:
            raise Exception("GCS_BUCKET_NAME not set")
            
        bucket = client.bucket(bucket_name)
        
        if bucket.exists():
            # Test write/read/delete operations
            test_blob_name = "health-check/test.txt"
            test_blob = bucket.blob(test_blob_name)
            test_blob.upload_from_string("health check test", content_type='text/plain')
            content = test_blob.download_as_text()
            test_blob.delete()
            
            health_status["checks"]["gcs"] = {
                "status": "ok",
                "bucket": bucket_name,
                "operations": "read/write/delete successful"
            }
        else:
            raise Exception(f"Bucket {bucket_name} does not exist or is not accessible")
            
    except Exception as e:
        health_status["checks"]["gcs"] = {
            "status": "failed",
            "error": str(e),
            "bucket": settings.gcs_bucket_name or 'not_set'
        }
        health_status["status"] = "degraded"
    
    # Celery check
    try:
        from worker.celery_app import celery
        
        # Test broker connection
        with celery.connection() as connection:
            connection.ensure_connection(max_retries=2)
        
        health_status["checks"]["celery"] = {
            "status": "ok",
            "broker": celery.conf.broker_url[:30] + "...",
            "backend": celery.conf.result_backend[:30] + "..."
        }
    except Exception as e:
        health_status["checks"]["celery"] = {
            "status": "failed",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Environment variables check
    required_envs = ['REDIS_URL', 'GCS_BUCKET_NAME', 'GOOGLE_API_KEY']
    missing_envs = []
    present_envs = {}
    
    for env in required_envs:
        value = os.getenv(env)
        if not value:
            missing_envs.append(env)
        else:
            # Show first few characters for debugging without exposing secrets
            present_envs[env] = value[:10] + "..." if len(value) > 10 else "set"
    
    if missing_envs:
        health_status["checks"]["environment"] = {
            "status": "failed",
            "missing": missing_envs,
            "present": present_envs
        }
        health_status["status"] = "degraded"
    else:
        health_status["checks"]["environment"] = {
            "status": "ok",
            "all_required_vars_present": True,
            "present": present_envs
        }
    
    # Python packages check
    try:
        import celery
        import redis
        import google.generativeai
        from google.cloud import storage
        from pptx import Presentation
        import PIL
        import fitz  # PyMuPDF
        
        health_status["checks"]["packages"] = {
            "status": "ok",
            "versions": {
                "celery": celery.__version__,
                "redis": redis.__version__,
                "PIL": PIL.__version__
            }
        }
    except ImportError as e:
        health_status["checks"]["packages"] = {
            "status": "failed",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/debug")
def debug_info():
    """Detailed debug information for troubleshooting"""
    try:
        debug_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": {
                "python_path": sys.path,
                "python_executable": sys.executable,
                "current_directory": os.getcwd(),
                "user": os.getenv('USER', 'unknown'),
                "home": os.getenv('HOME', 'unknown')
            },
            "system": {
                "platform": sys.platform,
                "python_version": sys.version_info._asdict(),
                "memory": {
                    "total": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
                    "available": f"{psutil.virtual_memory().available / (1024**3):.2f} GB",
                    "used": f"{psutil.virtual_memory().percent}%"
                },
                "disk": {
                    "total": f"{psutil.disk_usage('/').total / (1024**3):.2f} GB",
                    "free": f"{psutil.disk_usage('/').free / (1024**3):.2f} GB",
                    "used": f"{psutil.disk_usage('/').percent}%"
                },
                "cpu_count": psutil.cpu_count(),
                "processes": len(psutil.pids())
            },
            "env_vars": {
                key: value[:20] + "..." if len(value) > 20 else value
                for key, value in os.environ.items()
                if not key.lower().endswith('key') and not key.lower().endswith('secret')
            }
        }
        
        return debug_info
        
    except Exception as e:
        return {
            "error": "Failed to generate debug info",
            "details": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/test-task")
def test_celery_task():
    """Test if Celery can receive and process a simple task"""
    try:
        from worker.celery_app import celery
        
        # Send a simple test task
        result = celery.send_task('test_task', args=['hello world'])
        
        return {
            "status": "task_sent",
            "task_id": result.id,
            "message": "Test task sent to Celery worker"
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    port = settings.port
    print(f"Starting health check server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
