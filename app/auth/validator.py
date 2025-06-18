# This file will contain the new, secure token validation logic.
import httpx
import jwt
from fastapi import HTTPException
from jwt import PyJWKClient
from typing import Dict
import structlog

logger = structlog.get_logger(__name__)

class TokenValidator:
    """
    Handles fetching and caching of Azure AD's public keys and validating JWTs.
    """
    def __init__(self, tenant_id: str, client_id: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.metadata_url = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0/.well-known/openid-configuration"
        self.jwks_client = None

    async def load_keys(self):
        """
        Loads the JWKS (JSON Web Key Set) from the OIDC discovery endpoint.
        """
        if self.jwks_client:
            return

        try:
            async with httpx.AsyncClient() as client:
                logger.info("Fetching OIDC metadata", url=self.metadata_url)
                response = await client.get(self.metadata_url)
                response.raise_for_status()
                metadata = response.json()
                jwks_uri = metadata.get("jwks_uri")
                if not jwks_uri:
                    raise ValueError("jwks_uri not found in OIDC metadata")
                
                self.jwks_client = PyJWKClient(jwks_uri)
                logger.info("Successfully loaded JWKS client", jwks_uri=jwks_uri)

        except Exception as e:
            logger.error("Failed to load OIDC keys", exc_info=e)
            raise HTTPException(status_code=500, detail="Could not fetch authentication keys from provider.")

    async def validate_token(self, token: str) -> Dict:
        """
        Validates the JWT signature, expiration, and claims.

        Args:
            token: The encoded JWT string.

        Returns:
            The decoded token claims if valid.

        Raises:
            HTTPException: If the token is invalid in any way.
        """
        if not self.jwks_client:
            await self.load_keys()
        
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode the token, validating signature, expiration, and claims
            decoded_token = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=f"https://sts.windows.net/{self.tenant_id}/" # Note the trailing slash
            )
            return decoded_token

        except jwt.ExpiredSignatureError:
            logger.warning("Token validation failed: Expired signature")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidAudienceError:
            logger.warning("Token validation failed: Invalid audience")
            raise HTTPException(status_code=401, detail="Invalid token audience")
        except jwt.InvalidIssuerError:
            logger.warning("Token validation failed: Invalid issuer")
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        except Exception as e:
            logger.error("An unexpected error occurred during token validation", exc_info=e)
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

 