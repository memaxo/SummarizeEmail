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