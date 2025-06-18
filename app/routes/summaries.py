from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends

from .. import services
from ..models import BulkSummarizeRequest, BulkSummarizeResponse, SummaryResponse
from ..config import settings
from ..auth.dependencies import get_current_user_id

# Conditional import for repository
if settings.USE_MOCK_GRAPH_API:
    from ..graph.mock_email_repository import MockEmailRepository as EmailRepository
else:
    from ..graph.email_repository import EmailRepository

router = APIRouter(
    prefix="/summaries",
    tags=["Summaries"],
)

@router.post("/bulk", response_model=BulkSummarizeResponse)
async def bulk_summarize(
    request: BulkSummarizeRequest,
    user_id: str = Depends(get_current_user_id)
):
    """
    Summarizes multiple emails in a single request for the authenticated user.
    """
    repo = EmailRepository(user_id=user_id)
    summaries = []

    for msg_id in request.message_ids:
        # Fetch content for each email, optionally including attachments
        content = services.fetch_email_content(
            msg_id,
            user_id,
            include_attachments=request.include_attachments
        )
        
        # We don't use caching for bulk summaries to avoid complexity,
        # but the underlying summarize_email is what's called.
        summary_text = await services.summarize_email(content)
        
        summary_response = SummaryResponse(
            summary=summary_text,
            message_id=msg_id,
            cached=False,
            llm_provider=settings.LLM_PROVIDER,
            include_attachments=request.include_attachments
        )
        summaries.append(summary_response)
    
    return BulkSummarizeResponse(summaries=summaries, total=len(summaries))

@router.post("/daily", response_model=BulkSummarizeResponse)
async def daily_summary(user_id: str = Depends(get_current_user_id)):
    """
    Generates summaries for all emails from the past 24 hours for the authenticated user.
    """
    repo = EmailRepository(user_id=user_id)
    
    # Get emails from the last 24 hours
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    emails = repo.list_messages(start_datetime=yesterday, end_datetime=today)
    summaries = []
    
    for email in emails:
        content = email.get_full_content()
        summary_text = await services.summarize_email(content)
        summary_response = SummaryResponse(
            summary=summary_text,
            message_id=email.id,
            cached=False,
            llm_provider=settings.LLM_PROVIDER,
            include_attachments=False
        )
        summaries.append(summary_response)
    
    return BulkSummarizeResponse(summaries=summaries, total=len(summaries)) 