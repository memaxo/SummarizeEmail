import os

import pytest
import responses
from fastapi.testclient import TestClient

from app.main import app

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
    - Mocks Microsoft Graph API to return a sample email.
    - Mocks the LLM (OpenAI) API to return a predefined summary.
    - Verifies that the endpoint returns a 200 OK and the correct summary.
    """
    # 1. Read the sample email content to be used in the mock response
    with open(os.path.join(TEST_DATA_DIR, "sample_email.eml"), "r") as f:
        email_content = f.read()

    # The subject is extracted from the email content for the mock response
    subject_line = [line for line in email_content.split('\n') if line.lower().startswith("subject:")][0]
    email_subject = subject_line.split(":", 1)[1].strip()
    
    # 2. Define mock responses for external services
    message_id = "test_message_id_123"
    graph_url = f"https://graph.microsoft.com/v1.0/users/test_user/messages/{message_id}"
    openid_config_url = "https://login.microsoftonline.com/test/v2.0/.well-known/openid-configuration"
    expected_summary = "The Project Alpha Q3 kick-off meeting is scheduled for next Tuesday at 10 AM PST to discuss the roadmap and assign tasks. Attendees should review the attached Q3_Roadmap.pdf beforehand."

    # Mock for MSAL's OpenID configuration discovery
    responses.add(
        responses.GET,
        openid_config_url,
        json={
            "token_endpoint": "https://login.microsoftonline.com/test/oauth2/v2.0/token",
            "authorization_endpoint": "https://login.microsoftonline.com/test/oauth2/v2.0/authorize",
        },
        status=200,
    )

    # Mock for MSAL's token acquisition
    responses.add(
        responses.POST,
        "https://login.microsoftonline.com/test/oauth2/v2.0/token",
        json={"access_token": "fake_token", "expires_in": 3600},
        status=200,
    )

    # Mock for Microsoft Graph API
    responses.add(
        responses.GET,
        graph_url,
        json={"subject": email_subject, "body": {"content": email_content}},
        status=200,
    )

    # Mock the load_summarize_chain function to return a mock chain
    # that has a `run` method returning our expected summary.
    # This avoids the Pydantic validation error within the chain.
    mock_chain = mocker.MagicMock()
    mock_chain.run.return_value = expected_summary
    mocker.patch("app.services.load_summarize_chain", return_value=mock_chain)

    # 3. Call the API endpoint
    # We use the pytest.ini for base settings, but can still override
    # if a specific test needs a different value.
    api_response = client.get(f"/summarize?msg_id={message_id}")

    # 4. Assert the response
    assert api_response.status_code == 200
    response_json = api_response.json()
    assert response_json["summary"] == expected_summary
    assert response_json["message_id"] == message_id
    assert response_json["cached"] is False
    
    # Clean up the override
    app.dependency_overrides = {}


@responses.activate
def test_summarize_not_found(client):
    """
    Tests the scenario where the requested email message is not found (404).
    """
    message_id = "non_existent_id"
    graph_url = f"https://graph.microsoft.com/v1.0/users/test_user/messages/{message_id}"
    openid_config_url = "https://login.microsoftonline.com/test/v2.0/.well-known/openid-configuration"

    # Mock for MSAL discovery and token acquisition
    responses.add(
        responses.GET,
        openid_config_url,
        status=200,
        json={
            "token_endpoint": "https://login.microsoftonline.com/test/oauth2/v2.0/token",
            "authorization_endpoint": "https://login.microsoftonline.com/test/oauth2/v2.0/authorize",
        },
    )
    responses.add(responses.POST, "https://login.microsoftonline.com/test/oauth2/v2.0/token", status=200, json={"access_token": "..."})

    # Mock a 404 from the Graph API
    responses.add(responses.GET, graph_url, json={"error": "not found"}, status=404)
    
    api_response = client.get(f"/summarize?msg_id={message_id}")

    assert api_response.status_code == 404
    assert api_response.json()["detail"] == f"Email with message_id '{message_id}' not found."


def test_health_check(client):
    """
    Tests the /health endpoint to ensure it returns a 200 OK.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
