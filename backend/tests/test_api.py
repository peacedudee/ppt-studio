import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health_check():
    """Tests if the API is running and reachable."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_submit_ppt_for_enhancement_with_branding():
    """
    Tests uploading a pptx, a custom logo, and custom credits text.
    Verifies the background task is called with the correct parameters.
    """
    # Patch the enhance_ppt_task where it's used in the main app
    with patch('backend.app.main.enhance_ppt_task.delay') as mock_task:
        # Define the custom branding data
        custom_credits = "Custom Credits by Anju"
        
        # Prepare the files for upload
        dummy_ppt = ("test.pptx", b"fake pptx content", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
        dummy_logo = ("custom_logo.png", b"fake logo content", "image/png")
        
        # The TestClient sends form data in 'data' and files in 'files'
        response = client.post(
            "/api/v1/enhancer/process",
            files={
                "ppt_file": dummy_ppt,
                "logo_file": dummy_logo
            },
            data={
                "credits_text": custom_credits
            }
        )

        # Assert API response is correct
        assert response.status_code == 202
        assert "job_id" in response.json()
        
        # Assert that our Celery task was called with the new arguments
        mock_task.assert_called_once()
        call_args = mock_task.call_args[0]
        
        # Check that the task received the filenames and custom text
        assert "test.pptx" in call_args[0] # input_path
        assert "custom_logo.png" in call_args[2] # logo_path
        assert call_args[3] == custom_credits # credits_text