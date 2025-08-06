import asyncio
import json
import os
import signal
import uuid
from typing import Any, Dict, Optional

from redis.asyncio import Redis

from schemas import AppConfig, TaskMessage, ResultMessage
from providers.factory import build_provider, FakeProvider
from providers.asr_provider import BaseASRProvider


# 轻量日志
def log(level: str, msg: str, **kwargs: Any) -> None:
    extra = f" | {json.dumps(kwargs, ensure_ascii=False)}" if kwargs else ""
    print(f"[ASR][{level}] {msg}{extra}", flush=True)


def load_config(config_path: Optional[str] = None) -> AppConfig:
    cfg_path = config_path or os.path.join(os.path.dirname(__file__), "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return AppConfig(**raw)


class RedisClient:
    def __init__(self, host: str, port: int, db: int) -> None:
        self._client = Redis(host=host, port=port, db=db, decode_responses=True)

    async def blpop(self, queue: str, timeout: int = 1) -> Optional[str]:
        item = await self._client.blpop(queue, timeout=timeout)
        if item is None:
            return None
        return item[1]

    async def publish(self, channel: str, message: str) -> None:
        await self._client.publish(channel, message)

    async def lpush(self, queue: str, message: str) -> None:
        await self._client.lpush(queue, message)

    async def close(self) -> None:
        try:
            await self._client.close()
        except Exception:
            pass


async def worker_loop(
    name: str,
    redis_client: RedisClient,
    tasks_queue: str,
    results_channel: str,
    provider: BaseASRProvider,
    timeout_sec: int,
) -> None:
    log("INFO", f"Worker {name} started")
    while True:
        msg = await redis_client.blpop(tasks_queue, timeout=1)
        if not msg:
            continue
        try:
            data = json.loads(msg)
            task = TaskMessage(**data)  # Pydantic 校验
        except Exception as e:
            log("ERROR", "Invalid task message", raw=msg, error=str(e))
            continue

        task_id = task.task_id
        meta = task.meta.model_dump()

        # 仅支持文件路径
        if task.audio.type != "file" or not task.audio.path:
            err = ResultMessage(
                task_id=task_id,
                status="failed",
                error="Only file path supported in MVP",
                meta=meta,
            )
            await redis_client.publish(results_channel, err.model_dump_json())
            log("WARN", "Unsupported audio type", task_id=task_id, audio_type=task.audio.type)
            continue

        try:
            async with asyncio.timeout(timeout_sec):
                result = await provider.transcribe_file(
                    task.audio.path,
                    task.options.lang,
                    task.options.timestamps,
                    task.options.diarization,
                )

            out = ResultMessage(
                task_id=task_id,
                status="finished",
                text=result.text,
                words=[],
                provider=(result.provider_meta or {}).get("provider", "unknown"),
                lang=result.lang,
                error=None,
                meta=meta,
            )
            await redis_client.publish(results_channel, out.model_dump_json())
            log("INFO", "Task finished", task_id=task_id)

        except asyncio.TimeoutError:
            out = ResultMessage(task_id=task_id, status="failed", error="timeout", meta=meta)
            await redis_client.publish(results_channel, out.model_dump_json())
            log("ERROR", "Task timeout", task_id=task_id)
        except Exception as e:
            out = ResultMessage(task_id=task_id, status="failed", error=str(e), meta=meta)
            await redis_client.publish(results_channel, out.model_dump_json())
            log("ERROR", "Task failed", task_id=task_id, error=str(e))


async def run_service(config: AppConfig) -> None:
    redis_cfg = config.redis
    service_cfg = config.service
    provider_cfg = config.provider

    tasks_queue = redis_cfg.tasks_queue
    results_channel = redis_cfg.results_channel

    concurrency = service_cfg.concurrency
    timeout_sec = provider_cfg.timeout_sec

    provider = build_provider(provider_cfg.name, provider_cfg.model_dump())

    redis_client = RedisClient(
        host=redis_cfg.host,
        port=redis_cfg.port,
        db=redis_cfg.db,
    )

    stop_event = asyncio.Event()

    def _graceful_stop(*_: Any) -> None:
        log("INFO", "Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _graceful_stop)
        except NotImplementedError:
            pass

    log(
        "INFO",
        "ASR service starting",
        tasks_queue=tasks_queue,
        results_channel=results_channel,
        provider=provider_cfg.name,
        concurrency=concurrency,
    )

    workers = [
        asyncio.create_task(
            worker_loop(f"W{i+1}", redis_client, tasks_queue, results_channel, provider, timeout_sec)
        )
        for i in range(concurrency)
    ]

    try:
        await stop_event.wait()
    finally:
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        await redis_client.close()
        log("INFO", "ASR service stopped")
