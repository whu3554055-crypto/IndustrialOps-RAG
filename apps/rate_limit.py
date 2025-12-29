"""Gateway QPS 限流 — Redis 令牌桶；Redis 不可用时放行."""

from __future__ import annotations

import time

from apps.config import get_settings, load_profile


def _limits() -> tuple[int, int]:
    gw = load_profile().get("gateway", {})
    return int(gw.get("rate_limit_qps", 30)), int(gw.get("rate_limit_burst", 60))


def allow_request(client_key: str) -> bool:
    """返回 True 表示允许通过."""
    qps, burst = _limits()
    try:
        import redis

        r = redis.from_url(get_settings().redis_url, decode_responses=True)
        now = int(time.time())
        bucket = f"ior:rl:{client_key}:{now}"
        pipe = r.pipeline()
        pipe.incr(bucket)
        pipe.expire(bucket, 2)
        count, _ = pipe.execute()
        return int(count) <= max(qps, burst)
    except Exception:
        return True
