import uuid
import json
import csv
import shutil
import datetime
from pathlib import Path
from typing import List, Optional
from io import StringIO # Import StringIO for in-memory file handling
from fastapi import FastAPI, File, UploadFile, Form, status, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from google.cloud import storage
from google.auth.exceptions import DefaultCredentialsError
import google.auth
import requests
from google.cloud.exceptions import NotFound

from worker.celery_app import (
    celery as celery_app,
    enhance_ppt_task,
    generate_outline_task,
    generate_slide_plan_task,
    build_ppt_from_plan_task,
)

from config import settings
from config.storage import LocalStorageClient

# --- Configuration ---


def _create_storage_client() -> storage.Client:
    if settings.use_local_storage:
        return LocalStorageClient()
    try:
        return storage.Client()
    except DefaultCredentialsError:
        if settings.is_development:
            return LocalStorageClient()
        raise


storage_client = _create_storage_client()
GCS_BUCKET_NAME = settings.gcs_bucket_name


def _metadata_blob(bucket, job_id: str):
    return bucket.blob(f"{job_id}/metadata.json")


def _load_job_metadata(bucket, job_id: str) -> dict:
    blob = _metadata_blob(bucket, job_id)
    if not blob.exists():
        return {}
    try:
        return json.loads(blob.download_as_text())
    except Exception:
        return {}


def _store_job_metadata(bucket, job_id: str, metadata: dict) -> None:
    _metadata_blob(bucket, job_id).upload_from_string(
        json.dumps(metadata, indent=2), content_type="application/json"
    )
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

@app.middleware("http")
async def ensure_cors_headers(request, call_next):
    try:
        response = await call_next(request)
    except StarletteHTTPException as exc:
        response = await http_exception_handler(request, exc)
    except RequestValidationError as exc:
        response = JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )
    except Exception as exc:
        # Log and return generic error to avoid leaking details
        print(f"Unhandled server error: {exc}")
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal Server Error"},
        )

    origin = request.headers.get("origin")
    if origin and origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        vary = response.headers.get("Vary")
        response.headers["Vary"] = "Origin" if not vary else f"{vary}, Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# --- Pydantic Models & Helper Functions ---
class Feedback(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    feedback_type: str
    message: str

def _get_runtime_service_account_email() -> str | None:
    # Prefer explicit env override if present
    env_email = settings.service_account_email
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
    if settings.use_local_storage:
        raise HTTPException(status_code=501, detail="Signed URLs unavailable in local storage mode")
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


def _stream_blob_response(blob_name: str, download_filename: str):
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
        "Content-Disposition": f"attachment; filename=\"{download_filename}\""
    }
    media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    return StreamingResponse(iter_chunks(), media_type=media_type, headers=headers)

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
    if settings.use_local_storage:
        return _stream_blob_response(blob_name, filename)
    try:
        url = generate_download_signed_url_v4(blob_name)
        return RedirectResponse(url=url)
    except HTTPException:
        return _stream_blob_response(blob_name, filename)

@app.get("/api/v1/enhancer/download-url/{job_id}/{filename}", tags=["PPT Enhancer"])
def get_enhanced_download_url(job_id: str, filename: str):
    """Returns signed URL JSON instead of redirect, useful for debugging."""
    if settings.use_local_storage:
        return {"url": f"/api/v1/enhancer/download/{job_id}/{filename}"}
    url = generate_download_signed_url_v4(f"{job_id}/{filename}")
    return {"url": url}

@app.post("/api/v1/creator/generate-outline", status_code=status.HTTP_202_ACCEPTED, tags=["PPT Creator"])
async def generate_outline(
    source_file: UploadFile | None = File(None),
    slide_count: int | None = Form(None),
    source_text: str | None = Form(None),
):
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME is not configured.")

    pasted_text = (source_text or "").strip()
    has_file = bool(source_file and source_file.filename)

    if not has_file and not pasted_text:
        raise HTTPException(status_code=400, detail="Provide a source document or paste source text to continue.")

    target_slide_count: int | None = None
    if slide_count is not None:
        try:
            target_slide_count = max(1, min(int(slide_count), 30))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="slide_count must be an integer value.")

    job_id = str(uuid.uuid4())
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    metadata: dict[str, object] = {}

    source_blob_path: str | None = None

    if has_file:
        source_blob_path = f"source/{source_file.filename}"
        source_file.file.seek(0)
        bucket.blob(f"{job_id}/{source_blob_path}").upload_from_file(
            source_file.file, content_type=source_file.content_type
        )
        metadata.update(
            {
                "source_filename": source_file.filename,
                "source_content_type": source_file.content_type,
                "source_input_type": "file_upload",
            }
        )

    if pasted_text:
        text_blob_path = f"source/pasted-{uuid.uuid4().hex}.txt"
        bucket.blob(f"{job_id}/{text_blob_path}").upload_from_string(
            pasted_text, content_type="text/plain"
        )
        metadata.setdefault("source_text_preview", pasted_text[:500])
        if not source_blob_path:
            source_blob_path = text_blob_path
            metadata.setdefault("source_filename", Path(text_blob_path).name)
            metadata.setdefault("source_content_type", "text/plain")
            metadata["source_input_type"] = "pasted_text"
        else:
            metadata["supplemental_text_present"] = True

    if not source_blob_path:
        raise HTTPException(status_code=400, detail="Unable to determine source material for outline generation.")

    metadata["source_blob"] = source_blob_path
    if target_slide_count:
        metadata["desired_slide_count"] = target_slide_count

    _store_job_metadata(bucket, job_id, metadata)

    outline_task_id = f"{job_id}-outline"
    generate_outline_task.apply_async(
        kwargs={
            "job_id": job_id,
            "source_blob": source_blob_path,
        },
        task_id=outline_task_id,
    )

    return {
        "job_id": job_id,
        "outline_task_id": outline_task_id,
        "source_filename": metadata.get("source_filename"),
        "source_blob": source_blob_path,
        "slide_count": target_slide_count,
    }


@app.post("/api/v1/creator/generate-plan", status_code=status.HTTP_202_ACCEPTED, tags=["PPT Creator"])
async def generate_plan(
    job_id: Optional[str] = Form(None),
    image_strategy: str = Form("uploaded"),
    files: List[UploadFile] | None = File(None),
):
    if not GCS_BUCKET_NAME:
        raise HTTPException(status_code=500, detail="GCS_BUCKET_NAME is not configured.")

    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    workspace_id = job_id or str(uuid.uuid4())
    metadata = _load_job_metadata(bucket, workspace_id)
    source_blob_path = metadata.get("source_blob")

    strategy = (image_strategy or "uploaded").strip().lower()
    allowed_strategies = {"uploaded", "unsplash", "gemini_line_art"}
    if strategy not in allowed_strategies:
        raise HTTPException(status_code=400, detail=f"Unsupported image strategy: {image_strategy}")

    incoming_files = files or []
    image_records = []
    uploaded_source_blob = None

    for file in incoming_files:
        file.file.seek(0)
        if file.content_type and file.content_type.startswith('image/'):
            blob_path = f"images/{file.filename}"
            bucket.blob(f"{workspace_id}/{blob_path}").upload_from_file(
                file.file, content_type=file.content_type
            )
            image_records.append({"blob_path": blob_path, "filename": file.filename})
        else:
            uploaded_source_blob = f"source/{file.filename}"
            bucket.blob(f"{workspace_id}/{uploaded_source_blob}").upload_from_file(
                file.file, content_type=file.content_type
            )
            metadata.update(
                {
                    "source_blob": uploaded_source_blob,
                    "source_filename": file.filename,
                    "source_content_type": file.content_type,
                }
            )

    if strategy == "uploaded" and not image_records:
        raise HTTPException(status_code=400, detail="Please upload at least one image.")

    if uploaded_source_blob:
        source_blob_path = uploaded_source_blob

    if not source_blob_path:
        raise HTTPException(
            status_code=400,
            detail="Source document is missing for this job. Generate an outline first.",
        )

    if strategy != "uploaded" and not job_id:
        raise HTTPException(status_code=400, detail="Outline job_id is required for automatic image strategies.")

    if strategy != "uploaded" and not metadata.get("outline_blob"):
        raise HTTPException(status_code=400, detail="Generate an outline before requesting automatic images.")

    metadata["image_strategy"] = strategy
    _store_job_metadata(bucket, workspace_id, metadata)

    plan_task_id = f"{workspace_id}-plan"
    generate_slide_plan_task.apply_async(
        kwargs={
            "job_id": workspace_id,
            "image_records": image_records,
            "source_blob": source_blob_path,
            "image_strategy": strategy,
        },
        task_id=plan_task_id,
    )

    return {"job_id": workspace_id, "plan_task_id": plan_task_id, "image_strategy": strategy}

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
    """Return redirect to signed URL if possible; otherwise stream from GCS."""
    blob_name = f"{job_id}/presentation.pptx"
    if settings.use_local_storage:
        return _stream_blob_response(blob_name, "presentation.pptx")
    try:
        url = generate_download_signed_url_v4(blob_name)
        return RedirectResponse(url=url)
    except HTTPException:
        return _stream_blob_response(blob_name, "presentation.pptx")

@app.get("/api/v1/creator/download-url/{job_id}", tags=["PPT Creator"])
def creator_download_url(job_id: str):
    """Return a signed URL for the generated presentation, if possible."""
    if settings.use_local_storage:
        return {"url": f"/api/v1/creator/download/{job_id}"}
    url = generate_download_signed_url_v4(f"{job_id}/presentation.pptx")
    return {"url": url}

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
