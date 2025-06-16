import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import fakeredis
from fastapi import Request
from unittest.mock import MagicMock

from app.main import app
from app.graph.models import Email, EmailBody

def test_summarize_bulk(client, mocker):
    """
    Tests the POST /summaries endpoint for bulk summarization.
    """
    # 1. Mock the repository and service layers
    message_ids = ["id1", "id2"]
    expected_digest = "This is a digest of two emails."

    mocker.patch(
        "app.routes.summaries.email_repository.get_message",
        return_value=Email(id="id", subject="s", body=EmailBody(content="c", contentType="t"), from_address={"emailAddress":{"address":"test@test.com"}}, toRecipients=[], sentDateTime="-")
    )
    mocker.patch(
        "app.routes.summaries.services.run_bulk_summarization",
        return_value=(expected_digest, False)
    )

    # 2. Call the API
    response = client.post("/summaries", json={"message_ids": message_ids})

    # 3. Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["digest"] == expected_digest
    assert data["llm_provider"] == "openai" # From pytest.ini default

def test_summarize_daily_digest(client, mocker):
    """
    Tests the GET /summaries/daily endpoint.
    """
    # 1. Mock the repository and service layers
    expected_digest = "This is the daily digest."
    
    mocker.patch(
        "app.routes.summaries.email_repository.list_messages",
        return_value=[Email(id="id", subject="s", body=EmailBody(content="c", contentType="t"), from_address={"emailAddress":{"address":"test@test.com"}}, toRecipients=[], sentDateTime="-")]
    )
    mocker.patch(
        "app.routes.summaries.services.run_bulk_summarization",
        return_value=(expected_digest, False)
    )
    
    # 2. Call the API
    response = client.get("/summaries/daily")

    # 3. Assert the response
    assert response.status_code == 200
    data = response.json()
    assert data["digest"] == expected_digest

def test_summarize_daily_digest_no_emails(client, mocker):
    """
    Tests the daily digest when no emails are found.
    """
    # 1. Mock the repository to return an empty list
    mocker.patch(
        "app.routes.summaries.email_repository.list_messages",
        return_value=[]
    )
    mocker.patch(
        "app.routes.summaries.services.run_bulk_summarization",
        return_value=("No emails to summarize.", False)
    )
    
    # 2. Call the API
    response = client.get("/summaries/daily")

    # 3. Assert the response
    assert response.status_code == 200
    assert response.json()["digest"] == "No emails to summarize." 