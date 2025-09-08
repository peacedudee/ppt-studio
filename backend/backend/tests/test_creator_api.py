from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_submit_assets_for_plan_generation():
    """
    Tests that a user can upload a source document and multiple image files
    to the creator endpoint and that a background task is correctly queued.
    """
    # We will mock the new Celery task we're about to create
    with patch('backend.app.main.generate_slide_plan_task.delay') as mock_task:
        # Create dummy files to simulate a multi-file upload
        dummy_pdf = ("source.pdf", b"fake pdf content", "application/pdf")
        dummy_img1 = ("image1.png", b"fake png content", "image/png")
        dummy_img2 = ("image2.jpg", b"fake jpg content", "image/jpeg")
        
        # The TestClient accepts a list of tuples for multi-file uploads
        files = [
            ('files', dummy_pdf),
            ('files', dummy_img1),
            ('files', dummy_img2),
        ]
        
        # POST the files to our new creator endpoint
        response = client.post("/api/v1/creator/generate-plan", files=files)
        
        # 1. Assert the API returns the correct status code (202 Accepted)
        assert response.status_code == 202
        
        # 2. Assert the response body contains a 'job_id'
        data = response.json()
        assert "job_id" in data
        
        # 3. Assert that our background task was actually called once
        mock_task.assert_called_once()