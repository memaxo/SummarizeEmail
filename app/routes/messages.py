from typing import List

from fastapi import APIRouter, Path, Query, Request, HTTPException, Depends
from redis.asyncio import Redis
from sqlalchemy.orm import Session
import structlog

from .. import services
from ..config import settings
from ..graph.email_repository import EmailRepository
from ..graph.models import Attachment, Email
from ..models import ErrorResponse, SummarizeResponse, SummaryResponse, Summary
from ..database import get_db, get_redis
from ..exceptions import EmailNotFoundError, SummarizationError
from ..logger import logger
from ..auth import get_current_user

router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
)

logger = structlog.get_logger(__name__)

@router.get("/{msg_id}", response_model=Email)
async def get_message(
    msg_id: str,
    request: Request
):
    """
    Retrieves a specific email message by its ID.
    
    In production with Custom GPT, this uses the authenticated user's ID from the OAuth token.
    """
    # Get user ID from OAuth token or fall back to TARGET_USER_ID
    user_id = await services.get_user_id_from_token(request)
    
    # Create a repository instance for this specific user
    email_repo = EmailRepository(user_id=user_id)
    
    return email_repo.get_message(msg_id)

@router.post("/{message_id}/summary", response_model=SummaryResponse)
async def summarize_message(
    request: Request,
    message_id: str,
    include_attachments: bool = Query(False, description="Include attachments in the summary"),
    structured: bool = Query(False, description="Return structured output with key points and action items"),
    _: str = Depends(get_current_user)
):
    """
    Summarize a specific email message.
    
    This endpoint:
    1. Fetches the email content from Microsoft Graph API
    2. Optionally includes attachment content
    3. Generates a summary using the configured LLM
    4. Can return structured output with key points and action items
    
    Args:
        message_id: The ID of the email message to summarize
        include_attachments: Whether to include attachment content in the summary
        structured: Whether to return structured output (only supported for OpenAI and Gemini)
        
    Returns:
        SummaryResponse containing the summary and metadata
    """
    try:
        logger.info(f"Summarizing message: {message_id}", 
                   include_attachments=include_attachments,
                   structured=structured)
        
        # Fetch email content
        content = await services.fetch_email_content(
            message_id, 
            request, 
            include_attachments=include_attachments
        )
        
        # Generate summary
        if structured and settings.LLM_PROVIDER in ["openai", "gemini"]:
            # Get structured output
            result = await services.summarize_email(content, structured=True)
            if isinstance(result, EmailSummary):
                # Convert structured output to response format
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
        
        # Regular text summary or if structured output is not supported/requested
        summary, cached = services.run_summarization_chain(request, content)
        
        return SummaryResponse(
            message_id=message_id,
            summary=summary,
            cached=cached,
            llm_provider=settings.LLM_PROVIDER
        )
        
    except EmailNotFoundError as e:
        logger.error(f"Email not found: {message_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except SummarizationError as e:
        logger.error(f"Summarization failed for message {message_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to summarize email: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error summarizing message {message_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.get("/{msg_id}/attachments", response_model=List[Attachment])
async def list_attachments(
    msg_id: str,
    request: Request
):
    """
    Lists all attachments for a specific email message.
    
    In production with Custom GPT, this uses the authenticated user's ID from the OAuth token.
    """
    # Get user ID from OAuth token or fall back to TARGET_USER_ID
    user_id = await services.get_user_id_from_token(request)
    
    # Create a repository instance for this specific user
    email_repo = EmailRepository(user_id=user_id)
    
    return email_repo.list_attachments(msg_id)

@router.get("/{msg_id}/attachments/{att_id}", response_model=Attachment)
async def get_attachment(
    msg_id: str,
    att_id: str,
    request: Request
):
    """
    Retrieves a specific attachment from an email message.
    
    In production with Custom GPT, this uses the authenticated user's ID from the OAuth token.
    """
    # Get user ID from OAuth token or fall back to TARGET_USER_ID
    user_id = await services.get_user_id_from_token(request)
    
    # Create a repository instance for this specific user
    email_repo = EmailRepository(user_id=user_id)
    
    return email_repo.get_attachment(message_id=msg_id, attachment_id=att_id) 