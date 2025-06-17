#!/usr/bin/env python3
"""
Test script to verify Gemini Vertex AI connection and configuration.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.services.email import _get_llm


def test_gemini_connection():
    """Test the Gemini connection and basic functionality."""
    print("=== Testing Gemini Vertex AI Connection ===\n")
    
    # Check configuration
    print("Configuration:")
    print(f"- LLM Provider: {settings.LLM_PROVIDER}")
    print(f"- Google Cloud Project: {settings.GOOGLE_CLOUD_PROJECT}")
    print(f"- Google Cloud Location: {settings.GOOGLE_CLOUD_LOCATION}")
    print(f"- Credentials Path: {settings.GOOGLE_APPLICATION_CREDENTIALS}")
    print(f"- Model Name: {settings.GEMINI_MODEL_NAME}")
    
    # Verify credentials file exists
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        cred_path = Path(settings.GOOGLE_APPLICATION_CREDENTIALS)
        if cred_path.exists():
            print(f"\n✅ Credentials file found: {cred_path}")
        else:
            print(f"\n❌ Credentials file not found: {cred_path}")
            return False
    else:
        print("\n⚠️  Using API key authentication (not service account)")
    
    # Test LLM initialization
    print("\nInitializing LLM...")
    try:
        llm = _get_llm()
        print("✅ LLM initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize LLM: {e}")
        return False
    
    # Test a simple prompt
    print("\nTesting simple prompt...")
    try:
        test_prompt = "Say 'Hello from Gemini!' in exactly 5 words."
        response = llm.invoke(test_prompt)
        
        # Extract content from response
        if hasattr(response, 'content'):
            response_text = response.content
        else:
            response_text = str(response)
            
        print(f"✅ Response received: {response_text}")
        
        # Test structured output if supported
        if settings.LLM_PROVIDER in ["gemini", "openai"]:
            print("\nTesting structured output...")
            from app.services.email import EmailSummary
            
            try:
                structured_llm = llm.with_structured_output(EmailSummary)
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
                
                result = structured_llm.invoke(f"Analyze this email:\n{test_email}")
                print("✅ Structured output received:")
                print(f"   - Summary: {result.summary[:50]}...")
                print(f"   - Key Points: {len(result.key_points)} items")
                print(f"   - Action Items: {len(result.action_items)} items")
                print(f"   - Sentiment: {result.sentiment}")
            except Exception as e:
                print(f"⚠️  Structured output test failed: {e}")
                print("   (This is optional - basic functionality still works)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get response: {e}")
        return False


if __name__ == "__main__":
    print("Testing Gemini Vertex AI integration...\n")
    
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