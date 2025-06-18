"""
Microsoft Graph API authentication for service-to-service communication.
"""
import logging
import msal

from ..config import settings
from ..exceptions import GraphApiError

# Set up a logger for the auth module
logger = logging.getLogger(__name__)


def get_graph_token() -> str:
    """
    Acquires an OAuth2 token for the Microsoft Graph API using the
    client credentials flow.

    This function uses the MSAL library, which handles token caching automatically
    to avoid re-requesting a token on every call.

    Returns:
        str: The access token for Microsoft Graph API.

    Raises:
        GraphApiError: If the token acquisition fails.
    """
    # Return mock token for testing
    if settings.USE_MOCK_GRAPH_API:
        logger.info("Using mock Graph API token")
        return "mock-token-for-testing"
    
    logger.info("Acquiring Microsoft Graph API token...")
    # We create a new ConfidentialClientApplication each time, but MSAL's
    # internal token cache (in-memory by default) is keyed by client_id, authority, etc.
    # so we still benefit from caching. For a stateless or multi-replica setup,
    # a persistent token cache (like Redis) would be needed.
    # See: https://msal-python.readthedocs.io/en/latest/#tokencache
    cca = msal.ConfidentialClientApplication(
        settings.AZURE_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}",
        client_credential=settings.AZURE_CLIENT_SECRET,
    )

    # The acquire_token_for_client call will first look for a valid token in the cache
    token_result = cca.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )

    if "access_token" not in token_result:
        error_details = token_result.get("error_description", "No error description provided.")
        logger.error(f"Could not acquire Graph API token. Response: {token_result}")
        raise GraphApiError(
            f"Could not acquire token. Please check your Azure AD app credentials and permissions. Details: {error_details}"
        )

    logger.info("Successfully acquired Microsoft Graph API token.")
    return token_result["access_token"] 