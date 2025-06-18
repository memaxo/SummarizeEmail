"""
Unit tests for Microsoft Graph API authentication.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.auth.graph import get_graph_token
from app.exceptions import GraphApiError
from app.config import settings


class TestGraphAuthentication:
    """Test cases for Graph API authentication."""
    
    @patch('app.auth.graph.settings')
    def test_get_graph_token_mock_mode(self, mock_settings):
        """Test that mock token is returned when USE_MOCK_GRAPH_API is True."""
        mock_settings.USE_MOCK_GRAPH_API = True
        
        token = get_graph_token()
        
        assert token == "mock-token-for-testing"
    
    @patch('app.auth.graph.msal.ConfidentialClientApplication')
    @patch('app.auth.graph.settings')
    def test_get_graph_token_success(self, mock_settings, mock_msal):
        """Test successful token acquisition."""
        # Setup
        mock_settings.USE_MOCK_GRAPH_API = False
        mock_settings.AZURE_TENANT_ID = "test-tenant"
        mock_settings.AZURE_CLIENT_ID = "test-client"
        mock_settings.AZURE_CLIENT_SECRET = "test-secret"
        
        mock_app = MagicMock()
        mock_msal.return_value = mock_app
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        # Test
        token = get_graph_token()
        
        # Assert
        assert token == "test-access-token"
        mock_msal.assert_called_once_with(
            "test-client",
            authority="https://login.microsoftonline.com/test-tenant",
            client_credential="test-secret"
        )
        mock_app.acquire_token_for_client.assert_called_once_with(
            scopes=["https://graph.microsoft.com/.default"]
        )
    
    @patch('app.auth.graph.msal.ConfidentialClientApplication')
    @patch('app.auth.graph.settings')
    def test_get_graph_token_failure_no_token(self, mock_settings, mock_msal):
        """Test token acquisition failure when no access token is returned."""
        # Setup
        mock_settings.USE_MOCK_GRAPH_API = False
        mock_settings.AZURE_TENANT_ID = "test-tenant"
        mock_settings.AZURE_CLIENT_ID = "test-client"
        mock_settings.AZURE_CLIENT_SECRET = "test-secret"
        
        mock_app = MagicMock()
        mock_msal.return_value = mock_app
        mock_app.acquire_token_for_client.return_value = {}
        
        # Test & Assert
        with pytest.raises(GraphApiError, match="Could not acquire token"):
            get_graph_token()
    
    @patch('app.auth.graph.msal.ConfidentialClientApplication')
    @patch('app.auth.graph.settings')
    def test_get_graph_token_failure_with_error(self, mock_settings, mock_msal):
        """Test token acquisition failure with error details."""
        # Setup
        mock_settings.USE_MOCK_GRAPH_API = False
        mock_settings.AZURE_TENANT_ID = "test-tenant"
        mock_settings.AZURE_CLIENT_ID = "test-client"
        mock_settings.AZURE_CLIENT_SECRET = "test-secret"
        
        mock_app = MagicMock()
        mock_msal.return_value = mock_app
        mock_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Invalid client credentials"
        }
        
        # Test & Assert
        with pytest.raises(GraphApiError, match="Invalid client credentials"):
            get_graph_token()
    
    @patch('app.auth.graph.msal.ConfidentialClientApplication')
    @patch('app.auth.graph.settings')
    def test_get_graph_token_caching(self, mock_settings, mock_msal):
        """Test that MSAL handles token caching internally."""
        # Setup
        mock_settings.USE_MOCK_GRAPH_API = False
        mock_settings.AZURE_TENANT_ID = "test-tenant"
        mock_settings.AZURE_CLIENT_ID = "test-client"
        mock_settings.AZURE_CLIENT_SECRET = "test-secret"
        
        mock_app = MagicMock()
        mock_msal.return_value = mock_app
        
        # First call returns token
        mock_app.acquire_token_for_client.return_value = {
            "access_token": "cached-token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        # Test - call twice
        token1 = get_graph_token()
        token2 = get_graph_token()
        
        # Assert
        assert token1 == "cached-token"
        assert token2 == "cached-token"
        
        # MSAL should be instantiated twice (once per call)
        assert mock_msal.call_count == 2
        
        # But acquire_token_for_client should also be called twice
        # (MSAL handles caching internally)
        assert mock_app.acquire_token_for_client.call_count == 2 