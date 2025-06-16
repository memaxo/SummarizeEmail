from langchain_openai import OpenAIEmbeddings
from ..config import settings

def get_embedding_model():
    """
    Returns an instance of the OpenAI embedding model.
    """
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=settings.OPENAI_API_KEY
    ) 