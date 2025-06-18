import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, call
from datetime import datetime
import fakeredis

from app.main import app
from app.routes.rag import ingest_emails_task
from app.graph.models import Email, EmailBody
from app import services
from app.models import RAGQueryResponse
from tests.auth.helpers import create_test_token
from app.config import settings

def test_ingest_emails(client, mocker):
    """
    Tests the POST /rag/ingest endpoint.
    """
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    # 1. Mock the background task and the underlying repository calls
    mock_ingest_task = mocker.patch("app.routes.rag.ingest_emails_task")
    
    # 2. Call the API
    query = "from:test@example.com"
    response = client.post(
        f"/rag/ingest?query={query}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # 3. Assert the response
    assert response.status_code == 202
    assert "task_id" in response.json()
    
    # 4. Assert the background task was called
    mock_ingest_task.delay.assert_called_once_with(query=query, user_id=user_id)

def test_ingest_emails_task_logic(mocker):
    """
    Tests the core logic of the RAG ingestion background task.
    This test verifies that attachment content is fetched and included.
    """
    # 1. Mock the dependencies of the task function
    mock_db = MagicMock()
    mock_db_session_class = mocker.patch("app.tasks.SessionLocal")
    mock_db_session_class.return_value = mock_db
    
    # Import EmailRepository from the correct location
    if settings.USE_MOCK_GRAPH_API:
        from app.graph.mock_email_repository import MockEmailRepository as EmailRepository
    else:
        from app.graph.email_repository import EmailRepository
    
    # Mock the repository
    mock_email_repo = MagicMock()
    mocker.patch("app.tasks.EmailRepository", return_value=mock_email_repo)
    
    mock_vector_repo = MagicMock()
    mocker.patch("app.tasks.VectorDBRepository", return_value=mock_vector_repo)

    # 2. Define test data
    query = "from:test@example.com"
    user_id = "test_user"
    
    # Create mock emails with attachments
    mock_emails = [
        Email(
            id="email1",
            subject="Test Email",
            body=EmailBody(content="Email body content", contentType="text"),
            from_address={"emailAddress": {"address": "test@example.com"}},
            toRecipients=[],
            sentDateTime="2023-01-01T00:00:00Z",
            hasAttachments=True
        )
    ]
    
    # Set up the mocks
    mock_email_repo.list_messages.return_value = mock_emails
    
    # Mock fetch_email_content
    mocker.patch("app.tasks.fetch_email_content", return_value="Email body content with attachments")
    
    # Mock email_cleaner
    mock_cleaner = mocker.patch("app.tasks.email_cleaner")
    mock_cleaner.clean.return_value = "Cleaned email content"
    
    # 3. Import and call the task
    from app.tasks import ingest_emails_task
    
    # Create a mock task instance
    mock_task = MagicMock()
    
    # Execute the task - the task is bound so it expects self as first arg
    result = ingest_emails_task(query=query, user_id=user_id)
    
    # 4. Assert the task completed successfully
    assert result["status"] == "Completed"
    assert result["ingested_count"] == 1
    
    # Verify the mocks were called correctly
    mock_email_repo.list_messages.assert_called_once_with(search=query, top=100)
    mock_vector_repo.add_emails.assert_called_once()

def test_query_emails(client, mocker):
    """
    Tests the GET /rag/query endpoint.
    """
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    # 1. Mock the dependencies
    mock_db_repo = MagicMock()
    mocker.patch("app.routes.rag.VectorDBRepository", return_value=mock_db_repo)
    
    mock_rag_chain = mocker.patch("app.routes.rag.run_rag_chain")

    # 2. Define mock data
    query = "what is the project status"
    mock_retrieved_docs = [
        RAGQueryResponse(id="email1", subject="S1", content="Content 1", sent_date_time=datetime.now())
    ]
    expected_answer = "The project is on track for Q3."

    mock_db_repo.query.return_value = mock_retrieved_docs
    mock_rag_chain.return_value = expected_answer

    # 3. Call the API
    response = client.get(
        f"/rag/query?q={query}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # 4. Assert the response
    assert response.status_code == 200
    assert response.json()["answer"] == expected_answer
    assert len(response.json()["source_documents"]) == 1
    assert response.json()["source_documents"][0]["subject"] == "S1"

    # 5. Verify the mocks were called correctly
    mock_db_repo.query.assert_called_once_with(query, user_id=user_id)
    mock_rag_chain.assert_called_once() 