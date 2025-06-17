"""
Test file to verify authentication updates work correctly.
This tests the new OAuth/JWT handling for Custom GPT integration.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import Request

from app.services.email import get_user_id_from_token
from app.graph.email_repository import EmailRepository
from app.rag.vector_db_repository import VectorDBRepository


@pytest.mark.asyncio
async def test_get_user_id_from_token_with_bearer():
    """Test extracting user ID from OAuth token."""
    # Create a mock request with Authorization header
    request = MagicMock(spec=Request)
    request.headers = {
        "Authorization": "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJvaWQiOiJ0ZXN0X3VzZXJfMTIzIiwic3ViIjoidGVzdF91c2VyXzEyMyJ9.test"
    }
    
    # Mock jwt.decode to return test data
    import app.services.email
    original_decode = app.services.email.jwt.decode
    app.services.email.jwt.decode = lambda token, **kwargs: {"oid": "test_user_123", "sub": "test_user_123"}
    
    try:
        user_id = await get_user_id_from_token(request)
        assert user_id == "test_user_123"
    finally:
        app.services.email.jwt.decode = original_decode


@pytest.mark.asyncio
async def test_get_user_id_from_token_without_bearer(mocker):
    """Test fallback to TARGET_USER_ID when no token present."""
    # Create a mock request without Authorization header
    request = MagicMock(spec=Request)
    request.headers = {}
    
    # Mock settings to return a test TARGET_USER_ID
    mocker.patch("app.services.email.settings.TARGET_USER_ID", "fallback_user")
    
    user_id = await get_user_id_from_token(request)
    assert user_id == "fallback_user"


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
    """Test that routes properly extract and use user ID from tokens."""
    # Mock get_user_id_from_token to return a test user
    mocker.patch("app.routes.emails.get_user_id_from_token", return_value="oauth_user_789")
    
    # Mock EmailRepository to track instantiation
    mock_repo_class = mocker.patch("app.routes.emails.EmailRepository")
    mock_repo_instance = MagicMock()
    mock_repo_instance.list_messages.return_value = []
    mock_repo_class.return_value = mock_repo_instance
    
    # Make a request
    response = client.get("/emails/")
    
    assert response.status_code == 200
    # Verify EmailRepository was created with the OAuth user ID
    mock_repo_class.assert_called_once_with(user_id="oauth_user_789") 