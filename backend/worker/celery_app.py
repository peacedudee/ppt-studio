import os
import io
import json
import shutil
from pathlib import Path
from celery import Celery
from pptx import Presentation
from pptx.slide import Slide
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_PARAGRAPH_ALIGNMENT
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image
import imagehash
import google.generativeai as genai
from google.cloud import storage

from config import settings

# Import other project modules
from .creator_logic import extract_text_from_document, generate_content_for_batch
from .ppt_builder import build_presentation_from_plan

# --- Configuration ---
GCS_BUCKET_NAME = settings.gcs_bucket_name
storage_client = storage.Client()
LOGO_PATH = "temp/logo.png"  # Default logo path if none is provided
WATERMARK_KEYWORDS = ["CONFIDENTIAL", "DRAFT", "INTERNAL USE"]
if settings.google_api_key:
    genai.configure(api_key=settings.google_api_key)

# --- Initialize Celery ---
celery_backend = settings.celery_backend_url
celery = Celery("tasks", broker=settings.celery_broker_url, backend=celery_backend or None)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=settings.celery_result_expires,
)
if not celery_backend:
    celery.conf.update(result_backend=None, task_ignore_result=True)

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

# --- Other Business Logic (Full versions) ---
def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def _iter_picture_shapes(container):
    if not hasattr(container, "shapes"): return
    for shape in list(container.shapes):
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            yield shape
        elif shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            for inner in _iter_picture_shapes(shape):
                yield inner

def _image_hash_for_shape(shape):
    try:
        with Image.open(io.BytesIO(shape.image.blob)).convert("RGB") as im:
            return imagehash.phash(im)
    except Exception:
        return None

def remove_frequent_images(prs: Presentation, min_occurrences: int, hash_tolerance: int):
    all_pics_and_hashes = []
    for master in prs.slide_masters:
        for pic in _iter_picture_shapes(master):
            if h := _image_hash_for_shape(pic):
                all_pics_and_hashes.append({'shape': pic, 'hash': h})
    for layout in prs.slide_layouts:
        for pic in _iter_picture_shapes(layout):
            if h := _image_hash_for_shape(pic):
                all_pics_and_hashes.append({'shape': pic, 'hash': h})
    for slide in prs.slides:
        for pic in _iter_picture_shapes(slide):
            if h := _image_hash_for_shape(pic):
                all_pics_and_hashes.append({'shape': pic, 'hash': h})
    if not all_pics_and_hashes: return
    hash_clusters = {}
    for item in all_pics_and_hashes:
        found_cluster = False
        for h_key in hash_clusters:
            if item['hash'] - h_key <= hash_tolerance:
                hash_clusters[h_key].append(item['shape'])
                found_cluster = True
                break
        if not found_cluster:
            hash_clusters[item['hash']] = [item['shape']]
    shapes_to_delete = []
    for h, shapes in hash_clusters.items():
        if len(shapes) >= min_occurrences:
            shapes_to_delete.extend(shapes)
    for shape in shapes_to_delete:
        sp = shape.element
        sp.getparent().remove(sp)

def extract_text_from_slide(slide: Slide) -> str:
    slide_texts = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            text = shape.text_frame.text.strip()
            if text:
                slide_texts.append(text)
    return "\n".join(slide_texts)

def generate_and_add_speaker_notes(slide: Slide):
    try:
        slide_text = extract_text_from_slide(slide)
        if not slide_text: return
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Generate a concise, professional speaker note for a presentation slide with the following content:\n\n---\n{slide_text}\n---"
        response = model.generate_content(prompt)
        if response.text:
            slide.notes_slide.notes_text_frame.text = response.text
    except Exception as e:
        slide.notes_slide.notes_text_frame.text = f"Could not generate speaker notes: {e}"

def remove_watermarks_from_masters(prs: Presentation):
    for master in prs.slide_masters:
        shapes_to_delete = [
            shape for shape in master.shapes
            if shape.has_text_frame and any(keyword in shape.text.upper() for keyword in WATERMARK_KEYWORDS)
        ]
        for shape in shapes_to_delete:
            sp = shape.element
            sp.getparent().remove(sp)

def add_logo(slide: Slide, logo_path: str):
    if logo_path and os.path.exists(logo_path):
        slide.shapes.add_picture(logo_path, Inches(0.2), Inches(0.2), width=Inches(1.0))

def add_credits_to_slide(slide: Slide, slide_width, slide_height, text: str, url: str):
    textbox = slide.shapes.add_textbox(
        left=slide_width - Inches(2.6), top=slide_height - Inches(0.5),
        width=Inches(2.5), height=Inches(0.4)
    )
    tf = textbox.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.alignment = PP_PARAGRAPH_ALIGNMENT.RIGHT
    run = p.add_run()
    run.text = text
    run.hyperlink.address = url
    font = run.font
    font.size = Pt(10)
    font.color.rgb = RGBColor(150, 150, 150)

# --- Celery Tasks ---
@celery.task(name="enhance_ppt_task")
def enhance_ppt_task(input_blob: str, output_blob: str, logo_blob: str = None, credits_text: str = None):
    job_id = Path(input_blob).parts[0]
    local_job_dir = Path("/tmp") / job_id
    local_job_dir.mkdir(parents=True, exist_ok=True)
    try:
        local_input_path = local_job_dir / Path(input_blob).name
        download_blob(input_blob, str(local_input_path))
        
        local_logo_path = None
        if logo_blob:
            local_logo_path = local_job_dir / Path(logo_blob).name
            download_blob(logo_blob, str(local_logo_path))
        
        prs = Presentation(local_input_path)
        final_credits_text = credits_text if credits_text else "Processed by PPT Studio"
        final_credits_url = "https://mybrand.com" if credits_text else "https://www.example.com"
        final_logo_path = str(local_logo_path) if local_logo_path and local_logo_path.exists() else LOGO_PATH
        
        remove_watermarks_from_masters(prs)
        remove_frequent_images(prs, min_occurrences=3, hash_tolerance=5)

        for slide in prs.slides:
            shapes_to_delete_text = [
                shape for shape in slide.shapes
                if shape.has_text_frame and any(keyword in shape.text.upper() for keyword in WATERMARK_KEYWORDS)
            ]
            for shape in shapes_to_delete_text:
                sp = shape.element
                sp.getparent().remove(sp)
            add_logo(slide, final_logo_path)
            add_credits_to_slide(slide, prs.slide_width, prs.slide_height, final_credits_text, final_credits_url)
            generate_and_add_speaker_notes(slide)
        
        local_output_path = local_job_dir / Path(output_blob).name
        prs.save(str(local_output_path))
        upload_blob(str(local_output_path), output_blob)
        return {"status": "complete", "output_blob": output_blob}
    finally:
        shutil.rmtree(local_job_dir, ignore_errors=True)

@celery.task(name="generate_slide_plan_task")
def generate_slide_plan_task(job_id: str, image_filenames: list):
    local_job_dir = Path("/tmp") / job_id
    local_job_dir.mkdir(parents=True, exist_ok=True)
    try:
        blobs = list(list_blobs(job_id))
        source_doc_blob = next((b for b in blobs if Path(b.name).name not in image_filenames), None)
        if not source_doc_blob: return {"error": "No source document found in GCS."}
        
        local_source_path = local_job_dir / Path(source_doc_blob.name).name
        download_blob(source_doc_blob.name, str(local_source_path))
        source_text = extract_text_from_document(str(local_source_path))
        
        local_image_paths = []
        for filename in image_filenames:
            local_path = local_job_dir / filename
            download_blob(f"{job_id}/{filename}", str(local_path))
            local_image_paths.append(local_path)
        
        slide_plan = generate_content_for_batch(source_text, local_image_paths)
        if slide_plan:
            plan_path = local_job_dir / "slides.json"
            with open(plan_path, "w") as f:
                json.dump(slide_plan, f, indent=2)
            upload_blob(str(plan_path), f"{job_id}/slides.json")
            return {"status": "complete", "slide_plan": slide_plan}
        else: return {"error": "Failed to generate a slide plan."}
    finally:
        shutil.rmtree(local_job_dir, ignore_errors=True)

@celery.task(name="build_ppt_from_plan_task")
def build_ppt_from_plan_task(job_id: str):
    local_job_dir = Path("/tmp") / job_id
    local_job_dir.mkdir(parents=True, exist_ok=True)
    try:
        blobs = list_blobs(job_id)
        for blob in blobs:
            download_blob(blob.name, str(local_job_dir / Path(blob.name).name))
        
        output_filename = "presentation.pptx"
        local_output_path = build_presentation_from_plan(local_job_dir, output_filename)
        upload_blob(str(local_output_path), f"{job_id}/{output_filename}")
        return {"status": "complete", "output_file": f"{job_id}/{output_filename}"}
    finally:
        shutil.rmtree(local_job_dir, ignore_errors=True)
