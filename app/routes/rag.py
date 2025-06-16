from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List
import structlog

from ..db.session import get_db
from ..graph.email_repository import EmailRepository
from ..rag.vector_db_repository import VectorDBRepository
from ..models import ErrorResponse, RAGQueryResponse, RAGAnswerResponse
from ..rag.models import EmailEmbedding as RAGEmail
from ..services import fetch_email_content, run_rag_chain, get_user_id_from_token
from ..graph.models import EmailBody, Email
from langchain_core.documents import Document

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
)

async def ingest_emails_task(db: Session, query: str, user_id: str, request: Request):
    """
    Background task to fetch emails and their attachments, then ingest them into the vector DB.
    
    Args:
        db: Database session
        query: Search query for emails
        user_id: The user ID to fetch emails for
        request: The original request object for context
    """
    logger.info("Starting RAG ingestion task", query=query, user_id=user_id)
    
    # Create a repository instance for this specific user
    email_repo = EmailRepository(user_id=user_id)
    emails = email_repo.list_messages(search=query, top=100)  # Ingest up to 100 emails
    
    # Create a new list of emails with attachment content included
    enriched_emails = []
    for email in emails:
        try:
            # Fetch the full content including attachments
            # Note: We pass the request to maintain context
            full_content = await fetch_email_content(email.id, request, include_attachments=True)
            # We need to update the email object's body to reflect this new content
            # This is a bit of a hack, but it avoids changing the repository's contract
            email.body = EmailBody(content=full_content, contentType="text/plain")
            enriched_emails.append(email)
        except Exception as e:
            logger.error("Failed to process email for RAG ingestion", email_id=email.id, exc_info=e)

    if not enriched_emails:
        logger.warn("No emails were processed for RAG ingestion.")
        return

    repo = VectorDBRepository(db)
    # Store with user context for multi-tenant support
    repo.add_emails(enriched_emails, user_id=user_id)
    logger.info("Completed RAG ingestion task", ingested_count=len(enriched_emails), user_id=user_id)

@router.post("/ingest", status_code=202)
async def ingest_emails(
    query: str, 
    request: Request,
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    """
    Triggers a background task to ingest emails from a search query.
    
    In production with Custom GPT, this uses the authenticated user's ID from the OAuth token.
    """
    # Get user ID from OAuth token or fall back to TARGET_USER_ID
    user_id = await get_user_id_from_token(request)
    
    background_tasks.add_task(ingest_emails_task, db, query, user_id, request)
    return {"message": "Email ingestion started in the background.", "user_id": user_id}


@router.get("/query", response_model=RAGAnswerResponse)
async def query_emails(
    q: str, 
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Performs a semantic search and generates an answer based on the results.
    
    In production with Custom GPT, this searches only the authenticated user's emails.
    """
    # Get user ID from OAuth token or fall back to TARGET_USER_ID
    user_id = await get_user_id_from_token(request)
    
    # 1. Retrieve relevant documents from the vector database
    repo = VectorDBRepository(db)
    # Query with user context for multi-tenant support
    retrieved_emails = repo.query(q, user_id=user_id)
    
    # 2. Convert the SQLAlchemy models to LangChain Documents for the chain
    context_docs = [
        Document(
            page_content=email.content,
            metadata={"id": email.id, "subject": email.subject, "sent_date_time": email.sent_date_time}
        ) for email in retrieved_emails
    ]

    # 3. Generate an answer using the RAG chain
    answer = run_rag_chain(question=q, context_docs=context_docs)

    # 4. Format the response
    return RAGAnswerResponse(
        answer=answer,
        source_documents=retrieved_emails
    ) 