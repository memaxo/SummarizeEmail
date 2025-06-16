import pytest
import base64
from app.services import document_parser

def test_parse_valid_text_content():
    """
    Tests that the parser can correctly decode and extract text from a simple
    base64-encoded text file.
    """
    # 1. Prepare the test data
    original_text = "This is a test document."
    base64_encoded_text = base64.b64encode(original_text.encode('utf-8')).decode('utf-8')
    
    # 2. Call the service
    parsed_text = document_parser.parse_content(base64_encoded_text)
    
    # 3. Assert the result
    # The strip() is to handle any potential trailing newlines from parsing.
    assert parsed_text is not None
    assert parsed_text.strip() == original_text

def test_parse_empty_content():
    """
    Tests that the parser returns None for empty or None input.
    """
    assert document_parser.parse_content(None) is None
    assert document_parser.parse_content("") is None

def test_parse_invalid_base64():
    """
    Tests that the parser handles invalid base64 input gracefully.
    """
    # This is not a valid base64 string
    invalid_base64 = "this is not base64"
    # It should not raise an error, but return None
    assert document_parser.parse_content(invalid_base64) is None 