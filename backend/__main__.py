import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    # This tells uvicorn to find the 'app' object inside the 'main' module
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)