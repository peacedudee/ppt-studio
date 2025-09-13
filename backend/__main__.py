import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    # Point to the FastAPI app in app/main.py
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
