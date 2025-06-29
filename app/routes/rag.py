from fastapi import APIRouter, Depends, Request
from celery.result import AsyncResult
from sqlalchemy.orm import Session
import structlog

from ..db.session import get_db
from ..tasks import ingest_emails_task
from ..auth.dependencies import get_current_user_id
from ..database import get_redis
from ..services import run_rag_chain, astream_rag_chain
from ..rag.vector_db_repository import VectorDBRepository
from ..models import RAGAnswerResponse
from langchain_core.documents import Document

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
)

@router.post("/ingest", status_code=202)
async def ingest_emails(
    query: str, 
    user_id: str = Depends(get_current_user_id)
):
    """
    Triggers a background Celery task to ingest emails from a search query.
    """
    task = ingest_emails_task.delay(query=query, user_id=user_id)
    return {"task_id": task.id, "status": "Ingestion started."}

@router.get("/ingest/status/{task_id}")
def get_ingest_status(task_id: str):
    """
    Checks the status of a Celery ingestion task.
    """
    task_result = AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result
    }

@router.get("/query", response_model=RAGAnswerResponse)
async def query_emails(
    q: str, 
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    redis_client = Depends(get_redis)
):
    """
    Performs a semantic search and generates an answer based on the results.
    """
    repo = VectorDBRepository(db)
    retrieved_emails = repo.query(q, user_id=user_id)
    
    context_docs = [
        Document(
            page_content=email.content,
            metadata={"id": email.id, "subject": email.subject, "sent_date_time": email.sent_date_time}
        ) for email in retrieved_emails
    ]

    answer = await run_rag_chain(question=q, context_docs=context_docs, redis_client=redis_client)

    return RAGAnswerResponse(
        answer=answer,
        source_documents=retrieved_emails
    )


# ----------------------------- streaming ----------------------------- #

from fastapi.responses import StreamingResponse

@router.get("/query/stream")
async def query_emails_stream(
    q: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    redis_client = Depends(get_redis)
):
    repo = VectorDBRepository(db)
    retrieved_emails = repo.query(q, user_id=user_id)

    context_docs = [
        Document(
            page_content=email.content,
            metadata={"id": email.id}
        ) for email in retrieved_emails
    ]

    async def token_generator():
        async for token in astream_rag_chain(q, context_docs, redis_client=redis_client):
            yield token

    return StreamingResponse(token_generator(), media_type="text/plain") 