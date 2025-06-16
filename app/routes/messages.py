from typing import List

from fastapi import APIRouter, Path, Query, Request

from .. import services
from ..config import settings
from ..graph.email_repository import email_repository
from ..graph.models import Attachment, Email
from ..models import ErrorResponse, SummarizeResponse

router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
)

@router.get("/{msg_id}", response_model=Email)
def get_message(msg_id: str = Path(..., description="The ID of the email to retrieve.")):
    """
    Retrieves a single email message by its ID.
    """
    return email_repository.get_message(msg_id)

@router.get(
    "/{msg_id}/summary",
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
    include_attachments: bool = Query(
        False, 
        description="Set to true to parse and include the content of attachments in the summary."
    ),
):
    """
    Summarizes a single Outlook email message, with an option to include attachments.
    """
    # This endpoint is now a bit redundant with the bulk endpoint,
    # but we keep it for direct, single-email summarization.
    # The caching logic is now handled within the main app logic to
    # avoid duplication.
    content = services.fetch_email_content(msg_id, include_attachments=include_attachments)
    summary, from_cache = services.run_summarization_chain(request, content)

    return SummarizeResponse(
        summary=summary,
        message_id=msg_id,
        cached=from_cache,
        llm_provider=settings.LLM_PROVIDER,
    )

@router.get("/{msg_id}/attachments", response_model=List[Attachment])
def list_attachments(msg_id: str = Path(..., description="The ID of the email.")):
    """
    Lists all attachments for a specific email message.
    """
    return email_repository.list_attachments(msg_id)

@router.get("/{msg_id}/attachments/{att_id}", response_model=Attachment)
def get_attachment(
    msg_id: str = Path(..., description="The ID of the email."),
    att_id: str = Path(..., description="The ID of the attachment.")
):
    """
    Retrieves a single attachment, including its content bytes.
    """
    return email_repository.get_attachment(message_id=msg_id, attachment_id=att_id) 