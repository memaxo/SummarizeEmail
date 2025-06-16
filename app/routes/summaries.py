from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Body

from .. import services
from ..config import settings
from ..graph.email_repository import email_repository
from ..models import SummarizeBulkRequest, SummarizeDigestResponse

router = APIRouter(
    prefix="/summaries",
    tags=["Summarization"],
)

@router.post("/", response_model=SummarizeDigestResponse)
def summarize_bulk(request: SummarizeBulkRequest):
    """
    Creates a single digest summary from a list of provided email message IDs.
    """
    emails = [email_repository.get_message(msg_id) for msg_id in request.message_ids]
    
    digest = services.run_bulk_summarization(emails)
    
    return SummarizeDigestResponse(
        digest=digest,
        llm_provider=settings.LLM_PROVIDER
    )

@router.get("/daily", response_model=SummarizeDigestResponse)
def summarize_daily_digest():
    """
    Generates a digest summary of all emails received in the last 24 hours.
    """
    # Fetch emails from the last 24 hours
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    emails = email_repository.list_messages(start_datetime=yesterday, end_datetime=today)
    digest = services.run_bulk_summarization(emails)
    
    return SummarizeDigestResponse(
        digest=digest,
        llm_provider=settings.LLM_PROVIDER
    ) 