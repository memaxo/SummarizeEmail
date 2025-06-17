from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Request

from .. import services
from ..graph import graph_repo
from ..models import BulkSummarizeRequest, BulkSummarizeResponse, SummarizeResponse

router = APIRouter(
    prefix="/summaries",
    tags=["Summaries"],
)

@router.post("/bulk", response_model=BulkSummarizeResponse)
async def bulk_summarize(
    request: BulkSummarizeRequest,
    http_request: Request
):
    """
    Summarizes multiple emails in a single request.
    
    In production with Custom GPT, this uses the authenticated user's ID from the OAuth token.
    """
    # Get user ID from OAuth token or fall back to TARGET_USER_ID
    user_id = await services.get_user_id_from_token(http_request)
    
    # Use the imported graph_repo which respects mock mode
    emails = [graph_repo.get_message(msg_id) for msg_id in request.message_ids]
    summaries = []
    
    for email in emails:
        content = email.get_full_content()
        summary = await services.summarize_email(content)
        summaries.append(SummarizeResponse(
            summary=summary,
            message_id=email.id,
            cached=False,
            include_attachments=False
        ))
    
    return BulkSummarizeResponse(summaries=summaries)

@router.post("/daily", response_model=BulkSummarizeResponse)
async def daily_summary(http_request: Request):
    """
    Generates summaries for all emails from the past 24 hours.
    
    In production with Custom GPT, this uses the authenticated user's ID from the OAuth token.
    """
    # Get user ID from OAuth token or fall back to TARGET_USER_ID
    user_id = await services.get_user_id_from_token(http_request)
    
    # Use the imported graph_repo which respects mock mode
    # Get emails from the last 24 hours
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    
    emails = graph_repo.list_messages(start_datetime=yesterday, end_datetime=today)
    summaries = []
    
    for email in emails:
        content = email.get_full_content()
        summary = await services.summarize_email(content)
        summaries.append(SummarizeResponse(
            summary=summary,
            message_id=email.id,
            cached=False,
            include_attachments=False
        ))
    
    return BulkSummarizeResponse(summaries=summaries) 