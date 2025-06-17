#!/usr/bin/env python3
"""
Test script to verify Gemini connection using google.genai library.
"""

import os
import sys
from pathlib import Path
from google import genai
from google.genai import types
import vertexai

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings


def test_gemini_connection():
    """Test the Gemini connection and basic functionality."""
    print("=== Testing Gemini Connection ===\n")
    
    # Configuration
    print("Configuration:")
    print(f"- Google Cloud Project: {settings.GOOGLE_CLOUD_PROJECT}")
    print(f"- Google Cloud Location: {settings.GOOGLE_CLOUD_LOCATION}")
    print(f"- Credentials Path: {settings.GOOGLE_APPLICATION_CREDENTIALS}")
    
    # Set environment variable for authentication
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(settings.GOOGLE_APPLICATION_CREDENTIALS)
        cred_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
        if cred_path.exists():
            print(f"\n✅ Credentials file found: {cred_path}")
        else:
            print(f"\n❌ Credentials file not found: {cred_path}")
            return False
    
    # Initialize Vertex AI
    print("\nInitializing Vertex AI...")
    try:
        vertexai.init(project=settings.GOOGLE_CLOUD_PROJECT, location=settings.GOOGLE_CLOUD_LOCATION)
        print("✅ Vertex AI initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Vertex AI: {e}")
        return False
    
    # Initialize genai client
    print("\nInitializing genai client...")
    try:
        client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
        )
        print("✅ genai client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize genai client: {e}")
        return False
    
    # Test simple text generation
    print("\nTesting simple text generation...")
    try:
        prompt = "Say 'Hello from Gemini!' in exactly 5 words."
        
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=prompt,
        )
            
        print(f"✅ Response received: {response.text}")
        
        # Test with structured output
            print("\nTesting structured output...")
                test_email = """
                Subject: Project Update
                From: john@example.com
                
                Hi team,
                
                The project is going well. We completed the API integration yesterday.
                
                Action items:
                - Review the documentation by Friday
                - Schedule a demo for next week
                
                Overall, I'm feeling positive about our progress.
                
                Best,
                John
                """
                
        generate_content_config = types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=1024,
            response_modalities=["TEXT"],
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "summary": {"type": "STRING"},
                    "key_points": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "action_items": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"}
                    },
                    "sentiment": {"type": "STRING"}
                }
            },
        )
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"Analyze this email:\n{test_email}")
                ]
            )
        ]
        
        response = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=contents,
            config=generate_content_config,
        )
        
                print("✅ Structured output received:")
        print(f"   Response: {response.text}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get response: {e}")
        return False


if __name__ == "__main__":
    print("Testing Gemini integration...\n")
    
    if settings.LLM_PROVIDER != "gemini":
        print(f"⚠️  LLM_PROVIDER is set to '{settings.LLM_PROVIDER}', not 'gemini'")
        print("   Update your .env file to test Gemini")
        sys.exit(1)
    
    success = test_gemini_connection()
    
    if success:
        print("\n✅ All tests passed! Gemini is configured correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check your configuration.")
        sys.exit(1) 