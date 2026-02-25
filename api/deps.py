"""
Firebase Auth dependency — verifies Firebase ID tokens on incoming
requests and returns the caller's UID and email for data isolation.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Extract the Firebase ID token from the Authorization header,
    verify it, and return a dict with the user's UID and email.
    """
    try:
        decoded = auth.verify_id_token(credentials.credentials)
        return {"uid": decoded["uid"], "email": decoded.get("email", "")}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired Firebase token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
