from typing import List

from fastapi import APIRouter, Path, Query, Request, HTTPException, Depends
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from .. import services
from ..config import settings
from ..graph.email_repository import email_repository
from ..graph.models import Attachment, Email
from ..models import ErrorResponse, SummarizeResponse, SummaryResponse, Summary
from ..database import get_db, get_redis
from ..exceptions import EmailNotFoundError, SummarizationError
from ..logger import logger

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

@router.post("/{msg_id}/summary", response_model=SummaryResponse)
async def summarize_message(
    msg_id: str,
    request: Request,
    include_attachments: bool = Query(False, description="Include attachment content in summary"),
    redis: Redis = Depends(get_redis),
    db: Session = Depends(get_db)
) -> SummaryResponse:
    """
    Generate a summary for a specific email message.
    
    This endpoint:
    1. Checks Redis cache for existing summary
    2. If not cached, fetches the email content (optionally including attachments)
    3. Generates a summary using the configured LLM
    4. Caches the result in Redis
    5. Stores the summary in PostgreSQL for analytics
    
    The summary is cached with a key format: summary:{msg_id}:{include_attachments}
    """
    # Generate cache key based on message ID and attachment inclusion
    cache_key = f"summary:{msg_id}:{include_attachments}"
    
    # Check cache first
    if redis:
        cached_summary = await redis.get(cache_key)
        if cached_summary:
            logger.info("Cache hit for message summary", 
                       message_id=msg_id, 
                       include_attachments=include_attachments)
            return SummaryResponse(
                message_id=msg_id,
                summary=cached_summary,
                cached=True,
                include_attachments=include_attachments
            )
    
    try:
        # Fetch email content with optional attachments
        # Pass the request object to extract user ID from OAuth token
        content = await services.fetch_email_content(msg_id, request, include_attachments)
        
        # Generate summary
        summary = await services.summarize_email(content)
        
        # Cache the summary
        if redis:
            await redis.setex(
                cache_key,
                settings.CACHE_EXPIRATION_SECONDS,
                summary
            )
            logger.info("Cached message summary", 
                       message_id=msg_id,
                       include_attachments=include_attachments)
        
        # Store in database for analytics
        db_summary = Summary(
            message_id=msg_id,
            summary=summary,
            include_attachments=include_attachments
        )
        db.add(db_summary)
        db.commit()
        
        return SummaryResponse(
            message_id=msg_id,
            summary=summary,
            cached=False,
            include_attachments=include_attachments
        )
        
    except EmailNotFoundError:
        logger.warning("Email not found", message_id=msg_id)
        raise HTTPException(status_code=404, detail=f"Email {msg_id} not found")
    except SummarizationError as e:
        logger.error("Summarization failed", message_id=msg_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate summary")
    except Exception as e:
        logger.error("Unexpected error during summarization", 
                    message_id=msg_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

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