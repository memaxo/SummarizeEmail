"""
Database utilities and dependencies for FastAPI.
"""
from typing import Optional
import redis.asyncio as redis
from sqlalchemy.orm import Session
import structlog

from .db.session import SessionLocal
from .config import settings

logger = structlog.get_logger(__name__)

# Global Redis client
redis_client: Optional[redis.Redis] = None


def get_db():
    """
    FastAPI dependency to provide a database session per request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_redis() -> Optional[redis.Redis]:
    """
    FastAPI dependency to provide Redis client.
    Returns None if Redis is not available.
    """
    global redis_client
    
    if redis_client is None:
        try:
            redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            # Test the connection
            await redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            return None
    
    return redis_client


async def close_redis():
    """
    Close Redis connection on shutdown.
    """
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None 