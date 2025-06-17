from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query, Request

from ..graph import graph_repo
from ..graph.models import Email
from ..services.email import get_user_id_from_token

router = APIRouter(
    prefix="/emails",
    tags=["Emails"],
)

@router.get("/", response_model=List[Email])
async def search_emails(
    request: Request,
    search: Optional[str] = Query(None, description="A free-text search query (uses Graph's $search)."),
    from_address: Optional[str] = Query(None, description="Filter by the sender's email address."),
    subject_contains: Optional[str] = Query(None, description="Filter by a keyword in the subject."),
    is_unread: Optional[bool] = Query(None, description="Filter for unread (True) or read (False) emails."),
    start_date: Optional[datetime] = Query(None, description="The start date for the search window (ISO 8601 format)."),
    end_date: Optional[datetime] = Query(None, description="The end date for the search window (ISO 8601 format)."),
    limit: int = Query(25, ge=1, le=100, description="The maximum number of emails to return."),
):
    """
    Searches for emails based on a powerful, free-text query and other filters.
    
    In production with Custom GPT, this uses the authenticated user's ID from the OAuth token.
    """
    # Get user ID from OAuth token or fall back to TARGET_USER_ID
    user_id = await get_user_id_from_token(request)
    
    # Use the imported graph_repo which respects mock mode
    emails = graph_repo.list_messages(
        search=search,
        from_address=from_address,
        subject_contains=subject_contains,
        is_unread=is_unread,
        start_datetime=start_date,
        end_datetime=end_date,
        top=limit,
    )
    return emails 