"""
Unit tests for the TokenValidator class.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError, InvalidAudienceError, InvalidIssuerError
from fastapi import HTTPException

from app.auth.validator import TokenValidator
from app.config import settings


class TestTokenValidator:
    """Test cases for TokenValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a TokenValidator instance for testing."""
        return TokenValidator(
            tenant_id="test-tenant-id",
            client_id="test-client-id"
        )
    
    @pytest.fixture
    def valid_token_payload(self):
        """Create a valid token payload."""
        now = datetime.utcnow()
        return {
            "aud": "test-client-id",
            "iss": "https://sts.windows.net/test-tenant-id/",
            "exp": now + timedelta(hours=1),
            "nbf": now - timedelta(minutes=5),
            "iat": now - timedelta(minutes=5),
            "oid": "test-user-id",
            "name": "Test User",
            "email": "test@example.com"
        }
    
    @pytest.mark.asyncio
    async def test_validate_token_success(self, validator, valid_token_payload, mocker):
        """Test successful token validation."""
        # Mock the OIDC metadata fetch
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value={"jwks_uri": "https://mock.jwks.uri"})
        mock_response.raise_for_status = MagicMock()
        
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the PyJWKClient
        mock_jwk_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        
        with patch("app.auth.validator.httpx.AsyncClient", return_value=mock_httpx_client):
            with patch("app.auth.validator.PyJWKClient", return_value=mock_jwk_client):
                with patch("jwt.decode", return_value=valid_token_payload):
                    # Test
                    result = await validator.validate_token("test-token")
                    
                    # Assert
                    assert result == valid_token_payload
                    mock_jwk_client.get_signing_key_from_jwt.assert_called_once_with("test-token")
    
    @pytest.mark.asyncio
    async def test_validate_token_invalid_audience(self, validator, valid_token_payload, mocker):
        """Test token validation with invalid audience."""
        # Mock the OIDC metadata fetch
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value={"jwks_uri": "https://mock.jwks.uri"})
        mock_response.raise_for_status = MagicMock()
        
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the PyJWKClient
        mock_jwk_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        
        with patch("app.auth.validator.httpx.AsyncClient", return_value=mock_httpx_client):
            with patch("app.auth.validator.PyJWKClient", return_value=mock_jwk_client):
                with patch("jwt.decode", side_effect=InvalidAudienceError("Invalid audience")):
                    # Test & Assert
                    with pytest.raises(HTTPException) as exc_info:
                        await validator.validate_token("test-token")
                    
                    assert exc_info.value.status_code == 401
                    assert "Invalid token audience" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_validate_token_invalid_issuer(self, validator, valid_token_payload, mocker):
        """Test token validation with invalid issuer."""
        # Mock the OIDC metadata fetch
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value={"jwks_uri": "https://mock.jwks.uri"})
        mock_response.raise_for_status = MagicMock()
        
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the PyJWKClient
        mock_jwk_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        
        with patch("app.auth.validator.httpx.AsyncClient", return_value=mock_httpx_client):
            with patch("app.auth.validator.PyJWKClient", return_value=mock_jwk_client):
                with patch("jwt.decode", side_effect=InvalidIssuerError("Invalid issuer")):
                    # Test & Assert
                    with pytest.raises(HTTPException) as exc_info:
                        await validator.validate_token("test-token")
                    
                    assert exc_info.value.status_code == 401
                    assert "Invalid token issuer" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_validate_token_expired(self, validator, mocker):
        """Test token validation with expired token."""
        # Mock the OIDC metadata fetch
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value={"jwks_uri": "https://mock.jwks.uri"})
        mock_response.raise_for_status = MagicMock()
        
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the PyJWKClient
        mock_jwk_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        
        with patch("app.auth.validator.httpx.AsyncClient", return_value=mock_httpx_client):
            with patch("app.auth.validator.PyJWKClient", return_value=mock_jwk_client):
                with patch("jwt.decode", side_effect=ExpiredSignatureError("Token expired")):
                    # Test & Assert
                    with pytest.raises(HTTPException) as exc_info:
                        await validator.validate_token("test-token")
                    
                    assert exc_info.value.status_code == 401
                    assert "Token has expired" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_validate_token_invalid_signature(self, validator, mocker):
        """Test token validation with invalid signature."""
        # Mock the OIDC metadata fetch
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value={"jwks_uri": "https://mock.jwks.uri"})
        mock_response.raise_for_status = MagicMock()
        
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.__aexit__ = AsyncMock(return_value=None)
        
        # Mock the PyJWKClient
        mock_jwk_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test-key"
        mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
        
        with patch("app.auth.validator.httpx.AsyncClient", return_value=mock_httpx_client):
            with patch("app.auth.validator.PyJWKClient", return_value=mock_jwk_client):
                with patch("jwt.decode", side_effect=InvalidTokenError("Invalid signature")):
                    # Test & Assert
                    with pytest.raises(HTTPException) as exc_info:
                        await validator.validate_token("test-token")
                    
                    assert exc_info.value.status_code == 401
                    assert "Invalid token" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_load_keys_failure(self, validator, mocker):
        """Test handling of OIDC metadata fetch failure."""
        # Mock the OIDC metadata fetch to fail
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.__aexit__ = AsyncMock(return_value=None)
        
        with patch("app.auth.validator.httpx.AsyncClient", return_value=mock_httpx_client):
            # Test & Assert
            with pytest.raises(HTTPException) as exc_info:
                await validator.validate_token("test-token")
            
            assert exc_info.value.status_code == 500
            assert "Could not fetch authentication keys" in exc_info.value.detail
    
    def test_metadata_url_construction(self, validator):
        """Test that metadata URL is constructed correctly."""
        expected_url = "https://login.microsoftonline.com/test-tenant-id/v2.0/.well-known/openid-configuration"
        assert validator.metadata_url == expected_url 