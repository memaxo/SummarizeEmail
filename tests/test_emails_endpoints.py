import pytest
from fastapi.testclient import TestClient
from unittest.mock import call, MagicMock
import fakeredis

from app.main import app
from app.graph.models import Email, EmailBody

def test_search_emails_no_filters(client, mocker):
    """
    Tests the GET /emails endpoint with no filters, expecting a default call.
    """
    # Mock the user ID extraction
    mocker.patch(
        "app.routes.emails.get_user_id_from_token",
        return_value="test_user"
    )
    
    # 1. Mock the repository layer
    mock_list_messages = mocker.patch(
        "app.routes.emails.EmailRepository.list_messages",
        return_value=[]
    )

    # 2. Call the API
    response = client.get("/emails/")
    
    # 3. Assert the response and the repository call
    assert response.status_code == 200
    assert response.json() == []
    mock_list_messages.assert_called_once_with(
        search=None,
        from_address=None,
        subject_contains=None,
        is_unread=None,
        start_datetime=None,
        end_datetime=None,
        top=25, # Default limit
    )

def test_search_emails_with_filters(client, mocker):
    """
    Tests the GET /emails endpoint with all filters applied.
    """
    # 1. Mock the repository layer
    mock_list_messages = mocker.patch(
        "app.routes.emails.EmailRepository.list_messages",
        return_value=[
            Email(id="id1", subject="Test", body=EmailBody(content="c", contentType="t"), from_address={"emailAddress":{}}, toRecipients=[], sentDateTime="-")
        ]
    )
    
    # 2. Define filter parameters
    params = {
        "search": "meeting",
        "from_address": "test@example.com",
        "subject_contains": "urgent",
        "is_unread": "true",
        "start_date": "2025-01-01T00:00:00",
        "end_date": "2025-01-31T23:59:59",
        "limit": "50"
    }

    # 3. Call the API
    response = client.get("/emails/", params=params)
    
    # 4. Assert the response and that the correct parameters were passed to the repo
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    # Extract the call arguments to verify them
    call_args = mock_list_messages.call_args[1]
    assert call_args["search"] == params["search"]
    assert call_args["from_address"] == params["from_address"]
    assert call_args["subject_contains"] == params["subject_contains"]
    assert call_args["is_unread"] is True
    assert call_args["start_datetime"].isoformat() == params["start_date"]
    assert call_args["end_datetime"].isoformat() == params["end_date"]
    assert call_args["top"] == int(params["limit"]) 