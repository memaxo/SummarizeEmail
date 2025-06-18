from datetime import datetime, timedelta, timezone
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Generate a static, reusable RSA key pair for the entire test suite.
# This avoids re-generating keys for every test run and ensures consistency.
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

public_key = private_key.public_key()

# Serialize the keys into PEM format, which is what the jwt library expects.
PRIVATE_KEY_PEM = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

PUBLIC_KEY_PEM = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

TEST_KID = "test-key-id"

def create_test_token(
    claims: dict,
    headers: dict = {"kid": TEST_KID},
    algorithm: str = "RS256",
):
    """
    Encodes a JWT with the test private key.
    Merges default claims with any provided claims.
    """
    # Set default expiry and issued-at-time if not provided
    now = datetime.now(timezone.utc)
    
    # Defaults that can be overridden by the claims dict
    full_claims = {
        "iat": now,
        "exp": now + timedelta(seconds=3600),
        **claims
    }
    
    return jwt.encode(full_claims, PRIVATE_KEY_PEM, algorithm=algorithm, headers=headers) 