from datetime import datetime
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class SummarizeResponse(BaseModel):
    """
    Defines the successful response structure for the /summarize endpoint.
    """
    summary: str = Field(..., description="The generated summary of the email.")
    message_id: str = Field(..., description="The ID of the email that was summarized.")
    cached: bool = Field(..., description="Indicates if the response was served from the cache.")
    llm_provider: str = Field(..., description="The LLM provider used for the summary ('openai' or 'ollama').")
    include_attachments: bool = Field(False, description="Whether attachments were included in the summary.")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the summary was generated.")


class SummaryResponse(BaseModel):
    """
    Response model for individual email summary.
    """
    summary: str = Field(..., description="The generated summary of the email.")
    message_id: str = Field(..., description="The ID of the email that was summarized.")
    cached: bool = Field(..., description="Indicates if the response was served from the cache.")
    include_attachments: bool = Field(..., description="Whether attachments were included in the summary.")
    llm_provider: str = Field(..., description="The LLM provider used for the summary.")
    structured_data: Optional[Dict[str, Any]] = Field(None, description="Structured data (key points, action items, sentiment) if requested")


class ErrorResponse(BaseModel):
    """
    Defines the structure for error responses.
    """
    detail: str = Field(..., description="A clear, human-readable error message.")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SummarizeBulkRequest(BaseModel):
    """
    Defines the request for the bulk summarization endpoint.
    """
    message_ids: List[str] = Field(..., description="A list of email message IDs to summarize.", min_items=1)
    include_attachments: bool = Field(False, description="Whether to include attachments in summaries")


class BulkSummarizeRequest(BaseModel):
    """
    Request model for bulk email summarization.
    """
    message_ids: List[str] = Field(..., description="A list of email message IDs to summarize.", min_items=1)
    include_attachments: bool = Field(False, description="Whether to include attachments in the summaries.")


class BulkSummarizeResponse(BaseModel):
    """
    Response model for bulk email summarization.
    """
    summaries: List[SummaryResponse] = Field(..., description="List of individual email summaries.")
    total: int = Field(..., description="Total number of messages summarized.")
    failed: List[str] = Field(default_factory=list, description="List of message IDs that failed to summarize.")


class SummarizeDigestResponse(BaseModel):
    """
    Defines the successful response for a digest summary.
    """
    digest: str = Field(..., description="The generated digest summary from multiple emails.")
    llm_provider: str = Field(..., description="The LLM provider used for the summary.")


class RAGQueryResponse(BaseModel):
    """
    Defines the response for a RAG query, representing a single retrieved document.
    """
    id: str
    subject: str
    content: str
    sent_date_time: datetime

    class Config:
        from_attributes = True


class RAGAnswerResponse(BaseModel):
    """
    Defines the response for a RAG query that includes a synthesized answer.
    """
    answer: str = Field(..., description="The generated answer from the RAG chain.")
    source_documents: List[RAGQueryResponse] = Field(..., description="The source documents used to generate the answer.")


# SQLAlchemy Models
class Summary(Base):
    """
    Database model for storing email summaries.
    """
    __tablename__ = "summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, index=True, nullable=False)
    summary = Column(Text, nullable=False)
    include_attachments = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String, index=True)  # For multi-tenant support 