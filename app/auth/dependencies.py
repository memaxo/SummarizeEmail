"""
FastAPI dependencies for authentication.
"""
from typing import Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .validator import TokenValidator
from ..config import settings

# Create a single instance of the bearer scheme
bearer_scheme = HTTPBearer()

# Create a single instance of the token validator
token_validator = TokenValidator(
    tenant_id=settings.AZURE_TENANT_ID,
    client_id=settings.AZURE_CLIENT_ID
)


async def get_validated_token_claims(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> Dict:
    """
    Validates the JWT token and returns the claims.
    
    Args:
        credentials: The HTTP authorization credentials containing the bearer token
        
    Returns:
        Dict containing the validated token claims
        
    Raises:
        HTTPException: If the token is invalid or missing required claims
    """
    try:
        claims = await token_validator.validate_token(credentials.credentials)
        return claims
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(claims: Dict = Depends(get_validated_token_claims)) -> str:
    """
    Extracts the user ID from validated token claims.
    
    Args:
        claims: The validated JWT claims
        
    Returns:
        The user ID string
        
    Raises:
        HTTPException: If the user ID cannot be extracted
    """
    user_id = claims.get("oid") or claims.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id 