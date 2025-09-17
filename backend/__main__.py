import uvicorn

from config import settings

if __name__ == "__main__":
    port = settings.port
    # Point to the FastAPI app in app/main.py
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
