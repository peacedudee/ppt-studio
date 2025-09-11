import os
import io
import json
import time
import shutil
from pathlib import Path
from celery import Celery
from pptx import Presentation
from pptx.slide import Slide
from google.cloud import storage
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_PARAGRAPH_ALIGNMENT
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image
import imagehash
import google.generativeai as genai

from .creator_logic import extract_text_from_document, generate_content_for_batch
from .ppt_builder import build_presentation_from_plan

# --- Configuration ---
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
storage_client = storage.Client()
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
LOGO_PATH = "temp/logo.png"
WATERMARK_KEYWORDS = ["CONFIDENTIAL", "DRAFT", "INTERNAL USE"]
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# --- Initialize Celery ---
celery = Celery("tasks", broker=redis_url, backend=redis_url)
celery.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json")

# --- GCS Helper Functions ---
def download_blob(blob_name, destination_file_name):
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(destination_file_name)

def upload_blob(source_file_name, destination_blob_name):
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)

def list_blobs(prefix):
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    return bucket.list_blobs(prefix=prefix)

# --- Other Business Logic (unchanged) ---
# ... (chunks, _iter_picture_shapes, _image_hash_for_shape, remove_frequent_images, etc.)

# --- Celery Tasks ---
@celery.task(name="enhance_ppt_task")
def enhance_ppt_task(input_blob: str, output_blob: str, logo_blob: str = None, credits_text: str = None):
    job_id = Path(input_blob).parts[0]
    local_job_dir = Path("temp") / job_id
    local_job_dir.mkdir(parents=True, exist_ok=True)
    try:
        local_input_path = local_job_dir / Path(input_blob).name
        download_blob(input_blob, str(local_input_path))
        
        local_logo_path = None
        if logo_blob:
            local_logo_path = local_job_dir / Path(logo_blob).name
            download_blob(logo_blob, str(local_logo_path))
        
        prs = Presentation(local_input_path)
        # ... (full enhancement logic here) ...
        local_output_path = local_job_dir / Path(output_blob).name
        prs.save(str(local_output_path))
        upload_blob(str(local_output_path), output_blob)
        return {"status": "complete", "output_blob": output_blob}
    finally:
        shutil.rmtree(local_job_dir)

@celery.task(name="generate_slide_plan_task")
def generate_slide_plan_task(job_id: str, image_filenames: list):
    local_job_dir = Path("temp") / job_id
    local_job_dir.mkdir(parents=True, exist_ok=True)
    try:
        # ... (full logic to download files from GCS) ...
        # ... (call generate_content_for_batch) ...
        # ... (upload slides.json back to GCS) ...
        return {"status": "complete", "slide_plan": slide_plan}
    finally:
        shutil.rmtree(local_job_dir)

@celery.task(name="build_ppt_from_plan_task")
def build_ppt_from_plan_task(job_id: str):
    local_job_dir = Path("temp") / job_id
    local_job_dir.mkdir(parents=True, exist_ok=True)
    try:
        # ... (full logic to download all files from GCS) ...
        local_output_path = build_presentation_from_plan(local_job_dir, "presentation.pptx")
        upload_blob(str(local_output_path), f"{job_id}/presentation.pptx")
        return {"status": "complete", "output_file": f"{job_id}/presentation.pptx"}
    finally:
        shutil.rmtree(local_job_dir)