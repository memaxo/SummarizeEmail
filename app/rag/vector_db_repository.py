from typing import List, Optional
from sqlalchemy.orm import Session
import structlog

from .models import EmailEmbedding
from ..graph.models import Email
from .embedding_service import get_embedding_model

logger = structlog.get_logger(__name__)

class VectorDBRepository:
    """
    Handles all interactions with the vector database.
    """

    def __init__(self, db_session: Session):
        self._db = db_session
        self._embedding_model = get_embedding_model()

    def add_emails(self, emails: List[Email], user_id: Optional[str] = None):
        """
        Generates embeddings for a list of emails and adds them to the database.
        
        Args:
            emails: List of Email objects to add
            user_id: Optional user ID for multi-tenant support
        """
        if not emails:
            return
            
        logger.info(f"Generating embeddings for {len(emails)} emails.", user_id=user_id)
        
        texts_to_embed = [email.get_full_content() for email in emails]
        embeddings = self._embedding_model.embed_documents(texts_to_embed)
        
        email_embeddings = []
        for email, embedding in zip(emails, embeddings):
            email_embeddings.append(
                EmailEmbedding(
                    id=email.id,
                    subject=email.subject,
                    content=email.get_full_content(),
                    sent_date_time=email.sent_date_time,
                    embedding=embedding,
                    user_id=user_id  # Store user_id for multi-tenant support
                )
            )
        
        logger.info(f"Adding {len(email_embeddings)} embeddings to the database.", user_id=user_id)
        self._db.add_all(email_embeddings)
        self._db.commit()

    def query(self, query: str, user_id: Optional[str] = None, top_k: int = 5) -> List[EmailEmbedding]:
        """
        Performs a semantic search on the vector database.
        
        Args:
            query: The search query
            user_id: Optional user ID to filter results for multi-tenant support
            top_k: Number of results to return
        """
        logger.info(f"Performing semantic search for query: '{query}'", user_id=user_id)
        query_embedding = self._embedding_model.embed_query(query)
        
        # Build the query
        db_query = self._db.query(EmailEmbedding)
        
        # Filter by user_id if provided (for multi-tenant support)
        if user_id:
            db_query = db_query.filter(EmailEmbedding.user_id == user_id)
        
        # Use the l2_distance operator for similarity search
        results = db_query.order_by(
            EmailEmbedding.embedding.l2_distance(query_embedding)
        ).limit(top_k).all()
        
        return results 