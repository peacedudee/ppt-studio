// The base URL of our FastAPI backend
const API_BASE_URL = "https://ppt-studio-api-43q6ygpsma-el.a.run.app";

/**
 * Uploads files and data to the PPT Enhancer endpoint.
 * @param {File} pptFile - The main .pptx file.
 * @param {File} [logoFile] - An optional logo file.
 * @param {string} [creditsText] - Optional custom credits text.
 * @returns {Promise<object>} - The JSON response from the API.
 */
export async function enhancePresentation(pptFile, logoFile, creditsText) {
  const formData = new FormData();
  
  formData.append("ppt_file", pptFile);
  if (logoFile) {
    formData.append("logo_file", logoFile);
  }
  if (creditsText) {
    formData.append("credits_text", creditsText);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/enhancer/process`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Uploads source document and images to generate a slide plan.
 * @param {FileList} files - The files to upload.
 * @returns {Promise<object>} - The JSON response from the API.
 */
export async function generateSlidePlan(files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/creator/generate-plan`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
  return response.json();
}

/**
 * Sends the edited slide plan to trigger the final PPTX build on the backend.
 * @param {string} jobId - The ID of the job to build.
 * @param {object} slidePlan - The (potentially edited) slide plan.
 * @returns {Promise<object>}
 */
export async function buildPresentation(jobId, slidePlan) {
  const response = await fetch(`${API_BASE_URL}/api/v1/creator/build/${jobId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(slidePlan), // Send the edited plan in the request body
  });
  if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
  return response.json();
}

/**
 * Polls the backend for the status of a job.
 * @param {string} jobId - The ID of the job to check.
 * @returns {Promise<object>}
 */
export async function getJobStatus(jobId) {
  const response = await fetch(`${API_BASE_URL}/api/v1/jobs/status/${jobId}`);
  if (!response.ok) throw new Error(`API Error: ${response.statusText}`);
  return response.json();
}

// ... (all existing functions)

/**
 * Submits feedback to the backend.
 * @param {object} feedbackData - The feedback data from the form.
 * @returns {Promise<object>}
 */
export async function submitFeedback(feedbackData) {
  const response = await fetch(`${API_BASE_URL}/api/v1/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(feedbackData),
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }

  return response.json();
}