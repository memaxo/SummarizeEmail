from typing import List

from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session
import structlog

from .. import services
from ..config import settings
from ..graph.models import Attachment, Email
from ..models import ErrorResponse, SummarizeResponse, SummaryResponse
from ..database import get_db, get_redis
from ..exceptions import EmailNotFoundError, SummarizationError, GraphApiError
from ..logger import logger
from ..auth.dependencies import get_current_user_id
from ..services.email import EmailSummary
from redis.asyncio import Redis

# Conditional import for repository
if settings.USE_MOCK_GRAPH_API:
    from ..graph.mock_email_repository import MockEmailRepository as EmailRepository
else:
    from ..graph.email_repository import EmailRepository

router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
)

logger = structlog.get_logger(__name__)

@router.get("/{msg_id}", response_model=Email)
async def get_message(
    msg_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Retrieves a specific email message by its ID for the authenticated user.
    """
    repo = EmailRepository(user_id=user_id)
    return repo.get_message(msg_id)

@router.post("/{message_id}/summary", response_model=SummaryResponse)
async def summarize_message(
    message_id: str,
    user_id: str = Depends(get_current_user_id),
    include_attachments: bool = Query(False, description="Include attachments in the summary"),
    structured: bool = Query(False, description="Return structured output with key points and action items"),
    redis_client: Redis = Depends(get_redis)
):
    """
    Summarize a specific email message.
    """
    try:
        logger.info(f"Summarizing message: {message_id}", 
                   include_attachments=include_attachments,
                   structured=structured,
                   user_id=user_id)
        
        # Fetch email content using the validated user_id
        content = services.fetch_email_content(
            message_id, 
            user_id, 
            include_attachments=include_attachments
        )
        
        # Generate summary
        if structured and settings.LLM_PROVIDER in ["openai", "gemini"]:
            result = await services.summarize_email(content, structured=True)
            if isinstance(result, EmailSummary):
                summary_text = result.summary
                if result.key_points:
                    summary_text += "\n\nKey Points:\n" + "\n".join(f"• {point}" for point in result.key_points)
                if result.action_items:
                    summary_text += "\n\nAction Items:\n" + "\n".join(f"• {item}" for item in result.action_items)
                summary_text += f"\n\nSentiment: {result.sentiment}"
                
                return SummaryResponse(
                    message_id=message_id,
                    summary=summary_text,
                    cached=False,
                    llm_provider=settings.LLM_PROVIDER,
                    structured_data={
                        "key_points": result.key_points,
                        "action_items": result.action_items,
                        "sentiment": result.sentiment
                    }
                )
        
        summary, cached = await services.run_summarization_chain(content, redis_client=redis_client)
        
        return SummaryResponse(
            message_id=message_id,
            summary=summary,
            cached=cached,
            include_attachments=include_attachments,
            llm_provider=settings.LLM_PROVIDER
        )
        
    except EmailNotFoundError as e:
        logger.error(f"Email not found: {message_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except GraphApiError as e:
        logger.error(f"Graph API error for message {message_id}: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Graph API error: {str(e)}")
    except SummarizationError as e:
        logger.error(f"Summarization failed for message {message_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to summarize email: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error summarizing message {message_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.get("/{msg_id}/attachments", response_model=List[Attachment])
async def list_attachments(
    msg_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Lists all attachments for a specific email message for the authenticated user.
    """
    repo = EmailRepository(user_id=user_id)
    return repo.list_attachments(msg_id)

@router.get("/{msg_id}/attachments/{att_id}", response_model=Attachment)
async def get_attachment(
    msg_id: str,
    att_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Retrieves a specific attachment from an email message for the authenticated user.
    """
    repo = EmailRepository(user_id=user_id)
    return repo.get_attachment(message_id=msg_id, attachment_id=att_id) 