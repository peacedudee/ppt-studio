from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_generate_outline_starts_task_with_file():
    """Ensure outline generation uploads the document and schedules the worker."""
    with patch('backend.app.main.generate_outline_task.apply_async') as mock_task:
        dummy_pdf = ("source.pdf", b"fake pdf content", "application/pdf")

        response = client.post(
            "/api/v1/creator/generate-outline",
            data={'slide_count': '7'},
            files={"source_file": dummy_pdf},
        )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["outline_task_id"].endswith("-outline")
        assert data["slide_count"] == 7
        mock_task.assert_called_once()
        task_kwargs = mock_task.call_args.kwargs["kwargs"]
        assert "slide_count" not in task_kwargs


def test_generate_outline_with_pasted_text():
    with patch('backend.app.main.generate_outline_task.apply_async') as mock_task:
        response = client.post(
            "/api/v1/creator/generate-outline",
            data={'source_text': 'Inline outline source text', 'slide_count': '5'},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["slide_count"] == 5
        mock_task.assert_called_once()
        assert "slide_count" not in mock_task.call_args.kwargs["kwargs"]


def test_generate_outline_requires_input():
    response = client.post("/api/v1/creator/generate-outline")
    assert response.status_code == 400


def test_submit_assets_for_plan_generation():
    """Verify plan generation accepts files and queues the Celery task."""
    with patch('backend.app.main.generate_slide_plan_task.apply_async') as mock_task:
        dummy_pdf = ("source.pdf", b"fake pdf content", "application/pdf")
        dummy_img1 = ("image1.png", b"fake png content", "image/png")
        dummy_img2 = ("image2.jpg", b"fake jpg content", "image/jpeg")

        files = [
            ('files', dummy_pdf),
            ('files', dummy_img1),
            ('files', dummy_img2),
        ]

        response = client.post("/api/v1/creator/generate-plan", files=files)

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert "plan_task_id" in data
        mock_task.assert_called_once()
        task_kwargs = mock_task.call_args.kwargs["kwargs"]
        assert task_kwargs["image_strategy"] == "uploaded"


def test_uploaded_strategy_requires_image():
    with patch('backend.app.main.generate_slide_plan_task.apply_async'):
        dummy_pdf = ("source.pdf", b"fake pdf content", "application/pdf")

        response = client.post(
            "/api/v1/creator/generate-plan",
            files=[('files', dummy_pdf)],
        )

        assert response.status_code == 400


def test_unsplash_strategy_without_job_id_is_rejected():
    with patch('backend.app.main.generate_slide_plan_task.apply_async'):
        response = client.post(
            "/api/v1/creator/generate-plan",
            data={'image_strategy': 'unsplash'},
        )

        assert response.status_code == 400
