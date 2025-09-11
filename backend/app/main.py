import uuid
import shutil
import json
import csv
import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage
from worker.celery_app import (
    celery as celery_app,
    enhance_ppt_task, 
    generate_slide_plan_task, 
    build_ppt_from_plan_task
)

# Configuration
TEMP_DIR = Path("temp")
TEMP_DIR.mkdir(exist_ok=True)

app = FastAPI(title="PPT Studio API")

# CORS Middleware
origins = [
    "http://localhost:5173",
    "https://ppt-studio.web.app", # Replace with your project ID if different
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Model for Feedback
class Feedback(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    feedback_type: str
    message: str

# API Endpoints
@app.get("/health", tags=["Health Check"])
def health_check():
    return {"status": "ok"}

@app.post("/api/v1/enhancer/process", status_code=status.HTTP_202_ACCEPTED, tags=["PPT Enhancer"])
async def process_enhancement(
    ppt_file: UploadFile = File(...),
    logo_file: Optional[UploadFile] = File(None),
    credits_text: Optional[str] = Form(None)
):
    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir()

    input_path = job_dir / ppt_file.filename
    with open(input_path, "wb") as buffer:
        buffer.write(await ppt_file.read())

    logo_path = None
    if logo_file:
        logo_path = job_dir / logo_file.filename
        with open(logo_path, "wb") as buffer:
            buffer.write(await logo_file.read())

    output_path = job_dir / f"enhanced_{ppt_file.filename}"
    enhance_ppt_task.apply_async(
        args=[str(input_path), str(output_path), str(logo_path) if logo_path else None, credits_text],
        task_id=job_id
    )
    return {"job_id": job_id, "output_filename": f"enhanced_{ppt_file.filename}"}

@app.get("/api/v1/enhancer/download/{job_id}/{filename}", tags=["PPT Enhancer"])
def download_enhanced_ppt(job_id: str, filename: str):
    processed_file = TEMP_DIR / job_id / filename
    if not processed_file.exists():
        return {"error": "File not found or still processing"}, 404
    return FileResponse(processed_file, filename=filename)

@app.post("/api/v1/creator/generate-plan", status_code=status.HTTP_202_ACCEPTED, tags=["PPT Creator"])
async def generate_plan(files: List[UploadFile] = File(...)):
    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir()

    for file in files:
        file_path = job_dir / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    generate_slide_plan_task.apply_async(args=[job_id], task_id=job_id)
    return {"job_id": job_id}

@app.post("/api/v1/creator/build/{job_id}", status_code=status.HTTP_202_ACCEPTED, tags=["PPT Creator"])
async def build_presentation(job_id: str, slide_plan: List[dict]):
    job_dir = TEMP_DIR / job_id
    
    if slide_plan:
        with open(job_dir / "slides.json", "w") as f:
            json.dump(slide_plan, f, indent=2)

    build_task_id = str(uuid.uuid4())
    build_ppt_from_plan_task.apply_async(args=[job_id], task_id=build_task_id)
    return {"message": "Presentation build has been queued.", "build_job_id": build_task_id}

@app.get("/api/v1/creator/download/{job_id}", tags=["PPT Creator"])
def download_created_ppt(job_id: str):
    processed_file = TEMP_DIR / job_id / "presentation.pptx"
    if not processed_file.exists():
        return {"error": "File not found or still building"}, 404
    return FileResponse(processed_file, filename=f"{job_id}.pptx")

@app.get("/api/v1/jobs/status/{job_id}", tags=["Jobs"])
def get_status(job_id: str):
    task_result = celery_app.AsyncResult(job_id)
    return {"job_id": job_id, "status": task_result.status, "result": task_result.result if task_result.ready() else None}

@app.post("/api/v1/feedback", status_code=status.HTTP_201_CREATED, tags=["Feedback"])
async def receive_feedback(feedback: Feedback):
    feedback_file = Path("feedback.csv")
    if not feedback_file.exists():
        with open(feedback_file, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["name", "email", "feedback_type", "message"])
    with open(feedback_file, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([feedback.name, feedback.email, feedback.feedback_type, feedback.message])
    return {"message": "Feedback received successfully."}