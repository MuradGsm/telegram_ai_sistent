from redis.asyncio import Redis
from app.core.conf import settings

redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)