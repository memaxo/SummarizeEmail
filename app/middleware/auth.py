"""
JWT Token Validation Middleware for Production

This middleware validates JWT tokens from Custom GPT OAuth flow.
In development, it's bypassed when TARGET_USER_ID is used.
"""

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
from jwt import PyJWKClient
import structlog

from ..config import settings

logger = structlog.get_logger(__name__)

# Security scheme for OAuth2
security = HTTPBearer(auto_error=False)

class JWTValidator:
    """Validates JWT tokens from Microsoft/Azure AD"""
    
    def __init__(self):
        # Microsoft's public key endpoint for token validation
        self.jwks_client = PyJWKClient(
            "https://login.microsoftonline.com/common/discovery/v2.0/keys"
        )
    
    async def validate_token(self, token: str) -> dict:
        """
        Validate a JWT token and return the decoded claims.
        
        Args:
            token: The JWT token to validate
            
        Returns:
            Decoded token claims
            
        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Get the signing key from Microsoft
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate the token
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.AZURE_CLIENT_ID,  # Your app's client ID
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True
                }
            )
            
            logger.info("Token validated successfully", 
                       user_id=decoded.get('oid') or decoded.get('sub'))
            return decoded
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token", error=str(e))
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            logger.error("Token validation error", error=str(e))
            raise HTTPException(status_code=401, detail="Authentication failed")

# Global validator instance
jwt_validator = JWTValidator()

async def validate_request(request: Request) -> Optional[dict]:
    """
    Validate the request's JWT token if present.
    
    In development mode (when using TARGET_USER_ID), this is optional.
    In production with Custom GPT, this ensures valid authentication.
    
    Args:
        request: The incoming request
        
    Returns:
        Decoded token claims or None if no token
    """
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        # No token provided - OK in development mode
        logger.debug("No bearer token in request")
        return None
    
    token = auth_header.split(" ")[1]
    
    # In production, validate the token
    if settings.ENVIRONMENT == "production":
        return await jwt_validator.validate_token(token)
    else:
        # In development, optionally validate or just decode without verification
        try:
            # Decode without verification for development
            decoded = jwt.decode(token, options={"verify_signature": False})
            logger.debug("Token decoded (dev mode)", user_id=decoded.get('oid'))
            return decoded
        except Exception as e:
            logger.warning("Failed to decode token in dev mode", error=str(e))
            return None 