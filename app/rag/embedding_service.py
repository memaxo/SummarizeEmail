from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_vertexai import VertexAIEmbeddings
from langchain_core.embeddings import Embeddings
from ..config import settings
import os


def get_embedding_model() -> Embeddings:
    """
    Returns an instance of the embedding model based on the configured provider.
    
    Supports:
    - OpenAI embeddings (text-embedding-3-small)
    - Google Gemini embeddings via Google AI (models/embedding-001)
    - Google Gemini embeddings via Vertex AI (text-embedding-004)
    """
    provider = settings.LLM_PROVIDER.lower()
    
    if provider == "openai":
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.OPENAI_API_KEY
        )
    elif provider == "gemini":
        # Check if we should use Vertex AI (service account) or Google AI (API key)
        if settings.GOOGLE_APPLICATION_CREDENTIALS and settings.GOOGLE_CLOUD_PROJECT:
            # Use Vertex AI with service account
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS
            
            # Initialize Vertex AI
            import vertexai
            vertexai.init(
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION
            )
            
            return VertexAIEmbeddings(
                model_name="text-embedding-004",  # Vertex AI embedding model
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION
            )
        else:
            # Use Google AI with API key
            return GoogleGenerativeAIEmbeddings(
                model="models/embedding-001",
                google_api_key=settings.GOOGLE_API_KEY
            )
    else:
        # Default to OpenAI for backward compatibility
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.OPENAI_API_KEY
        ) 