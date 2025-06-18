"""
Test file to verify authentication updates work correctly.
This tests the new JWT authentication system.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import Request

from app.graph.email_repository import EmailRepository
from app.rag.vector_db_repository import VectorDBRepository
from tests.auth.helpers import create_test_token
from app.config import settings


def test_email_repository_with_user_id():
    """Test EmailRepository accepts dynamic user ID."""
    # Test with specific user ID
    repo = EmailRepository(user_id="custom_user_123")
    assert repo.user_id == "custom_user_123"
    assert "custom_user_123" in repo._base_url
    
    # Test fallback to TARGET_USER_ID
    import app.graph.email_repository
    original_target = app.graph.email_repository.settings.TARGET_USER_ID
    app.graph.email_repository.settings.TARGET_USER_ID = "default_user"
    
    try:
        repo_default = EmailRepository()
        assert repo_default.user_id == "default_user"
    finally:
        app.graph.email_repository.settings.TARGET_USER_ID = original_target


def test_vector_db_repository_with_user_id(mocker):
    """Test VectorDBRepository handles user_id for multi-tenant support."""
    # Mock dependencies
    mock_db = MagicMock()
    mock_embedding_model = MagicMock()
    mocker.patch("app.rag.vector_db_repository.get_embedding_model", return_value=mock_embedding_model)
    
    repo = VectorDBRepository(mock_db)
    
    # Test add_emails with user_id
    from app.graph.models import Email, EmailBody
    test_email = Email(
        id="test_id",
        subject="Test",
        body=EmailBody(content="Test content", contentType="text/plain"),
        from_address={"emailAddress": {"address": "test@example.com"}},
        toRecipients=[],
        sentDateTime="2024-01-01T00:00:00Z"
    )
    
    mock_embedding_model.embed_documents.return_value = [[0.1, 0.2, 0.3]]
    
    repo.add_emails([test_email], user_id="test_user_456")
    
    # Verify the email was added with user_id
    assert mock_db.add_all.called
    added_embeddings = mock_db.add_all.call_args[0][0]
    assert len(added_embeddings) == 1
    assert added_embeddings[0].user_id == "test_user_456"
    
    # Test query with user_id
    mock_embedding_model.embed_query.return_value = [0.1, 0.2, 0.3]
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    
    repo.query("test query", user_id="test_user_456")
    
    # Verify filter was called with user_id
    mock_db.query.return_value.filter.assert_called_once()


@pytest.mark.asyncio
async def test_routes_use_dynamic_user_id(client, mocker):
    """Test that routes properly extract and use user ID from JWT tokens."""
    # Create a valid token for authentication
    user_id = "oauth_user_789"
    token = create_test_token(
        claims={
            "oid": user_id,
            "aud": settings.AZURE_CLIENT_ID,
            "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
        }
    )
    
    # Mock EmailRepository to track instantiation
    mock_repo_class = mocker.patch("app.routes.emails.EmailRepository")
    mock_repo_instance = MagicMock()
    mock_repo_instance.list_messages.return_value = []
    mock_repo_class.return_value = mock_repo_instance
    
    # Make a request with authentication
    response = client.get(
        "/emails/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    # Verify EmailRepository was created with the OAuth user ID
    mock_repo_class.assert_called_once_with(user_id=user_id) 