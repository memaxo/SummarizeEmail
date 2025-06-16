import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app

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