from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SummarizeResponse(BaseModel):
    """
    Defines the successful response structure for the /summarize endpoint.
    """
    summary: str = Field(..., description="The generated summary of the email.")
    message_id: str = Field(..., description="The ID of the email that was summarized.")
    cached: bool = Field(..., description="Indicates if the response was served from the cache.")
    llm_provider: str = Field(..., description="The LLM provider used for the summary ('openai' or 'ollama').")


class ErrorResponse(BaseModel):
    """
    Defines the structure for error responses.
    """
    detail: str = Field(..., description="A clear, human-readable error message.")


class SummarizeBulkRequest(BaseModel):
    """
    Defines the request for the bulk summarization endpoint.
    """
    message_ids: List[str] = Field(..., description="A list of email message IDs to summarize.", min_items=1)


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