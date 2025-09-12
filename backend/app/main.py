import os
import uuid
import json
import csv
import shutil
import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, Form, status
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage

from worker.celery_app import (
    celery as celery_app,
    enhance_ppt_task, 
    generate_slide_plan_task, 
    build_ppt_from_plan_task
)

# --- Configuration ---
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
storage_client = storage.Client()
app = FastAPI(title="PPT Studio API")

# --- CORS Middleware Configuration ---
origins = [
    # "http://localhost:5173", # For local development
    "https://ppt-studio.web.app", # Your production Firebase URL
    "https://ppt-studio--ppt-studio.web.app" # For Firebase preview channels
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models & Helper Functions ---
class Feedback(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    feedback_type: str
    message: str

def generate_download_signed_url_v4(blob_name):
    """Generates a secure, temporary URL to download a file from GCS."""
    if not GCS_BUCKET_NAME:
        raise RuntimeError("GCS_BUCKET_NAME environment variable not set.")
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_name)
    return blob.generate_signed_url(version="v4", expiration=datetime.timedelta(minutes=15), method="GET")

# --- API Endpoints ---
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
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    
    input_blob_name = f"{job_id}/{ppt_file.filename}"
    bucket.blob(input_blob_name).upload_from_file(ppt_file.file, content_type=ppt_file.content_type)

    logo_blob_name = None
    if logo_file and logo_file.filename:
        logo_blob_name = f"{job_id}/{logo_file.filename}"
        bucket.blob(logo_blob_name).upload_from_file(logo_file.file, content_type=logo_file.content_type)

    output_filename = f"enhanced_{ppt_file.filename}"
    output_blob_name = f"{job_id}/{output_filename}"
    
    enhance_ppt_task.apply_async(args=[input_blob_name, output_blob_name, logo_blob_name, credits_text], task_id=job_id)
    return {"job_id": job_id, "output_filename": output_filename}

@app.get("/api/v1/enhancer/download/{job_id}/{filename}", tags=["PPT Enhancer"])
def download_enhanced_ppt(job_id: str, filename: str):
    url = generate_download_signed_url_v4(f"{job_id}/{filename}")
    return RedirectResponse(url=url)

@app.post("/api/v1/creator/generate-plan", status_code=status.HTTP_202_ACCEPTED, tags=["PPT Creator"])
async def generate_plan(files: List[UploadFile] = File(...)):
    job_id = str(uuid.uuid4())
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    image_filenames = []
    for file in files:
        if file.content_type and file.content_type.startswith('image/'):
            image_filenames.append(file.filename)
        bucket.blob(f"{job_id}/{file.filename}").upload_from_file(file.file, content_type=file.content_type)
    
    generate_slide_plan_task.apply_async(args=[job_id, image_filenames], task_id=job_id)
    return {"job_id": job_id}

@app.post("/api/v1/creator/build/{job_id}", status_code=status.HTTP_202_ACCEPTED, tags=["PPT Creator"])
async def build_presentation(job_id: str, slide_plan: List[dict]):
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    bucket.blob(f"{job_id}/slides.json").upload_from_string(json.dumps(slide_plan, indent=2), content_type='application/json')
    build_task_id = str(uuid.uuid4())
    build_ppt_from_plan_task.apply_async(args=[job_id], task_id=build_task_id)
    return {"message": "Presentation build has been queued.", "build_job_id": build_task_id}

@app.get("/api/v1/creator/download/{job_id}", tags=["PPT Creator"])
def download_created_ppt(job_id: str):
    url = generate_download_signed_url_v4(f"{job_id}/presentation.pptx")
    return RedirectResponse(url=url)

@app.get("/api/v1/jobs/status/{job_id}", tags=["Jobs"])
def get_status(job_id: str):
    task_result = celery_app.AsyncResult(job_id)
    return {"job_id": job_id, "status": task_result.status, "result": task_result.result if task_result.ready() else None}

@app.post("/api/v1/feedback", status_code=status.HTTP_201_CREATED, tags=["Feedback"])
async def receive_feedback(feedback: Feedback):
    # This can still save to a local file on the API server's temporary disk
    feedback_file = Path("feedback.csv")
    if not feedback_file.exists():
        with open(feedback_file, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["name", "email", "feedback_type", "message"])
    with open(feedback_file, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([feedback.name, feedback.email, feedback.feedback_type, feedback.message])
    return {"message": "Feedback received successfully."}