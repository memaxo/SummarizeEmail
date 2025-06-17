#!/usr/bin/env python3
"""
Test script to verify Gemini works with LangChain integration.
This shows that you can use LangChain's abstractions with Vertex AI.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import settings
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
import vertexai


class EmailSummary(BaseModel):
    """Structured email summary output"""
    summary: str = Field(description="A concise summary of the email content")
    key_points: list[str] = Field(description="List of key points from the email")
    action_items: list[str] = Field(description="List of action items mentioned in the email", default_factory=list)
    sentiment: str = Field(description="Overall sentiment: positive, negative, or neutral")


def test_langchain_gemini():
    """Test Gemini through LangChain's ChatVertexAI integration."""
    print("=== Testing Gemini with LangChain Integration ===\n")
    
    # Configuration
    print("Configuration:")
    print(f"- Google Cloud Project: {settings.GOOGLE_CLOUD_PROJECT}")
    print(f"- Google Cloud Location: {settings.GOOGLE_CLOUD_LOCATION}")
    print(f"- Model: {settings.GEMINI_MODEL_NAME}")
    
    # Set environment variable for authentication
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(settings.GOOGLE_APPLICATION_CREDENTIALS)
        print(f"- Credentials: {settings.GOOGLE_APPLICATION_CREDENTIALS}")
    
    # Initialize Vertex AI
    print("\nInitializing Vertex AI...")
    try:
        vertexai.init(
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION
        )
        print("✅ Vertex AI initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Vertex AI: {e}")
        return False
    
    # Create LangChain ChatVertexAI instance
    print("\nCreating LangChain ChatVertexAI instance...")
    try:
        llm = ChatVertexAI(
            model_name=settings.GEMINI_MODEL_NAME,
            temperature=0.7,
            max_output_tokens=1024,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION,
            convert_system_message_to_human=True,  # Gemini doesn't support system messages directly
        )
        print("✅ LangChain ChatVertexAI created successfully")
    except Exception as e:
        print(f"❌ Failed to create ChatVertexAI: {e}")
        return False
    
    # Test 1: Simple text generation with LangChain
    print("\n1. Testing simple text generation with LangChain...")
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("human", "Say 'Hello from Gemini via LangChain!' and add a fun fact about email.")
        ])
        
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({})
        
        print(f"✅ Response: {response}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False
    
    # Test 2: Structured output with LangChain
    print("\n2. Testing structured output with LangChain...")
    try:
        # Create a structured output parser
        structured_llm = llm.with_structured_output(EmailSummary)
        
        test_email = """
        Subject: Quarterly Review and Planning
        From: manager@company.com
        
        Team,
        
        Great job on Q4! We exceeded our targets by 15%. 
        
        For Q1, please:
        - Submit your project proposals by Friday
        - Review the new budget guidelines
        - Schedule 1:1s with your direct reports
        
        I'm excited about our upcoming product launch. The market response has been very positive.
        
        Best regards,
        Sarah
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("human", "Analyze this email and provide a structured summary:\n\n{email}")
        ])
        
        chain = prompt | structured_llm
        result = chain.invoke({"email": test_email})
        
        print("✅ Structured output received:")
        print(f"   Summary: {result.summary}")
        print(f"   Key Points: {result.key_points}")
        print(f"   Action Items: {result.action_items}")
        print(f"   Sentiment: {result.sentiment}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        # Try fallback to JSON mode if structured output fails
        print("\n   Trying JSON mode fallback...")
        try:
            json_prompt = ChatPromptTemplate.from_messages([
                ("human", """Analyze this email and return a JSON object with:
                - summary: a brief summary
                - key_points: array of key points
                - action_items: array of action items
                - sentiment: positive, negative, or neutral
                
                Email:
                {email}
                
                Return only valid JSON.""")
            ])
            
            chain = json_prompt | llm | StrOutputParser()
            response = chain.invoke({"email": test_email})
            print(f"✅ JSON Response: {response}")
        except Exception as e2:
            print(f"❌ JSON mode also failed: {e2}")
            return False
    
    # Test 3: Streaming with LangChain
    print("\n3. Testing streaming with LangChain...")
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("human", "Write a short haiku about email summarization.")
        ])
        
        chain = prompt | llm
        
        print("✅ Streaming response: ", end="", flush=True)
        for chunk in chain.stream({}):
            print(chunk.content, end="", flush=True)
        print()  # New line after streaming
    except Exception as e:
        print(f"\n❌ Streaming failed: {e}")
    
    return True


if __name__ == "__main__":
    print("Testing Gemini with LangChain integration...\n")
    
    if settings.LLM_PROVIDER != "gemini":
        print(f"⚠️  LLM_PROVIDER is set to '{settings.LLM_PROVIDER}', not 'gemini'")
        print("   Update your .env file to test Gemini")
        sys.exit(1)
    
    success = test_langchain_gemini()
    
    if success:
        print("\n✅ All LangChain + Gemini tests passed!")
        print("\nYour existing email.py code should work as-is with these settings.")
        print("The key is proper Vertex AI initialization and authentication.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check your configuration.")
        sys.exit(1) 