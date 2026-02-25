import uuid
from datetime import timedelta, datetime
from typing import Any, Union

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.models.operation_log import OperationLog
from sqlmodel import Session

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Export ALGORITHM for other modules
ALGORITHM = settings.ALGORITHM

# Redis client for token blocklist (lazy init)
_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client

# Prefix for revoked token keys in Redis
_REVOKED_TOKEN_PREFIX = "revoked_token:"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    now = datetime.utcnow()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = str(uuid.uuid4())
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "jti": jti,
        "iat": int(now.timestamp()),
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def revoke_token(jti: str, ttl: int) -> None:
    """Add a token's jti to the Redis blocklist with a TTL (in seconds).

    The TTL should match the remaining lifetime of the token so the
    blocklist entry is automatically cleaned up after the token would
    have expired anyway.
    """
    _get_redis().setex(f"{_REVOKED_TOKEN_PREFIX}{jti}", ttl, "1")


def is_token_revoked(jti: str) -> bool:
    """Check whether a token's jti has been revoked."""
    return _get_redis().exists(f"{_REVOKED_TOKEN_PREFIX}{jti}") > 0

def create_log(session: Session, action: str, username: str, details: str = None, ip_address: str = None, status: str = "success"):
    try:
        log = OperationLog(
            action=action,
            username=username,
            details=details,
            ip_address=ip_address,
            status=status
        )
        session.add(log)
        session.commit()
    except Exception as e:
        print(f"Failed to create log: {e}")
