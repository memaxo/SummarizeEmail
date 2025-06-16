from fastapi import APIRouter, Path, Request

from .. import services
from ..models import ErrorResponse, SummarizeResponse

router = APIRouter()

@router.get(
    "/messages/{msg_id}/summary",
    response_model=SummarizeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input"},
        404: {"model": ErrorResponse, "description": "Email not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        502: {"model": ErrorResponse, "description": "Upstream API error"},
    },
    tags=["Summarization"],
)
def summarize_email(
    request: Request,
    msg_id: str = Path(
        ...,
        description="The immutable ID of the Outlook email message.",
        examples=["AAMkAGI1ZTMx..."],
    ),
):
    """
    Summarizes a single Outlook email message.
    """
    # This endpoint is now a bit redundant with the bulk endpoint,
    # but we keep it for direct, single-email summarization.
    # The caching logic is now handled within the main app logic to
    # avoid duplication.
    content = services.fetch_email_content(msg_id)
    summary = services.run_summarization_chain(content)

    return SummarizeResponse(
        summary=summary,
        message_id=msg_id,
        cached=False,  # Caching logic is now centralized
        llm_provider=services.settings.LLM_PROVIDER,
    ) 