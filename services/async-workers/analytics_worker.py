import asyncio
import json
import os
import sys
from typing import Any, Dict

import redis.asyncio as redis


STREAM = os.getenv("ANALYTICS_STREAM", "events.analytics")
GROUP = os.getenv("ANALYTICS_GROUP", "a11y-workers")
CONSUMER = os.getenv("ANALYTICS_CONSUMER", os.uname().nodename)
BLOCK_MS = int(os.getenv("ANALYTICS_BLOCK_MS", "2000"))


async def ensure_group(r: redis.Redis) -> None:
    try:
        await r.xgroup_create(name=STREAM, groupname=GROUP, id="$", mkstream=True)
    except Exception:
        pass


async def handle_message(fields: Dict[str, Any]) -> None:
    try:
        etype = fields.get("type")
        payload = json.loads(fields.get("payload", "{}"))
    except Exception:
        etype = fields.get("type")
        payload = {"raw": fields.get("payload")}
    print(f"[analytics_worker] type={etype} payload.keys={list(payload)[:5]}")


async def main():
    r = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", "6379")), decode_responses=True)
    await r.ping()
    await ensure_group(r)
    while True:
        try:
            resp = await r.xreadgroup(groupname=GROUP, consumername=CONSUMER, streams={STREAM: ">"}, count=10, block=BLOCK_MS)
            if not resp:
                continue
            for stream, messages in resp:
                for msg_id, fields in messages:
                    await handle_message(fields)
                    await r.xack(STREAM, GROUP, msg_id)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[analytics_worker] error: {e}")
            await asyncio.sleep(0.5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

