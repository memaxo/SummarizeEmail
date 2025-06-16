import os

import pytest
import responses
from fastapi.testclient import TestClient
import fakeredis

from app.main import app
from app.graph.models import Email, EmailBody, Attachment
from app.exceptions import EmailNotFoundError, GraphApiError

# Path to the directory containing test data
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "golden")


@pytest.fixture
def client(mocker):
    """
    Pytest fixture to create a FastAPI TestClient.
    """
    mocker.patch("app.main.init_db", return_value=None)
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
    mocker.patch("app.services.fetch_email_content", return_value=mock_email.get_full_content())

    # 4. Mock the summarization chain to return the expected string directly
    mocker.patch("app.services.run_summarization_chain", return_value=expected_summary)

    # 5. Call the API endpoint
    api_response = client.get(f"/messages/{message_id}/summary")

    # 6. Assert the response
    assert api_response.status_code == 200
    response_json = api_response.json()
    assert response_json["summary"] == expected_summary
    assert response_json["message_id"] == message_id
    assert response_json["cached"] is False


def test_summarize_with_attachments(client, mocker):
    """
    Tests that the `include_attachments` flag is correctly passed to the service layer.
    """
    message_id = "test_message_id_456"
    expected_summary = "This is a summary of an email and its attachment."
    
    # 1. Mock the service-level function that gets called by the endpoint
    mock_fetch = mocker.patch("app.services.fetch_email_content", return_value="email and attachment content")
    mocker.patch("app.services.run_summarization_chain", return_value=expected_summary)
    
    # 2. Call the API endpoint with the query parameter
    response = client.get(f"/messages/{message_id}/summary?include_attachments=true")
    
    # 3. Assert the response is successful
    assert response.status_code == 200
    assert response.json()["summary"] == expected_summary
    
    # 4. Assert that the service function was called with the correct arguments
    mock_fetch.assert_called_once_with(message_id, include_attachments=True)


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
    mocker.patch("app.services.fetch_email_content", side_effect=GraphApiError("Test Graph API Error"))
    
    api_response = client.get(f"/messages/{message_id}/summary")

    assert api_response.status_code == 502
    assert "Test Graph API Error" in api_response.json()["detail"]


def test_summarize_not_found(client, mocker):
    """
    Tests the scenario where the requested email message is not found (404).
    """
    message_id = "non_existent_id"
    mocker.patch("app.services.fetch_email_content", side_effect=EmailNotFoundError(message_id))
    
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


def test_get_message(client, mocker):
    """Tests retrieving a single message."""
    message_id = "test_id"
    mock_email = Email(
        id=message_id,
        subject="Test",
        body=EmailBody(content="c", contentType="t"),
        from_address={"emailAddress": {}},
        toRecipients=[],
        sentDateTime="-"
    )
    mocker.patch("app.routes.messages.email_repository.get_message", return_value=mock_email)
    
    response = client.get(f"/messages/{message_id}")
    
    assert response.status_code == 200
    assert response.json()["id"] == message_id


def test_list_attachments(client, mocker):
    """Tests listing attachments for a message."""
    message_id = "test_id"
    mock_attachments = [Attachment(id="att1", name="test.txt", contentType="text/plain", size=123, isInline=False)]
    mocker.patch("app.routes.messages.email_repository.list_attachments", return_value=mock_attachments)
    
    response = client.get(f"/messages/{message_id}/attachments")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "test.txt"


def test_get_single_attachment(client, mocker):
    """Tests retrieving a single attachment."""
    message_id = "test_id"
    attachment_id = "att1"
    mock_attachment = Attachment(
        id=attachment_id,
        name="test.txt",
        contentType="text/plain",
        size=123,
        isInline=False,
        contentBytes="dGVzdA==" # "test" in base64
    )
    mocker.patch("app.routes.messages.email_repository.get_attachment", return_value=mock_attachment)
    
    response = client.get(f"/messages/{message_id}/attachments/{attachment_id}")
    
    assert response.status_code == 200
    assert response.json()["contentBytes"] == "dGVzdA=="
