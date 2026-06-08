from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings
import redis
from loguru import logger

# Password Crypt Context
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Optional Redis connection for token revocation
redis_client: Optional[redis.Redis] = None
try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Connected to Redis successfully for token blacklist.")
except Exception as e:
    logger.warning(f"Could not connect to Redis for token blacklist ({e}). Using in-memory store fallback.")
    # Local fallback for blacklist
    _in_memory_blacklist = set()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"JWT Decode error: {e}")
        raise

def blacklist_token(token: str, expires_in_seconds: int) -> None:
    """Add a token to the blacklist to revoke it."""
    if redis_client:
        try:
            redis_client.setex(f"blacklist:{token}", expires_in_seconds, "true")
            logger.info("Revoked token successfully in Redis.")
        except Exception as e:
            logger.error(f"Failed to blacklist token in Redis: {e}")
            _in_memory_blacklist.add(token)
    else:
        _in_memory_blacklist.add(token)

def is_token_blacklisted(token: str) -> bool:
    """Check if token is blacklisted."""
    if redis_client:
        try:
            val = redis_client.get(f"blacklist:{token}")
            return val is not None
        except Exception as e:
            logger.error(f"Failed to check token blacklist in Redis: {e}")
            return token in _in_memory_blacklist
    else:
        return token in _in_memory_blacklist
