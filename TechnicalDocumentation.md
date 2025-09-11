Of course. Here is the final Technical Design Document, updated to reflect all the features, architectural decisions, and workflows we've built and refined together.

This document represents the complete state of the PPT Studio application as of our last development sprint.

***
## Final Technical Design Document: PPT Studio

**Version:** 3.0
**Date:** September 11, 2025
**Status:** Feature Complete

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