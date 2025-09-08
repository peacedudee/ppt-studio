
## Final Technical Design Document: PPT Studio

**Version:** 2.0  
**Date:** September 2, 2025  
**Status:** Finalized for Development

### 1\. Introduction

#### 1.1. Project Overview

PPT Studio is a dual-function web application designed to be a comprehensive toolkit for PowerPoint presentations. It centralizes two major workflows: **creating** new presentations from raw materials using AI and **enhancing** existing presentations with standardized branding and AI-generated content.

#### 1.2. Goals and Objectives

  * **Efficiency:** Drastically reduce the manual effort and time required to create and standardize presentations.
  * **Consistency:** Ensure all presentations adhere to brand guidelines by automatically applying logos, credits, and removing unwanted watermarks.
  * **Quality:** Improve the quality of presentations by leveraging an LLM to generate well-structured content and insightful speaker notes.
  * **Usability:** Provide a simple, intuitive web interface that abstracts away the complexity of the underlying processes.

#### 1.3. Scope

  * **In-Scope:**
      * **Creator Workflow:** Generation of `.pptx` files from uploaded source documents (PDF, DOCX, TXT) and image files.
      * **Enhancer Workflow:** Modification of existing `.pptx` files.
      * Automated addition of a pre-configured logo and credits link.
      * Surgical removal of watermark shapes from slide masters.
      * LLM-based generation of slide content plans (`slides.json`) and speaker notes.
      * Asynchronous job processing with status tracking.
      * A web-based user interface for all functionalities.
  * **Out-of-Scope (for V1.0):**
      * User authentication and multi-user accounts.
      * Real-time collaboration or editing.
      * Support for file formats other than those specified.
      * Dynamic, user-configurable branding (logo, colors, fonts) via the UI.
      * Saving/managing a library of user presentations.

-----

### 2\. System Architecture

The system is designed as a decoupled, scalable web service.

#### 2.1. Component Breakdown

  * **Frontend (React SPA):** A self-contained single-page application responsible for all user interactions. It handles file uploads, renders job status, displays the "Review & Edit" interface for the Creator workflow, and communicates with the Backend API via RESTful calls.
  * **Backend API (Python/FastAPI):** The central control unit. It exposes the API endpoints, handles initial requests and validation, saves uploaded files to temporary storage, and dispatches jobs to the Celery task queue. It does **not** perform heavy processing itself, ensuring it remains highly responsive.
  * **Task Queue (Celery & Redis):** The asynchronous core of the application. Redis acts as a message broker, holding a queue of tasks. Celery workers subscribe to this queue. This decouples the long-running PPT processing from the user's web request, preventing timeouts and allowing for horizontal scaling.
  * **Worker Processes (Python/Celery):** Independent processes that execute the actual business logic. They pull tasks from the Redis queue and perform the computationally expensive operations: parsing documents, calling the LLM API, and building/modifying `.pptx` files using the `python-pptx` library.
  * **Temporary File Storage:** A designated storage volume for holding user-uploaded files and the final generated presentations. For local development, this can be a Docker volume. For production, a cloud solution like an **AWS S3 bucket** or **Google Cloud Storage** is recommended for scalability and persistence.
  * **External Services:**
      * **LLM API (Google Gemini):** A third-party dependency for all AI-powered text generation tasks.

-----

### 3\. Technology Stack

| Component               | Technology                        | Justification                                                                                                                                   |
| ----------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Frontend** | **React.js** | A mature, component-based library ideal for building dynamic, multi-step user interfaces. Strong community and ecosystem.                           |
| **Backend API** | **Python 3.10+ / FastAPI** | Python is required for the core `python-pptx` library. FastAPI provides high performance, automatic API documentation (Swagger UI), and modern async support. |
| **PPT Manipulation** | **`python-pptx`** | The definitive library for programmatically creating and manipulating `.pptx` files in Python.                                                   |
| **Document Parsing** | **`PyMuPDF`, `python-docx`** | Proven, efficient libraries for accurately extracting text content from PDF and DOCX files, respectively.                                       |
| **Task Queue** | **Celery & Redis** | The industry standard in the Python ecosystem for robust, scalable asynchronous task processing.                                                  |
| **Containerization** | **Docker & Docker Compose** | Ensures a consistent and reproducible environment across development and production, simplifying dependency management.                            |
| **LLM Service** | **Google Gemini API** | Provides powerful and context-aware text generation capabilities necessary for creating slide plans and speaker notes.                         |

-----

### 4\. Detailed Workflows & Logic

#### 4.1. Workflow 1: PPT Enhancer

This workflow modifies an existing `.pptx` file.

1.  **Upload:** The user uploads a `.pptx` file via the frontend.
2.  **API Call:** The frontend sends a `POST` request to `/api/v1/enhancer/process` with the file.
3.  **Job Creation:** The API saves the file to temporary storage and creates a Celery task named `enhance_presentation`, passing the file's path. It immediately returns a `job_id` to the user.
4.  **Worker Execution:** A Celery worker picks up the task and executes the following sequence:
    a. Loads the presentation using `prs = Presentation(file_path)`.
    b. Calls `remove_master_slide_watermarks(prs)`. This function iterates through `prs.slide_masters`, finds shapes matching watermark heuristics (keywords, position), and deletes them.
    c. Iterates through each `slide` in `prs.slides`.
    d. For each slide, it calls `add_logo(slide)` and `add_credits(slide)`.
    e. It then calls `generate_speaker_notes(slide)`, which extracts slide text, prompts the LLM, and injects the response into `slide.notes_slide`.
5.  **Save & Complete:** The worker saves the modified presentation to a new file (e.g., `original-name_enhanced.pptx`) and updates the job status to "completed."
6.  **Download:** The frontend, which has been polling the `/api/v1/status/{job_id}` endpoint, sees the "completed" status and displays a download link pointing to `/api/v1/download/{job_id}`.

#### 4.2. Workflow 2: PPT Creator

This workflow creates a new `.pptx` file from scratch.

1.  **Upload Assets:** The user uploads source documents (e.g., `source.pdf`) and multiple images (`image1.png`, `image2.jpg`) via the frontend.
2.  **API Call 1 (Plan Generation):** The frontend sends a `POST` request to `/api/v1/creator/generate-plan` with all files.
3.  **Job Creation (Plan):** The API saves all files to a unique directory in storage and creates a Celery task named `generate_slide_plan`. It returns a `job_id`.
4.  **Worker Execution (Plan):** The worker picks up the task:
    a. It uses `PyMuPDF` or `python-docx` to extract all text from the source document.
    b. It constructs a detailed prompt for the LLM, including the extracted text and the list of image filenames.
    c. It calls the LLM, requesting a response that strictly follows the `slides.json` schema.
    d. The worker validates the returned JSON. It then saves the JSON plan and updates the job status, associating the plan with the `job_id`.
5.  **Review & Edit:** The frontend polls for the plan generation status. Once complete, it fetches the `slides.json` plan and displays it in an editable interface for the user.
6.  **API Call 2 (Build):** After making edits, the user clicks "Build." The frontend sends a `POST` request to `/api/v1/creator/build` with the `job_id` and the final, user-approved JSON plan.
7.  **Job Creation (Build):** The API queues a final Celery task named `build_presentation`, returning a `build_id`.
8.  **Worker Execution (Build):** The worker picks up the build task:
    a. It loads the `slides.json` and the associated image files from storage.
    b. It executes the core logic from `dynamic_ppt_builder.py`, creating a new presentation, iterating through the JSON objects, and adding a slide for each one with the specified title, content, and corresponding image.
9.  **Save & Complete:** The worker saves the newly created `.pptx` file and updates the build job's status.
10. **Download:** The user retrieves the final file via the status/download endpoints.

-----

### 5\. API Specification

  * **Enhancer Endpoints:**
      * `POST /api/v1/enhancer/process`
          * **Request:** `multipart/form-data` with a single `.pptx` file.
          * **Response:** `202 Accepted` - `{"job_id": "uuid"}`
  * **Creator Endpoints:**
      * `POST /api/v1/creator/generate-plan`
          * **Request:** `multipart/form-data` with source document(s) and image files.
          * **Response:** `202 Accepted` - `{"job_id": "uuid"}`
      * `POST /api/v1/creator/build`
          * **Request Body (JSON):** `{"job_id": "uuid", "slide_plan": [...]}`
          * **Response:** `202 Accepted` - `{"build_id": "uuid"}`
  * **Common Endpoints:**
      * `GET /api/v1/status/{job_id}`
          * **Response:** `200 OK` - `{"job_id": "uuid", "status": "processing|completed|failed", "result_url": "/api/v1/download/...", "slide_plan": [...] | null}`
      * `GET /api/v1/download/{job_id}`
          * **Response:** The `.pptx` file stream.

-----

### 6\. Data Models

#### 6.1. `slides.json` Schema (for Creator)

This is the contract between the LLM and the PPT builder script.

```json
[
  {
    "slide_title": "Required: A concise title (2-5 words)",
    "slide_content": [
      "Required: A list of bullet points for the slide.",
      "Each bullet should be a string.",
      "The LLM should aim for 2-5 bullets per slide."
    ],
    "speaker_notes": "Required: A detailed paragraph for the speaker."
  }
]
```

-----

### 7\. Deployment & Infrastructure

  * **Containerization:** The application will be packaged using `docker-compose.yml`, defining services for the `api`, `worker`, and `redis`. This guarantees a consistent runtime environment.
  * **Environment Variables:** The application will be configured via environment variables, not hardcoded values. Critical variables include:
      * `GOOGLE_API_KEY`: For authenticating with the Gemini API.
      * `REDIS_URL`: The connection string for the Redis broker.
      * `TEMP_STORAGE_PATH`: The file path for storing uploads.
      * `LOGO_FILE_PATH`: Path to the standard company logo image.
      * `CREDITS_TEXT` & `CREDITS_URL`: For the credits hyperlink.
  * **Logging:** All services (API and workers) should log structured output (e.g., JSON format) to `stdout`. This allows for easy integration with log aggregation services like Datadog or ELK Stack.

-----

### 8\. Assumptions, Risks, and Mitigation

| Risk                                   | Description                                                                                             | Mitigation Strategy                                                                                                                                                             |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **LLM Unpredictability / Errors** | The LLM may return malformed JSON, irrelevant content, or fail entirely.                                | **Schema Validation:** The worker must rigorously validate the LLM's JSON response against the required schema before proceeding. **Retry Logic:** Implement an exponential backoff retry mechanism for API calls. **User Review:** The "Review & Edit" step in the Creator workflow is a critical human-in-the-loop check. |
| **Incorrect Watermark Deletion** | The master slide heuristic may incorrectly delete a legitimate footer or non-watermark shape.           | **Configuration & Logging:** Make the watermark keywords and position heuristics configurable via environment variables. Log every shape deletion for easy debugging.                   |
| **Poor Document Parsing** | The text extraction from a poorly formatted or scanned PDF may be inaccurate, leading to poor AI content. | **User Notification:** If a document yields very little text, notify the user that the quality of the AI-generated content may be low. Explicitly state that scanned/image-based PDFs are not supported. |
| **Processing Time & Cost** | Large presentations or numerous LLM calls can be slow and expensive.                                      | **Asynchronous Architecture:** The Celery/Redis architecture is designed specifically to handle this. **User Feedback:** The UI must provide clear feedback that the job is processing in the background. Cost monitoring for the LLM API is essential. |
| **Dependency on External Tools** | The system relies entirely on the availability and performance of the external LLM API.                 | **Circuit Breaker:** Implement a circuit breaker pattern to temporarily halt sending requests to a failing or slow LLM API. Provide clear error messages to the user. |