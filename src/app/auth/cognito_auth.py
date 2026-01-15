"""
AWS Cognito authentication and authorization middleware.
"""
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
import requests
from functools import lru_cache

from src.settings import settings


security = HTTPBearer()


@lru_cache(maxsize=1)
def get_cognito_public_keys():
    """
    Fetch Cognito public keys for JWT verification.
    Cached to avoid repeated requests.
    """
    url = f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com/{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch Cognito public keys: {str(e)}"
        )


def get_public_key(token: str):
    """
    Get the appropriate public key for JWT verification.
    """
    try:
        # Decode token header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing key ID"
            )
        
        # Get public keys
        keys = get_cognito_public_keys()
        
        # Find the matching key
        for key in keys.get("keys", []):
            if key.get("kid") == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(key)
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to find matching public key"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Error getting public key: {str(e)}"
        )


def verify_token(token: str) -> dict:
    """
    Verify and decode JWT token from AWS Cognito.
    Supports both ID tokens and Access tokens.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Get public key
        public_key = get_public_key(token)
        
        # Decode without verification first to check token type
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        token_use = unverified_payload.get("token_use")
        
        issuer = f"https://cognito-idp.{settings.COGNITO_REGION}.amazonaws.com/{settings.COGNITO_USER_POOL_ID}"
        
        # Verify and decode token
        # ID tokens have audience=CLIENT_ID, Access tokens don't have audience
        if token_use == "id":
            # ID Token validation
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=settings.COGNITO_CLIENT_ID,
                issuer=issuer,
            )
        elif token_use == "access":
            # Access Token validation (no audience check)
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=issuer,
            )
        else:
            # Try with audience first (ID token), then without (Access token)
            try:
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    audience=settings.COGNITO_CLIENT_ID,
                    issuer=issuer,
                )
            except jwt.InvalidAudienceError:
                # If audience fails, try without audience (Access token)
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=["RS256"],
                    issuer=issuer,
                )
        
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}"
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency function for FastAPI endpoints that require authentication.
    
    This function validates the JWT token and extracts user information.
    Use this as a dependency in any endpoint that requires authentication.
    
    Usage in endpoints:
        @router.get("/example")
        def example_endpoint(
            current_user: dict = Depends(get_current_user)  # ← Requires authentication
        ):
            # current_user contains: user_id, username, groups, email
            ...
    
    Args:
        credentials: HTTP Bearer token credentials (automatically extracted from Authorization header)
        
    Returns:
        Dictionary with user information:
        {
            "user_id": str,      # Cognito user ID (sub claim)
            "username": str,     # Username
            "groups": list,      # Cognito groups (e.g., ["uploader"])
            "email": str         # User email (if available)
        }
        
    Raises:
        HTTPException 401: If token is missing, invalid, or expired
        
    Note:
        This function only validates authentication, NOT authorization.
        To require a specific group, use require_group() instead.
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    # Extract user information
    user_id = payload.get("sub")
    username = payload.get("username") or payload.get("cognito:username")
    groups = payload.get("cognito:groups", [])
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID"
        )
    
    return {
        "user_id": user_id,
        "username": username,
        "groups": groups,
        "email": payload.get("email"),
    }


def require_group(allowed_group: str = settings.ALLOWED_GROUP):
    """
    Dependency factory to require a specific Cognito group for authorization.
    
    This function creates a dependency that validates both authentication AND
    group membership. Use this for endpoints that require specific permissions.
    
    Usage in endpoints:
        @router.post("/upload")
        def upload_endpoint(
            current_user: dict = Depends(require_group("uploader"))  # ← Requires "uploader" group
        ):
            # Only users in "uploader" group can access this
            ...
    
    Args:
        allowed_group: Required Cognito group name (default: "uploader" from settings)
        
    Returns:
        Dependency function that:
        1. Validates JWT token (via get_current_user)
        2. Checks if user belongs to the required group
        3. Returns user info if authorized
        
    Raises:
        HTTPException 401: If token is invalid (from get_current_user)
        HTTPException 403: If user doesn't belong to required group
        
    Example:
        # Use default group from settings
        Depends(require_group())
        
        # Use custom group
        Depends(require_group("admin"))
    """
    def group_checker(user: dict = Depends(get_current_user)) -> dict:
        """
        Verify user belongs to the required group.
        
        This is the actual dependency function that gets executed.
        It first calls get_current_user() to validate authentication,
        then checks group membership.
        
        Args:
            user: Current user from get_current_user dependency
            
        Returns:
            User information if authorized
            
        Raises:
            HTTPException 403: If user doesn't belong to required group
        """
        user_groups = user.get("groups", [])
        
        if allowed_group not in user_groups:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User must belong to group '{allowed_group}'"
            )
        
        return user
    
    return group_checker
