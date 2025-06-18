from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone

from .helpers import create_test_token
from app.config import settings

def test_valid_token_access(client: TestClient):
    """
    Tests that a valid, correctly signed token provides access to a protected endpoint.
    """
    user_id = "test-user-123"
    token = create_test_token(
        claims={
            "oid": user_id,
            "aud": settings.AZURE_CLIENT_ID,
            "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
        }
    )
    
    response = client.get(
        "/emails/",
        headers={"Authorization": f"Bearer {token}"}
    )
    # 200 OK means authentication was successful.
    # The endpoint may return an empty list if no emails are found, which is fine.
    assert response.status_code == 200

def test_no_token_access(client: TestClient):
    """
    Tests that a request without a token is rejected with a 403 Forbidden error.
    HTTPBearer returns 403 by default when no Authorization header is provided.
    """
    response = client.get("/emails/")
    assert response.status_code == 403
    assert "Not authenticated" in response.json()["detail"]

def test_expired_token(client: TestClient):
    """
    Tests that a token that is past its expiration time is rejected.
    """
    user_id = "test-user-123"
    # Create a token that expired 1 minute ago
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    
    token = create_test_token(
        claims={
            "oid": user_id,
            "aud": settings.AZURE_CLIENT_ID,
            "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/",
            "exp": expired_time
        }
    )
    
    response = client.get(
        "/emails/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert "Token has expired" in response.json()["detail"]
    
def test_invalid_signature(client: TestClient):
    """
    Tests that a token with an invalid signature is rejected.
    We simulate this by creating a token and then modifying it.
    """
    user_id = "test-user-123"
    token = create_test_token(
        claims={
            "oid": user_id,
            "aud": settings.AZURE_CLIENT_ID,
            "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
        }
    )
    
    # Modify the token to make the signature invalid
    # JWT format is header.payload.signature, so we'll change the payload
    parts = token.split('.')
    if len(parts) == 3:
        # Change one character in the payload
        modified_payload = parts[1][:-1] + ('A' if parts[1][-1] != 'A' else 'B')
        invalid_token = f"{parts[0]}.{modified_payload}.{parts[2]}"
    else:
        invalid_token = token + "invalid"
    
    response = client.get(
        "/emails/",
        headers={"Authorization": f"Bearer {invalid_token}"}
    )
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]

def test_invalid_audience(client: TestClient):
    """
    Tests that a token with the wrong 'aud' (audience) claim is rejected.
    """
    user_id = "test-user-123"
    token = create_test_token(
        claims={
            "oid": user_id,
            "aud": "some-other-application-client-id",
            "iss": f"https://sts.windows.net/{settings.AZURE_TENANT_ID}/"
        }
    )
    
    response = client.get(
        "/emails/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert "Invalid token audience" in response.json()["detail"]

def test_invalid_issuer(client: TestClient):
    """
    Tests that a token with the wrong 'iss' (issuer) claim is rejected.
    """
    user_id = "test-user-123"
    token = create_test_token(
        claims={
            "oid": user_id,
            "aud": settings.AZURE_CLIENT_ID,
            "iss": "https://some-other-issuer.com/"
        }
    )
    
    response = client.get(
        "/emails/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
    assert "Invalid token issuer" in response.json()["detail"] 