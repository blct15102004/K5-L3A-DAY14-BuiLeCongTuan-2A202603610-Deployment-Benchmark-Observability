"""
Rate limiting (tiêu chí 7) — sliding window 60 giây lưu trong Redis.
"""
import logging
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

logger = logging.getLogger("agent.rate_limiter")
WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """Giới hạn RATE_LIMIT_PER_MINUTE request / 60 giây theo từng API key."""
    if r is None:
        logger.warning("redis_unavailable_for_rate_limit")
        return

    redis_key = f"ratelimit:{key}"
    now = time.time()
    window_start = now - WINDOW_SECONDS

    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        _, current_count = pipe.execute()

        if current_count >= settings.rate_limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(WINDOW_SECONDS)},
            )

        member = f"{now:.6f}-{uuid.uuid4().hex[:8]}"
        pipe = r.pipeline()
        pipe.zadd(redis_key, {member: now})
        pipe.expire(redis_key, WINDOW_SECONDS + 5)
        pipe.execute()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("rate_limit_redis_error", extra={"error": str(exc)})
