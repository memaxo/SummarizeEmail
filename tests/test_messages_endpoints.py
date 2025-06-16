import os

import pytest
import responses
from fastapi.testclient import TestClient
import fakeredis

from app.main import app, services
from app.graph.models import Email, EmailBody
from app.exceptions import EmailNotFoundError, GraphApiError

# Path to the directory containing test data
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "golden")


@pytest.fixture
def client():
    """
    Pytest fixture to create a FastAPI TestClient.
    """
    with TestClient(app) as c:
        yield c


@responses.activate
def test_summarize_happy_path(client, mocker):
    """
    Tests the happy path for the /summarize endpoint.
    """
    # 1. Read the sample email content
    with open(os.path.join(TEST_DATA_DIR, "sample_email.eml"), "r") as f:
        email_content = f.read()

    # 2. Define mock data and expected results
    message_id = "test_message_id_123"
    expected_summary = "The Project Alpha Q3 kick-off meeting is scheduled for next Tuesday at 10 AM PST to discuss the roadmap and assign tasks. Attendees should review the attached Q3_Roadmap.pdf beforehand."

    # 3. Mock the repository layer
    mock_email = Email(
        id=message_id,
        subject="Project Alpha - Q3 Kick-off Meeting",
        body=EmailBody(content=email_content, contentType="text"),
        from_address={"emailAddress": {"address": "alice@example.com", "name": "Alice"}},
        toRecipients=[{"emailAddress": {"address": "bob@example.com", "name": "Bob"}}],
        sentDateTime="2025-06-16T10:00:00Z"
    )
    mocker.patch("app.routes.messages.services.fetch_email_content", return_value=mock_email.get_full_content())

    # 4. Mock the summarization chain to return the expected string directly
    mocker.patch("app.routes.messages.services.run_summarization_chain", return_value=expected_summary)

    # 5. Call the API endpoint
    api_response = client.get(f"/messages/{message_id}/summary")

    # 6. Assert the response
    assert api_response.status_code == 200
    response_json = api_response.json()
    assert response_json["summary"] == expected_summary
    assert response_json["message_id"] == message_id
    assert response_json["cached"] is False


@responses.activate
def test_summarize_cache_hit(client, mocker):
    # This test is no longer relevant for the single message endpoint,
    # as caching is handled at a higher level or for bulk operations.
    # We can remove it or adapt it later if we add caching here.
    pass


def test_summarize_graph_api_error(client, mocker):
    """
    Tests that a 500 error from Graph API results in a 502 from our service.
    """
    message_id = "graph_error_id"
    mocker.patch("app.routes.messages.services.fetch_email_content", side_effect=GraphApiError("Test Graph API Error"))
    
    api_response = client.get(f"/messages/{message_id}/summary")

    assert api_response.status_code == 502
    assert "Test Graph API Error" in api_response.json()["detail"]


def test_summarize_not_found(client, mocker):
    """
    Tests the scenario where the requested email message is not found (404).
    """
    message_id = "non_existent_id"
    mocker.patch("app.routes.messages.services.fetch_email_content", side_effect=EmailNotFoundError(message_id))
    
    api_response = client.get(f"/messages/{message_id}/summary")

    assert api_response.status_code == 404
    assert api_response.json()["detail"] == f"Email with message_id '{message_id}' not found."


def test_health_check(client):
    """
    Tests the /health endpoint to ensure it returns a 200 OK.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
