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
    mock_email_repo = mocker.patch("app.routes.rag.EmailRepository")
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
    response = client.get(f"/rag/query?q={query}")
    
    # 4. Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == expected_answer
    assert len(data["source_documents"]) == 1
    assert data["source_documents"][0]["id"] == "email1"
    
    # 5. Assert the service calls
    mock_db_repo.query.assert_called_once_with(query)
    # This assertion is a bit tricky as the Document objects are created inline
    # So we check the chain was called, but not the exact content of the docs
    mock_rag_chain.assert_called_once() 