import pytest
from fastapi.testclient import TestClient
import fakeredis
from unittest.mock import patch, MagicMock
import os
from dotenv import load_dotenv

from .auth.helpers import PUBLIC_KEY_PEM

# Load .env file for testing environment
load_dotenv()

TEST_TENANT_ID = "00000000-0000-0000-0000-000000000000"
TEST_CLIENT_ID = "11111111-1111-1111-1111-111111111111"

# Set test environment variables, prioritizing .env file over defaults
os.environ.update({
    "LLM_PROVIDER": os.getenv("LLM_PROVIDER", "gemini"),
    "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY"),
    "GOOGLE_APPLICATION_CREDENTIALS": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    "GOOGLE_CLOUD_PROJECT": os.getenv("GOOGLE_CLOUD_PROJECT"),
    
    # Set static Azure AD identifiers for consistent testing
    "AZURE_TENANT_ID": TEST_TENANT_ID,
    "AZURE_CLIENT_ID": TEST_CLIENT_ID,
    "AZURE_CLIENT_SECRET": "test_secret",
    
    # Mock other credentials for tests that don't hit external services
    "TARGET_USER_ID": "test_user",
    "REDIS_URL": "redis://localhost:6379/0",
    "POSTGRES_USER": "test_user",
    "POSTGRES_PASSWORD": "test_password",
    "POSTGRES_DB": "test_db",
    "POSTGRES_SERVER": "localhost",
    "POSTGRES_PORT": "5432",
    "DB_USER": "test_user",
    "DB_PASSWORD": "test_password",
    "DB_NAME": "test_db",
    "DB_HOST": "localhost",
    "DB_PORT": "5433",
    "USE_MOCK_GRAPH_API": "true", # Default to mock graph for most tests
})

# Mock the database engine before importing the app
with patch('sqlalchemy.create_engine') as mock_create_engine:
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine
    
    # Now import the app after mocking
    from app.main import app

@pytest.fixture(autouse=True)
def mock_jwks_client(monkeypatch):
    """
    Mocks the JWKS client to prevent network calls to Azure AD during tests.
    It provides a test public key to validate tokens signed with the test private key.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    
    # Load the public key from PEM
    public_key = serialization.load_pem_public_key(
        PUBLIC_KEY_PEM, 
        backend=default_backend()
    )
    
    # We create a mock signing key object that the PyJWKClient would normally return
    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    # Mock the PyJWKClient class itself
    class MockPyJWKClient:
        def __init__(self, *args, **kwargs):
            # Don't make any network calls
            pass
            
        def get_signing_key_from_jwt(self, token):
            return mock_signing_key
    
    # Replace the PyJWKClient class with our mock
    monkeypatch.setattr("jwt.PyJWKClient", MockPyJWKClient)
    
    # Also need to patch it in the validator module since it's already imported
    monkeypatch.setattr("app.auth.validator.PyJWKClient", MockPyJWKClient)
    
    # Also mock the httpx client to prevent any network calls
    async def mock_get(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.json.return_value = {"jwks_uri": "https://mock.jwks.uri"}
        mock_response.raise_for_status = MagicMock()
        return mock_response
    
    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)


@pytest.fixture
def client():
    """Create a test client with mocked Redis and database."""
    # Create a fake Redis instance for testing
    fake_redis = fakeredis.FakeRedis(decode_responses=True)
    
    # Mock the database initialization to prevent actual DB connections
    with patch('app.db.session.init_db') as mock_init_db:
        mock_init_db.return_value = None
        
        # Mock the scheduler to prevent it from running
        with patch('app.main.scheduler') as mock_scheduler:
            mock_scheduler.running = False
            
            # Mock get_db to return a mock session
            with patch('app.db.session.get_db') as mock_get_db:
                mock_session = MagicMock()
                mock_get_db.return_value = iter([mock_session])
                
                # Mock redis.from_url to return our fake Redis
                with patch('app.main.redis.from_url') as mock_redis_from_url:
                    mock_redis_from_url.return_value = fake_redis
                    
                    # Create the test client
                    with TestClient(app) as test_client:
                        # Ensure the fake Redis is set on the app state
                        test_client.app.state.redis = fake_redis
                        yield test_client


@pytest.fixture
def mock_redis():
    """Provide a fake Redis instance for tests that need direct Redis access."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset environment variables to test defaults for each test."""
    # Environment variables are already set at module level
    pass 