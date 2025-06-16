from typing import List
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

    def add_emails(self, emails: List[Email]):
        """
        Generates embeddings for a list of emails and adds them to the database.
        """
        if not emails:
            return
            
        logger.info(f"Generating embeddings for {len(emails)} emails.")
        
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
                    embedding=embedding
                )
            )
        
        logger.info(f"Adding {len(email_embeddings)} embeddings to the database.")
        self._db.add_all(email_embeddings)
        self._db.commit()

    def query(self, query: str, top_k: int = 5) -> List[EmailEmbedding]:
        """
        Performs a semantic search on the vector database.
        """
        logger.info(f"Performing semantic search for query: '{query}'")
        query_embedding = self._embedding_model.embed_query(query)
        
        # Use the l2_distance operator for similarity search
        results = self._db.query(EmailEmbedding).order_by(
            EmailEmbedding.embedding.l2_distance(query_embedding)
        ).limit(top_k).all()
        
        return results 