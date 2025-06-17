from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class EmailEmbedding(Base):
    """
    SQLAlchemy model for storing email embeddings.
    """
    __tablename__ = "email_embeddings"

    id = Column(String, primary_key=True, index=True)
    subject = Column(String)
    content = Column(Text)
    sent_date_time = Column(DateTime)
    embedding = Column(Vector(1536)) # Assuming OpenAI's text-embedding-3-small
    user_id = Column(String, index=True)  # For multi-tenant support 