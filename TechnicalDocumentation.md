
***
## Technical Design Document: PPT Studio

**Version:** 3.0
**Date:** September 17, 2025

### 1. Introduction

#### 1.1. Project Overview
PPT Studio is a full-stack, AI-powered web application designed to be a comprehensive toolkit for PowerPoint presentations. It centralizes two major workflows: **enhancing** existing presentations with automated branding and AI-generated content, and **creating** new, professionally laid-out presentations from raw documents and images.

#### 1.2. Scope
* **In-Scope:**
    * **PPT Enhancer Workflow:** A UI-driven process to modify existing `.pptx` files with dynamic logos, custom credits, text-based watermark removal, repeating image removal, and AI-generated speaker notes.
    * **PPT Creator Workflow:** A multi-step UI wizard to generate new `.pptx` files from source documents (PDF, DOCX, TXT) and images. This includes AI-powered content planning, an interactive review/edit stage, and an intelligent layout engine.
    * **Feedback System:** A dedicated page for users to submit feedback, which is saved to a server-side CSV file.
    * **Deployment:** A fully automated CI/CD pipeline using GitHub Actions to deploy the application to Google Cloud (Cloud Run and Firebase Hosting).
* **Out-of-Scope:**
    * User accounts and authentication.
    * Saving and managing a user's presentation history.
    * Real-time collaboration.

---
### 2. System Architecture
The application uses a modern, decoupled client-server architecture designed for scalability and asynchronous processing.



* **Frontend:** A **React SPA (Single Page Application)** built with Vite and the Mantine component library. It handles all user interaction and communicates with the backend API.
* **Backend API:** A **Python/FastAPI** server that handles HTTP requests, manages file storage, and dispatches long-running jobs to a task queue. It is deployed as a stateless container on **Google Cloud Run**.
* **Background Worker:** A **Python/Celery** worker that performs all heavy processing (PPT manipulation, AI calls, file parsing). It is deployed as a separate, non-public service on **Google Cloud Run**.
* **Task Queue:** A managed **Memorystore for Redis** instance on Google Cloud, which acts as the message broker between the API and the Worker.
* **Container Registry:** **Google Artifact Registry** stores the production Docker images for the backend.
* **Static Hosting:** **Firebase Hosting** serves the React frontend, providing a global CDN for fast load times.

---
### 3. Technology Stack

| Component | Technology | Justification |
|---|---|---|
| **Frontend** | React.js, Vite, Mantine | Modern, fast, component-based UI with a professional design system. |
| **Backend API** | Python 3.10, FastAPI, Gunicorn | High-performance, async-capable Python framework with a production-grade server. |
| **PPT Manipulation** | `python-pptx`, `Pillow`, `imagehash` | Robust libraries for creating, modifying, and analyzing presentation files and images. |
| **Document Parsing**| `PyMuPDF`, `python-docx` | Efficient libraries for extracting text from source documents. |
| **Task Queue** | Celery, Redis (Memorystore) | Industry-standard for reliable, scalable background job processing in Python. |
| **Containerization**| Docker | Ensures a consistent environment from local development to cloud production. |
| **LLM Service** | Google Gemini API (`1.5-pro`) | Powerful multimodal (text and image) model for high-quality content generation. |
| **Deployment** | Google Cloud Run, Firebase Hosting | Serverless, scalable, and cost-effective solutions for hosting containers and web apps. |
| **CI/CD** | GitHub Actions | Native, powerful automation for building, testing, and deploying directly from the source repository. |

---
### 4. Detailed Workflows & Logic

#### 4.1. PPT Enhancer Workflow
A guided, three-step wizard in the UI allows users to:
1.  Upload a `.pptx` file via a large drag-and-drop zone.
2.  Optionally upload a custom logo image and provide custom credits text.
3.  Submit the job. The backend task then:
    * Removes text-based watermarks from slide masters and individual slides.
    * Removes frequently repeating images (identified by perceptual hashing) from masters, layouts, and slides.
    * Adds the specified logo and credits.
    * Generates AI speaker notes for each slide.
    * The frontend polls a status endpoint and provides a download link upon completion.

#### 4.2. PPT Creator Workflow
A guided, multi-step wizard in the UI allows users to:
1.  Upload a single source document (PDF, DOCX, TXT).
2.  Upload multiple images, which can be reordered via drag-and-drop.
3.  Trigger an AI plan generation task. The backend worker:
    * Extracts text from the source document.
    * Sends the full text and batches of images to the multimodal Gemini API.
    * Generates a structured `slides.json` plan.
4.  Review and edit the AI-generated titles, bullets, and notes in an interactive UI that shows a preview of the corresponding image.
5.  Trigger a final build task. The backend worker:
    * Reads the (potentially edited) `slides.json` and images.
    * Uses an intelligent layout engine to build a `.pptx` file, choosing between side-by-side or top-and-bottom layouts based on image classification to prevent content overflow.
    * The frontend polls for status and provides a final download link.

---
### 5. API Specification
The API exposes endpoints for health checks, job status, file downloads, and feedback, in addition to the primary workflow endpoints:

* `POST /api/v1/enhancer/process`: Accepts `ppt_file`, optional `logo_file`, and `credits_text` to start an enhancement job.
* `POST /api/v1/creator/generate-plan`: Accepts multiple `files` (source doc + images) to start a plan generation job.
* `POST /api/v1/creator/build/{job_id}`: Accepts an edited `slide_plan` in the request body to start the final build task.
* `POST /api/v1/feedback`: Accepts user feedback and saves it to a server-side CSV file.

---
### 6. Environment Configuration

#### 6.1. Environment Files
* `.env.development` — Local-only file checked out with the repository; sets `APP_ENV=development` and points Celery/Redis to the Docker Compose services.
* `.env.production` — Materialized during CI/CD from the Secret Manager entry `ppt-studio-prod-env`; the workflow appends `APP_ENV=production` before deploying.
* `.env` — Legacy file retained for backward compatibility; not referenced by the new tooling.

> **Security:** Both `.env.development` and `.env.production` are listed in `.gitignore`. Never commit secrets. Update the Secret Manager payload when production configuration changes (e.g., rotating Redis URLs or toggling `CELERY_ENABLE_RESULT_BACKEND`).

#### 6.2. Central Settings Module
`backend/config/settings.py` unifies environment lookups. Key outputs:
* `settings.celery_broker_url` and `settings.celery_backend_url` drive Celery configuration.
* `settings.gcs_bucket_name`, `settings.google_api_key`, and `settings.service_account_email` back the storage and Gemini dependencies.
* `settings.port` standardizes service ports for API and health endpoints.

The worker, API, and diagnostics modules import this settings object instead of calling `os.getenv` directly, ensuring parity between environments.

---
### 7. Runtime & Compose Profiles

#### 7.1. Local Development
Run the full stack with hot reload and a local Redis broker:
```
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```
This wires services to `.env.development`, mounts the backend code into the containers, and exposes Redis on `localhost:6379` for debugging.

The Vite frontend reads `VITE_API_URL` from `frontend/.env.development` (ignored by git). By default it points to `http://localhost:8000`, so `npm run dev` will call the locally running FastAPI service while the compose stack is up.

Both API and worker containers mount `./local-storage` into `/data/storage`, honoring `LOCAL_STORAGE_PATH=/data/storage` from `.env.development`. This keeps uploads and generated artifacts shared between services without touching cloud buckets.

#### 7.2. Production-equivalent Validation
Use the production override to inspect the final container wiring without launching Cloud Run:
```
docker compose -f docker-compose.yml -f docker-compose.prod.yml config
```
The CI workflow runs this command to catch configuration drift before deployment.

#### 7.3. CI/CD Integration
* `deploy.yml` triggers only on `main` branch pushes. It retrieves `.env.production` from Secret Manager, builds a single backend image, and deploys API + worker services to Cloud Run with `APP_ENV=production`.
* `ci-dev.yml` runs on `dev` pushes and pull requests. It executes backend pytest (with ephemeral Redis), validates the dev compose stack, and builds the frontend bundle.

---
### 8. Branching & Release Strategy

#### 8.1. Branch Roles
* `dev` — Integration branch for day-to-day development. Feature branches target `dev` via pull requests.
* `main` — Protected release branch; merging into `main` triggers production deployment.

#### 8.2. Protection Rules
Configure in GitHub → Settings → Branches:
1. **main rule:** Require pull requests, at least one approval, conversation resolution, and passing status checks (deploy workflow + CI). Optionally enforce linear history.
2. **dev rule (optional):** Require pull requests and passing `CI (dev branch)` checks to keep the branch green while allowing fast iteration.

#### 8.3. Promotion Flow
1. Branch from `dev` for new work; open a PR back into `dev` when ready.
2. After stabilizing, open a PR from `dev` into `main`. Resolve conflicts, ensure CI passes, then merge.
3. The merge deploys to production. Immediately back-merge `main` into `dev` to sync hotfixes and version bumps.

#### 8.4. Hotfix Procedure
For urgent fixes, branch from `main`, patch, and PR directly into `main`. After deployment, merge `main` back into `dev` so the fix propagates.
