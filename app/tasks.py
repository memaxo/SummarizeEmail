from .celery_app import celery_app
from .db.session import SessionLocal
from .graph import graph_repo
from .rag.vector_db_repository import VectorDBRepository
from .graph.models import Email as GraphEmail, EmailBody, Recipient
from .services.email import fetch_email_content
from .services.email_cleaner import email_cleaner
from .config import settings
import structlog

# Conditional import for repository
if settings.USE_MOCK_GRAPH_API:
    from .graph.mock_email_repository import MockEmailRepository
    # Alias it to EmailRepository for consistent use
    EmailRepository = MockEmailRepository
else:
    from .graph.email_repository import EmailRepository

logger = structlog.get_logger(__name__)

@celery_app.task(bind=True)
def ingest_emails_task(self, query: str, user_id: str):
    """
    Celery task to fetch emails and their attachments, then ingest them into the vector DB.
    
    Args:
        query: Search query for emails
        user_id: The user ID to fetch emails for
    """
    logger.info("Starting RAG ingestion task", query=query, user_id=user_id)
    db = SessionLocal()
    try:
        # Instantiate the repository with the correct user_id
        repo = EmailRepository(user_id=user_id)
        
        emails = repo.list_messages(search=query, top=100)
        
        enriched_emails = []
        for email in emails:
            try:
                # This is now a synchronous call
                full_content = fetch_email_content(email.id, user_id, include_attachments=True)
                
                # Clean the email content before ingestion
                cleaned_content = email_cleaner.clean(full_content)
                
                # Correctly create a new GraphEmail object for ingestion
                enriched_email = GraphEmail(
                    id=email.id,
                    subject=email.subject,
                    body=EmailBody(content=cleaned_content, contentType="text/plain"),
                    from_address=email.from_address,
                    to_recipients=email.to_recipients,
                    cc_recipients=email.cc_recipients,
                    sent_date_time=email.sent_date_time,
                )
                enriched_emails.append(enriched_email)
            except Exception as e:
                logger.error("Failed to process email for RAG ingestion", email_id=email.id, exc_info=e)

        if not enriched_emails:
            logger.warn("No emails were processed for RAG ingestion.")
            return {'status': 'No emails found', 'ingested_count': 0}

        vector_repo = VectorDBRepository(db)
        vector_repo.add_emails(enriched_emails, user_id=user_id)
        
        logger.info("Completed RAG ingestion task", ingested_count=len(enriched_emails), user_id=user_id)
        return {'status': 'Completed', 'ingested_count': len(enriched_emails)}
    finally:
        db.close() 