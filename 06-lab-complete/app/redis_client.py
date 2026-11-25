"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

App vẫn khởi động được khi Redis chưa sẵn sàng (không ping lúc import).
"""
import redis

from app.config import settings


def _create_client() -> redis.Redis | None:
    if not settings.redis_url:
        return None
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1.0,
        socket_timeout=1.0,
    )


r = _create_client()


def redis_healthy() -> bool:
    """Ping Redis cho GET /ready; lỗi kết nối -> False."""
    if r is None:
        return False
    try:
        return bool(r.ping())
    except Exception:
        return False
