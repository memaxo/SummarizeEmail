import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import fakeredis
from fastapi import Request
from unittest.mock import MagicMock

from app.main import app
from app.graph.models import Email, EmailBody
from tests.auth.helpers import create_test_token
from app.config import settings

def test_summarize_bulk(client, mocker):
    """
    Tests the POST /summaries/bulk endpoint for bulk summarization.
    """
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    # 1. Mock the repository and service layers
    message_ids = ["id1", "id2"]
    expected_summary = "This is a summary."

    mocker.patch(
        "app.routes.summaries.services.fetch_email_content",
        return_value="email content"
    )
    mocker.patch(
        "app.routes.summaries.services.summarize_email",
        return_value=expected_summary
    )

    # 2. Call the API with correct endpoint
    response = client.post(
        "/summaries/bulk", 
        json={"message_ids": message_ids},
        headers={"Authorization": f"Bearer {token}"}
    )

    # 3. Assert the response
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["summaries"]) == 2
    assert all(s["summary"] == expected_summary for s in response.json()["summaries"])

def test_summarize_daily_digest(client, mocker):
    """
    Tests the POST /summaries/daily endpoint.
    """
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    # 1. Mock the repository and service layers
    expected_summary = "This is the daily summary."

    mock_email = Email(
        id="id", 
        subject="s", 
        body=EmailBody(content="c", contentType="t"), 
        from_address={"emailAddress":{"address":"test@test.com"}}, 
        toRecipients=[], 
        sentDateTime="-"
    )
    
    mocker.patch(
        "app.routes.summaries.EmailRepository.list_messages",
        return_value=[mock_email]
    )
    mocker.patch(
        "app.routes.summaries.services.summarize_email",
        return_value=expected_summary
    )

    # 2. Call the API with POST method
    response = client.post(
        "/summaries/daily",
        headers={"Authorization": f"Bearer {token}"}
    )

    # 3. Assert the response
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["summaries"][0]["summary"] == expected_summary

def test_summarize_daily_digest_no_emails(client, mocker):
    """
    Tests the daily digest when no emails are found.
    """
    # Create auth token
    user_id = "test_user"
    token = create_test_token(claims={
        "oid": user_id,
        "aud": settings.AZURE_CLIENT_ID,
        "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
    })
    
    # 1. Mock the repository to return an empty list
    mocker.patch(
        "app.routes.summaries.EmailRepository.list_messages",
        return_value=[]
    )

    # 2. Call the API with POST method
    response = client.post(
        "/summaries/daily",
        headers={"Authorization": f"Bearer {token}"}
    )

    # 3. Assert the response
    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["summaries"] == [] 