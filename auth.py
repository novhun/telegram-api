import jwt
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
import os
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "your-very-secure-secret-key-123")
ALGORITHM = "HS256"
security = HTTPBearer()

def create_token(payload: dict) -> str:
    """Create persistent JWT token without expiration"""
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validate token and check Telegram session status"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        
        from telegram_client import is_session_active
        if not await is_session_active(payload["phone"]):
            raise HTTPException(status_code=401, detail="Telegram session expired")
            
        return payload
    except jwt.PyJWTError as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

def validate_token_not_expired(token: str):
    """Validate token without session check (for middleware)"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
    except jwt.PyJWTError as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from valid token"""
    try:
        payload = validate_token_not_expired(credentials.credentials)
        return {"phone": payload["phone"]}
    except HTTPException as e:
        raise e

def logout_user(token: str):
    """Logout handler (stateless)"""
    return {"message": "Logged out", "success": True}