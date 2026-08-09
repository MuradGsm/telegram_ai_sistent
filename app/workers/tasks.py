from arq.connections import RedisSettings

from app.core.conf import settings


async def ping(ctx: dict) -> str:
    return "pong"


class WorkerSettings:
    functions = [ping]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)