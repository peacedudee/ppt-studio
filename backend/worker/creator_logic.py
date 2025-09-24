import json
import fitz  # PyMuPDF
import docx
from pathlib import Path
from typing import List
from PIL import Image
from google import genai

from config import settings


class _NoopModel:
    def generate_content(self, *_args, **_kwargs):
        raise RuntimeError("Google AI Model is not configured. Check API Key.")


# --- Configure the AI Model ---
class _ClientTextModel:
    def __init__(self, client: genai.Client, model_name: str):
        self._client = client
        self._model_name = model_name

    def generate_content(self, contents):
        return self._client.models.generate_content(
            model=self._model_name,
            contents=contents,
        )


try:
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not configured")
    genai_client = genai.Client(api_key=settings.google_api_key)
    model = _ClientTextModel(genai_client, settings.gemini_text_model)
except Exception as e:
    print(f"Error configuring Google AI: {e}")
    genai_client = None
    model = _NoopModel()

def extract_text_from_document(filepath: str) -> str:
    """
    Extracts raw text from a given document (PDF, DOCX, or TXT).
    """
    path = Path(filepath)
    suffix = path.suffix.lower()
    text = ""
    try:
        if suffix == ".pdf":
            with fitz.open(path) as doc:
                for page in doc:
                    text += page.get_text()
        elif suffix == ".docx":
            doc = docx.Document(path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        elif suffix == ".txt":
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        else:
            return f"Unsupported file type: {suffix}"
    except Exception as e:
        return f"Error processing file {path.name}: {e}"
    return text

def generate_content_for_batch(source_text: str, image_paths: List[Path]) -> List[dict]:
    """
    Takes the full source text and a BATCH of images, prompts the vision model,
    and returns a list of slide content dictionaries for that batch.
    """
    if isinstance(model, _NoopModel):
        raise RuntimeError("Google AI Model is not configured. Check API Key.")

    # --- FINAL, OPTIMIZED PROMPT WITH YOUR SCHEMA ---
    
    # Define the instruction templates
    header = "You are a professional-grade assistant skilled at converting raw material (text, PDFs, transcripts, or links) into presentation JSON."
    
    instructions = f"""
    You must return a valid JSON array detailing the source text into slides according to the {len(image_paths)} images provided to you. The number of slides must be the same as the number of images attached.
    
    Adhere to these properties:
     - JSON: Use double quotes (Standard ASCII, no smart Quotes); no markdown, comments, or unescaped backslashes.
     - Slides: 2–5 bullets (under 80 characters each) that explain the image's content based on the source text. Use sub-bullets if necessary.
     - Speaker Notes: A detailed paragraph for each slide.
     - Narrative Flow: Ensure the content flows logically from one slide to the next.
    """
    
    output_schema_example = """
    Output strictly adheres to the following schema:
    [
      {
        "slide_title": "Required: Title (2-3 Words Max)",
        "slide_content": [
          "Bullet 1 – ≤40 chars",
          "Bullet 2 – ≤40 chars",
          "(Sub-bullet – ≤80 chars)"
        ],
        "speaker_notes": "Required: Detailed paragraph covering everything given in the source related to the image for the slide."
      }
    ]
    """

    # Assemble the final prompt
    prompt = f"""
    {header}

    <instructions>
    {instructions}
    </instructions>

    <output_example>
    {output_schema_example}
    </output_example>

    **SOURCE MATERIAL:**
    ---
    {source_text}
    ---

    **IMAGE CATALOG:**
    [Image 1, Image 2, ...]

    Now, generate ONLY the raw JSON output based on these instructions.
    """
    
    prompt_parts = [prompt]
    for img_path in image_paths:
        try:
            img = Image.open(img_path)
            prompt_parts.append(img)
        except Exception as e:
            print(f"Warning: Could not open image {img_path}, skipping. Error: {e}")
            
    try:
        response = model.generate_content(prompt_parts)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except (json.JSONDecodeError, AttributeError, Exception) as e:
        print(f"An error occurred while generating content for a batch: {e}")
        # Return a list of error slides matching the batch size
        return [
            {
                "slide_title": "AI Generation Error",
                "slide_content": ["The AI failed to generate content for this batch."],
                "speaker_notes": "This might be due to an API issue or a problem with the prompt."
            }
        ] * len(image_paths)


def generate_outline_from_text(source_text: str, desired_slide_count: int | None = None) -> List[dict]:
    """Generate a slide-wise outline using only the provided source material."""
    if isinstance(model, _NoopModel):
        raise RuntimeError("Google AI Model is not configured. Check API Key.")

    if desired_slide_count is not None:
        try:
            desired_slide_count = max(1, int(desired_slide_count))
        except (TypeError, ValueError):
            desired_slide_count = None

    slide_guidance = (
        f"- Create exactly {desired_slide_count} slide entries."
        if desired_slide_count
        else "- Create 6-10 slide entries depending on the richness of the material."
    )

    prompt = f"""
You are an expert presentation strategist. Based only on the SOURCE TEXT below,
produce a high-level outline for a compelling presentation.

Guidelines:
- Return ONLY valid JSON (no Markdown fences).
{slide_guidance}
- Each slide entry must contain:
  * "slide_title": Title with ≤6 words.
  * "bullet_outline": Array of 2-4 concise bullet sentences (≤90 characters each).
- Focus on logical progression and ensure coverage of key ideas from the source.
- Omit speaker notes, imagery, or styling instructions.

SOURCE TEXT:
---
{source_text}
---

Respond with the JSON array only.
"""

    try:
        response = model.generate_content(prompt)
        cleaned = response.text.strip().replace("```json", "").replace("```", "")
        outline = json.loads(cleaned)
        if not isinstance(outline, list):
            raise ValueError("Outline response is not a list")
        return outline
    except Exception as exc:
        raise RuntimeError(f"Failed to generate outline: {exc}")


def generate_slide_plan(source_text: str, image_filenames: List[str]) -> List[dict]:
    """Lightweight wrapper to create a slide plan from raw text and image names.

    The CI tests mock the underlying Gemini call; this helper keeps the real
    implementation centralized while providing an easy seam for testing.
    """
    if isinstance(model, _NoopModel):
        raise RuntimeError("Google AI Model is not configured. Check API Key.")

    image_catalog = "\n".join(f"- {name}" for name in image_filenames)
    prompt = f"""
You are a professional-grade assistant skilled at turning raw source material into
presentation JSON.

SOURCE TEXT:
{source_text}

IMAGE LIST:
{image_catalog}

Return ONLY valid JSON per the documented schema.
"""

    response = model.generate_content(prompt)
    cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
    return json.loads(cleaned_response)
