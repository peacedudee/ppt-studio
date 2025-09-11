import os
import io
import json
import time
import shutil
from pathlib import Path
from celery import Celery
from pptx import Presentation
from pptx.slide import Slide
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_PARAGRAPH_ALIGNMENT, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image
import imagehash
import google.generativeai as genai

# Import our creator and builder logic functions
from .creator_logic import extract_text_from_document, generate_content_for_batch
from .ppt_builder import build_presentation_from_plan

# --- Configuration ---
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
LOGO_PATH = "temp/logo.png"
WATERMARK_KEYWORDS = ["CONFIDENTIAL", "DRAFT", "INTERNAL USE"]
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# --- Initialize Celery ---
celery = Celery("tasks", broker=redis_url, backend=redis_url)
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# --- Helper and Business Logic Functions ---

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def _iter_picture_shapes(container):
    """Recursively finds all picture shapes, even inside groups."""
    if not hasattr(container, "shapes"): return
    for shape in list(container.shapes):
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            yield shape
        elif shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            for inner in _iter_picture_shapes(shape):
                yield inner

def _image_hash_for_shape(shape):
    """Calculates the perceptual hash for an image shape."""
    try:
        with Image.open(io.BytesIO(shape.image.blob)).convert("RGB") as im:
            return imagehash.phash(im)
    except Exception:
        return None

def remove_frequent_images(prs: Presentation, min_occurrences: int, hash_tolerance: int):
    """
    Finds and removes images that repeat frequently across the entire presentation
    (masters, layouts, and slides).
    """
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
    """Extracts all text from shapes on a given slide, including placeholders."""
    slide_texts = []
    for shape in slide.shapes:
        if shape.has_text_frame:
            text = shape.text_frame.text.strip()
            if text:
                slide_texts.append(text)
    return "\n".join(slide_texts)

def generate_and_add_speaker_notes(slide: Slide):
    """Generates speaker notes for a slide using the Gemini API and adds them."""
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
    """Iterates through all slide masters and removes shapes containing watermark keywords."""
    for master in prs.slide_masters:
        shapes_to_delete = [
            shape for shape in master.shapes
            if shape.has_text_frame and any(keyword in shape.text.upper() for keyword in WATERMARK_KEYWORDS)
        ]
        for shape in shapes_to_delete:
            sp = shape.element
            sp.getparent().remove(sp)

def add_logo(slide: Slide, logo_path: str):
    """Adds a logo from a given path to the top-left of the slide."""
    if logo_path and os.path.exists(logo_path):
        slide.shapes.add_picture(logo_path, Inches(0.2), Inches(0.2), width=Inches(1.0))

def add_credits_to_slide(slide: Slide, slide_width, slide_height, text: str, url: str):
    """Adds a formatted, hyperlinked textbox with custom text and URL."""
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
def enhance_ppt_task(input_path: str, output_path: str, logo_path: str = None, credits_text: str = None):
    try:
        prs = Presentation(input_path)
        final_credits_text = credits_text if credits_text else "Processed by PPT Studio"
        final_credits_url = "https://mybrand.com" if credits_text else "https://www.example.com"
        final_logo_path = logo_path if logo_path else LOGO_PATH

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
            
        prs.save(output_path)
        return f"Successfully processed {input_path}"
    except Exception as e:
        return f"Error processing {input_path}: {str(e)}"

@celery.task(name="generate_slide_plan_task")
def generate_slide_plan_task(job_id: str):
    job_dir = Path("temp") / job_id
    source_doc = next((f for f in job_dir.iterdir() if f.suffix.lower() in [".pdf", ".docx", ".txt"]), None)
    if not source_doc:
        return {"error": "No source document found."}
    
    image_files = sorted([f for f in job_dir.iterdir() if f.suffix.lower() in [".png", ".jpg", ".jpeg"]])
    source_text = extract_text_from_document(str(source_doc))
    
    full_slide_plan = []
    batch_size = 5
    image_batches = list(chunks(image_files, batch_size))
    
    print(f"Starting multimodal generation for {len(image_files)} slides in {len(image_batches)} batches...")
    
    for i, batch in enumerate(image_batches):
        print(f" - Processing batch {i+1}/{len(image_batches)} with {len(batch)} images...")
        slide_contents = generate_content_for_batch(source_text, batch)
        full_slide_plan.extend(slide_contents)
        
        # Wait between batches to respect API rate limits
        if i < len(image_batches) - 1:
            time.sleep(2)
    
    if full_slide_plan:
        plan_path = job_dir / "slides.json"
        with open(plan_path, "w") as f:
            json.dump(full_slide_plan, f, indent=2)
        return {"status": "complete", "slide_plan": full_slide_plan}
    else:
        return {"error": "Failed to generate a slide plan."}

@celery.task(name="build_ppt_from_plan_task")
def build_ppt_from_plan_task(job_id: str):
    job_dir = Path("temp") / job_id
    output_filename = "presentation.pptx"
    if not (job_dir / "slides.json").exists():
        return {"error": f"slides.json not found for job {job_id}"}
    try:
        output_path = build_presentation_from_plan(job_dir, output_filename)
        return {"status": "complete", "output_file": str(output_path)}
    except Exception as e:
        return f"Error processing {job_id}: {e}"