# Import the 'celery' object from the 'celery_app' module
# and give it an alias 'celery_app' to match the test's variable name.
from backend.worker.celery_app import celery as celery_app

def test_redis_connection():
    """
    Tests if the Celery worker can connect to Redis by checking the connection.
    """
    try:
        # Now this calls .control.ping() on the actual Celery app object
        celery_app.control.ping()
    except Exception as e:
        assert False, f"Could not connect to Redis broker: {e}"