from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query, Depends

from ..graph.models import Email
from ..config import settings
from ..auth.dependencies import get_current_user_id

# Conditional import for repository
if settings.USE_MOCK_GRAPH_API:
    from ..graph.mock_email_repository import MockEmailRepository as EmailRepository
else:
    from ..graph.email_repository import EmailRepository

router = APIRouter(
    prefix="/emails",
    tags=["Emails"],
)

@router.get("/", response_model=List[Email])
async def search_emails(
    user_id: str = Depends(get_current_user_id),
    search: Optional[str] = Query(None, description="A free-text search query (uses Graph's $search)."),
    from_address: Optional[str] = Query(None, description="Filter by the sender's email address."),
    subject_contains: Optional[str] = Query(None, description="Filter by a keyword in the subject."),
    is_unread: Optional[bool] = Query(None, description="Filter for unread (True) or read (False) emails."),
    start_date: Optional[datetime] = Query(None, description="The start date for the search window (ISO 8601 format)."),
    end_date: Optional[datetime] = Query(None, description="The end date for the search window (ISO 8601 format)."),
    limit: int = Query(25, ge=1, le=100, description="The maximum number of emails to return."),
):
    """
    Searches for emails for the authenticated user based on a powerful, free-text query and other filters.
    """
    repo = EmailRepository(user_id=user_id)
    emails = repo.list_messages(
        search=search,
        from_address=from_address,
        subject_contains=subject_contains,
        is_unread=is_unread,
        start_datetime=start_date,
        end_datetime=end_date,
        top=limit,
    )
    return emails 