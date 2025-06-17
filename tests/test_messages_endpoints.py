import os

import pytest
import responses
from fastapi.testclient import TestClient
import fakeredis
import hashlib
from unittest.mock import MagicMock

from app.main import app
from app.graph.models import Email, EmailBody, Attachment
from app.exceptions import EmailNotFoundError, GraphApiError

# Path to the directory containing test data
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "golden")


@responses.activate
def test_summarize_happy_path_cache_miss(client, mocker):
    """
    Tests the happy path for the /summarize endpoint on a cache miss.
    """
    message_id = "test_message_id_123"
    email_content = "This is a test email body."
    expected_summary = "This is a summary."

    # Mock the service layer to simulate a cache miss
    mocker.patch("app.routes.messages.services.fetch_email_content", return_value=email_content)
    mock_chain = mocker.patch("app.routes.messages.services.run_summarization_chain", return_value=(expected_summary, False))

    # Call the API endpoint
    api_response = client.get(f"/messages/{message_id}/summary")

    # Assert the response
    assert api_response.status_code == 200
    response_json = api_response.json()
    assert response_json["summary"] == expected_summary
    assert response_json["cached"] is False
    mock_chain.assert_called_once()


def test_summarize_with_attachments(client, mocker):
    """
    Tests that the `include_attachments` flag is correctly passed to the service layer.
    """
    message_id = "test_message_id_456"
    expected_summary = "This is a summary of an email and its attachment."
    
    # 1. Mock the service-level function that gets called by the endpoint
    mock_fetch = mocker.patch("app.routes.messages.services.fetch_email_content", return_value="email and attachment content")
    mocker.patch("app.routes.messages.services.run_summarization_chain", return_value=(expected_summary, False))
    
    # 2. Call the API endpoint
    response = client.get(f"/messages/{message_id}/summary?include_attachments=true")
    
    # 3. Assert the response is successful
    assert response.status_code == 200
    assert response.json()["summary"] == expected_summary
    
    # 4. Assert that the service function was called with the correct arguments
    mock_fetch.assert_called_once_with(message_id, include_attachments=True)


@responses.activate
def test_summarize_cache_hit(client, mocker):
    """
    Tests that a cached summary is returned correctly.
    """
    message_id = "test_message_id_123"
    email_content = "This is a test email body."
    expected_summary = "This is a summary."
    
    # 1. Manually set the value in the fake redis
    cache_key = f"summary:{hashlib.sha256(email_content.encode()).hexdigest()}"
    client.app.state.redis.set(cache_key, expected_summary)

    # 2. Mock the underlying service and the LLM chain itself.
    # We want the caching logic in run_summarization_chain to execute,
    # but we don't want to actually call the LLM.
    mocker.patch("app.routes.messages.services.fetch_email_content", return_value=email_content)
    mock_llm_chain = MagicMock()
    mocker.patch("app.services.email.load_summarize_chain", return_value=mock_llm_chain)

    # 3. Call the API
    response = client.get(f"/messages/{message_id}/summary")

    # 4. Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == expected_summary
    assert data["cached"] is True
    
    # 5. Assert that the summarization chain was NOT called
    mock_llm_chain.run.assert_not_called()


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


def test_get_message(client, mocker):
    """Tests retrieving a single message."""
    message_id = "test_id"
    mock_email = Email(
        id=message_id,
        subject="Test",
        body=EmailBody(content="c", contentType="t"),
        from_address={"emailAddress": {"address": "test@test.com"}},
        toRecipients=[],
        sentDateTime="-"
    )
    mocker.patch("app.routes.messages.EmailRepository.get_message", return_value=mock_email)
    
    response = client.get(f"/messages/{message_id}")
    
    assert response.status_code == 200
    assert response.json()["id"] == message_id


def test_list_attachments(client, mocker):
    """Tests listing attachments for a message."""
    message_id = "test_id"
    mock_attachments = [Attachment(id="att1", name="test.txt", contentType="text/plain", size=123, isInline=False)]
    mocker.patch("app.routes.messages.EmailRepository.list_attachments", return_value=mock_attachments)
    
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
    mocker.patch("app.routes.messages.EmailRepository.get_attachment", return_value=mock_attachment)
    
    response = client.get(f"/messages/{message_id}/attachments/{attachment_id}")
    
    assert response.status_code == 200
    assert response.json()["contentBytes"] == "dGVzdA=="
