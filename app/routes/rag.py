from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from ..db.session import get_db
from ..graph.email_repository import email_repository
from ..rag.vector_db_repository import VectorDBRepository
from ..models import ErrorResponse
from ..rag.models import EmailEmbedding as RAGEmail

router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
)

def ingest_emails_task(db: Session, query: str):
    """
    Background task to fetch emails and ingest them into the vector DB.
    """
    emails = email_repository.list_messages(search=query, top=100) # Ingest up to 100 emails
    repo = VectorDBRepository(db)
    repo.add_emails(emails)

@router.post("/ingest", status_code=202)
def ingest_emails(query: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Triggers a background task to ingest emails from a search query.
    """
    background_tasks.add_task(ingest_emails_task, db, query)
    return {"message": "Email ingestion started in the background."}


@router.get("/query", response_model=List[RAGEmail])
def query_emails(q: str, db: Session = Depends(get_db)):
    """
    Performs a semantic search over the ingested emails.
    """
    repo = VectorDBRepository(db)
    results = repo.query(q)
    return results 