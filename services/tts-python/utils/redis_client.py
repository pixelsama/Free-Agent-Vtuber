import redis.asyncio as redis
from typing import Dict, Any

class RedisClient:
    """
    An asynchronous Redis client with connection pooling.
    """

    def __init__(self, config: Dict[str, Any]):
        self.pool = redis.ConnectionPool(
            host=config.get("host", "localhost"),
            port=config.get("port", 6379),
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
