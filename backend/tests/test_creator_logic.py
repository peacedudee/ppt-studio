import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# We will create both of these functions in the creator_logic module
from backend.worker.creator_logic import extract_text_from_document, generate_slide_plan

def test_extract_text_from_pdf():
    """
    Tests that text can be successfully extracted from a sample PDF file.
    """
    test_file_path = Path(__file__).parent / "sample.pdf"
    assert test_file_path.exists(), "Test file 'sample.pdf' not found in tests/ directory."

    extracted_text = extract_text_from_document(str(test_file_path))

    assert "quick brown fox" in extracted_text.lower()

# --- Add this new test function ---
def test_generate_slide_plan():
    """
    Tests that the AI is prompted correctly and that its JSON response is parsed.
    """
    # 1. Define our test inputs
    sample_text = "AI is transforming healthcare by improving diagnostics and personalizing treatments."
    image_filenames = ["chart.png", "doctor.jpg"]
    
    # 2. Define the fake JSON response we want our mock AI to return
    fake_json_response = json.dumps([
        {
            "slide_title": "AI in Healthcare",
            "slide_content": ["Improves diagnostics", "Personalizes treatments"],
            "speaker_notes": "Discuss the impact of AI on modern medicine."
        }
    ])

    # 3. Mock the Gemini model's generate_content method
    with patch('backend.worker.creator_logic.model.generate_content') as mock_generate_content:
        # Configure the mock to return our fake response
        mock_response = MagicMock()
        mock_response.text = fake_json_response
        mock_generate_content.return_value = mock_response

        # 4. Call the function we are testing
        slide_plan = generate_slide_plan(sample_text, image_filenames)

        # 5. Assertions
        # Check that the AI was called
        mock_generate_content.assert_called_once()
        
        # Check that the prompt contained our source text and image names
        prompt_sent_to_ai = mock_generate_content.call_args[0][0]
        assert sample_text in prompt_sent_to_ai
        assert "chart.png" in prompt_sent_to_ai
        assert "doctor.jpg" in prompt_sent_to_ai
        
        # Check that the function correctly parsed the JSON into a Python list
        assert isinstance(slide_plan, list)
        assert slide_plan[0]["slide_title"] == "AI in Healthcare"