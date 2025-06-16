import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, call

from app.main import app
from app.routes.rag import ingest_emails_task
from app.graph.models import Email, EmailBody
from app import services

@pytest.fixture
def client(mocker):
    """Pytest fixture to create a FastAPI TestClient."""
    mocker.patch("app.main.init_db", return_value=None)
    with TestClient(app) as c:
        yield c

def test_ingest_emails(client, mocker):
    """
    Tests the POST /rag/ingest endpoint.
    """
    # 1. Mock the background task and the underlying repository calls
    mock_ingest_task = mocker.patch("app.routes.rag.ingest_emails_task")
    
    # 2. Call the API
    query = "from:test@example.com"
    response = client.post(f"/rag/ingest?query={query}")
    
    # 3. Assert the response
    assert response.status_code == 202
    assert response.json() == {"message": "Email ingestion started in the background."}
    
    # 4. Assert that the background task was called
    # Note: We can't easily assert the arguments here without more complex mocking,
    # but we can at least verify it was called.
    assert mock_ingest_task.call_count == 1

def test_ingest_emails_task_logic(mocker):
    """
    Tests the core logic of the RAG ingestion background task.
    This test verifies that attachment content is fetched and included.
    """
    # 1. Mock the dependencies of the task function
    mock_db_session = MagicMock()
    mock_email_repo = mocker.patch("app.routes.rag.email_repository")
    mock_vector_repo_instance = MagicMock()
    mocker.patch("app.routes.rag.VectorDBRepository", return_value=mock_vector_repo_instance)
    mock_fetch_content = mocker.patch("app.routes.rag.fetch_email_content")

    # 2. Set up the mock return values
    mock_emails = [
        Email(id="email1", subject="S1", body=EmailBody(content="Body 1", contentType="text"), from_address={"emailAddress": {"address": "test@example.com"}}, toRecipients=[], sentDateTime="-"),
        Email(id="email2", subject="S2", body=EmailBody(content="Body 2", contentType="text"), from_address={"emailAddress": {"address": "test2@example.com"}}, toRecipients=[], sentDateTime="-"),
    ]
    mock_email_repo.list_messages.return_value = mock_emails
    
    # Simulate fetch_email_content returning enriched content
    mock_fetch_content.side_effect = [
        "Body 1 plus attachment 1", 
        "Body 2 plus attachment 2"
    ]

    # 3. Call the function directly
    ingest_emails_task(db=mock_db_session, query="test query")

    # 4. Assert that the correct calls were made
    mock_email_repo.list_messages.assert_called_once_with(search="test query", top=100)
    
    # Assert that we tried to fetch content for each email, including attachments
    expected_fetch_calls = [
        call("email1", include_attachments=True),
        call("email2", include_attachments=True)
    ]
    mock_fetch_content.assert_has_calls(expected_fetch_calls)

    # 5. Assert that the data sent to the DB was the enriched data
    # We inspect the arguments passed to the `add_emails` method
    call_args, _ = mock_vector_repo_instance.add_emails.call_args
    sent_emails = call_args[0]
    
    assert len(sent_emails) == 2
    assert sent_emails[0].body.content == "Body 1 plus attachment 1"
    assert sent_emails[1].body.content == "Body 2 plus attachment 2"

def test_query_emails(client, mocker):
    """
    Tests the GET /rag/query endpoint.
    """
    # 1. Mock the VectorDBRepository
    mock_query_results = [
        # This is a simplified mock. In a real scenario, you'd use a mock RAGEmail object.
        {"id": "test_id", "subject": "Test Subject", "content": "Test content.", "sent_date_time": "2025-01-01T12:00:00", "embedding": [0.1, 0.2]}
    ]
    
    mock_vector_repo_instance = MagicMock()
    mock_vector_repo_instance.query.return_value = mock_query_results
    mocker.patch(
        "app.routes.rag.VectorDBRepository",
        return_value=mock_vector_repo_instance
    )
    
    # 2. Call the API
    query = "what is the project status"
    response = client.get(f"/rag/query?q={query}")
    
    # 3. Assert the response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "test_id"
    mock_vector_repo_instance.query.assert_called_once_with(query) 