import os
import uuid
import json
import csv
import shutil
import datetime
from pathlib import Path
from typing import List, Optional
from io import StringIO # Import StringIO for in-memory file handling
from fastapi import FastAPI, File, UploadFile, Form, status, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage
import google.auth
import requests
from google.cloud.exceptions import NotFound

from worker.celery_app import (
    celery as celery_app,
    enhance_ppt_task, 
    generate_slide_plan_task, 
    build_ppt_from_plan_task
)

# --- Configuration ---
storage_client = storage.Client()
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
app = FastAPI(title="PPT Studio API")

# --- CORS Middleware Configuration ---
origins = [
    "http://localhost:5173", # For local development
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

def _get_runtime_service_account_email() -> str | None:
    # Prefer explicit env override if present
    env_email = os.getenv("SERVICE_ACCOUNT_EMAIL")
    if env_email:
        return env_email
    # Try to read from metadata server (Cloud Run / GCE)
    try:
        r = requests.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email",
            headers={"Metadata-Flavor": "Google"},
            timeout=1.5,
        )
        if r.ok:
            return r.text.strip()
    except Exception:
        pass
    # Try to read from ADC credentials
    try:
        creds, _ = google.auth.default()
        email = getattr(creds, "service_account_email", None)
        return email
    except Exception:
        return None


def generate_download_signed_url_v4(blob_name):
    """Generates a secure, temporary URL to download a file from GCS.
    Returns a signed URL string or raises HTTPException with details.
    """
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME environment variable not set.")
    try:
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        # Optional existence check to return 404 instead of generic errors
        if not blob.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {blob_name}")
        # Ensure we have a signer email when running on Cloud Run without a private key
        signer_email = _get_runtime_service_account_email()
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="GET",
            service_account_email=signer_email,
        )
        return url
    except HTTPException:
        raise
    except Exception as e:
        # Common cause: runtime SA lacks roles/iam.serviceAccountTokenCreator to sign URLs
        raise HTTPException(status_code=500, detail=f"Failed to generate signed URL: {e}")

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
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME is not configured.")
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
    """Return a redirect to a signed URL when possible; otherwise stream directly from GCS.
    This avoids requiring a private key in environments where IAM SignBlob is unavailable.
    """
    blob_name = f"{job_id}/{filename}"
    try:
        url = generate_download_signed_url_v4(blob_name)
        return RedirectResponse(url=url)
    except HTTPException:
        # Fallback: stream from GCS through this API
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        if not blob.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {blob_name}")

        def iter_chunks(chunk_size=1024 * 1024):
            with blob.open("rb") as fh:
                while True:
                    data = fh.read(chunk_size)
                    if not data:
                        break
                    yield data

        headers = {
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        }
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        return StreamingResponse(iter_chunks(), media_type=media_type, headers=headers)

@app.get("/api/v1/enhancer/download-url/{job_id}/{filename}", tags=["PPT Enhancer"])
def get_enhanced_download_url(job_id: str, filename: str):
    """Returns signed URL JSON instead of redirect, useful for debugging."""
    url = generate_download_signed_url_v4(f"{job_id}/{filename}")
    return {"url": url}

@app.post("/api/v1/creator/generate-plan", status_code=status.HTTP_202_ACCEPTED, tags=["PPT Creator"])
async def generate_plan(files: List[UploadFile] = File(...)):
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME is not configured.")
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
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME is not configured.")
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
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME is not configured.")
    
    try:
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        feedback_blob = bucket.blob("feedback/feedback.csv")
        
        # Download existing content if the file exists
        try:
            content = feedback_blob.download_as_text()
            file_exists = True
        except NotFound:
            content = ""
            file_exists = False
            
        # Use StringIO to handle CSV writing in memory
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header only if the file is new
        if not file_exists:
            writer.writerow(["name", "email", "feedback_type", "message"])
            
        # Write the new feedback row
        writer.writerow([feedback.name, feedback.email, feedback.feedback_type, feedback.message])
        
        # Prepend the new content to the existing content
        new_content = content + output.getvalue()
        
        # Upload the updated content back to GCS
        feedback_blob.upload_from_string(new_content, content_type="text/csv")

        return {"message": "Feedback received successfully."}
    except Exception as e:
        # Log the exception e for debugging
        raise HTTPException(status_code=500, detail="Could not save feedback.")
