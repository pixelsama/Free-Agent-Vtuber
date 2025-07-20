import redis.asyncio as redis
import os
from typing import Dict, Any

class RedisClient:
    """
    An asynchronous Redis client with connection pooling.
    """

    def __init__(self, config: Dict[str, Any]):
        redis_host = os.getenv("REDIS_HOST", config.get("host", "localhost"))
        redis_port = int(os.getenv("REDIS_PORT", config.get("port", 6379)))

        self.pool = redis.ConnectionPool(
            host=redis_host,
            port=redis_port,
            db=config.get("db", 0),
            password=config.get("password"),
            decode_responses=True
        )
        self.client = redis.Redis(connection_pool=self.pool)

    async def publish(self, channel: str, message: str):
        """
        Publishes a message to a Redis channel.
        """
        await self.client.publish(channel, message)

    async def blpop(self, keys: list, timeout: int):
        """
        Blocking list pop from one or more lists.
        """
        return await self.client.blpop(keys, timeout)

    async def close(self):
        """
        Closes the Redis connection.
        """
        await self.client.close()
        await self.pool.disconnect()

    def get_client(self):
        """
        Returns the raw redis client instance.
        """
        return self.client
