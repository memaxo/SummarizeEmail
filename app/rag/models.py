from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector
from ..config import settings

Base = declarative_base()

# Determine embedding dimension based on provider
def get_embedding_dimension():
    """Get the embedding dimension based on the configured LLM provider"""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai":
        return 1536  # text-embedding-3-small
    elif provider == "gemini":
        # Vertex AI models typically use 768 dimensions
        return 768
    else:
        # Default to OpenAI dimensions
        return 1536

class EmailEmbedding(Base):
    """
    SQLAlchemy model for storing email embeddings.
    """
    __tablename__ = "email_embeddings"

    id = Column(String, primary_key=True, index=True)
    subject = Column(String)
    content = Column(Text)
    sent_date_time = Column(DateTime)
    embedding = Column(Vector(get_embedding_dimension()))
    user_id = Column(String, index=True)  # For multi-tenant support 