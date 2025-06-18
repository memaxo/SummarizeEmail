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
from tests.auth.helpers import create_test_token
from app.config import settings
from app.database import get_redis

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
    
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })

    # Mock the service layer to simulate a cache miss
    mocker.patch("app.routes.messages.services.fetch_email_content", return_value=email_content)
    mock_chain = mocker.patch("app.routes.messages.services.run_summarization_chain", return_value=(expected_summary, False))
    
    # Call the API endpoint with POST method
    api_response = client.post(
        f"/messages/{message_id}/summary",
        headers={"Authorization": f"Bearer {token}"}
    )

    # Assert the response
    assert api_response.status_code == 200
    assert api_response.json()["summary"] == expected_summary
    assert api_response.json()["cached"] is False
    assert api_response.json()["message_id"] == message_id

    # Assert the mocks were called correctly
    mock_chain.assert_called_once()


def test_summarize_with_attachments(client, mocker):
    """
    Tests that the `include_attachments` flag is correctly passed to the service layer.
    """
    message_id = "test_message_id_456"
    expected_summary = "This is a summary of an email and its attachment."
    
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })

    # 1. Mock the service-level function that gets called by the endpoint
    mock_fetch = mocker.patch("app.routes.messages.services.fetch_email_content", return_value="email and attachment content")
    mocker.patch("app.routes.messages.services.run_summarization_chain", return_value=(expected_summary, False))

    # 2. Call the API endpoint with POST method
    response = client.post(
        f"/messages/{message_id}/summary?include_attachments=true",
        headers={"Authorization": f"Bearer {token}"}
    )

    # 3. Assert the response is successful
    assert response.status_code == 200
    assert response.json()["summary"] == expected_summary
    assert response.json()["include_attachments"] is True

    # 4. Verify that the mock was called with the correct arguments
    mock_fetch.assert_called_once_with(message_id, user_id, include_attachments=True)


@responses.activate
def test_summarize_cache_hit(client, mocker):
    """
    Tests that a cached summary is returned correctly.
    """
    message_id = "test_message_id_123"
    email_content = "This is a test email body."
    expected_summary = "This is a summary."
    
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })

    # 1. Set up fake Redis with the cached value
    cache_key = f"summary:{hashlib.sha256(email_content.encode()).hexdigest()}"
    
    # Create a proper async mock for Redis
    from unittest.mock import AsyncMock
    
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=lambda key: expected_summary if key == cache_key else None)
    mock_redis.set = AsyncMock(return_value=True)
    
    # Replace the get_redis dependency
    async def get_mock_redis():
        return mock_redis
    
    app.dependency_overrides[get_redis] = get_mock_redis

    # 2. Mock the underlying service
    mocker.patch("app.routes.messages.services.fetch_email_content", return_value=email_content)
    
    # Mock the LLM chain (shouldn't be called due to cache hit)
    mock_llm_chain = MagicMock()
    mocker.patch("app.services.email.load_summarize_chain", return_value=mock_llm_chain)

    try:
        # 3. Call the API with POST method
        response = client.post(
            f"/messages/{message_id}/summary",
            headers={"Authorization": f"Bearer {token}"}
        )

        # 4. Assert the response
        assert response.status_code == 200
        assert response.json()["summary"] == expected_summary
        assert response.json()["cached"] is True

        # 5. Assert that the LLM was NOT called (cache hit)
        mock_llm_chain.invoke.assert_not_called()
    finally:
        # Clean up dependency override
        app.dependency_overrides.pop(get_redis, None)


def test_summarize_graph_api_error(client, mocker):
    """
    Tests that a 500 error from Graph API results in a 502 from our service.
    """
    message_id = "graph_error_id"
    
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    mocker.patch("app.routes.messages.services.fetch_email_content", side_effect=GraphApiError("Test Graph API Error"))
    
    api_response = client.post(
        f"/messages/{message_id}/summary",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert api_response.status_code == 502
    assert "Graph API error" in api_response.json()["detail"]


def test_summarize_not_found(client, mocker):
    """
    Tests the scenario where the requested email message is not found (404).
    """
    message_id = "non_existent_id"
    
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    mocker.patch("app.routes.messages.services.fetch_email_content", side_effect=EmailNotFoundError(message_id))
    
    api_response = client.post(
        f"/messages/{message_id}/summary",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert api_response.status_code == 404
    assert message_id in api_response.json()["detail"]


def test_health_check(client):
    """
    Tests the health check endpoint.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_message(client, mocker):
    """Tests retrieving a single message."""
    message_id = "test_id"
    
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    mock_email = Email(
        id=message_id,
        subject="Test",
        body=EmailBody(content="c", contentType="t"),
        from_address={"emailAddress": {"address": "test@test.com"}},
        toRecipients=[],
        sentDateTime="-"
    )
    mocker.patch("app.routes.messages.EmailRepository.get_message", return_value=mock_email)

    response = client.get(
        f"/messages/{message_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == message_id


def test_list_attachments(client, mocker):
    """Tests listing attachments for a message."""
    message_id = "test_id"
    
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    mock_attachments = [Attachment(id="att1", name="test.txt", contentType="text/plain", size=123, isInline=False)]
    mocker.patch("app.routes.messages.EmailRepository.list_attachments", return_value=mock_attachments)

    response = client.get(
        f"/messages/{message_id}/attachments",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == "att1"


def test_get_single_attachment(client, mocker):
    """Tests retrieving a single attachment."""
    message_id = "test_id"
    attachment_id = "att1"
    
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    mock_attachment = Attachment(
        id=attachment_id,
        name="test.txt",
        contentType="text/plain",
        size=123,
        isInline=False,
        contentBytes="dGVzdA==" # "test" in base64
    )
    mocker.patch("app.routes.messages.EmailRepository.get_attachment", return_value=mock_attachment)

    response = client.get(
        f"/messages/{message_id}/attachments/{attachment_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == attachment_id
    assert response.json()["contentBytes"] == "dGVzdA=="
